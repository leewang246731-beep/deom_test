"""
SaaS Webhook 消费端点 (接收 vMall 推送)
处理: ORDER_PAID / ORDER_SHIPPED / ORDER_COMPLETED / LOGISTICS_UPDATED / REFUND_SUCCESS / NEW_MESSAGE
每次接收均记录到 webhook_delivery_logs 表。
"""
import json
from datetime import datetime

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from app.core.response import ok
from app.database.session import SessionLocal
from app.models.external_order import ExternalOrder
from app.models.external_product import ExternalProduct
from app.models.conversation import Conversation
from app.models.platform_shop import PlatformShop
from app.models.webhook_delivery_log import WebhookDeliveryLog

router = APIRouter(prefix="/webhooks", tags=["Webhook"])


def _resolve_shop(db: Session, data: dict):
    """解析事件目标店铺：saas_shop_id 优先 → shop_name 精确匹配 → 回退首个 active vmall 店铺。"""
    sid = data.get("saas_shop_id")
    if sid:
        s = db.query(PlatformShop).filter(
            PlatformShop.id == sid, PlatformShop.is_active == 1).first()
        if s:
            return s
    name = data.get("shop_name")
    if name:
        s = db.query(PlatformShop).filter(
            PlatformShop.platform_type == "vmall", PlatformShop.is_active == 1,
            PlatformShop.shop_name == name).first()
        if s:
            return s
    return db.query(PlatformShop).filter(
        PlatformShop.platform_type == "vmall", PlatformShop.is_active == 1).first()


@router.post("/vmall")
async def vmall_webhook(request: Request):
    """接收 vMall Webhook 推送。"""
    body = await request.json()
    event = request.headers.get("X-Event-Type", body.get("event", ""))
    data = body.get("data", {})

    db = SessionLocal()
    status = "success"
    error_msg = None
    try:
        if event == "ORDER_PAID":
            _upsert_order(db, data, "paid")
        elif event == "ORDER_SHIPPED":
            _upsert_order(db, data, "shipped")
        elif event == "ORDER_COMPLETED":
            _upsert_order(db, data, "completed")
        elif event == "LOGISTICS_UPDATED":
            _handle_logistics(db, data)
        elif event == "REFUND_SUCCESS":
            _upsert_order(db, data, "refunded")
        elif event == "NEW_MESSAGE":
            _handle_message(db, data)
            await _maybe_auto_reply(db, data)
            # 广播给对应商户的客服工作台 WebSocket
            shop = _resolve_shop(db, data)
            if shop:
                from app.api.v1.conversations import broadcast_service_event
                await broadcast_service_event(shop.merchant_id, "new_message", {
                    "conversation_id": data.get("conversation_id"),
                    "buyer_nick": data.get("buyer_nick", ""),
                })
        elif event == "AFTER_SALE_CREATED":
            _upsert_order(db, data, "refunding")
            # 回写 vmall 售后单 id（refund_order 联动需要）
            order_no = data.get("order_no") or str(data.get("order_id", data.get("id", "")))
            sale_id = data.get("id")  # vmall VmAfterSale.id
            if order_no and sale_id:
                shop = _resolve_shop(db, data)
                if shop:
                    exist = db.query(ExternalOrder).filter(
                        ExternalOrder.shop_id == shop.id,
                        ExternalOrder.platform_order_id == order_no,
                    ).first()
                    if exist:
                        exist.after_sale_id = sale_id
                        exist.after_sale_status = "created"
                        db.commit()
        else:
            status = "ignored"
            error_msg = f"未知事件类型: {event}"
    except Exception as e:
        status = "failed"
        error_msg = str(e)
    finally:
        # 记录 webhook 投递日志
        try:
            db.add(WebhookDeliveryLog(
                event_type=event or "unknown",
                payload_json=json.dumps(body, ensure_ascii=False, default=str)[:8000],
                status=status,
                response_code=200 if status == "success" else 400,
                response_body=error_msg[:500] if error_msg else None,
                created_at=datetime.now(),
            ))
            db.commit()
        except Exception:
            pass
        db.close()
    return ok(msg="received")


