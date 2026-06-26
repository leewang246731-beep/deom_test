"""TicketAgent — 工单历史搜索与处理建议专家"""
from app.ai.agents.base_agent import BaseExpertAgent
from langchain_core.tools import tool


class TicketAgent(BaseExpertAgent):
    name = "ticket"
    description = "历史工单搜索、工单创建建议、处理方案推荐"

    def _build_tools(self) -> list:
        mid = self.merchant_id

        @tool
        def search_ticket_history(query: str) -> str:
            """搜索历史工单处理方案。query 为问题描述。返回相似工单及处理方式。"""
            try:
                from app.services.chroma_client import get_collection
                from app.services.embedding import embed_query
                vec = embed_query(query)
                col = get_collection(mid)
                result = col.query(query_embeddings=[vec], n_results=5, where={"type": "ticket_case"})
                metas = result.get("metadatas", [[]])[0]
                docs = result.get("documents", [[]])[0]
                if not metas: return "暂无历史工单参考"
                lines = [f"标题:{m.get('title','?')} 分类:{m.get('category','?')} 优先级:{m.get('priority','?')} 描述:{d[:120]}" for m, d in zip(metas, docs)]
                return "\n".join(lines)
            except Exception as e:
                return f"工单搜索失败: {e}"

        @tool
        def suggest_ticket_priority(description: str) -> str:
            """根据问题描述建议工单优先级(P0/P1/P2/P3)。"""
            urgent_kw = ["退款", "投诉", "差评", "法律", "举报", "欺诈"]
            high_kw = ["物流", "发货", "延迟", "破损", "质量问题"]
            if any(k in description for k in urgent_kw): return "建议优先级: P0 (紧急)"
            if any(k in description for k in high_kw): return "建议优先级: P1 (高)"
            if len(description) > 30: return "建议优先级: P2 (中)"
            return "建议优先级: P3 (低)"

        return [search_ticket_history, suggest_ticket_priority]

    def _build_prompt(self) -> str:
        return f"""你是工单处理专家。你可以搜索历史工单参考、建议优先级。
{self.role_prompt}
规则：必须调用工具。回复简洁（<200字）。"""
