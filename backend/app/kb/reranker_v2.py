"""
Enhanced Reranker — DashScope gte-rerank-v2 API.

Replaces the old cosine-similarity reranker (which re-embeds all chunks).
Professional Cross-Encoder reranker: 1 API call vs O(20) embedding calls.
"""
from app.core.config import settings


MODEL = "gte-rerank-v2"


def rerank(query: str, chunks: list[dict], top_n: int = 5) -> list[dict]:
    """
    Rerank chunks using DashScope gte-rerank-v2.

    Args:
        query:   User question
        chunks:  List of chunk dicts with 'content' key
        top_n:   Number of top results to return

    Returns:
        Rescored chunks with added 'rerank_score' and 'rerank_index' fields.
        Falls back to original order on API failure.
    """
    if not chunks:
        return []

    if not settings.DASHSCOPE_API_KEY:
        # Fallback: keep original order, mark as unranked
        for i, c in enumerate(chunks):
            c["rerank_score"] = 1.0 - i * 0.05
            c["rerank_index"] = i
        return chunks[:top_n]

    try:
        import dashscope
        from dashscope import TextReRank
        dashscope.api_key = settings.DASHSCOPE_API_KEY

        documents = [c.get("content", "")[:500] for c in chunks]  # Truncate for API limit
        resp = TextReRank.call(
            model=MODEL,
            query=query,
            documents=documents,
            top_n=min(top_n, len(documents)),
            return_documents=True,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Rerank API failed: {resp.status_code} {resp.message}")

        results = []
        for item in resp.output.get("results", []):
            idx = item["index"]
            if idx < len(chunks):
                c = dict(chunks[idx])
                c["rerank_score"] = item["relevance_score"]
                c["rerank_index"] = item["index"]
                results.append(c)

        return results[:top_n]

    except Exception as e:
        # Fallback: cosine similarity (single embed + numpy)
        return _fallback_rerank(query, chunks, top_n)


def _fallback_rerank(query: str, chunks: list[dict], top_n: int) -> list[dict]:
    """Fallback: cosine similarity using embedding API."""
    try:
        import numpy as np
        from app.services.embedding import embed_query, embed_texts

        q_vec = np.array(embed_query(query))
        texts = [c.get("content", "")[:500] for c in chunks]
        c_vecs = [np.array(v) for v in embed_texts(texts)]

        for i, (c, cv) in enumerate(zip(chunks, c_vecs)):
            na, nb = np.linalg.norm(q_vec), np.linalg.norm(cv)
            score = float(np.dot(q_vec, cv) / (na * nb)) if na > 0 and nb > 0 else 0.0
            c["rerank_score"] = score
            c["rerank_index"] = i

        ranked = sorted(chunks, key=lambda x: x.get("rerank_score", 0), reverse=True)
        return ranked[:top_n]
    except Exception:
        for i, c in enumerate(chunks):
            c["rerank_score"] = 1.0 - i * 0.05
        return chunks[:top_n]
