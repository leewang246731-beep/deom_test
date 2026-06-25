"""CRAG (Corrective RAG)：评估 → 判决 → 校正动作"""
import json
from typing import Callable


class CragEvaluator:
    def __init__(self, llm_fn: Callable[[str, str], str] | None = None):
        self.llm = llm_fn

    def evaluate(self, query: str, top_chunks: list[dict]) -> dict:
        """对 Top-5 chunks 做 LLM 相关性评估，返回 CRAG 判决"""
        if not top_chunks:
            return {"verdict": "no_context", "relevant": [], "irrelevant": []}

        if not self.llm:
            return {"verdict": "all_relevant", "relevant": [c["chunk_id"] for c in top_chunks], "irrelevant": []}

        ctx = "\n\n".join(f"[{i+1}] {c['content'][:300]}" for i, c in enumerate(top_chunks[:5]))
        prompt = (
            f"评估以下检索到的文档片段与问题的相关性。\n"
            f"问题: {query}\n\n"
            f"片段:\n{ctx}\n\n"
            f"对每个片段，标记为 relevant 或 irrelevant。输出 JSON 数组: [{{\"id\": 数字, \"verdict\": \"relevant|irrelevant\"}}]"
        )
        try:
            resp = self.llm(prompt, "crag").strip()
            verdicts = _parse_verdicts(resp, top_chunks)
        except Exception:
            verdicts = [{"id": i+1, "verdict": "relevant"} for i in range(len(top_chunks[:5]))]

        relevant = [top_chunks[v["id"]-1]["chunk_id"] for v in verdicts if v["verdict"] == "relevant" and v["id"]-1 < len(top_chunks)]
        irrelevant = [top_chunks[v["id"]-1]["chunk_id"] for v in verdicts if v["verdict"] == "irrelevant" and v["id"]-1 < len(top_chunks)]

        if not relevant:
            return {"verdict": "no_relevant", "relevant": [], "irrelevant": irrelevant}

        return {"verdict": "partial", "relevant": relevant, "irrelevant": irrelevant}


def _parse_verdicts(resp: str, top_chunks: list[dict]) -> list[dict]:
    """从 LLM 响应中解析判决 JSON"""
    import re
    match = re.search(r'\[[\s\S]*\]', resp)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return [{"id": i+1, "verdict": "relevant"} for i in range(len(top_chunks[:5]))]
