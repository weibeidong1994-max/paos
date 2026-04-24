from abc import ABC, abstractmethod

from paos.core.models import InputItem, ProcessedItem


class BaseStorage(ABC):
    """存储层抽象基类"""

    @abstractmethod
    def save_raw(self, item: InputItem) -> int:
        """保存原始输入，返回记录ID"""
        raise NotImplementedError

    @abstractmethod
    def save_processed(self, item: ProcessedItem) -> int:
        """保存提纯结果，返回记录ID"""
        raise NotImplementedError

    @abstractmethod
    def get_processed(self, item_id: int) -> ProcessedItem | None:
        """根据ID获取单条提纯记录"""
        raise NotImplementedError

    @abstractmethod
    def list_processed(self, limit: int = 10, offset: int = 0) -> list[ProcessedItem]:
        """列出提纯记录"""
        raise NotImplementedError

    @abstractmethod
    def update_processed(self, item: ProcessedItem) -> bool:
        """更新提纯记录"""
        raise NotImplementedError

    @abstractmethod
    def init_db(self) -> None:
        """初始化数据库（创建表等）"""
        raise NotImplementedError
