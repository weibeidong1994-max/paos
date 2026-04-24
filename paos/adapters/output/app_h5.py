from paos.adapters.output.base import BaseOutputAdapter
from paos.core.models import GenerationResult, ProcessedItem


class AppH5Adapter(BaseOutputAdapter):
    """App/H5 输出适配器（预留占位）"""

    name = "app_h5"

    def generate(self, items: list[ProcessedItem], config_override: dict | None = None) -> GenerationResult:
        raise NotImplementedError("AppH5Adapter is not implemented yet")