def _upsert_order(db: Session, data: dict, status: str):
    """按 platform_order_id 更新或创建订单。"""
    order_no = data.get("order_no") or str(data.get("order_id", data.get("id", "")))
    if not order_no:
        return
    shop = _resolve_shop(db, data)
    if not shop:
        return

    exist = db.query(ExternalOrder).filter(
        ExternalOrder.shop_id == shop.id,
        ExternalOrder.platform_order_id == order_no,
    ).first()
    if exist:
        exist.status = status
        if status == "shipped":
            exist.ship_time = datetime.now()
    else:
        db.add(ExternalOrder(
            shop_id=shop.id, platform_order_id=order_no,
            buyer_openid=data.get("buyer_id", ""),
            buyer_nick=data.get("buyer_nick", ""),
            total_amount=data.get("total_amount", 0),
            pay_amount=data.get("pay_amount", 0),
            status=status,
            sku_details_json=data.get("sku_details", []),
            receiver_name=data.get("receiver_name", ""),
            receiver_phone=data.get("receiver_phone", ""),
            receiver_address=data.get("receiver_address", ""),
            pay_time=data.get("pay_time"),
            ship_time=data.get("ship_time"),
            created_at=data.get("created_at"),
        ))
    db.commit()


def _handle_logistics(db: Session, data: dict):
    """物流状态变更 → 更新订单状态 + 记录物流信息到 sku_details_json 扩展字段。"""
    order_no = data.get("order_no", "")
    if not order_no:
        return
    shop = _resolve_shop(db, data)
    if not shop:
        return
    exist = db.query(ExternalOrder).filter(
        ExternalOrder.shop_id == shop.id, ExternalOrder.platform_order_id == order_no,
    ).first()
    if exist:
        # 把物流信息追加到 sku_details_json 的 _logistics 扩展字段
        sku = exist.sku_details_json or []
        # 更新或追加 _logistics 元数据
        if isinstance(sku, list):
            pass  # 保持原有结构，不污染 sku_details
        exist.status = "shipped"


def _handle_message(db: Session, data: dict):
    """vMall 新消息 → SaaS Conversation 同步（双向桥接：消费端）"""
    conv_id = data.get("conversation_id")
    if not conv_id:
        return
    platform_conv_id = f"vmall_{conv_id}"

    conv = db.query(Conversation).filter(
        Conversation.platform_conversation_id == platform_conv_id
    ).first()

    if not conv:
        shop = _resolve_shop(db, data)
        if not shop:
            return
        buyer_id = data.get("buyer_id", "")
        # vMall product_id → SaaS ExternalProduct.id 映射（通过 platform_product_id）
        ext_pid = None
        vm_pid = data.get("product_id")
        if vm_pid:
            ep = db.query(ExternalProduct).filter(
                ExternalProduct.platform_product_id == f"vm_{vm_pid}",
                ExternalProduct.shop_id == shop.id,
            ).first()
            if ep:
                ext_pid = ep.id
        conv = Conversation(
            shop_id=shop.id,
            platform_conversation_id=platform_conv_id,
            product_id=ext_pid,
            buyer_nick=data.get("buyer_nick") or f"买家{buyer_id}",
            messages_json=[],
            handled_status="pending",
        )
        db.add(conv)
        db.flush()

    # 已有会话但 product_id 为空 → 补绑
    if conv.product_id is None:
        vm_pid = data.get("product_id")
        if vm_pid:
            # 1) 精确匹配: shop + platform_product_id
            ep = db.query(ExternalProduct).filter(
                ExternalProduct.platform_product_id == f"vm_{vm_pid}",
                ExternalProduct.shop_id == conv.shop_id,
            ).first()
            # 2) 放宽: 同 merchant 任意 shop
            if not ep:
                from app.models.platform_shop import PlatformShop
                shop_ids = [r[0] for r in db.query(PlatformShop.id).filter(
                    PlatformShop.merchant_id == db.query(PlatformShop).get(conv.shop_id).merchant_id
                ).all()] if conv.shop_id else []
                ep = db.query(ExternalProduct).filter(
                    ExternalProduct.platform_product_id == f"vm_{vm_pid}",
                    ExternalProduct.shop_id.in_(shop_ids),
                ).first() if shop_ids else None
            if ep:
                conv.product_id = ep.id

    msgs = list(conv.messages_json or [])
    content = data.get("content", {})
    if isinstance(content, dict):
        text = content.get("text", str(content))
    else:
        text = str(content)
    msgs.append({
        "role": data.get("sender_role", "buyer"),
        "content": text,
        "time": data.get("created_at") or datetime.now().isoformat(),
    })
    conv.messages_json = msgs
    conv.last_message_at = datetime.now()
    if data.get("sender_role") == "buyer":
        conv.handled_status = "pending"
    db.commit()


