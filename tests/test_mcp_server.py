"""
PAOS MCP Server 测试
"""

import os
import tempfile

import pytest

from paos.config.settings import settings
from paos.core.fallback import queue_request
from paos.core.models import InputItem
from paos.mcp_server.tools import (
    paos_add_note,
    paos_complete_fallback,
    paos_generate_article,
    paos_get_processed,
    paos_health_check,
    paos_list_fallback,
    paos_list_index,
    paos_regenerate_summary,
    paos_update_tags,
)
from paos.services.input_service import InputService
from paos.storage.index_manager import IndexManager
from paos.storage.sqlite_store import SQLiteStorage


@pytest.fixture
def mcp_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        original_data_dir = settings.data_dir
        original_db_filename = settings.database.filename
        original_api_key = settings.llm.api_key

        settings.data_dir = tmpdir
        settings.database.filename = "paos.db"
        settings.llm.api_key = ""  # 强制 fallback 模式，避免调用真实 LLM

        os.makedirs(os.path.join(tmpdir, "fallback_queue"), exist_ok=True)

        storage = SQLiteStorage(settings.db_path)
        storage.init_db()
        index = IndexManager(data_dir=tmpdir)

        # 预写入一条测试数据
        input_service = InputService(storage=storage)
        item = InputItem(source="test", content="MCP 测试输入")
        result = input_service.pipeline.process_input(item)

        yield tmpdir, storage, index, result

        settings.data_dir = original_data_dir
        settings.database.filename = original_db_filename
        settings.llm.api_key = original_api_key


def test_mcp_list_index(mcp_env):
    tmpdir, storage, index, result = mcp_env
    resp = paos_list_index()
    assert resp["success"] is True
    assert resp["count"] >= 1


def test_mcp_get_processed(mcp_env):
    tmpdir, storage, index, result = mcp_env
    resp = paos_get_processed(result.id)
    assert resp["success"] is True
    assert resp["record"]["id"] == result.id


def test_mcp_health_check(mcp_env):
    resp = paos_health_check()
    assert resp["success"] is True
    assert resp["overall"] == "ok"
    assert resp["checks"]["database"]["status"] == "ok"


def test_mcp_list_fallback(mcp_env):
    tmpdir, storage, index, result = mcp_env
    # 先造一个 fallback 请求
    req_id = queue_request("chat_completion", "sys", "user")
    resp = paos_list_fallback(status="pending")
    assert resp["success"] is True
    assert resp["count"] >= 1
    assert any(r["id"] == req_id for r in resp["requests"])


def test_mcp_complete_fallback(mcp_env):
    tmpdir, storage, index, result = mcp_env
    # 模拟一个带 context 的 fallback
    req_id = queue_request("chat_completion", "sys", "user")
    from paos.core.fallback import attach_context

    attach_context(req_id, {"processed_id": result.id, "proc_file_path": os.path.join(tmpdir, "processed", "test.md")})

    resp = paos_complete_fallback(req_id, "摘要：测试补全。\n标签：测试, MCP")
    assert resp["success"] is True

    updated = paos_get_processed(result.id)
    assert updated["record"]["distilled_content"] == "测试补全。"
    assert "测试" in updated["record"]["tags"]


def test_mcp_update_tags(mcp_env):
    tmpdir, storage, index, result = mcp_env
    resp = paos_update_tags(result.id, ["新标签1", "新标签2"])
    assert resp["success"] is True
    assert resp["tags"] == ["新标签1", "新标签2"]

    updated = paos_get_processed(result.id)
    assert updated["record"]["tags"] == ["新标签1", "新标签2"]

    # 验证汇总文件已刷新
    summary_path = os.path.join(tmpdir, "processed_summary.md")
    assert os.path.exists(summary_path)


def test_mcp_regenerate_summary(mcp_env):
    resp = paos_regenerate_summary()
    assert resp["success"] is True
    assert resp["exists"] is True


def test_mcp_add_note(mcp_env):
    resp = paos_add_note(content="Hermes 运维日志：测试添加笔记", tags=["运维", "测试"])
    assert resp["success"] is True
    assert resp["source"] == "hermes_ops"


def test_mcp_generate_article(mcp_env):
    resp = paos_generate_article(limit=5, prompt_override="请写测试文章")
    assert resp["success"] is True
    assert resp["adapter"] == "article"
    # fallback 模式下 file_path 可能为 None，但至少返回成功
