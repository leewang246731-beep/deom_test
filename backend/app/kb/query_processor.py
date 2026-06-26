"""
Query Processor — query rewrite + HyDE + auto-correction.

Enables HyDE (previously disabled) and adds Step-Back expansion.
Adapted from D:/project_test/backend/rag/query_rewriter.py.
"""
from app.services.llm import chat


# ===== T2: Prompt Rewrite =====
REWRITE_PROMPT = """你是电商知识库的检索查询改写器。把用户问题改写成一行检索关键词。

规则：
1. 只输出改写后的关键词，一行，不超过 30 字。
2. 不要反问、解释、不要输出"请补充型号"之类的话。
3. 提取商品名、品牌、问题类型(物流/售后/退款/使用)、操作意图。

示例：
用户问题: 怎么退货 → 退货 流程 规则
用户问题: 华为手机怎么样 → 华为 手机 评测 参数

用户问题: {question}
改写关键词:"""

_MAX_REWRITE_LEN = 40


def prompt_rewrite(question: str) -> str:
    """LLM rewrite fuzzy question into precise keywords. Falls back to original on failure."""
    try:
        rewritten = chat([{"role": "user", "content": REWRITE_PROMPT.format(question=question)}])
        rewritten = (rewritten or "").strip().split("\n")[0].strip()
        if not rewritten or len(rewritten) > _MAX_REWRITE_LEN:
            return question
        return rewritten
    except Exception:
        return question


# ===== T8: HyDE (Hypothetical Document Embedding) =====
HYDE_PROMPT = """你是电商客服专家。根据用户问题，写出你认为知识库中会包含的相关信息。
不要直接回答问题，写出 2-3 句假设的知识库内容。
使用专业、客观的语气。

用户问题: {question}
假设的知识库内容:"""


def hyde_rewrite(question: str) -> str:
    """
    HyDE: Generate hypothetical answer → use {question + hypothetical} for retrieval.
    Falls back to original question on failure.
    """
    try:
        hypothetical = chat([{"role": "user", "content": HYDE_PROMPT.format(question=question)}])
        hypothetical = (hypothetical or "").strip()
        return f"{question}\n{hypothetical}" if hypothetical else question
    except Exception:
        return question


# ===== T12: Step-Back Expansion =====
STEP_BACK_PROMPT = """以下是一个电商用户问题。请"退一步"写一个更宽泛的相关检索查询。
不要回答原问题。

用户问题: {question}
更宽泛的检索查询:"""


def step_back_expand(question: str) -> str | None:
    """Generate broader query for expanded recall. Returns None on failure."""
    try:
        expanded = chat([{"role": "user", "content": STEP_BACK_PROMPT.format(question=question)}])
        expanded = (expanded or "").strip()
        return expanded if expanded else None
    except Exception:
        return None


# ===== Unified Optimizer =====
def optimize_query(question: str, mode: str = "auto") -> list[str]:
    """
    Unified query optimization.

    Modes:
      "fast"         → original only
      "auto"(default)→ original + rewrite + hyde (if short/vague)
      "comprehensive"→ auto + step_back

    Returns list of query strings for multi-query retrieval.
    """
    queries = [question]

    if mode == "fast":
        return queries

    # Auto mode: always rewrite
    rewritten = prompt_rewrite(question)
    if rewritten != question:
        queries.append(rewritten)

    # HyDE for short/vague questions
    if len(question) < 15 or any(w in question for w in ["怎么", "如何", "为什么", "什么"]):
        hyde_q = hyde_rewrite(question)
        if hyde_q != question:
            queries.append(hyde_q)

    if mode == "comprehensive":
        expanded = step_back_expand(question)
        if expanded:
            queries.append(expanded)

    return queries
