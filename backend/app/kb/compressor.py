"""
Context Compressor — sentence-level relevance pruning.

Adapted from D:/project_test/backend/rag/compressor.py.
Implements LlamaIndex SentenceEmbeddingOptimizer logic using project's own DashScope embedding.
"""
import re
import numpy as np
from app.services.embedding import embed_texts

_SENT_SPLIT = re.compile(r'(?<=[。！？；\n])')


def _split_sentences(text: str) -> list[str]:
    return [p.strip() for p in _SENT_SPLIT.split(text) if p.strip()]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def compress_chunks(chunks: list[dict], question: str,
                    percentile_cutoff: float = 0.5,
                    min_sentences: int = 1) -> list[dict]:
    """
    Prune irrelevant sentences from each chunk.

    Args:
        chunks:             Retrieved chunk list with 'content' key
        question:           User question
        percentile_cutoff:  Keep top N% sentences by relevance (0.5 = top 50%)
        min_sentences:      Minimum sentences to keep per chunk

    Returns:
        Compressed chunk list (content pruned, other fields unchanged)
    """
    if not chunks:
        return chunks

    all_sentences = []
    chunk_ranges = []  # (start, end, prefix)

    for c in chunks:
        content = c.get("content", "")
        prefix = ""
        body = content
        m = re.match(r'^(\[[^\]]+\]\n)', content)
        if m:
            prefix = m.group(1)
            body = content[len(prefix):]

        sents = _split_sentences(body)
        start = len(all_sentences)
        all_sentences.extend(sents)
        chunk_ranges.append((start, len(all_sentences), prefix))

    if not all_sentences:
        return chunks

    try:
        embeds = embed_texts([question] + all_sentences)
    except Exception:
        return chunks  # Embedding failed, return original

    q_vec = np.array(embeds[0])
    sims = [_cosine(q_vec, np.array(v)) for v in embeds[1:]]

    compressed = []
    for c, (start, end, prefix) in zip(chunks, chunk_ranges):
        sent_count = end - start
        if sent_count == 0:
            compressed.append(c)
            continue

        chunk_sims = sims[start:end]
        chunk_sents = all_sentences[start:end]

        keep_n = max(min_sentences, int(round(sent_count * percentile_cutoff)))
        keep_n = min(keep_n, sent_count)

        top_idx = sorted(
            sorted(range(sent_count), key=lambda i: chunk_sims[i], reverse=True)[:keep_n]
        )
        kept = [chunk_sents[i] for i in top_idx]

        new_chunk = dict(c)
        new_chunk["content"] = prefix + "".join(kept)
        new_chunk["_compressed"] = True
        compressed.append(new_chunk)

    return compressed
