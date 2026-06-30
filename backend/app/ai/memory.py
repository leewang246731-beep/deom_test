"""
Agent Memory System — 短期会话持久化 + 长期买家画像 + 执行记忆。

D.1: 会话落库 — 每次 Agent 调用后写入 kb_messages
D.2: 买家画像 — 从订单+会话中提取偏好 → ChromaDB buyer_memory
D.3: 执行记忆 — 记录工具调用效果 → 相似问题复用成功策略
"""
import json
import hashlib
from datetime import datetime
from typing import Optional

from app.database.session import SessionLocal
from app.models.external_order import ExternalOrder
from app.models.platform_shop import PlatformShop


# ===== D.1: 会话持久化 =====

def save_conversation_turn(
    merchant_id: int,
    user_id: int,
    question: str,
    reply: str,
    intent: str = "",
    confidence: float = 0.0,
    trace: list = None,
):
    """保存一轮 Agent 对话到 kb_messages。"""
    try:
        from app.kb.models import KbConversation, KbMessage

        db = SessionLocal()
        # 查找或创建会话
        conv = db.query(KbConversation).filter(
            KbConversation.merchant_id == merchant_id,
            KbConversation.user_id == user_id,
        ).order_by(KbConversation.updated_at.desc()).first()

        if not conv:
            conv = KbConversation(
                merchant_id=merchant_id,
                user_id=user_id,
                title=question[:50] if question else "新对话",
                retrieval_mode="auto",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(conv)
            db.flush()

        # 写入用户消息
        db.add(KbMessage(
            conversation_id=conv.id,
            role="user",
            content=question,
            created_at=datetime.now(),
        ))
        # 写入 Agent 回复
        db.add(KbMessage(
            conversation_id=conv.id,
            role="assistant",
            content=reply,
            references_json={"intent": intent, "confidence": confidence, "trace": trace or []},
            confidence=confidence,
            created_at=datetime.now(),
        ))
        conv.message_count = (conv.message_count or 0) + 2
        conv.updated_at = datetime.now()
        db.commit()
        db.close()
    except Exception:
        pass  # 会话持久化非关键路径


# ===== D.2: 买家画像 =====

def build_buyer_profile(merchant_id: int, buyer_id: int = 0, buyer_openid: str = "") -> dict:
    """从订单历史和会话中构建买家画像。"""
    db = SessionLocal()
    profile = {"buyer_id": buyer_id, "buyer_openid": buyer_openid, "preferences": [], "stats": {}}

    try:
        sids = [r[0] for r in db.query(PlatformShop.id).filter(
            PlatformShop.merchant_id == merchant_id).all()]

        if not sids:
            db.close()
            return profile

        # 订单统计
        orders = db.query(ExternalOrder).filter(
            ExternalOrder.shop_id.in_(sids),
        )
        if buyer_id > 0:
            orders = orders.filter(ExternalOrder.buyer_openid == str(buyer_id))
        elif buyer_openid:
            orders = orders.filter(ExternalOrder.buyer_openid == buyer_openid)

        orders = orders.order_by(ExternalOrder.created_at.desc()).limit(20).all()

        if orders:
            total_spent = sum(float(o.pay_amount) for o in orders)
            categories = set()
            for o in orders:
                skus = o.sku_details_json or []
                for s in skus if isinstance(skus, list) else []:
                    title = s.get("title", "") if isinstance(s, dict) else str(s)
                    if title:
                        categories.add(title[:20])

            profile["stats"] = {
                "total_orders": len(orders),
                "total_spent": round(total_spent, 2),
                "last_order_at": str(orders[0].created_at) if orders else None,
                "common_products": list(categories)[:5],
                "avg_order_value": round(total_spent / len(orders), 2) if orders else 0,
            }

            # 偏好标签
            for o in orders[:5]:
                skus = o.sku_details_json or []
                for s in skus if isinstance(skus, list) else []:
                    if isinstance(s, dict) and s.get("title"):
                        profile["preferences"].append(s["title"][:30])

            profile["preferences"] = list(set(profile["preferences"]))[:10]

    finally:
        db.close()

    return profile


def store_buyer_profile(merchant_id: int, buyer_id: int, profile: dict):
    """将买家画像存入 ChromaDB buyer_memory collection。"""
    try:
        from app.services.chroma_client import get_collection
        from app.services.embedding import embed_texts

        col = get_collection(merchant_id, collection_name="buyer_memory")
        profile_text = json.dumps(profile, ensure_ascii=False, default=str)
        vec = embed_texts([profile_text])[0]

        doc_id = f"buyer_{merchant_id}_{buyer_id}"
        # 幂等：先删旧的再插入
        try:
            col.delete(ids=[doc_id])
        except Exception:
            pass
        col.add(
            ids=[doc_id],
            embeddings=[vec],
            metadatas=[{
                "buyer_id": buyer_id,
                "merchant_id": merchant_id,
                "total_orders": profile.get("stats", {}).get("total_orders", 0),
                "total_spent": profile.get("stats", {}).get("total_spent", 0),
                "updated_at": datetime.now().isoformat(),
            }],
            documents=[profile_text],
        )
    except Exception:
        pass  # ChromaDB 操作非关键路径


def query_buyer_profile(merchant_id: int, buyer_id: int = 0, buyer_openid: str = "") -> str:
    """查询买家画像。先查 ChromaDB，若无则实时构建。"""
    try:
        from app.services.chroma_client import get_collection
        col = get_collection(merchant_id, collection_name="buyer_memory")
        doc_id = f"buyer_{merchant_id}_{buyer_id}"
        result = col.get(ids=[doc_id])
        if result and result.get("documents"):
            return str(result["documents"][0])
    except Exception:
        pass

    # 实时构建
    profile = build_buyer_profile(merchant_id, buyer_id, buyer_openid)
    if profile.get("stats", {}).get("total_orders", 0) > 0:
        store_buyer_profile(merchant_id, buyer_id, profile)

    if not profile.get("stats", {}).get("total_orders"):
        return f"暂无买家{buyer_id}的购买记录"

    s = profile["stats"]
    prefs = ", ".join(profile["preferences"][:5]) or "暂无"
    return (
        f"买家{buyer_id}画像: "
        f"累计{s['total_orders']}笔订单/¥{s['total_spent']:.0f}, "
        f"客单价¥{s['avg_order_value']:.0f}, "
        f"偏好:{prefs}, "
        f"最近购买:{s.get('last_order_at', 'N/A')[:10]}"
    )


# ===== D.3: Agent 执行记忆 =====

def record_execution(
    merchant_id: int,
    question: str,
    intent: str,
    intents: list,
    tools_used: list,
    success: bool,
    confidence: float,
    latency_ms: int = 0,
):
    """记录一次 Agent 执行到 ChromaDB agent_memory。"""
    try:
        from app.services.chroma_client import get_collection
        from app.services.embedding import embed_query

        col = get_collection(merchant_id, collection_name="agent_memory")
        vec = embed_query(question)

        doc_id = hashlib.md5(
            f"{merchant_id}_{question}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:32]

        col.add(
            ids=[doc_id],
            embeddings=[vec],
            metadatas=[{
                "intent": intent,
                "intents": json.dumps(intents, ensure_ascii=False),
                "tools_used": json.dumps(tools_used, ensure_ascii=False),
                "success": success,
                "confidence": confidence,
                "latency_ms": latency_ms,
                "created_at": datetime.now().isoformat(),
            }],
            documents=[question],
        )
    except Exception:
        pass


def query_similar_executions(merchant_id: int, question: str, top_k: int = 3) -> list[dict]:
    """查询相似历史执行，复用成功策略。"""
    try:
        from app.services.chroma_client import get_collection
        from app.services.embedding import embed_query

        col = get_collection(merchant_id, collection_name="agent_memory")
        vec = embed_query(question)
        result = col.query(query_embeddings=[vec], n_results=top_k)

        memories = []
        metas = result.get("metadatas", [[]])[0]
        docs = result.get("documents", [[]])[0]

        for meta, doc in zip(metas, docs):
            if meta.get("success"):
                memories.append({
                    "question": doc,
                    "intent": meta.get("intent", ""),
                    "tools_used": json.loads(meta.get("tools_used", "[]")),
                    "confidence": meta.get("confidence", 0),
                })

        return memories
    except Exception:
        return []


def recall_best_strategy(merchant_id: int, question: str) -> Optional[str]:
    """回忆最佳策略：找到最相似的成功执行，返回其工具链建议。"""
    memories = query_similar_executions(merchant_id, question, top_k=3)
    if not memories:
        return None

    # 提取成功使用的工具名
    tools_seen = set()
    for m in memories:
        for t in m.get("tools_used", []):
            name = t.get("tool", "") if isinstance(t, dict) else str(t)
            if name:
                tools_seen.add(name)

    if tools_seen:
        return f"历史相似问题使用了这些工具: {', '.join(tools_seen)}。可参考优先调用。"
    return None
