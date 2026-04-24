from paos.storage.base_vector_store import BaseVectorStore


class VectorStore(BaseVectorStore):
    """向量数据库存储（预留占位）"""

    def add_texts(self, texts, metadatas=None):
        raise NotImplementedError("VectorStore is not implemented yet")

    def similarity_search(self, query, k=4):
        raise NotImplementedError("VectorStore is not implemented yet")