async def _maybe_auto_reply(db: Session, data: dict):
    """auto 模式下，买家消息进来即由 AI 智能体自动生成回复并回流消费端（无需人工）。"""
    if data.get("sender_role", "buyer") != "buyer":
        return
    conv_id = data.get("conversation_id")
    if not conv_id:
        return
    conv = db.query(Conversation).filter(
        Conversation.platform_conversation_id == f"vmall_{conv_id}").first()
    if not conv:
        return
    shop = db.query(PlatformShop).filter(PlatformShop.id == conv.shop_id).first()
    if not shop:
        return
    from app.services.mode_engine import get_effective_mode
    if get_effective_mode(db, shop.merchant_id, conv) != "auto":
        return  # 仅 auto 模式自动回复；manual/copilot 留给人工
    content = data.get("content", {})
    question = content.get("text", "") if isinstance(content, dict) else str(content)
    if not question:
        return
    # 兜底：商品上下文缺失 + 纯指代词（短问题）→ 反问澄清，不硬猜
    # 仅拦截「这个多少钱」这类完全依赖商品上下文的短问题；正常关键词留给 AI 处理
    PURE_DEMO = ["这个", "这款", "那个", "那款", "它"]
    if conv.product_id is None and len(question) < 25 and any(w in question for w in PURE_DEMO):
        reply = "亲，您咨询的是哪款商品呢？方便发下商品链接或告诉我具体的商品名称吗～"
        msgs = list(conv.messages_json or [])
        msgs.append({"role": "service", "content": reply, "time": datetime.now().isoformat(), "auto": True})
        conv.messages_json = msgs
        conv.handled_status = "replied"
        conv.last_message_at = datetime.now()
        conv.auto_reply_count = (conv.auto_reply_count or 0) + 1
        db.commit()
        # 仍然回流到 vMall
        target = f"{(shop.shop_url or 'http://vmall-backend:8020')}/api/v1/consumer/conversations/{conv_id}/messages/internal"
        try:
            import urllib.request
            req = urllib.request.Request(
                target,
                data=json.dumps({"api_key": "vmall-internal-demo-key", "content": reply, "msg_type": "text"}).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass
        return
    try:
        from app.services.ai_suggest import get_ai_suggestions
        # 传递最近 10 条历史消息，实现多轮对话记忆
        chat_history = (conv.messages_json or [])[-10:]
        result = await get_ai_suggestions(shop.merchant_id, shop.id, question, chat_history, conv.product_id, db)
        sugg = result.get("suggestions", []) if isinstance(result, dict) else []
        reply = sugg[0]["content"] if sugg else "您好，您的消息已收到，我们会尽快为您处理。"
    except Exception:
        reply = "您好，您的消息已收到，我们会尽快为您处理。"
    msgs = list(conv.messages_json or [])
    msgs.append({"role": "service", "content": reply, "time": datetime.now().isoformat(), "auto": True})
    conv.messages_json = msgs
    conv.handled_status = "replied"
    conv.last_message_at = datetime.now()
    try:
        conv.auto_reply_count = (conv.auto_reply_count or 0) + 1
    except Exception:
        pass
    db.commit()
    try:
        from app.services.mode_engine import log_auto_reply
        log_auto_reply(db, conv.id, shop.merchant_id, "auto", question, reply, 0.8, "auto_sent")
    except Exception:
        pass
    # 回流到 vMall 消费端
    target = f"{(shop.shop_url or 'http://vmall-backend:8020')}/api/v1/consumer/conversations/{conv_id}/messages/internal"
    try:
        import urllib.request
        req = urllib.request.Request(
            target,
            data=json.dumps({"api_key": "vmall-internal-demo-key", "content": reply, "msg_type": "text"}).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass
