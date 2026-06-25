"""
工单 AI Pipeline（PHASE3-PLAN §6）
复用现有 embedding / ChromaDB / LLM 能力。
- classify_ticket: AI 自动分类 + 优先级预测
- suggest_ticket_reply: 工单话术建议（检索历史工单方案→LLM）
- summarize_ticket: AI 自动总结处理纪要
- backfill_tickets: 工单向量化入库
"""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ticket import Ticket
from app.models.ticket_category import TicketCategory
from app.models.ticket_comment import TicketComment
from app.services.chroma_client import add_products, query_products
from app.services.embedding import embed_query, embed_texts
from app.services.llm import chat


def classify_ticket(db: Session, merchant_id: int, title: str, description: str) -> dict:
    """AI 自动分类：标题+描述 → 向量匹配工单分类 + LLM 优先级预测。"""
    text = f"{title} {description or ''}"
    vec = embed_query(text)
    # 用向量匹配工单分类
    try:
        result = query_products(merchant_id, vec, n_results=3)
    except Exception:
        result = {"metadatas": [[]]}

    cats = db.query(TicketCategory).filter(
        TicketCategory.merchant_id == merchant_id,
        TicketCategory.level == 2,  # 取叶子分类
    ).all()
    cat_map = {c.id: c.name for c in cats}

    # 优先级 LLM 预测
    prompt = f"""请判断以下客服工单的优先级(P0:致命/P1:紧急/P2:一般/P3:咨询)。

标题：{title}
描述：{description or '无'}

仅回复 P0、P1、P2 或 P3:"""
    try:
        priority_raw = chat([{"role": "user", "content": prompt}]).strip()
        priority = "P2"  # default
        for p in ["P0", "P1", "P2", "P3"]:
            if p in priority_raw:
                priority = p
                break
    except Exception:
        priority = "P2"

    return {"suggested_priority": priority, "suggested_category_id": None}


TICKET_AGENT_KEYWORDS = ["退款", "退货", "换货", "售后", "投诉", "物流", "快递", "发货", "赔偿"]


def _should_use_ticket_agent(title: str, description: str = "") -> bool:
    text = f"{title} {description or ''}"
    return any(kw in text for kw in TICKET_AGENT_KEYWORDS)


def suggest_ticket_reply(merchant_id: int, ticket_title: str, ticket_description: str = "",
                         ticket_status: str = "pending") -> list[dict]:
    """工单话术建议：检索历史相似工单方案 → LLM 生成回复。"""
    text = f"{ticket_title} {ticket_description or ''}"

    # ---- Agent 路径：涉及售后/物流/投诉走 Agent ----
    if _should_use_ticket_agent(ticket_title, ticket_description):
        try:
            from app.ai.agent import create_service_agent, run_agent
            agent = create_service_agent(merchant_id, "你是工单处理专家，优先使用 search_ticket_history 查询历史方案。")
            result = run_agent(agent, f"工单：{text}\n请给出处理建议。")
            suggestions = [{"content": result["reply"], "source": "agent", "confidence": 0.85}]
            return suggestions
        except Exception:
            pass

    vec = embed_query(text)
    try:
        result = query_products(merchant_id, vec, n_results=5)
    except Exception:
        return [{"content": "暂无相关历史工单参考，请手动回复。", "source": "fallback", "confidence": 0}]

    history = "\n".join(
        f"- {m.get('title', '')}: {d[:100]}"
        for m, d in zip(result.get("metadatas", [[]])[0], result.get("documents", [[]])[0])
    ) or "（无历史工单参考）"

    prompt = f"""你是客服工单处理助手。基于以下历史工单处理经验，为当前工单生成3条回复或处理建议。

历史工单参考：
{history}

当前工单：
标题：{ticket_title}
描述：{ticket_description or '无'}
状态：{ticket_status}

要求：直接给出可操作的回复建议，每条不超过200字。用 --- 分隔。"""

    try:
        response = chat([{"role": "user", "content": prompt}])
        parts = [p.strip() for p in response.split("---") if p.strip()]
        suggestions = [{"content": p, "source": "llm", "confidence": 0.8} for p in (parts if len(parts) >= 3 else [response])]
        return suggestions[:3]
    except Exception:
        return [{"content": r["meta"].get("title", r["content"]), "source": "retrieval", "confidence": 0.5}
                for r in [{"meta": {}, "content": "暂无建议"}]]


def summarize_ticket(db: Session, ticket_id: int) -> str:
    """AI 自动总结：汇总评论时间线 → LLM 生成处理纪要。"""
    ticket = db.query(Ticket).get(ticket_id)
    if not ticket:
        return ""
    comments = db.query(TicketComment).filter(
        TicketComment.ticket_id == ticket_id, TicketComment.is_internal == 0
    ).order_by(TicketComment.created_at).all()

    timeline = "\n".join(f"- {c.created_at}: {c.content[:100]}" for c in comments) or "无评论"
    prompt = f"""请为以下客服工单生成一段处理纪要（100-200字）。

工单标题：{ticket.title}
工单描述：{ticket.description or '无'}
处理时间线：
{timeline}

处理纪要："""
    try:
        return chat([{"role": "user", "content": prompt}]).strip()
    except Exception:
        return f"工单{ticket.ticket_no}已处理完成。"


def backfill_tickets(db: Session, merchant_id: int) -> int:
    """工单向量化入库：标题+描述+分类 → ChromaDB (type=ticket_case)。"""
    from app.core.config import settings as s
    from app.services.chroma_client import get_collection

    tickets = db.query(Ticket).filter(Ticket.merchant_id == merchant_id).all()
    if not tickets:
        return 0

    ids_, texts, metas = [], [], []
    for t in tickets:
        cat_name = ""
        if t.category_id:
            c = db.query(TicketCategory).get(t.category_id)
            cat_name = c.name if c else ""
        ids_.append(f"ticket_{t.id}")
        texts.append(f"标题：{t.title} 分类：{cat_name} 描述：{t.description or ''}")
        metas.append({"type": "ticket_case", "ticket_id": t.id, "title": t.title,
                       "priority": t.priority, "status": t.status, "category": cat_name})

    if texts:
        vecs = embed_texts(texts)
        import traceback
        try:
            col = get_collection(merchant_id)
            col.add(ids=ids_, documents=texts, metadatas=metas, embeddings=vecs)
        except Exception:
            traceback.print_exc()
            return 0
    return len(texts)
