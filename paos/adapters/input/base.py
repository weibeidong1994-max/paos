from abc import ABC, abstractmethod

from paos.core.models import InputItem


class BaseInputAdapter(ABC):
    """输入适配器基类"""

    name: str = ""

    @abstractmethod
    def parse(self, raw_data: dict) -> InputItem:
        """将原始数据解析为统一的 InputItem"""
        raise NotImplementedError
