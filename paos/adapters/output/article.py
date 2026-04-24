import logging
from datetime import datetime
from pathlib import Path

from paos.adapters.output.base import BaseOutputAdapter
from paos.config.settings import settings
from paos.core.fallback import extract_fallback_id, is_fallback_response
from paos.core.llm import LLMClient
from paos.core.models import GenerationResult, ProcessedItem
from paos.storage.index_manager import IndexManager

logger = logging.getLogger(__name__)

DEFAULT_WRITER_SKILL = "khazix-writer"


def _load_writer_skill_instructions() -> str | None:
    try:
        from paos.skills import SkillRegistry

        registry = SkillRegistry()
        registry.discover()
        skill = registry.get(DEFAULT_WRITER_SKILL)
        if skill and skill.loaded and skill.instructions:
            logger.info("Writer skill '%s' loaded for style rewrite", DEFAULT_WRITER_SKILL)
            return skill.instructions
    except Exception as e:
        logger.warning("Failed to load writer skill '%s': %s", DEFAULT_WRITER_SKILL, e)
    return None


def _postprocess_article(content: str, llm: LLMClient | None = None) -> str:
    import re

    result = content.rstrip() + "\n"

    has_h1 = bool(re.match(r"^#\s+.+", result.lstrip(), re.MULTILINE))
    if not has_h1:
        h2_match = re.search(r"^##\s+(.+)$", result, re.MULTILINE)
        if h2_match:
            title = h2_match.group(1).strip()
        else:
            title = _extract_title_from_content(result, llm=llm)
        result = f"# {title}\n\n{result}"

    return result


def _extract_title_from_content(content: str, llm: LLMClient | None = None) -> str:
    import re

    clean_content = content.strip()
    if not clean_content or len(clean_content) < 10:
        return "未命名文章"

    if llm is None:
        llm = LLMClient()

    try:
        preview = clean_content[:1500]
        title = llm.chat_completion(
            system_prompt="你是一个标题生成器。根据文章内容生成一个简洁有力的标题，8-20个字，不要加引号、书名号或其他标点，只输出标题本身。",
            user_content=f"请为以下文章生成一个标题：\n\n{preview}",
        )
        title = title.strip().strip('''"'《》【】''')
        if 2 <= len(title) <= 40:
            return title
    except Exception:
        pass

    lines = [l.strip() for l in content.split("\n") if l.strip() and not l.strip().startswith("---")]

    for match in re.finditer(r"\*\*(.+?)\*\*", content):
        title = match.group(1).strip()
        title = re.sub(r"[。！？，、；：]$", "", title)
        if 8 <= len(title) <= 40:
            return title

    if lines:
        for line in lines[:10]:
            sentences = re.split(r"[。！？]", line)
            for s in sentences:
                clean = re.sub(r"[#*_`]", "", s).strip()
                if 8 <= len(clean) <= 40:
                    return clean

    return "未命名文章"


class ArticleAdapter(BaseOutputAdapter):
    """文章生成适配器，输出 Markdown 格式"""

    name = "article"

    def __init__(self, llm: LLMClient | None = None, index_manager: IndexManager | None = None) -> None:
        self.llm = llm or LLMClient()
        self.index = index_manager or IndexManager()

    def generate(self, items: list[ProcessedItem], config_override: dict | None = None) -> GenerationResult:
        if not items:
            return GenerationResult(adapter=self.name, content="无可用素材，无法生成文章。")

        material_lines = []
        for idx, item in enumerate(items, 1):
            material_lines.append(f"【素材 {idx}】\n来源：{item.source}\n标签：{', '.join(item.tags)}\n摘要：{item.distilled_content}\n")
        material = "\n".join(material_lines)

        cfg = settings.output.article

        if config_override:
            prompt_override = config_override.get("prompt_override")
            prompt_template = prompt_override if prompt_override is not None else cfg.prompt_template
        else:
            prompt_template = cfg.prompt_template

        # Step 1: 生成文章（纯内容生成，不涉及任何风格 skill）
        logger.info("Step 1: Generating article from material")
        system_prompt = prompt_template.format(content=material)
        content = self.llm.chat_completion(
            system_prompt=system_prompt,
            user_content="请根据以上素材生成一篇 Markdown 文章。",
        )

        if not content or not content.strip():
            logger.error("Step 1 returned empty content")
            return GenerationResult(
                adapter=self.name,
                content="",
                file_path=None,
                metadata={"item_count": len(items), "model": self.llm.model, "error": "LLM returned empty content in Step 1"},
            )

        if is_fallback_response(content):
            req_id = extract_fallback_id(content)
            return GenerationResult(
                adapter=self.name,
                content=content,
                file_path=None,
                metadata={"item_count": len(items), "model": self.llm.model, "fallback": True, "fallback_id": req_id},
            )

        # Step 2: 如果有写作 skill，用 skill 的指令对文章做风格优化
        writer_instructions = _load_writer_skill_instructions()
        style_rewrite = False
        if writer_instructions:
            logger.info("Step 2: Applying %s style rewrite", DEFAULT_WRITER_SKILL)
            rewritten = self.llm.chat_completion(
                system_prompt=writer_instructions,
                user_content=f"请按照以上写作风格要求，对以下文章进行风格优化改写。保留所有核心事实和观点，不丢失信息。\n\n---\n\n{content}",
            )
            if rewritten and rewritten.strip() and not is_fallback_response(rewritten):
                content = rewritten
                style_rewrite = True
            else:
                logger.warning("Step 2 style rewrite failed or returned empty, keeping Step 1 content")
        else:
            logger.info("Step 2: No writer skill available, skip style rewrite")

        content = _postprocess_article(content, llm=self.llm)

        if is_fallback_response(content):
            req_id = extract_fallback_id(content)
            return GenerationResult(
                adapter=self.name,
                content=content,
                file_path=None,
                metadata={
                    "item_count": len(items),
                    "model": self.llm.model,
                    "fallback": True,
                    "fallback_id": req_id,
                },
            )

        save_dir = Path(cfg.save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rel_path = f"output/article_{timestamp}.md"
        file_path = save_dir / f"article_{timestamp}.md"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("Article saved to %s", file_path)
        except OSError as e:
            logger.error("Failed to save article: %s", e)
            return GenerationResult(
                adapter=self.name,
                content=content,
                file_path=None,
                metadata={"item_count": len(items), "model": self.llm.model, "error": str(e)},
            )

        for item in items:
            if item.id is not None:
                self.index.add_output(item.id, self.name, rel_path)

        metadata = {
            "item_count": len(items),
            "model": self.llm.model,
            "style_rewrite": style_rewrite,
        }
        return GenerationResult(
            adapter=self.name,
            content=content,
            file_path=str(file_path),
            metadata=metadata,
        )
