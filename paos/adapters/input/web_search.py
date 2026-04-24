import logging

from paos.adapters.input.base import BaseInputAdapter
from paos.config.settings import settings
from paos.core.models import InputItem
from paos.core.web_search import WebSearchService

logger = logging.getLogger(__name__)


class WebSearchAdapter(BaseInputAdapter):
    name = "web_search"

    def __init__(self, search_service: WebSearchService | None = None) -> None:
        self.search_service = search_service or WebSearchService(
            timeout=settings.search.timeout,
            max_results=settings.search.max_results,
        )

    def parse(self, raw_data: dict) -> InputItem:
        query = raw_data.get("query", "")
        engine = raw_data.get("engine", settings.search.default_engine)
        max_results = raw_data.get("max_results", settings.search.max_results)

        if not query:
            raise ValueError("web_search adapter requires 'query' field")

        logger.info("WebSearchAdapter: searching '%s' on %s", query, engine)
        response = self.search_service.search(query, engine=engine, max_results=max_results)

        content_parts = []
        if response.error:
            content_parts.append(f"搜索失败: {response.error}")
        else:
            content_parts.append(f"# 在线搜索: {query}")
            content_parts.append(f"搜索引擎: {response.engine}\n")
            for r in response.results:
                content_parts.append(f"## {r.rank}. {r.title}")
                if r.url:
                    content_parts.append(f"链接: {r.url}")
                if r.snippet:
                    content_parts.append(f"摘要: {r.snippet}")
                content_parts.append("")

        content = "\n".join(content_parts)

        return InputItem(
            source=f"web_search:{response.engine}",
            content=content,
            metadata={
                "search_query": query,
                "search_engine": response.engine,
                "result_count": len(response.results),
                "search_results": [r.__dict__ for r in response.results],
                "search_error": response.error,
            },
        )
