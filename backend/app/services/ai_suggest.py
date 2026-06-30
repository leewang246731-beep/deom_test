"""
AI 话术引擎（PHASE1-PLAN 步骤6 / agent-design.md Pipeline）

对外暴露：
- semantic_search_products  —— 商品向量搜索（/products/search）
- get_ai_suggestions         —— 话术建议（POST /ai/suggest + WS）
- generate_payment_reminders —— 催单话术（POST /ai/campaign/pending-payment）
- knowledge_search           —— 知识库语义搜索（POST /ai/search）
- backfill_all               —— 存量商品+会话向量化回填（步骤6.2）
"""
import json
import math
import traceback
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.conversation import Conversation
from app.models.external_order import ExternalOrder
from app.models.external_product import ExternalProduct
from app.models.platform_shop import PlatformShop
from app.services.chroma_client import (
    add_products,
    add_replies,
    query_products,
    query_replies,
)
from app.services.embedding import embed_query, embed_texts
from app.services.llm import chat, achat

# ===== Agent 关键词检测 =====
AGENT_KEYWORDS = [
    "订单", "物流", "快递", "发货", "到哪", "运输", "配送", "收货",
    "库存", "有货", "没货", "下架", "补货",
    "退款", "退货", "售后", "工单",
    "order", "logistics", "tracking", "shipping", "delivery", "stock", "inventory", "refund",
]


def _should_use_agent(question: str) -> bool:
    return any(kw in question.lower() for kw in AGENT_KEYWORDS)


# ===== RRF 融合 =====
def _rrf_fusion(
    product_results: dict,
    reply_results: dict,
    k: int = 60,
    top_n: int = 5,
    current_product_id: int = None,
) -> list[dict]:
    """RRF (Reciprocal Rank Fusion)：商品向量 + 话术向量 → 统一排序。
    若提供 current_product_id，匹配商品会获得加权提升。"""
    scores = {}
    for rank, (doc_id, meta, doc) in enumerate(zip(
        product_results.get("ids", [[]])[0],
        product_results.get("metadatas", [[]])[0],
        product_results.get("documents", [[]])[0],
    )):
        rrf = 1.0 / (k + rank + 1)
        # 当前咨询商品加权：RRF 值 × 2（确保排在前面）
        if current_product_id and meta.get("product_id") == current_product_id:
            rrf *= 2.0
        scores[doc_id] = {
            "content": doc, "meta": meta, "source": "product",
            "rrf": scores.get(doc_id, {}).get("rrf", 0) + rrf,
        }
    for rank, (doc_id, meta, doc) in enumerate(zip(
        reply_results.get("ids", [[]])[0],
        reply_results.get("metadatas", [[]])[0],
        reply_results.get("documents", [[]])[0],
    )):
        rrf = 1.0 / (k + rank + 1)
        if doc_id in scores:
            scores[doc_id]["rrf"] += rrf
        else:
            scores[doc_id] = {
                "content": doc, "meta": meta, "source": "reply",
                "rrf": rrf,
            }
    ranked = sorted(scores.values(), key=lambda x: x["rrf"], reverse=True)
    return ranked[:top_n]


# ===== 商品语义搜索 =====
def semantic_search_products(merchant_id: int, query: str, shop_ids: list, top_k: int = 10) -> list[dict]:
    """向量检索商品，返回含评分的商品列表。shop_ids 用于 post-filter（缺口5）。"""
    vec = embed_query(query)
    n_fetch = min(top_k * 3 if shop_ids else top_k, 30)
    result = query_products(merchant_id, vec, n_results=n_fetch)
    output = []
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]
    for i, meta in enumerate(metas):
        sid = meta.get("shop_id")
        if shop_ids and sid not in shop_ids:
            continue
        dist = dists[i] if i < len(dists) else 1.0
        score = round(1.0 / (1.0 + dist), 4)
        output.append({
            "id": meta.get("product_id"),
            "title": meta.get("title", ""),
            "price": meta.get("price"),
            "shop_id": sid,
            "score": score,
        })
        if len(output) >= top_k:
            break
    return output


