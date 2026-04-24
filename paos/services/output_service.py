from paos.adapters.output.app_h5 import AppH5Adapter
from paos.adapters.output.article import ArticleAdapter
from paos.adapters.output.website import WebsiteAdapter
from paos.core.models import GenerationRequest, GenerationResult
from paos.storage.base import BaseStorage


def _get_output_adapter(name: str):
    """工厂函数：每次调用创建新的 adapter 实例，避免全局单例并发隐患"""
    if name == ArticleAdapter.name:
        return ArticleAdapter()
    if name == WebsiteAdapter.name:
        return WebsiteAdapter()
    if name == AppH5Adapter.name:
        return AppH5Adapter()
    raise ValueError(f"Unknown output adapter: {name}")


class OutputService:
    def __init__(self, storage: BaseStorage) -> None:
        self.storage = storage

    def generate(self, request: GenerationRequest, adapter_override=None) -> GenerationResult:
        adapter = adapter_override or _get_output_adapter(request.adapter)
        items = self.storage.list_processed(limit=request.limit)
        return adapter.generate(items, config_override={"prompt_override": request.prompt_override})
