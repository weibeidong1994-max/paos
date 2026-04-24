from abc import ABC, abstractmethod


class BaseVectorStore(ABC):
    """向量存储抽象基类，职责为语义检索而非 CRUD"""

    @abstractmethod
    def add_texts(self, texts: list[str], metadatas: list[dict] | None = None) -> list[str]:
        """添加文本到向量库，返回向量 ID 列表"""
        raise NotImplementedError

    @abstractmethod
    def similarity_search(self, query: str, k: int = 4) -> list[dict]:
        """语义相似度检索，返回最相关的 k 条记录"""
        raise NotImplementedError