# ===== 话术建议（核心 Pipeline）=====
async def get_ai_suggestions(
    merchant_id: int,
    shop_id: int,
    buyer_question: str,
    conversation_history: list[dict] | None,
    product_id: int | None,
    db: Session,
) -> dict:
    """话术建议 Pipeline：向量检索 → RRF → LLM 生成 3 条回复（含物流感知+角色感知）。"""
    # ---- 当前商品上下文注入 ----
    product_context = ""
    if product_id:
        try:
            from app.models.external_product import ExternalProduct
            ep = db.query(ExternalProduct).filter(ExternalProduct.id == product_id).first()
            if ep:
                product_context = (
                    f"【当前咨询商品】用户正在浏览此商品，所有指代词如「这个」「这款」「它」默认指该商品。\n"
                    f"- 商品名: {ep.title}\n"
                    f"- 商品ID: {ep.id}\n"
                    f"- 价格: ¥{float(ep.price):.2f}\n"
                    f"- 库存: {ep.stock}件\n"
                    f"- 分类: {ep.category_path or '未分类'}\n"
                    f"- 描述: {ep.description or '无'}\n"
                )
        except Exception:
            pass

    # ---- 角色 Prompt 注入 ----
    from app.services.mode_engine import get_role_prompt
    role_prompt = ""
    try:
        from app.models.skill_group import SkillMember
        from app.models.conversation import Conversation
        conv = db.query(Conversation).filter(Conversation.shop_id == shop_id).order_by(
            Conversation.last_message_at.desc()).first()
        if conv and conv.assigned_to:
            sm = db.query(SkillMember).filter(SkillMember.user_id == conv.assigned_to).first()
            if sm:
                role_prompt = get_role_prompt(sm.skill_tags or "")
    except Exception:
        pass

    # ---- Agent 路径：订单/物流/库存/售后 → LangChain Agent ----
    if _should_use_agent(buyer_question):
        try:
            from app.ai.agent import _build_agent, run_agent
            agent = _build_agent(merchant_id, role_prompt)
            # 注入商品上下文到问题中
            augmented_question = f"{product_context}\n用户问题: {buyer_question}" if product_context else buyer_question
            result = run_agent(agent, augmented_question,
                               [(h.get("role", ""), h.get("content", "")) for h in (conversation_history or [])])
            suggestions = [
                {"content": result["reply"], "source": "agent", "confidence": 0.85}
            ]
            if len(result["reply"]) < 80:
                # Agent 回复偏短时，补充 RAG 检索结果作为备选话术
                vec = embed_query(buyer_question)
                replies = query_replies(merchant_id, vec, n_results=2)
                for meta in replies.get("metadatas", [[]])[0][:2]:
                    suggestions.append({"content": meta.get("reply", ""), "source": "retrieval", "confidence": 0.6})
            _writeback_ai_reply(db, shop_id, buyer_question, suggestions)
            return {"suggestions": suggestions[:3], "agent_steps": result["intermediate_steps"]}
        except Exception as e:
            # Agent 失败，继续走原 RAG 链路
            pass

    # ---- 物流状态注入 (tuozhan.md §2.6) ----
    logistics_info = await _get_logistics_context(merchant_id, shop_id, db)

    vec = embed_query(buyer_question)
    products = query_products(merchant_id, vec, n_results=min(settings.RAG_TOP_K, 10))
    replies = query_replies(merchant_id, vec, n_results=min(settings.RAG_TOP_K, 10))

    fused = _rrf_fusion(products, replies, k=60, top_n=5, current_product_id=product_id)
    if not fused:
        return {"suggestions": [{"content": "暂无相关参考，请手动回复。", "source": "fallback", "confidence": 0}],
                "logistics": logistics_info}

    product_info = "\n".join(
        f"- {r['content']}" for r in fused if r["source"] == "product"
    ) or "（无匹配商品信息）"
    reply_examples = "\n".join(
        f"Q: {r['meta'].get('buyer_question', '?')}  A: {r['meta'].get('reply', r['content'])}"
        for r in fused if r["source"] == "reply"
    ) or "（无历史话术参考）"

    # 物流信息注入 Prompt
    logistics_block = ""
    if logistics_info:
        logistics_block = f"""
【物流状态】：{logistics_info.get('status_label', '未知')}
【当前节点】：{logistics_info.get('current_node', '未知')}
【预计送达】：{logistics_info.get('estimated_days', '?')}天
【快递公司】：{logistics_info.get('company', '未知')} {logistics_info.get('tracking_no', '')}
【异常信息】：{logistics_info.get('exception_detail', '无')}
"""

    role_block = f"\n【角色定位】：{role_prompt}\n" if role_prompt else ""

    prompt = f"""你是电商客服助手。基于以下信息，为买家问题生成3条回复建议。
{product_context}{role_block}{logistics_block}
商品信息：
{product_info}

历史参考话术：
{reply_examples}

买家问题：{buyer_question}

要求：语气自然亲切、直接回答买家问题、每条不超过200字。
若提供了【当前咨询商品】，所有指代词默认指向该商品。仅当买家明确提到其他商品时才切换。
若买家问物流相关，必须引用物流状态具体信息。
用 --- 分隔三条建议。"""

    try:
        response = await achat([{"role": "user", "content": prompt}])
        parts = [p.strip() for p in response.split("---") if p.strip()]
        # 计算置信度
        from app.services.mode_engine import calc_confidence
        conf = calc_confidence(fused, response, buyer_question)
        suggestions = [
            {"content": p, "source": "llm", "confidence": conf}
            for p in (parts if len(parts) >= 3 else [response])
        ]
        if len(suggestions) < 3:
            suggestions += [
                {"content": r["meta"].get("reply", r["content"]), "source": "retrieval", "confidence": round(conf * 0.7, 2)}
                for r in fused[:3 - len(suggestions)]
            ]
        result = {"suggestions": suggestions[:3], "confidence": conf, "query_ms": 0, "logistics": logistics_info}
    except Exception as e:
        result = {"suggestions": [
            {"content": r["meta"].get("reply", r["content"]), "source": "retrieval", "confidence": 0.5}
            for r in fused[:3]
        ], "fallback_reason": str(e), "logistics": logistics_info}

    # 回写 ai_suggest_reply 到会话（缺口8）
    _writeback_ai_reply(db, shop_id, buyer_question, result["suggestions"])
    return result


