import logging

from paos.adapters.input.natural_language import NaturalLanguageAdapter
from paos.adapters.input.openclaw import OpenClawAdapter
from paos.adapters.input.rss import RSSAdapter
from paos.adapters.input.social_media import SocialMediaAdapter
from paos.adapters.input.web_search import WebSearchAdapter
from paos.core.models import InputItem, ProcessedItem
from paos.core.pipeline import Pipeline
from paos.storage.base import BaseStorage

logger = logging.getLogger(__name__)

_INPUT_ADAPTERS = {
    NaturalLanguageAdapter.name: NaturalLanguageAdapter(),
    OpenClawAdapter.name: OpenClawAdapter(),
    RSSAdapter.name: RSSAdapter(),
    SocialMediaAdapter.name: SocialMediaAdapter(),
    WebSearchAdapter.name: WebSearchAdapter(),
}


class InputService:
    def __init__(self, storage: BaseStorage) -> None:
        self.pipeline = Pipeline(storage=storage)

    def parse(self, source: str, raw_data: dict) -> InputItem:
        adapter = _INPUT_ADAPTERS.get(source)
        if not adapter:
            raise ValueError(f"Unknown input source: {source}")
        return adapter.parse(raw_data)

    def ingest(self, source: str, raw_data: dict) -> ProcessedItem:
        item = self.parse(source, raw_data)
        return self.pipeline.process_input(item)

    async def ingest_async(self, source: str, raw_data: dict) -> ProcessedItem:
        item = self.parse(source, raw_data)
        return await self.pipeline.aprocess_input(item)

    async def pipeline_async_process(self, item: InputItem) -> ProcessedItem:
        return await self.pipeline.aprocess_input(item)
