"""分层检索：Dense → Hybrid(Dense+BM25 → RRF) → Rerank → Postprocess"""
import logging
import numpy as np
from typing import Callable

from app.kb.chroma_client import get_collection
from app.kb.bm25_index import search as bm25_search, load_index, build_index, search
from app.database.session import SessionLocal
from app.kb.models import KbChunk

logger = logging.getLogger(__name__)


def _bm25_is_healthy(merchant_id: int) -> bool:
    """检查 BM25 索引是否存在且可用"""
    idx = load_index(merchant_id)
    return idx is not None and len(getattr(idx, "chunk_ids", [])) > 0


def _bm25_cold_rebuild(merchant_id: int):
    """从数据库拉取 KnowledgeChunk 冷启动重建 BM25 索引"""
    db = SessionLocal()
    try:
        chunks = (
            db.query(KbChunk)
            .filter(KbChunk.merchant_id == merchant_id)
            .all()
        )
        if not chunks:
            logger.warning("BM25 rebuild: no chunks found for merchant %s", merchant_id)
            return
        data = [{"id": c.id, "content": c.content} for c in chunks]
        build_index(merchant_id, data)
        logger.info("BM25 cold-rebuilt for merchant %s, %d chunks", merchant_id, len(data))
    except Exception as e:
        logger.error("BM25 cold-rebuild failed for merchant %s: %s", merchant_id, e)
    finally:
        db.close()


def dense_retrieve(
    merchant_id: int,
    query_embedding: list[float],
    top_k: int = 20,
) -> list[dict]:
    """Dense 检索：余弦相似度"""
    collection = get_collection(merchant_id)
    results = collection.query(query_embeddings=[query_embedding], n_results=top_k, include=["documents", "metadatas", "distances"])

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "chunk_id": int(results["ids"][0][i]),
            "content": results["documents"][0][i],
            "meta": results["metadatas"][0][i] if results["metadatas"] else {},
            "dense_score": 1.0 - results["distances"][0][i],  # cosine → 1-dist
        })
    return chunks


def rrf_fusion(dense_chunks: list[dict], bm25_results: list[dict], k: int = 60) -> list[dict]:
    """RRF 融合 Dense + BM25 结果"""
    scores = {}
    content_map = {}

    r = 1
    for c in dense_chunks:
        cid = c["chunk_id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + r)
        content_map.setdefault(cid, c)
        r += 1

    r = 1
    for b in bm25_results:
        cid = b["chunk_id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + r)
        content_map.setdefault(cid, {"chunk_id": cid, "content": "", "meta": {}})
        r += 1

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    result = []
    for cid, score in ranked:
        c = content_map.get(cid, {"chunk_id": cid})
        c["fusion_score"] = score
        result.append(c)
    return result


def hybrid_retrieve(
    merchant_id: int,
    query: str,
    query_embedding: list[float],
    dense_k: int = 20,
    bm25_k: int = 20,
    use_bm25: bool = True,
) -> list[dict]:
    """Hybrid 检索：Dense + BM25 → RRF

    BM25 索引健康检查：若内存索引因服务重启丢失，自动从数据库
    KnowledgeChunk 冷启动重建，避免直接报错。
    """
    dense = dense_retrieve(merchant_id, query_embedding, dense_k)
    if not use_bm25:
        return dense

    # BM25 健康检查 + 自动重建
    if not _bm25_is_healthy(merchant_id):
        logger.info("BM25 index missing for merchant %s, triggering cold rebuild", merchant_id)
        _bm25_cold_rebuild(merchant_id)

    bm25 = search(merchant_id, query, bm25_k)
    return rrf_fusion(dense, bm25)


def degrade_retrieve(merchant_id: int, query_embedding: list[float]) -> list[dict]:
    """降级检索：仅 Dense"""
    return dense_retrieve(merchant_id, query_embedding, 20)
