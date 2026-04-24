import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ENGINES: dict[str, dict[str, str]] = {
    "duckduckgo": {
        "name": "DuckDuckGo",
        "url_template": "https://html.duckduckgo.com/html/?q={keyword}",
        "result_selector": ".result",
        "title_selector": ".result__a",
        "snippet_selector": ".result__snippet",
    },
    "baidu": {
        "name": "百度",
        "url_template": "https://www.baidu.com/s?wd={keyword}",
        "result_selector": ".result, .c-container",
        "title_selector": "h3 a, .t a",
        "snippet_selector": ".c-abstract, .content-right_8Zs40, span.content-right_8Zs40",
    },
    "bing_cn": {
        "name": "Bing 国内",
        "url_template": "https://cn.bing.com/search?q={keyword}&ensearch=0",
        "result_selector": ".b_algo",
        "title_selector": "h2 a",
        "snippet_selector": ".b_caption p, p",
    },
    "bing_int": {
        "name": "Bing 国际",
        "url_template": "https://cn.bing.com/search?q={keyword}&ensearch=1",
        "result_selector": ".b_algo",
        "title_selector": "h2 a",
        "snippet_selector": ".b_caption p, p",
    },
    "sogou": {
        "name": "搜狗",
        "url_template": "https://sogou.com/web?query={keyword}",
        "result_selector": ".vrwrap, .rb",
        "title_selector": "h3 a",
        "snippet_selector": ".space-txt, .str-text-info, p.str_time",
    },
    "wechat": {
        "name": "微信搜索",
        "url_template": "https://wx.sogou.com/weixin?type=2&query={keyword}",
        "result_selector": ".news-box .news-list li",
        "title_selector": "h3 a",
        "snippet_selector": ".txt-box p",
    },
    "toutiao": {
        "name": "头条搜索",
        "url_template": "https://so.toutiao.com/search?keyword={keyword}",
        "result_selector": ".result-content",
        "title_selector": "a.title",
        "snippet_selector": ".content",
    },
    "so360": {
        "name": "360搜索",
        "url_template": "https://www.so.com/s?q={keyword}",
        "result_selector": ".res-list",
        "title_selector": "h3 a",
        "snippet_selector": ".res-desc",
    },
    "ecosia": {
        "name": "Ecosia",
        "url_template": "https://www.ecosia.org/search?q={keyword}",
        "result_selector": ".result",
        "title_selector": ".result-title a",
        "snippet_selector": ".result-snippet",
    },
}

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str
    rank: int = 0


@dataclass
class SearchResponse:
    query: str
    engine: str
    results: list[SearchResult] = field(default_factory=list)
    error: str | None = None

    def to_text(self) -> str:
        if self.error:
            return f"搜索 '{self.query}' 失败: {self.error}"
        if not self.results:
            return f"搜索 '{self.query}' 无结果"
        lines = [f"## 搜索结果: {self.query} (来源: {self.engine})\n"]
        for r in self.results:
            lines.append(f"### {r.rank}. {r.title}")
            lines.append(f"链接: {r.url}")
            lines.append(f"{r.snippet}\n")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "engine": self.engine,
            "result_count": len(self.results),
            "results": [
                {"rank": r.rank, "title": r.title, "url": r.url, "snippet": r.snippet, "engine": r.engine}
                for r in self.results
            ],
            "error": self.error,
        }


