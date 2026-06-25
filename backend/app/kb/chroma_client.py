"""ChromaDB PersistentClient 单例，租户级 collection 隔离"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings

_client = None


def get_chroma():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection(merchant_id: int, embedding_dim: int = 1024):
    """获取租户专属 collection，不存在则创建。"""
    c = get_chroma()
    name = f"kb_merchant_{merchant_id}"
    try:
        return c.get_collection(name)
    except Exception:
        return c.create_collection(
            name=name,
            metadata={"hnsw:space": "cosine", "dimension": embedding_dim},
        )


def delete_collection(merchant_id: int):
    c = get_chroma()
    try:
        c.delete_collection(f"kb_merchant_{merchant_id}")
    except Exception:
        pass
