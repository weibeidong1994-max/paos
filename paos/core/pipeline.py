import asyncio
import logging
import os
import re
from datetime import datetime

from paos.adapters.output.article import ArticleAdapter
from paos.config.settings import settings
from paos.core.fallback import extract_fallback_id, is_fallback_response
from paos.core.llm import LLMClient
from paos.core.models import InputItem, ProcessedItem
from paos.core.web_search import WebSearchService
from paos.storage.base import BaseStorage
from paos.storage.index_manager import IndexManager

logger = logging.getLogger(__name__)


class Pipeline:
    """信息处理主流程：接收输入 -> (可选)搜索补充 -> 提纯 -> 存储（数据库 + 归档文件 + 索引目录）"""

    def __init__(self, storage: BaseStorage, llm: LLMClient | None = None, index_manager: IndexManager | None = None) -> None:
        self.storage = storage
        self.llm = llm or LLMClient()
        self.index = index_manager or IndexManager()
        self.article_adapter = ArticleAdapter()
        self.search_service: WebSearchService | None = None
        if settings.search.enrich_pipeline or settings.search.auto_search:
            self.search_service = WebSearchService(
                timeout=settings.search.timeout,
                max_results=settings.search.max_results,
            )

    async def aprocess_input(self, item: InputItem) -> ProcessedItem:
        """异步处理输入，避免阻塞事件循环"""
        return await asyncio.to_thread(self.process_input, item)

    def process_input(self, item: InputItem) -> ProcessedItem:
        # 使用本地时间（系统时区），确保文件名和内容时间符合用户时区
        timestamp = datetime.now()  # 本地时间
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S")

        # 1. 保存原始输入到数据库
        raw_id = self.storage.save_raw(item)
        logger.info("Raw input saved: id=%s source=%s", raw_id, item.source)

        # 1.1 同时保存原始输入为 Markdown 文件
        raw_filename = f"raw/{ts_str}_{raw_id:05d}.md"
        raw_file_path = os.path.join(self.index.data_dir, raw_filename)
        self._write_md(raw_file_path, self._build_raw_md(item, raw_id, timestamp))

        # 1.5 (可选) 在线搜索补充素材
        search_context = ""
        search_metadata = {}
        if self.search_service and settings.search.enrich_pipeline:
            search_context, search_metadata = self._enrich_with_search(item)

        enriched_content = item.content
        if search_context:
            enriched_content = f"{item.content}\n\n---\n\n## 在线搜索补充\n\n{search_context}"

        # 2. LLM 提纯
        system_prompt = settings.pipeline.distillation_prompt
        distilled_text = self.llm.chat_completion(
            system_prompt=system_prompt,
            user_content=enriched_content,
        )

        if is_fallback_response(distilled_text):
            req_id = extract_fallback_id(distilled_text)
            summary = ""
            tags = settings.pipeline.default_tags.copy()
            metadata = {
                "raw_id": raw_id,
                "raw_filename": raw_filename,
                "llm_model": self.llm.model,
                "fallback": True,
                "fallback_id": req_id,
                "distilled_raw": distilled_text,
            }
        else:
            summary, tags = self._parse_distillation(distilled_text)
            metadata = {
                "raw_id": raw_id,
                "raw_filename": raw_filename,
                "llm_model": self.llm.model,
                "distilled_raw": distilled_text,
            }

        if search_metadata:
            metadata["web_search"] = search_metadata

        processed = ProcessedItem(
            source=item.source,
            raw_content=item.content,
            distilled_content=summary,
            tags=tags,
            metadata=metadata,
            created_at=timestamp,
        )

        # 3. 保存提纯结果到数据库
        proc_id = self.storage.save_processed(processed)
        logger.info("Processed item saved: id=%s", proc_id)
        processed.id = proc_id

        # 3.1 同时保存提纯结果为 Markdown 文件
        proc_filename = f"processed/{ts_str}_{proc_id:05d}.md"
        proc_file_path = os.path.join(self.index.data_dir, proc_filename)
        self._write_md(proc_file_path, self._build_processed_md(processed, proc_id, timestamp))

        # 3.2 若为 fallback，将业务上下文关联到 fallback 队列，便于后续补全后联动更新
        if is_fallback_response(distilled_text):
            req_id = extract_fallback_id(distilled_text)
            from paos.core.fallback import attach_context

            attach_context(
                req_id,
                {
                    "processed_id": proc_id,
                    "proc_file_path": proc_file_path,
                    "proc_filename": proc_filename,
                },
            )

        # 3.3 更新索引目录
        self.index.add_entry(
            raw_id=raw_id,
            raw_file=raw_filename,
            processed_id=proc_id,
            processed_file=proc_filename,
            source=item.source,
            content_preview=item.content,
            distilled_preview=summary,
        )

        # 3.4 重新生成提纯知识汇总文件
        Pipeline.regenerate_summary(self.storage, self.index.data_dir)

        # 4. 自动生成文章（默认流程的最后一步）
        article_result = None
        if settings.pipeline.auto_generate_article and not is_fallback_response(distilled_text):
            try:
                article_result = self.article_adapter.generate([processed])
                processed.metadata["article_file_path"] = article_result.file_path
                processed.metadata["article_generated"] = True
                logger.info("Auto-generated article for processed_id=%s: %s", proc_id, article_result.file_path)
            except Exception as e:
                logger.error("Auto article generation failed for processed_id=%s: %s", proc_id, e)
                processed.metadata["article_generated"] = False
                processed.metadata["article_error"] = str(e)
        elif is_fallback_response(distilled_text):
            processed.metadata["article_generated"] = False
            processed.metadata["article_skipped_reason"] = "distillation_fallback"
            logger.info("Skipped article generation for processed_id=%s (distillation fallback)", proc_id)

        return processed

    @staticmethod
    def regenerate_summary(storage: BaseStorage, data_dir: str) -> None:
        """从 DB 重新生成极简提纯知识汇总文件到 data_dir 根目录"""
        summary_path = os.path.join(data_dir, "processed_summary.md")
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)
        items = storage.list_processed(limit=10000)
        lines = ["# 提纯知识汇总\n"]
        for item in items:
            ts = item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else ""
            tags = ", ".join(item.tags) if item.tags else "未分类"
            summary = item.distilled_content or "（待补全）"
            lines.append(f"### {ts} | {item.source}")
            lines.append(f"**标签**: {tags}")
            lines.append(f"**摘要**: {summary}\n")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info("Processed summary regenerated: %s", summary_path)

    @staticmethod
    def _write_md(path: str, content: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    @staticmethod
    def _build_raw_md(item: InputItem, raw_id: int, timestamp: datetime) -> str:
        return f"""# 原始输入 #{raw_id:05d}

- **来源**: {item.source}
- **时间**: {timestamp.isoformat()}

---

{item.content}
"""

    @staticmethod
    def _build_processed_md(item: ProcessedItem, proc_id: int, timestamp: datetime) -> str:
        tags_line = ", ".join(item.tags) if item.tags else "未分类"
        fallback_notice = "\n> ⚠️ 本条为 **Agent Fallback** 队列生成，等待 Kimi Agent 补全摘要。\n" if item.metadata.get("fallback") else ""
        # 优先使用 metadata 中记录的 raw_filename，避免跨秒边界导致文件名不一致
        raw_fn = item.metadata.get("raw_filename")
        if not raw_fn:
            ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
            raw_fn = f"{ts_str}_{item.metadata.get('raw_id', 0):05d}.md"
        return f"""# 提纯知识 #{proc_id:05d}

- **来源**: {item.source}
- **时间**: {timestamp.isoformat()}
- **标签**: {tags_line}
- **关联原文**: raw/{raw_fn}

---

{item.distilled_content}{fallback_notice}
"""

    @staticmethod
    def _parse_distillation(text: str) -> tuple[str, list[str]]:
        """从 LLM 返回中提取摘要和标签，支持多种格式，具备容错能力"""
        import json

        cleaned = text.strip()

        # 1. 尝试 JSON 结构化输出
        try:
            if cleaned.startswith("{") and cleaned.endswith("}"):
                data = json.loads(cleaned)
                summary = data.get("摘要") or data.get("summary", "")
                tags = data.get("标签") or data.get("tags", [])
                if summary and isinstance(tags, list):
                    return str(summary).strip(), [str(t).strip() for t in tags if t]
        except Exception:
            pass

        # 2. 标准正则匹配
        summary_match = re.search(r"摘要[：:]\s*(.+?)(?=\n标签[：:]|$)", cleaned, re.DOTALL)
        tags_match = re.search(r"标签[：:]\s*(.+?)$", cleaned, re.DOTALL)

        summary = ""
        tags = []

        if summary_match and tags_match:
            summary = summary_match.group(1).strip()
            tags_raw = tags_match.group(1).strip()
            tags = [t.strip() for t in re.split(r"[,，、]", tags_raw) if t.strip()]
        else:
            # 3. 容错兜底：按关键词位置切分
            lower_text = cleaned.lower()
            summary_idx = lower_text.find("摘要")
            tag_idx = lower_text.find("标签")

            if summary_idx != -1 and tag_idx != -1 and tag_idx > summary_idx:
                summary_part = cleaned[summary_idx + 2 : tag_idx].strip(": \n")
                tags_part = cleaned[tag_idx + 2 :].strip(": \n")
                summary = summary_part
                tags = [t.strip() for t in re.split(r"[,，、]", tags_part) if t.strip()]
            elif summary_idx != -1:
                summary = cleaned[summary_idx + 2 :].strip(": \n")
            elif tag_idx != -1:
                tags_part = cleaned[tag_idx + 2 :].strip(": \n")
                tags = [t.strip() for t in re.split(r"[,，、]", tags_part) if t.strip()]
                summary = cleaned
            else:
                summary = cleaned

        if not tags:
            tags = settings.pipeline.default_tags.copy()

        return summary, tags

    def _enrich_with_search(self, item: InputItem) -> tuple[str, dict]:
        if not self.search_service:
            return "", {}

        query = item.content[:100].strip()
        engine = settings.search.auto_search_engine
        max_results = min(settings.search.max_results, 5)

        logger.info("Pipeline search enrichment: query='%s' engine=%s", query, engine)
        try:
            response = self.search_service.search(query, engine=engine, max_results=max_results)
        except Exception as e:
            logger.error("Search enrichment failed: %s", e)
            return "", {"error": str(e), "engine": engine, "query": query}

        if response.error or not response.results:
            logger.warning("Search enrichment returned no results: %s", response.error)
            return "", {"error": response.error, "engine": engine, "query": query, "result_count": 0}

        context_parts = []
        for r in response.results:
            entry = f"- **{r.title}**"
            if r.snippet:
                entry += f": {r.snippet}"
            if r.url:
                entry += f" [链接]({r.url})"
            context_parts.append(entry)

        context = "\n".join(context_parts)
        metadata = {
            "engine": engine,
            "query": query,
            "result_count": len(response.results),
        }
        return context, metadata
