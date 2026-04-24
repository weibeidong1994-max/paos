"""
Agent Fallback Queue

当外部 LLM 不可用时（无 API Key 或接口失效），将请求写入本地队列，
由对话中的 Kimi Agent 读取并处理，再把结果写回。
"""

import json
import logging
import os
import re
import uuid
from datetime import UTC, datetime

from paos.config.settings import settings

logger = logging.getLogger(__name__)


def _fallback_dir() -> str:
    return os.path.join(settings.data_dir, "fallback_queue")


def _ensure_dir() -> None:
    os.makedirs(_fallback_dir(), exist_ok=True)


def queue_request(task_type: str, system_prompt: str, user_content: str) -> str:
    """将请求写入 fallback 队列，返回 request_id"""
    _ensure_dir()
    req_id = str(uuid.uuid4())[:8]
    record = {
        "id": req_id,
        "task_type": task_type,
        "system_prompt": system_prompt,
        "user_content": user_content,
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
        "result": None,
        "completed_at": None,
    }
    path = os.path.join(_fallback_dir(), f"{req_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    logger.info("Fallback request queued: %s (%s)", req_id, task_type)
    return req_id


def attach_context(req_id: str, context: dict) -> bool:
    """为 fallback 请求附加业务上下文（如 processed_id、文件路径等）"""
    record = get_request(req_id)
    if not record:
        return False
    record["context"] = context
    path = os.path.join(_fallback_dir(), f"{req_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return True


def list_requests(status: str | None = None) -> list[dict]:
    """列出 fallback 队列中的请求"""
    directory = _fallback_dir()
    if not os.path.exists(directory):
        return []

    results = []
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(directory, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                record = json.load(f)
            if status is None or record.get("status") == status:
                results.append(record)
        except Exception:
            continue
    return results


def get_request(req_id: str) -> dict | None:
    """获取单个请求详情"""
    path = os.path.join(_fallback_dir(), f"{req_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def complete_request(req_id: str, result: str, storage=None, index_manager=None) -> bool:
    """写入 Agent 处理结果，并联动更新数据库和归档文件"""
    from paos.storage.base import BaseStorage
    from paos.storage.index_manager import IndexManager

    record = get_request(req_id)
    if not record:
        return False
    record["status"] = "completed"
    record["result"] = result
    record["completed_at"] = datetime.now(UTC).isoformat()
    path = os.path.join(_fallback_dir(), f"{req_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    logger.info("Fallback request completed: %s", req_id)

    # 联动更新 SQLite 和 Markdown 归档
    context = record.get("context", {})
    processed_id = context.get("processed_id")
    if processed_id is not None and isinstance(storage, BaseStorage):
        _sync_fallback_to_storage(processed_id, result, record["completed_at"], storage, index_manager, context)

    return True


def _sync_fallback_to_storage(processed_id, result, completed_at, storage, index_manager, context):
    """将 fallback 结果同步回存储层和索引"""
    from paos.core.pipeline import Pipeline
    from paos.storage.index_manager import IndexManager

    summary, tags = Pipeline._parse_distillation(result)

    existing = storage.get_processed(processed_id)
    if not existing:
        logger.warning("Fallback sync skipped: processed_id %s not found in storage", processed_id)
        return

    existing.distilled_content = summary
    existing.tags = tags
    existing.metadata["fallback"] = False
    existing.metadata["fallback_completed"] = True
    existing.metadata["fallback_completed_at"] = completed_at
    storage.update_processed(existing)
    logger.info("Fallback synced to DB: processed_id=%s", processed_id)

    # 更新 Markdown 文件
    proc_file_path = context.get("proc_file_path")
    if proc_file_path:
        md_content = Pipeline._build_processed_md(existing, processed_id, existing.created_at)
        os.makedirs(os.path.dirname(proc_file_path), exist_ok=True)
        with open(proc_file_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logger.info("Fallback synced to MD: %s", proc_file_path)

    # 更新索引
    if isinstance(index_manager, IndexManager):
        data = index_manager._load_index()
        for entry in data:
            if entry["processed_id"] == processed_id:
                entry["distilled_preview"] = summary[:200]
                entry["updated_at"] = datetime.now(UTC).isoformat()
        index_manager._save_index(data)
        logger.info("Fallback synced to index: processed_id=%s", processed_id)

    # 重新生成提纯知识汇总文件
    Pipeline.regenerate_summary(storage, index_manager.data_dir)
    logger.info("Processed summary regenerated after fallback: processed_id=%s", processed_id)


def is_fallback_response(text: str) -> bool:
    """判断文本是否是 fallback 占位符"""
    return text.startswith("[FALLBACK_QUEUED:")


def extract_fallback_id(text: str) -> str | None:
    """从 fallback 占位符中提取 request_id"""
    if not is_fallback_response(text):
        return None
    try:
        return text.split(":")[1].split("]")[0].strip()
    except Exception:
        return None
