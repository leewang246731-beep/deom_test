"""BM25 全文检索 — 租户级索引，jieba 分词 + rank-bm25"""
import pickle
import os

import jieba
from rank_bm25 import BM25Okapi

INDEX_DIR = os.path.join(os.path.dirname(__file__), "bm25_stores")


def _ensure_dir():
    os.makedirs(INDEX_DIR, exist_ok=True)


def _index_path(merchant_id: int) -> str:
    return os.path.join(INDEX_DIR, f"merchant_{merchant_id}.pkl")


def build_index(merchant_id: int, chunks: list[dict]) -> BM25Okapi:
    """构建 BM25 索引。chunks 为 [{id, content}, ...]"""
    _ensure_dir()
    corpus = []
    chunk_ids = []
    for c in chunks:
        tokenized = [w for w in jieba.cut_for_search(c["content"]) if len(w.strip()) > 1]
        corpus.append(tokenized)
        chunk_ids.append(c["id"])

    index = BM25Okapi(corpus)
    index.chunk_ids = chunk_ids
    with open(_index_path(merchant_id), "wb") as f:
        pickle.dump({"corpus": corpus, "chunk_ids": chunk_ids}, f)
    return index


def load_index(merchant_id: int) -> BM25Okapi | None:
    path = _index_path(merchant_id)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        data = pickle.load(f)
    index = BM25Okapi(data["corpus"])
    index.chunk_ids = data["chunk_ids"]
    return index


def delete_index(merchant_id: int):
    path = _index_path(merchant_id)
    if os.path.exists(path):
        os.remove(path)


def search(merchant_id: int, query: str, top_k: int = 20) -> list[dict]:
    """BM25 搜索，返回 [{chunk_id, score}，按分数降序]"""
    idx = load_index(merchant_id)
    if not idx:
        return []
    tokenized = [w for w in jieba.cut_for_search(query) if len(w.strip()) > 1]
    if not tokenized:
        return []
    scores = idx.get_scores(tokenized)
    ranked = sorted(zip(idx.chunk_ids, scores), key=lambda x: -x[1])
    return [{"chunk_id": int(cid), "score": float(s)} for cid, s in ranked[:top_k]]
