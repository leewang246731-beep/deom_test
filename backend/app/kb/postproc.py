"""后处理：压缩 + 重排序"""


def compress_chunks(chunks: list[dict], max_tokens: int = 2000) -> list[dict]:
    """压缩：控制上下文总 token 数"""
    total = 0
    result = []
    token_ratio = 0.77  # ~1.3 char/token
    for c in chunks:
        t = int(len(c.get("content", "")) * token_ratio)
        total += t
        result.append(c)
        if total >= max_tokens:
            break
    return result


def reorder_chunks(chunks: list[dict]) -> list[dict]:
    """信息重排：高分放在首尾（首尾优先效应）"""
    if len(chunks) < 3:
        return chunks
    half = len(chunks) // 2
    result = []
    for i in range(half):
        result.append(chunks[i])
        result.insert(i + 1, chunks[-(i + 1)])
    if len(chunks) % 2 == 1:
        result.append(chunks[half])
    return result
