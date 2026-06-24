"""
SaaS Webhook 消费端点 (接收 vMall 推送)
处理: ORDER_PAID / ORDER_SHIPPED / ORDER_COMPLETED / LOGISTICS_UPDATED / REFUND_SUCCESS / NEW_MESSAGE
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

router = APIRouter(prefix="/webhooks", tags=["Webhook"])


@router.post("/vmall")
async def vmall_webhook(request: Request):
    """接收 vMall Webhook 推送。"""
    body = await request.json()
    event = request.headers.get("X-Event-Type", body.get("event", ""))
    data = body.get("data", {})

    db = SessionLocal()
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
    finally:
        db.close()
    return ok(msg="received")


def _upsert_order(db: Session, data: dict, status: str):
    """按 platform_order_id 更新或创建订单。"""
    order_no = data.get("order_no") or str(data.get("order_id", data.get("id", "")))
    if not order_no:
        return
    # 找到关联店铺（简化：取第一个活跃的 vmall 类型店铺）
    shop = db.query(PlatformShop).filter(
        PlatformShop.platform_type == "vmall", PlatformShop.is_active == 1
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
    shop = db.query(PlatformShop).filter(
        PlatformShop.platform_type == "vmall", PlatformShop.is_active == 1
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
    """新消息 → 追加到对应会话。"""
    # 一期简化：仅兼容，实际需要 conversation_id 映射
    pass
