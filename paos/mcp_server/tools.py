"""
PAOS MCP Server 工具实现
"""

import json
import os
from datetime import UTC, datetime

from paos.config.settings import settings
from paos.core.fallback import complete_request, list_requests
from paos.core.models import GenerationRequest, InputItem
from paos.core.pipeline import Pipeline
from paos.core.web_search import WebSearchService
from paos.services.input_service import InputService
from paos.services.output_service import OutputService
from paos.storage.index_manager import IndexManager
from paos.storage.sqlite_store import SQLiteStorage


def _get_storage() -> SQLiteStorage:
    return SQLiteStorage(settings.db_path)


def _get_index() -> IndexManager:
    return IndexManager(data_dir=settings.data_dir)


def paos_list_index(source: str | None = None) -> dict:
    """查看 PAOS 全局目录索引"""
    index = _get_index()
    entries = index.list_entries(source=source)
    return {
        "success": True,
        "count": len(entries),
        "entries": entries,
    }


def paos_list_fallback(status: str | None = None) -> dict:
    """查看 PAOS fallback 队列状态"""
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


def paos_get_processed(item_id: int) -> dict:
    """按 ID 读取单条提纯记录"""
    storage = _get_storage()
    record = storage.get_processed(item_id)
    if not record:
        return {"success": False, "error": f"processed_id {item_id} not found"}
    return {
        "success": True,
        "record": {
            "id": record.id,
            "source": record.source,
            "distilled_content": record.distilled_content,
            "tags": record.tags,
            "metadata": record.metadata,
            "created_at": record.created_at.isoformat() if record.created_at else None,
        },
    }


def paos_health_check() -> dict:
    """检查 PAOS 健康状态（API/DB/索引/目录）"""
    checks = {}

    # 1. 数据库检查
    try:
        storage = _get_storage()
        storage.engine.connect()
        checks["database"] = {"status": "ok", "path": settings.db_path}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}

    # 2. 索引文件检查
    index = _get_index()
    index_exists = os.path.exists(index.index_path)
    checks["index_json"] = {
        "status": "ok" if index_exists else "missing",
        "path": index.index_path,
        "entries": len(index.list_entries()),
    }

    # 3. 关键目录检查
    required_dirs = ["raw", "processed", "output", "fallback_queue"]
    dir_checks = {}
    for d in required_dirs:
        path = os.path.join(settings.data_dir, d)
        dir_checks[d] = "ok" if os.path.isdir(path) else "missing"
    checks["directories"] = dir_checks

    overall = "ok" if all(
        c.get("status") == "ok" for k, c in checks.items() if k != "directories"
    ) and all(v == "ok" for v in dir_checks.values()) else "degraded"

    return {
        "success": True,
        "overall": overall,
        "checks": checks,
    }


def paos_add_note(content: str, tags: list[str] | None = None) -> dict:
    """添加一条笔记/运维日志到 PAOS"""
    storage = _get_storage()
    index = _get_index()
    input_service = InputService(storage=storage)
    item = InputItem(
        source="hermes_ops",
        content=content,
        metadata={"tags": tags or [], "added_by": "hermes_agent"},
    )
    result = input_service.pipeline.process_input(item)
    return {
        "success": True,
        "processed_id": result.id,
        "source": result.source,
        "tags": result.tags,
    }


def paos_complete_fallback(req_id: str, result: str) -> dict:
    """补全指定 fallback 请求，并联动更新 DB / MD / Index / Summary"""
    storage = _get_storage()
    index = _get_index()
    ok = complete_request(req_id, result, storage=storage, index_manager=index)
    if not ok:
        return {"success": False, "error": f"fallback request {req_id} not found"}
    return {
        "success": True,
        "req_id": req_id,
        "message": "fallback completed and synced to PAOS storage",
    }


def paos_update_tags(item_id: int, tags: list[str]) -> dict:
    """更新指定 processed 记录的标签，并联动刷新汇总文件"""
    storage = _get_storage()
    record = storage.get_processed(item_id)
    if not record:
        return {"success": False, "error": f"processed_id {item_id} not found"}
    record.tags = tags
    record.metadata["tag_updated_by"] = "hermes_agent"
    record.metadata["tag_updated_at"] = datetime.now(UTC).isoformat()
    storage.update_processed(record)
    # 刷新汇总
    Pipeline.regenerate_summary(storage, settings.data_dir)
    return {
        "success": True,
        "processed_id": item_id,
        "tags": tags,
    }


def paos_regenerate_summary() -> dict:
    """重新生成 processed_summary.md"""
    storage = _get_storage()
    Pipeline.regenerate_summary(storage, settings.data_dir)
    summary_path = os.path.join(settings.data_dir, "processed_summary.md")
    return {
        "success": True,
        "summary_path": summary_path,
        "exists": os.path.exists(summary_path),
    }


def paos_generate_article(limit: int = 5, prompt_override: str | None = None) -> dict:
    """基于最近 N 条提纯记录生成文章"""
    storage = _get_storage()
    output_service = OutputService(storage=storage)
    request = GenerationRequest(adapter="article", limit=limit, prompt_override=prompt_override)
    result = output_service.generate(request)
    return {
        "success": True,
        "adapter": result.adapter,
        "file_path": result.file_path,
        "content_preview": result.content[:500] if result.content else "",
        "metadata": result.metadata,
    }


def paos_web_search(query: str, engine: str | None = None, max_results: int | None = None) -> dict:
    """在线搜索：通过搜索引擎查询信息，返回结构化搜索结果

    支持的搜索引擎: baidu, bing_cn, bing_int, sogou, wechat, toutiao, so360, ecosia
    """
    svc = WebSearchService(
        timeout=settings.search.timeout,
        max_results=max_results or settings.search.max_results,
    )
    eng = engine or settings.search.default_engine
    response = svc.search(query, engine=eng, max_results=max_results)
    result = response.to_dict()
    result["success"] = not bool(response.error)
    if not response.error:
        result["text"] = response.to_text()
    svc.close()
    return result


def paos_web_search_and_ingest(query: str, engine: str | None = None, max_results: int | None = None) -> dict:
    """在线搜索并将结果存入 PAOS 系统（搜索 → 提纯 → 存储）"""
    storage = _get_storage()
    input_service = InputService(storage=storage)
    raw_data = {
        "query": query,
        "engine": engine or settings.search.default_engine,
        "max_results": max_results or settings.search.max_results,
    }
    try:
        result = input_service.ingest("web_search", raw_data)
        return {
            "success": True,
            "processed_id": result.id,
            "tags": result.tags,
            "source": result.source,
            "search_query": query,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def paos_list_search_engines() -> dict:
    """列出所有支持的搜索引擎"""
    engines = WebSearchService.list_engines()
    return {
        "success": True,
        "engines": engines,
        "default_engine": settings.search.default_engine,
    }
