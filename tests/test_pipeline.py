import os
import tempfile

import pytest

from paos.config.settings import Settings, load_settings
from paos.core.llm import LLMClient
from paos.core.models import InputItem
from paos.core.pipeline import Pipeline
from paos.storage.index_manager import IndexManager
from paos.storage.sqlite_store import SQLiteStorage


@pytest.fixture
def temp_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        storage = SQLiteStorage(db_path)
        storage.init_db()
        index = IndexManager(data_dir=tmpdir)
        yield tmpdir, storage, index


class FakeLLMClient(LLMClient):
    def __init__(self):
        self.model = "fake-model"

    def chat_completion(self, system_prompt, user_content, **kwargs):
        return f"摘要：这是测试摘要。\n标签：测试, 自动化, demo"


def test_pipeline_processes_and_saves(temp_env):
    tmpdir, storage, index = temp_env
    pipeline = Pipeline(storage=storage, llm=FakeLLMClient(), index_manager=index)
    item = InputItem(source="natural_language", content="这是一个测试输入")
    result = pipeline.process_input(item)

    assert result.id is not None
    assert result.distilled_content == "这是测试摘要。"
    assert "测试" in result.tags

    # 验证存储
    fetched = storage.get_processed(result.id)
    assert fetched is not None
    assert fetched.distilled_content == result.distilled_content

    # 验证文件归档
    raw_files = [f for f in os.listdir(os.path.join(tmpdir, "raw")) if f.endswith(".md")]
    proc_files = [f for f in os.listdir(os.path.join(tmpdir, "processed")) if f.endswith(".md")]
    assert len(raw_files) == 1
    assert len(proc_files) == 1

    # 验证索引
    entries = index.list_entries()
    assert len(entries) == 1
    assert entries[0]["raw_id"] == result.metadata["raw_id"]
    assert entries[0]["processed_id"] == result.id


def test_article_adapter_generation(temp_env):
    tmpdir, storage, index = temp_env
    # 先写入一条测试数据
    pipeline = Pipeline(storage=storage, llm=FakeLLMClient(), index_manager=index)
    pipeline.process_input(InputItem(source="test", content="测试素材"))

    from paos.adapters.output.article import ArticleAdapter
    from paos.config.settings import settings

    # 临时修改 article save_dir 到临时目录
    original_save_dir = settings.output.article.save_dir
    settings.output.article.save_dir = os.path.join(tmpdir, "output")
    try:
        adapter = ArticleAdapter(llm=FakeLLMClient(), index_manager=index)
        items = storage.list_processed(limit=1)
        result = adapter.generate(items)

        assert result.adapter == "article"
        assert "摘要：这是测试摘要。" in result.content or "测试" in result.content
        assert result.file_path is not None

        # 验证索引关联
        entries = index.list_entries()
        assert len(entries) == 1
        assert "article" in entries[0]["output_files"]
    finally:
        settings.output.article.save_dir = original_save_dir
