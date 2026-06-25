"""分层检索：Dense → Hybrid(Dense+BM25 → RRF) → Rerank → Postprocess"""
import numpy as np
from typing import Callable

from app.kb.chroma_client import get_collection
from app.kb.bm25_index import search as bm25_search


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
    """Hybrid 检索：Dense + BM25 → RRF"""
    dense = dense_retrieve(merchant_id, query_embedding, dense_k)
    if not use_bm25:
        return dense
    bm25 = bm25_search(merchant_id, query, bm25_k)
    return rrf_fusion(dense, bm25)


def degrade_retrieve(merchant_id: int, query_embedding: list[float]) -> list[dict]:
    """降级检索：仅 Dense"""
    return dense_retrieve(merchant_id, query_embedding, 20)
