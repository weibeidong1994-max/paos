import asyncio
import hashlib
import logging
import re
import time

from fastapi import APIRouter, HTTPException

from paos.config.settings import settings
from paos.core.fallback import complete_request, list_requests
from paos.core.models import CreateInputRequest, GenerationRequest
from paos.core.web_search import WebSearchService
from paos.services.input_service import InputService
from paos.services.output_service import OutputService
from paos.storage.index_manager import IndexManager
from paos.storage.sqlite_store import SQLiteStorage

router = APIRouter()

storage = SQLiteStorage()
input_service = InputService(storage)
output_service = OutputService(storage)
index_manager = IndexManager()

_recent_ingest_cache: dict[str, tuple[int, float]] = {}
_DEDUP_WINDOW_SECONDS = 60

# 后台任务追踪：检测静默失败
_pending_tasks: dict[str, dict] = {}  # task_id -> {"accepted_at": float, "done": bool, "failed": bool}
_TASK_HEALTH_THRESHOLD = 300  # 超过 300 秒未完成的任务视为异常


def _content_fingerprint(content: str) -> str:
    normalized = re.sub(r"\s+", "", content.strip().lower())
    prefix = normalized[:200] if len(normalized) > 200 else normalized
    return hashlib.md5(prefix.encode()).hexdigest()


def _cleanup_cache():
    """清理过期的去重缓存条目"""
    now = time.time()
    expired = [k for k, v in _recent_ingest_cache.items() if now - v[1] > _DEDUP_WINDOW_SECONDS]
    for k in expired:
        del _recent_ingest_cache[k]


def _check_dedup(source: str, content: str) -> tuple[int, float] | None:
    _cleanup_cache()
    fingerprint = _content_fingerprint(content)
    now = time.time()
    for key, cached in _recent_ingest_cache.items():
        if key.startswith("fp:") and key[3:] == fingerprint and (now - cached[1]) < _DEDUP_WINDOW_SECONDS:
            return cached
    return None


def _record_ingest(source: str, content: str, processed_id: int) -> None:
    _cleanup_cache()
    fingerprint = _content_fingerprint(content)
    _recent_ingest_cache[f"fp:{fingerprint}"] = (processed_id, time.time())