# ===== 催单话术生成 =====
def generate_payment_reminders(merchant_id: int, shop_id: int, db: Session,
                               limit: int = 20, offset: int = 0) -> dict:
    """扫描未支付订单 → LLM 生成千人千面催付话术 → 模拟发送（缺口4：分页）"""
    shop_ids = [r[0] for r in db.query(PlatformShop.id).filter(
        PlatformShop.merchant_id == merchant_id).all()]
    if shop_id and shop_id in shop_ids:
        shop_ids = [shop_id]
    if not shop_ids:
        return {"reminders": [], "count": 0, "total_pending": 0, "has_more": False}

    total_pending = db.query(ExternalOrder).filter(
        ExternalOrder.shop_id.in_(shop_ids),
        ExternalOrder.status == "pending",
    ).count()

    pending = db.query(ExternalOrder).filter(
        ExternalOrder.shop_id.in_(shop_ids),
        ExternalOrder.status == "pending",
    ).offset(offset).limit(min(limit, 50)).all()

    # 预先提取标量，避免在工作线程中触发 SQLAlchemy 懒加载（session 非线程安全）
    items = [(o.id, o.buyer_openid or "", o.buyer_nick,
              (o.sku_details_json or [{}])[0].get("title", "商品")) for o in pending]

    def _gen_one(item):
        order_id, buyer_openid, buyer_nick, product_title = item
        prompt = f"""生成一条催付话术：
买家：{buyer_nick}
商品：{product_title}
要求：语气亲切、突出商品卖点、制造合理紧迫感、不超过150字。"""
        try:
            script = chat([{"role": "user", "content": prompt}])
        except Exception:
            script = f"亲爱的{buyer_nick}，您拍下的{product_title}还未完成支付哦，库存有限抓紧下单吧~"
        return {"order_id": order_id, "buyer_openid": buyer_openid,
                "buyer_nick": buyer_nick, "product_title": product_title,
                "script": script, "sent": True}

    # 并发生成（LLM 调用为网络 I/O，线程池可显著降低总耗时）；池大小受限以尊重 API 限流
    if items:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(8, len(items))) as ex:
            reminders = list(ex.map(_gen_one, items))  # map 保序，输出顺序与原串行一致
    else:
        reminders = []

    return {"reminders": reminders, "count": len(reminders), "total_pending": total_pending,
            "has_more": (offset + len(reminders)) < total_pending}


# ===== 知识库搜索 =====
def knowledge_search(merchant_id: int, query: str, top_k: int = 5) -> list[dict]:
    vec = embed_query(query)
    prods = query_products(merchant_id, vec, n_results=min(top_k, 10))
    results = []
    for meta, doc in zip(prods.get("metadatas", [[]])[0], prods.get("documents", [[]])[0]):
        results.append({"content": doc, "type": meta.get("type", "product"), "score": None})
    return results[:top_k]


