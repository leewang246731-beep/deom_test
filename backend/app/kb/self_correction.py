"""
Self-Correction Module — Fact-check + Hallucination Detection.

Post-generation quality check:
1. Verify generated answer against retrieved chunks
2. Detect unsupported claims (hallucination)
3. Trigger re-generation if needed
"""
from app.services.llm import chat


FACT_CHECK_PROMPT = """你是事实核查员。判断以下AI回复是否完全基于提供的知识来源。

知识来源:
{context}

AI回复:
{answer}

请判断:
1. 回复中的每句话是否都能在来源中找到依据？
2. 是否存在编造、猜测或来源中没有的信息？

输出JSON:
{{"factual": true/false, "unsupported_claims": ["claim1", "claim2"], "score": 0.0-1.0}}
"""

CORRECTION_PROMPT = """你是电商客服专家。以下AI回复包含不准确的信息。请基于知识来源重新生成回复。

知识来源:
{context}

不准确的AI回复:
{answer}

问题部分: {issues}

请生成修正后的回复（<200字）:"""


class SelfCorrection:
    """Post-generation fact-check and self-correction."""

    def __init__(self, enabled: bool = True, threshold: float = 0.6):
        self.enabled = enabled
        self.threshold = threshold

    def check(self, answer: str, chunks: list[dict]) -> dict:
        """
        Fact-check answer against retrieved chunks.

        Returns:
            {"factual": bool, "score": float, "unsupported_claims": list, "needs_correction": bool}
        """
        if not self.enabled or not chunks:
            return {"factual": True, "score": 1.0, "unsupported_claims": [], "needs_correction": False}

        context = "\n\n".join(
            f"[来源{i+1}] {c.get('content', '')[:300]}"
            for i, c in enumerate(chunks[:5])
        )

        try:
            response = chat([{
                "role": "user",
                "content": FACT_CHECK_PROMPT.format(context=context, answer=answer),
            }])

            # Parse JSON from response
            import json, re
            match = re.search(r'\{[^}]+\}', response)
            if match:
                result = json.loads(match.group())
            else:
                result = {"factual": True, "score": 0.7}

            result["needs_correction"] = (
                not result.get("factual", True) or
                result.get("score", 1.0) < self.threshold
            )
            return result

        except Exception:
            return {"factual": True, "score": 0.7, "unsupported_claims": [], "needs_correction": False}

    def correct(self, answer: str, chunks: list[dict], issues: list[str]) -> str:
        """Regenerate answer based on source chunks."""
        context = "\n\n".join(
            f"[来源{i+1}] {c.get('content', '')[:300]}"
            for i, c in enumerate(chunks[:5])
        )
        try:
            corrected = chat([{
                "role": "user",
                "content": CORRECTION_PROMPT.format(
                    context=context, answer=answer,
                    issues="; ".join(issues) if issues else "包含未验证的信息",
                ),
            }])
            return corrected.strip() if corrected else answer
        except Exception:
            return answer