class WebSearchService:
    def __init__(self, timeout: float = 15.0, max_results: int = 10) -> None:
        self.timeout = timeout
        self.max_results = max_results
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                headers=DEFAULT_HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=10,
            )
        return self._client

    def search(self, query: str, engine: str = "bing_cn", max_results: int | None = None) -> SearchResponse:
        engine_key = engine.lower().replace("-", "_").replace(" ", "_")
        if engine_key not in ENGINES:
            return SearchResponse(query=query, engine=engine, error=f"不支持的搜索引擎: {engine}，可选: {', '.join(ENGINES.keys())}")

        engine_cfg = ENGINES[engine_key]
        url = engine_cfg["url_template"].format(keyword=quote(query))
        limit = max_results or self.max_results

        try:
            client = self._get_client()
            resp = client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Search request failed for %s: %s", engine_key, e)
            return SearchResponse(query=query, engine=engine_key, error=f"请求失败: {e}")

        results = self._parse_results(resp.text, engine_cfg, engine_key, limit)
        return SearchResponse(query=query, engine=engine_key, results=results)

    async def asearch(self, query: str, engine: str = "bing_cn", max_results: int | None = None) -> SearchResponse:
        engine_key = engine.lower().replace("-", "_").replace(" ", "_")
        if engine_key not in ENGINES:
            return SearchResponse(query=query, engine=engine, error=f"不支持的搜索引擎: {engine}，可选: {', '.join(ENGINES.keys())}")

        engine_cfg = ENGINES[engine_key]
        url = engine_cfg["url_template"].format(keyword=quote(query))
        limit = max_results or self.max_results

        try:
            async with httpx.AsyncClient(
                headers=DEFAULT_HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=10,
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Async search request failed for %s: %s", engine_key, e)
            return SearchResponse(query=query, engine=engine_key, error=f"请求失败: {e}")

        results = self._parse_results(resp.text, engine_cfg, engine_key, limit)
        return SearchResponse(query=query, engine=engine_key, results=results)

    def multi_search(self, query: str, engines: list[str] | None = None, max_results: int | None = None) -> list[SearchResponse]:
        if engines is None:
            engines = ["bing_cn"]
        responses = []
        for eng in engines:
            resp = self.search(query, engine=eng, max_results=max_results)
            responses.append(resp)
        return responses

    def _parse_results(self, html: str, engine_cfg: dict[str, str], engine_key: str, limit: int) -> list[SearchResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[SearchResult] = []

        result_selector = engine_cfg.get("result_selector", "")
        title_selector = engine_cfg.get("title_selector", "")
        snippet_selector = engine_cfg.get("snippet_selector", "")

        containers = soup.select(result_selector) if result_selector else []
        if not containers:
            results = self._fallback_parse(soup, engine_key, limit)
            return results[:limit]

        for idx, container in enumerate(containers):
            if len(results) >= limit:
                break
            title_el = container.select_one(title_selector) if title_selector else None
            snippet_el = container.select_one(snippet_selector) if snippet_selector else None

            title = self._clean_text(title_el.get_text()) if title_el else ""
            url = ""
            if title_el and title_el.name == "a":
                url = title_el.get("href", "")
            elif title_el:
                link = title_el.find("a")
                if link:
                    url = link.get("href", "")
            snippet = self._clean_text(snippet_el.get_text()) if snippet_el else ""

            if not title:
                continue

            url = self._normalize_url(url, engine_key)
            results.append(SearchResult(
                title=title,
                url=url,
                snippet=snippet,
                engine=engine_key,
                rank=idx + 1,
            ))

        if not results:
            results = self._fallback_parse(soup, engine_key, limit)

        return results[:limit]

    def _fallback_parse(self, soup: BeautifulSoup, engine_key: str, limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            text = self._clean_text(a_tag.get_text())
            if not text or len(text) < 5:
                continue
            if any(skip in href.lower() for skip in ["javascript:", "mailto:", "#", "login", "register", "about"]):
                continue
            url = self._normalize_url(href, engine_key)
            if not url:
                continue
            results.append(SearchResult(
                title=text[:200],
                url=url,
                snippet="",
                engine=engine_key,
                rank=len(results) + 1,
            ))
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _clean_text(text: str | None) -> str:
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text).strip()
        return text[:500]

    @staticmethod
    def _normalize_url(url: str, engine_key: str) -> str:
        if not url:
            return ""
        if engine_key == "duckduckgo":
            if "uddg=" in url:
                from urllib.parse import parse_qs, urlparse
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                real_url = params.get("uddg", [url])[0]
                return real_url
            if "y.js?" in url or "ad_domain=" in url:
                return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return f"https:{url}"
        if engine_key == "baidu" and url.startswith("/link"):
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            real_url = params.get("url", [""])[0]
            if real_url:
                return real_url
            return url
        if url.startswith("/"):
            return url
        return ""

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    @staticmethod
    def list_engines() -> list[dict[str, str]]:
        return [{"key": k, "name": v["name"]} for k, v in ENGINES.items()]


web_search_service = WebSearchService()