async def _get_logistics_context(merchant_id: int, shop_id: int, db: Session) -> dict | None:
    """从 vMall 获取当前会话关联订单的物流状态 (tuozhan.md §2.6)。"""
    try:
        from app.models.platform_shop import PlatformShop
        shop = db.query(PlatformShop).filter(
            PlatformShop.id == shop_id, PlatformShop.platform_type == "vmall"
        ).first()
        if not shop or not shop.access_token:
            return None
        from app.core.platform_connector.vmall import V3Connector
        connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
        # 尝试获取最近订单的物流（简化：取最近一个 conversation 关联的 order）
        return await connector.get_logistics(None)  # 需要具体 order_id，先返回 None
    except Exception:
        return None


def _writeback_ai_reply(db: Session, shop_id: int, buyer_question: str, suggestions: list):
    """缺口8：将 AI 最佳建议回写到 conversations.ai_suggest_reply。"""
    try:
        from app.models.conversation import Conversation
        # 找到该店铺最近一条 buyer_question 匹配的待处理会话
        conv = db.query(Conversation).filter(
            Conversation.shop_id == shop_id,
            Conversation.handled_status.in_(["pending", "replied"]),
        ).order_by(Conversation.last_message_at.desc()).first()
        if conv and suggestions:
            conv.ai_suggest_reply = suggestions[0]["content"]
            db.commit()
    except Exception:
        pass  # 非关键路径，静默失败


# ===== 存量商品向量化回填（步骤6.2 + 缺口7增量模式）=====
def backfill_all(db: Session, merchant_id: int, full_rebuild: bool = False) -> dict:
    """
    扫描 embedding_status='pending' 的商品 → BGE(→DashScope) embed → ChromaDB
    同样扫描 conversations 提取客服回复 → embed Q+A → ChromaDB
    先清空旧 Collection 再重建，确保 shop_id 与当前 DB 一致。
    完成后返回统计数量。
    """
    shop_ids = [r[0] for r in db.query(PlatformShop.id).filter(
        PlatformShop.merchant_id == merchant_id).all()]
    if not shop_ids:
        return {"products": 0, "replies": 0, "total_vectors": 0}

    # 仅 full_rebuild 时清空旧 Collection
    if full_rebuild:
        from app.services.chroma_client import _get_client
        col_name = f"merchant_{merchant_id}"
        try:
            _get_client().delete_collection(col_name)
        except Exception:
            pass

    # 1. 商品向量化
    pending_prods = db.query(ExternalProduct).filter(
        ExternalProduct.shop_id.in_(shop_ids),
        ExternalProduct.embedding_status == "pending",
    ).all()

    p_ids, p_texts, p_metas = [], [], []
    for p in pending_prods:
        text = f"{p.title} {p.description[:500] or ''} {p.category_path or ''}"
        p_ids.append(f"product_{p.id}")
        p_texts.append(text)
        p_metas.append({
            "type": "product",
            "product_id": p.id,
            "shop_id": p.shop_id,
            "title": p.title,
            "price": float(p.price),
        })

    if p_texts:
        try:
            vecs = embed_texts(p_texts)
            add_products(merchant_id, p_ids, p_texts, p_metas, vecs)
            for p, eid in zip(pending_prods, p_ids):
                p.embedding_status = "done"
                p.embedding_id = eid
            db.commit()
        except Exception:
            db.rollback()
            traceback.print_exc()

    # 2. 话术向量化（从 conversations.messages_json 提取客服回复）
    convs = db.query(Conversation).filter(Conversation.shop_id.in_(shop_ids)).all()
    r_ids, r_texts, r_metas = [], [], []
    for c in convs:
        msgs = c.messages_json or []
        for i, msg in enumerate(msgs):
            if msg.get("role") == "service":
                buyer_q = msgs[i - 1].get("content", "") if i > 0 else ""
                text = f"Q: {buyer_q} A: {msg['content']}"
                r_ids.append(f"reply_conv{c.id}_{i}")
                r_texts.append(text)
                r_metas.append({
                    "type": "reply",
                    "product_id": c.product_id,
                    "buyer_question": buyer_q,
                    "reply": msg["content"],
                    "conversation_id": c.id,
                })

    if r_texts:
        try:
            vecs = embed_texts(r_texts)
            add_replies(merchant_id, r_ids, r_texts, r_metas, vecs)
        except Exception:
            traceback.print_exc()

    return {
        "products": len(p_texts),
        "replies": len(r_texts),
        "total_vectors": len(p_texts) + len(r_texts),
    }
