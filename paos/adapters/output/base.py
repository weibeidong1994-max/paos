from abc import ABC, abstractmethod

from paos.core.models import GenerationResult, ProcessedItem


class BaseOutputAdapter(ABC):
    """输出适配器基类"""

    name: str = ""

    @abstractmethod
    def generate(self, items: list[ProcessedItem], config_override: dict | None = None) -> GenerationResult:
        """根据提纯后的数据生成输出内容"""
        raise NotImplementedError
