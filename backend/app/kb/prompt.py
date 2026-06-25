"""Prompt 构建器：System prompt + 知识注入 + 引用去重 + 置信度"""

SYSTEM_PROMPT = (
    "你是店铺客服智能助手。基于以下知识库内容回答用户问题。"
    "如果知识库中没有相关信息，请诚实说明不知道，不要编造。"
    "回答时请标注引用来源编号，例如【来源1】【来源2】。"
    "回答应简洁专业，用中文回复。"
)


def build_context(chunks: list[dict], max_chars: int = 4000) -> str:
    """构建注入上下文字符串"""
    parts = []
    total = 0
    for i, c in enumerate(chunks):
        content = c.get("content", "")
        heading = c.get("heading_context", "") or c.get("meta", {}).get("heading", "")
        header = f"【来源{i+1}】"
        if heading:
            header += f"[{heading}]"
        block = f"{header}\n{content}\n"
        total += len(block)
        if total > max_chars:
            break
        parts.append(block)
    return "\n".join(parts)


def dedup_references(chunks: list[dict]) -> list[dict]:
    """按 content 去重引用"""
    seen = set()
    result = []
    for c in chunks:
        key = c.get("content", "")[:100]
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


def build_qa_prompt(
    query: str,
    chunks: list[dict],
    conversation_history: list[str] | None = None,
) -> str:
    """构建完整 QA prompt"""
    deduped = dedup_references(chunks)
    context = build_context(deduped)

    history = ""
    if conversation_history:
        recent = conversation_history[-6:]
        history = "\n".join(f"Q: {q}\nA: {a}" for q, a in recent)

    parts = [SYSTEM_PROMPT]
    if history:
        parts.append(f"\n对话历史:\n{history}")
    parts.append(f"\n知识库内容:\n{context}")
    parts.append(f"\n用户问题: {query}")
    parts.append("\n回答:")
    return "\n".join(parts)


def compute_confidence(chunks: list[dict], answer: str) -> float:
    """基于 fusion_score 均值计算置信度"""
    if not chunks:
        return 0.0
    scores = [c.get("fusion_score") or c.get("rerank_score") or c.get("dense_score") or 0.0 for c in chunks[:5]]
    avg = sum(scores) / len(scores) if scores else 0.0
    return round(min(avg * 1.2, 1.0), 3)


def build_references(chunks: list[dict]) -> list[dict]:
    """构建引用列表"""
    refs = []
    for i, c in enumerate(chunks[:10]):
        refs.append({
            "index": i + 1,
            "chunk_id": c.get("chunk_id"),
            "heading": c.get("heading_context") or c.get("meta", {}).get("heading", ""),
            "content_snippet": (c.get("content", "") or "")[:120],
            "score": c.get("fusion_score") or c.get("rerank_score") or c.get("dense_score") or 0.0,
        })
    return refs
