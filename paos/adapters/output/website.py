from paos.adapters.output.base import BaseOutputAdapter
from paos.core.models import GenerationResult, ProcessedItem


class WebsiteAdapter(BaseOutputAdapter):
    """网站/Demo 输出适配器（预留占位）"""

    name = "website"

    def generate(self, items: list[ProcessedItem], config_override: dict | None = None) -> GenerationResult:
        raise NotImplementedError("WebsiteAdapter is not implemented yet")
