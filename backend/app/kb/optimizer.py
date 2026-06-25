"""查询优化：模式升级 fast→auto→comprehensive，查询重写，HyDE"""
import json
from typing import Callable

VAGUE_WORDS = ["那个", "这个", "东西", "怎么样", "好不好", "大概", "可能", "也"]


class QueryOptimizer:
    def __init__(self, llm_fn: Callable[[str, str], str] | None = None):
        self.llm = llm_fn

    def detect_mode(self, query: str) -> str:
        """检测查询复杂度，返回 fast/auto/comprehensive"""
        qlen = len(query)
        vague = sum(1 for w in VAGUE_WORDS if w in query)
        if qlen < 8 or vague >= 3:
            return "comprehensive"
        if qlen < 20:
            return "auto"
        return "fast"

    def rewrite(self, query: str) -> str:
        """模糊查询重写（基于规则），有 LLM 时用 LLM"""
        if self.llm:
            prompt = f"将用户的模糊查询改写成准确的信息检索查询。\n原始: {query}\n改写后:"
            try:
                return self.llm(prompt, "rewrite").strip()
            except Exception:
                pass

        # 规则回退
        if any(w in query for w in VAGUE_WORDS):
            q = query
            for w in VAGUE_WORDS:
                q = q.replace(w, "")
            return q.strip() or query
        return query

    def hyde(self, query: str) -> str:
        """HyDE：生成假设文档"""
        if not self.llm:
            return query
        prompt = (
            "请根据以下问题，生成一段假设性的答案文本（不超过200字），"
            "用于改进信息检索效果。\n"
            f"问题: {query}\n假设答案:"
        )
        try:
            return self.llm(prompt, "hyde").strip()
        except Exception:
            return query

    def dedup(self, chunks: list[dict]) -> list[dict]:
        """对检索结果去重（基于 chunk_id）"""
        seen = set()
        result = []
        for c in chunks:
            if c["chunk_id"] not in seen:
                seen.add(c["chunk_id"])
                result.append(c)
        return result
