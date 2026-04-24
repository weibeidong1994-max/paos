"""
端到端测试：验证输入 → Pipeline → Fallback → 补全联动的完整链路
"""

import json
import os
import tempfile

import pytest

from paos.adapters.output.article import ArticleAdapter
from paos.config.settings import settings
from paos.core.fallback import complete_request, get_request, list_requests
from paos.core.models import GenerationRequest, InputItem
from paos.services.input_service import InputService
from paos.services.output_service import OutputService
from paos.storage.index_manager import IndexManager
from paos.storage.sqlite_store import SQLiteStorage


@pytest.fixture
def e2e_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 隔离数据目录
        original_data_dir = settings.data_dir
        original_db_path = settings.db_path
        original_save_dir = settings.output.article.save_dir
        original_api_key = settings.llm.api_key

        settings.data_dir = tmpdir
        settings.database.filename = "test.db"
        settings.output.article.save_dir = os.path.join(tmpdir, "output")
        settings.llm.api_key = ""  # 强制进入 fallback 模式，避免测试调用真实 LLM

        os.makedirs(os.path.join(tmpdir, "fallback_queue"), exist_ok=True)

        storage = SQLiteStorage(settings.db_path)
        storage.init_db()
        index = IndexManager(data_dir=tmpdir)

        input_service = InputService(storage=storage)
        output_service = OutputService(storage=storage)

        yield tmpdir, storage, index, input_service, output_service

        # teardown
        settings.data_dir = original_data_dir
        settings.database.filename = "paos.db"
        settings.output.article.save_dir = original_save_dir
        settings.llm.api_key = original_api_key


def test_e2e_input_pipeline_and_fallback_sync(e2e_env):
    tmpdir, storage, index, input_service, output_service = e2e_env

    # 1. 输入 Peter Yang 推文
    content = "恰好看到 Roblox 产品 Peter Yang 也发了一条推文，他说：我经常提醒自己，是在设置真正的 workflow，还是在优化 OpenClaw/Claude Code 配置？"
    item = InputItem(source="natural_language", content=content)

    # 走同步 pipeline（底层与 aprocess_input 共享同一逻辑）
    result = input_service.pipeline.process_input(item)

    # 2. 验证基础存储
    assert result.id is not None
    assert result.metadata.get("fallback") is True
    fallback_id = result.metadata.get("fallback_id")
    assert fallback_id is not None

    # DB 验证
    fetched = storage.get_processed(result.id)
    assert fetched is not None
    assert fetched.raw_content == content

    # 文件验证
    raw_files = [f for f in os.listdir(os.path.join(tmpdir, "raw")) if f.endswith(".md")]
    proc_files = [f for f in os.listdir(os.path.join(tmpdir, "processed")) if f.endswith(".md")]
    assert len(raw_files) == 1
    assert len(proc_files) == 1

    # 索引验证
    entries = index.list_entries()
    assert len(entries) == 1
    assert entries[0]["processed_id"] == result.id

    # 3. 验证 fallback 队列及上下文关联
    fb_reqs = list_requests(status="pending")
    assert len(fb_reqs) == 1
    fb_req = fb_reqs[0]
    assert fb_req["id"] == fallback_id
    assert fb_req["context"]["processed_id"] == result.id
    assert fb_req["context"]["proc_file_path"] is not None

    # 4. 模拟 Agent 补全 fallback
    agent_result = "摘要：Peter Yang 提醒我们要区分真正的 workflow 和工具配置游戏。\n标签：workflow, 生产力, AI工具"
    ok = complete_request(fallback_id, agent_result, storage=storage, index_manager=index)
    assert ok is True

    # 5. 验证 fallback 文件已更新
    fb_record = get_request(fallback_id)
    assert fb_record["status"] == "completed"
    assert fb_record["result"] == agent_result

    # 6. 验证 DB 联动更新
    updated = storage.get_processed(result.id)
    assert updated.distilled_content == "Peter Yang 提醒我们要区分真正的 workflow 和工具配置游戏。"
    assert "workflow" in updated.tags
    assert "生产力" in updated.tags
    assert updated.metadata.get("fallback_completed") is True

    # 7. 验证 processed Markdown 联动更新
    proc_file_path = fb_record["context"]["proc_file_path"]
    assert os.path.exists(proc_file_path)
    with open(proc_file_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    assert "Peter Yang 提醒我们要区分真正的 workflow 和工具配置游戏。" in md_content
    assert "workflow" in md_content or "生产力" in md_content
    assert "Agent Fallback" not in md_content  # fallback 提示应已移除

    # 8. 验证 index.json 联动更新
    entries = index.list_entries()
    assert len(entries) == 1
    assert "Peter Yang 提醒我们要区分真正的 workflow 和工具配置游戏。" in entries[0]["distilled_preview"]

    # 9. 验证文章生成（prompt_override 端到端）
    # 由于无 API key，给 article adapter 注入 FakeLLMClient 避免 fallback
    class FakeLLMClient:
        model = "fake-model"

        def chat_completion(self, system_prompt, user_content, **kwargs):
            # 保留 prompt_override 的关键字以便断言验证
            return f"[TEST_ARTICLE] 请用产品经理的视角 system_prompt_used={system_prompt[:40]}"

    from paos.services.output_service import _get_output_adapter

    adapter = _get_output_adapter("article")
    adapter.llm = FakeLLMClient()
    adapter.index = index

    gen_request = GenerationRequest(
        adapter="article",
        limit=5,
        prompt_override="请用产品经理的视角，基于以下素材写一篇深度分析文章。",
    )
    article_result = output_service.generate(gen_request, adapter_override=adapter)
    assert article_result.adapter == "article"
    assert article_result.file_path is not None
    # 验证 prompt_override 确实被传递并使用了（之前 key 断裂导致永远不生效）
    assert "请用产品经理的视角" in article_result.content

    # 验证文章已保存到 output 目录
    output_files = [f for f in os.listdir(os.path.join(tmpdir, "output")) if f.endswith(".md")]
    assert len(output_files) == 1

    # 验证汇总文件已保存到 data 根目录
    data_files = [f for f in os.listdir(tmpdir) if f.endswith(".md")]
    assert "processed_summary.md" in data_files

    # 验证索引关联了输出
    entries = index.list_entries()
    assert "article" in entries[0]["output_files"]
