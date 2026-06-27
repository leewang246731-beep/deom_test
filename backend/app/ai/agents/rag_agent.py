"""RAGAgent — 知识库检索专家（企业级 RAG 接口）"""
from app.ai.agents.base_agent import BaseExpertAgent
from langchain_core.tools import tool

# 顶部导入：避免高并发下延迟导入导致的性能损耗
from app.services.embedding import embed_query
from app.kb.chroma_client import get_collection as kb_get_collection
from app.kb.retriever import hybrid_retrieve


class RAGAgent(BaseExpertAgent):
    name = "rag"
    description = "知识库问答、文档检索、RAG 生成"

    def _build_tools(self) -> list:
        mid = self.merchant_id

        @tool
        def kb_search(query: str) -> str:
            """搜索知识库文档。query 为自然语言问题。返回相关文档片段。"""
            try:
                vec = embed_query(query)
                col = kb_get_collection(mid)
                result = col.query(query_embeddings=[vec], n_results=5)
                docs = result.get("documents", [[]])[0]
                metas = result.get("metadatas", [[]])[0]
                if not docs:
                    return "知识库中暂无相关内容"
                lines = []
                for i, (m, d) in enumerate(zip(metas, docs)):
                    heading = m.get("heading_context", m.get("title", "?"))
                    lines.append(f"[{i+1}] {heading}\n{d[:200]}")
                return "\n\n".join(lines)
            except Exception:
                # 降级：向量服务离线时不崩溃，返回友好提示
                return "知识库当前不可用，请稍后重试或联系管理员"

        @tool
        def kb_hybrid_search(query: str) -> str:
            """混合检索知识库（向量+关键词）。适合精确查找。"""
            try:
                vec = embed_query(query)
                chunks = hybrid_retrieve(mid, query, vec, top_k=8)
                if not chunks:
                    return "未找到匹配文档"
                return "\n\n".join(
                    f"[{c.get('chunk_index', i)}] {c.get('heading_context', '')}\n{c.get('content', '')[:200]}"
                    for i, c in enumerate(chunks[:5])
                )
            except Exception:
                return "知识库当前不可用，请稍后重试或联系管理员"

        return [kb_search, kb_hybrid_search]

    def _build_prompt(self) -> str:
        return f"""你是知识库检索专家。基于知识库文档回答买家问题。
{self.role_prompt}
规则：必须引用知识库来源。不知道就说不知道。回复简洁（<300字）。"""
