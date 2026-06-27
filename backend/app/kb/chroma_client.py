"""ChromaDB PersistentClient 单例，租户级 collection 隔离"""
import os
import chromadb
from app.core.config import settings

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

_client = None


def get_chroma():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    return _client


def get_collection(merchant_id: int, embedding_dim: int = 1024):
    """获取租户专属 collection，不存在则创建。"""
    c = get_chroma()
    name = f"kb_merchant_{merchant_id}"
    return c.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine", "dimension": embedding_dim},
    )


def delete_collection(merchant_id: int):
    c = get_chroma()
    try:
        c.delete_collection(f"kb_merchant_{merchant_id}")
    except Exception:
        pass
