"""Re-ranker：基于相关度对候选段落重新排序"""
import numpy as np
from typing import Callable


def cosine_sim(a: list[float], b: list[float]) -> float:
    a = np.array(a)
    b = np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def rerank_by_relevance(
    chunks: list[dict],
    query_embedding: list[float],
    embed_fn: Callable[[list[str]], list[list[float]]],
) -> list[dict]:
    """用 query embedding 与各 chunk 内容重算 cosine，按分数降序"""
    if not chunks:
        return chunks
    texts = [c.get("content", "") for c in chunks]
    embeddings = embed_fn(texts)
    for i, c in enumerate(chunks):
        c["rerank_score"] = cosine_sim(query_embedding, embeddings[i])
    return sorted(chunks, key=lambda x: -(x.get("rerank_score", 0)))
