"""ReplyAgent — 回复聚合与话术生成专家（不调用工具，纯 LLM 合成）"""
from app.ai.agents.base_agent import BaseExpertAgent


class ReplyAgent(BaseExpertAgent):
    name = "reply"
    description = "聚合各专家结果，生成最终客服回复"

    # ReplyAgent 不需要工具 — 它是纯 LLM 合成器
    def _build_tools(self) -> list:
        return []

    def get_agent(self):
        # ReplyAgent 不使用 ReAct Agent — 直接使用 LLM
        return None

    def _build_prompt(self) -> str:
        return ""

    def synthesize(self, question: str, expert_results: dict) -> dict:
        """
        聚合所有专家结果，生成最终回复。

        Args:
            question: 原始买家问题
            expert_results: {"order": {...}, "logistics": {...}, "product": {...}, ...}

        Returns:
            {"reply": str, "confidence": float, "sources": list}
        """
        # 构建聚合上下文
        ctx_parts = [f"买家问题: {question}\n"]
        sources = []

        for name, result in expert_results.items():
            if result and result.get("reply") and "无法处理" not in str(result.get("reply", "")) and "异常" not in str(result.get("reply", "")):
                ctx_parts.append(f"【{name}专家回复】\n{result['reply']}")
                if result.get("steps"):
                    sources.extend(result["steps"])

        if len(ctx_parts) <= 1:
            return {"reply": "抱歉，暂未查到相关信息，请稍后重试或联系人工客服。", "confidence": 0.0, "sources": []}

        ctx = "\n\n".join(ctx_parts)

        prompt = f"""你是专业电商客服助手。基于以下专家分析结果，为买家生成一条自然、亲切的最终回复。

{ctx}

{self.role_prompt}

要求：
- 语气自然亲切，像真人客服
- 直接回答买家问题
- 整合所有相关专家信息
- 不超过200字
- 不要重复专家分析过程"""

        try:
            response = self.llm.invoke([{"role": "user", "content": prompt}])
            reply = response.content if hasattr(response, 'content') else str(response)
            return {"reply": reply.strip(), "confidence": 0.85, "sources": sources}
        except Exception as e:
            # LLM 失败时，直接拼接专家结果
            fallback = "\n".join(
                f"{name}: {result['reply'][:100]}"
                for name, result in expert_results.items()
                if result and result.get("reply")
            )
            return {"reply": fallback or "系统繁忙，请稍后重试", "confidence": 0.3, "sources": sources}