@router.post("/api/v1/input")
async def create_input(request: CreateInputRequest):
    """通用输入接口"""
    raw_data = request.data or request.model_dump()
    content = (
        raw_data.get("content")
        or raw_data.get("text")
        or raw_data.get("message")
        or (isinstance(raw_data.get("data"), dict) and raw_data["data"].get("content"))
        or (isinstance(raw_data.get("data"), dict) and raw_data["data"].get("text"))
        or ""
    )
    dedup = _check_dedup(request.source, content)
    if dedup:
        return {"success": True, "processed_id": dedup[0], "tags": [], "deduplicated": True}
    try:
        result = await input_service.ingest_async(request.source, raw_data)
        _record_ingest(request.source, content, result.id)
        response = {"success": True, "processed_id": result.id, "tags": result.tags}
        if result.metadata.get("article_generated"):
            response["article_file_path"] = result.metadata.get("article_file_path")
        if result.metadata.get("article_error"):
            response["article_error"] = result.metadata.get("article_error")
        if result.metadata.get("article_skipped_reason"):
            response["article_skipped"] = result.metadata.get("article_skipped_reason")
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/webhook/openclaw")
async def openclaw_webhook(payload: dict):
    """OpenClaw Webhook 入口（异步模式：立即返回确认，后台处理蒸馏和文章生成）"""
    content = payload.get("text") or payload.get("content") or payload.get("message") or ""
    dedup = _check_dedup("openclaw", content)
    if dedup:
        return {"success": True, "processed_id": dedup[0], "tags": [], "deduplicated": True}

    try:
        item = input_service.parse("openclaw", payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    fingerprint = _content_fingerprint(content)
    task_id = f"oc:{fingerprint[:12]}:{int(time.time()*1000)}"

    # 立即写入去重缓存，防止短时间内重复提交
    _recent_ingest_cache[f"fp:{fingerprint}"] = (-1, time.time())
    # 记录 pending 状态
    _pending_tasks[task_id] = {"accepted_at": time.time(), "done": False, "failed": False}

    async def _background_process():
        try:
            result = await input_service.pipeline_async_process(item)
            # 后台完成后更新为真实 id
            _recent_ingest_cache[f"fp:{fingerprint}"] = (result.id, time.time())
            _pending_tasks[task_id] = {"accepted_at": _pending_tasks[task_id]["accepted_at"], "done": True, "failed": False}
        except Exception:
            _logger = logging.getLogger("paos.api")
            _logger.error("Background ingest task %s failed", task_id, exc_info=True)
            # 处理失败时清除缓存，允许重试
            _recent_ingest_cache.pop(f"fp:{fingerprint}", None)
            _pending_tasks[task_id] = {"accepted_at": _pending_tasks[task_id]["accepted_at"], "done": True, "failed": True}

    asyncio.create_task(_background_process())

    return {"status": "accepted", "success": True, "message": "内容已接收，后台处理中", "task_id": task_id}


@router.get("/api/v1/ping")
async def ping():
    """轻量级健康检查，确认 PAOS 服务在线 + 后台任务健康"""
    now = time.time()
    # 清理已完成的旧任务（保留最近 60 秒）
    stale = [tid for tid, t in _pending_tasks.items()
             if t["done"] and (now - t["accepted_at"]) > 60]
    for tid in stale:
        del _pending_tasks[tid]

    # 统计待处理任务
    pending = [t for t in _pending_tasks.values() if not t["done"]]
    stuck = [t for t in pending if (now - t["accepted_at"]) > _TASK_HEALTH_THRESHOLD]
    failed_recent = [t for t in _pending_tasks.values() if t["failed"] and (now - t["accepted_at"]) < 60]

    result = {
        "status": "ok",
        "service": "paos",
        "timestamp": now,
        "tasks": {
            "pending": len(pending),
            "stuck": len(stuck),
            "failed_recent": len(failed_recent),
        },
    }

    # 如果有卡住的任务，降级为 degraded
    if stuck:
        result["status"] = "degraded"
        result["message"] = f"{len(stuck)} background task(s) stuck for >{_TASK_HEALTH_THRESHOLD}s"
    elif failed_recent:
        result["status"] = "degraded"
        result["message"] = f"{len(failed_recent)} task(s) failed in last 60s"

    return result


@router.post("/api/v1/generate/article")
async def generate_article(limit: int = 5):
    """基于最近 N 条提纯数据生成文章"""
    request = GenerationRequest(adapter="article", limit=limit)
    try:
        result = output_service.generate(request)
        return {
            "success": True,
            "adapter": result.adapter,
            "file_path": result.file_path,
            "content": result.content,
            "metadata": result.metadata,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/fallback")
async def list_fallback_requests(status: str | None = None):
    """查看 Agent Fallback 队列状态"""
    reqs = list_requests(status=status)
    return {
        "success": True,
        "count": len(reqs),
        "requests": [
            {
                "id": r["id"],
                "task_type": r["task_type"],
                "status": r["status"],
                "created_at": r["created_at"],
                "has_result": r.get("result") is not None,
            }
            for r in reqs
        ],
    }


@router.post("/api/v1/fallback/{req_id}/complete")
async def complete_fallback(req_id: str, payload: dict):
    """提交 Agent 对 fallback 请求的处理结果"""
    result = payload.get("result", "")
    ok = complete_request(req_id, result, storage=storage, index_manager=index_manager)
    if not ok:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"success": True, "request_id": req_id}


@router.get("/api/v1/index")
async def get_index(source: str | None = None):
    """查询整体目录映射：原文 -> 提纯知识 -> 生成输出"""
    entries = index_manager.list_entries(source=source)
    return {
        "success": True,
        "count": len(entries),
        "entries": entries,
    }


@router.get("/api/v1/config")
async def get_config():
    """查看当前配置（脱敏）"""
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "server": settings.server.model_dump(),
        "data_dir": settings.data_dir,
        "database": settings.database.model_dump(),
        "pipeline": {
            "default_tags": settings.pipeline.default_tags,
            "auto_generate_article": settings.pipeline.auto_generate_article,
            "distillation_prompt_configured": bool(settings.pipeline.distillation_prompt),
        },
        "llm": {
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "base_url": settings.llm.base_url,
            "api_key_configured": bool(settings.llm.api_key),
            "fallback_enabled": settings.llm.fallback.enabled,
        },
        "output": settings.output.model_dump(),
        "adapters": settings.adapters.model_dump(),
        "search": {
            "default_engine": settings.search.default_engine,
            "auto_search": settings.search.auto_search,
            "enrich_pipeline": settings.search.enrich_pipeline,
            "max_results": settings.search.max_results,
        },
    }


@router.get("/api/v1/search/engines")
async def list_search_engines():
    """列出所有支持的搜索引擎"""
    engines = WebSearchService.list_engines()
    return {
        "success": True,
        "engines": engines,
        "default_engine": settings.search.default_engine,
    }


@router.post("/api/v1/search")
async def web_search(payload: dict):
    """在线搜索：通过搜索引擎查询信息

    请求体:
    - query: 搜索关键词（必填）
    - engine: 搜索引擎（可选，默认使用配置中的 default_engine）
    - max_results: 最大结果数（可选，默认使用配置中的 max_results）
    """
    query = payload.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="'query' is required")

    engine = payload.get("engine", settings.search.default_engine)
    max_results = payload.get("max_results", settings.search.max_results)

    svc = WebSearchService(timeout=settings.search.timeout, max_results=max_results)
    try:
        response = svc.search(query, engine=engine, max_results=max_results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        svc.close()

    result = response.to_dict()
    result["success"] = not bool(response.error)
    if not response.error:
        result["text"] = response.to_text()
    return result


@router.post("/api/v1/search/ingest")
async def web_search_and_ingest(payload: dict):
    """在线搜索并将结果存入 PAOS 系统（搜索 → 提纯 → 存储 → 可选生成文章）

    请求体:
    - query: 搜索关键词（必填）
    - engine: 搜索引擎（可选）
    - max_results: 最大结果数（可选）
    """
    query = payload.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="'query' is required")

    raw_data = {
        "query": query,
        "engine": payload.get("engine", settings.search.default_engine),
        "max_results": payload.get("max_results", settings.search.max_results),
    }
    try:
        result = await input_service.ingest_async("web_search", raw_data)
        response = {"success": True, "processed_id": result.id, "tags": result.tags, "source": result.source}
        if result.metadata.get("article_generated"):
            response["article_file_path"] = result.metadata.get("article_file_path")
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
