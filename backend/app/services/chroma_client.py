"""
ChromaDB 嵌入式客户端（PersistentClient，不单独起服务）
Collection 按商户隔离：merchant_{merchant_id}
存储：商品向量 (type=product) + 话术向量 (type=reply)
"""
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_collection(merchant_id: int):
    """获取/创建商户专属 Collection：merchant_{merchant_id}"""
    name = f"merchant_{merchant_id}"
    return _get_client().get_or_create_collection(name=name)


def add_products(merchant_id: int, ids: list[str], documents: list[str],
                 metadatas: list[dict], embeddings: list[list[float]]):
    """批量写入商品向量（type=product）。"""
    if not ids:
        return
    for m in metadatas:
        m.setdefault("type", "product")
    get_collection(merchant_id).add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)


def add_replies(merchant_id: int, ids: list[str], documents: list[str],
                metadatas: list[dict], embeddings: list[list[float]]):
    """批量写入话术向量（type=reply）。"""
    if not ids:
        return
    for m in metadatas:
        m.setdefault("type", "reply")
    get_collection(merchant_id).add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)


def query_products(merchant_id: int, query_vector: list[float], n_results: int = 5):
    """商品向量检索。"""
    try:
        return get_collection(merchant_id).query(
            query_embeddings=[query_vector],
            n_results=n_results,
            where={"type": "product"},
        )
    except Exception:
        return {"ids": [[]], "distances": [[]], "metadatas": [[]], "documents": [[]]}


def query_replies(merchant_id: int, query_vector: list[float], n_results: int = 5):
    """话术向量检索。"""
    try:
        return get_collection(merchant_id).query(
            query_embeddings=[query_vector],
            n_results=n_results,
            where={"type": "reply"},
        )
    except Exception:
        return {"ids": [[]], "distances": [[]], "metadatas": [[]], "documents": [[]]}


def collection_count(merchant_id: int) -> int:
    try:
        return get_collection(merchant_id).count()
    except Exception:
        return 0
