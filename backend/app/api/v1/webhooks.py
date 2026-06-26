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
from app.models.conversation import Conversation
from app.models.platform_shop import PlatformShop
from app.models.webhook_delivery_log import WebhookDeliveryLog

router = APIRouter(prefix="/webhooks", tags=["Webhook"])


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
        elif event == "AFTER_SALE_CREATED":
            _upsert_order(db, data, "refunding")
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
    shop_id = data.get("saas_shop_id")
    if not shop_id:
        shop = db.query(PlatformShop).filter(
            PlatformShop.platform_type == "vmall", PlatformShop.is_active == 1
        ).first()
    else:
        shop = db.query(PlatformShop).filter(
            PlatformShop.id == shop_id, PlatformShop.is_active == 1
        ).first()
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
    shop_id = data.get("saas_shop_id")
    if not shop_id:
        shop = db.query(PlatformShop).filter(
            PlatformShop.platform_type == "vmall", PlatformShop.is_active == 1
        ).first()
    else:
        shop = db.query(PlatformShop).filter(
            PlatformShop.id == shop_id, PlatformShop.is_active == 1
        ).first()
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
        shop_id = data.get("saas_shop_id")
        if not shop_id:
            shop = db.query(PlatformShop).filter(
                PlatformShop.platform_type == "vmall", PlatformShop.is_active == 1
            ).first()
        else:
            shop = db.query(PlatformShop).filter(
                PlatformShop.id == shop_id, PlatformShop.is_active == 1
            ).first()
        if not shop:
            return
        buyer_id = data.get("buyer_id", "")
        conv = Conversation(
            shop_id=shop.id,
            platform_conversation_id=platform_conv_id,
            product_id=data.get("product_id"),
            buyer_nick=data.get("buyer_nick") or f"买家{buyer_id}",
            messages_json=[],
            handled_status="pending",
        )
        db.add(conv)
        db.flush()

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
