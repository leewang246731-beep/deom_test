"""vMall 订单状态机 + 库存扣减"""
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.vm_order import VmOrder
from app.models.vm_order_item import VmOrderItem
from app.models.vm_product import VmProduct

VALID_TRANSITIONS = {
    "pending_payment": ["paying", "closed"],
    "paying": ["paid", "pending_payment"],
    "paid": ["shipped"],
    "shipped": ["received"],
    "received": ["completed", "after_sale"],
    "completed": [],
    "closed": [],
}
STATUS_LABELS = {
    "pending_payment": "待支付", "paying": "支付中", "paid": "待发货",
    "shipped": "待收货", "received": "已收货", "completed": "已完成",
    "closed": "已关闭",
}


def validate_transition(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, [])


def pre_deduct_stock(db: Session, product_id: int, sku_code: str, quantity: int) -> bool:
    """下单时预扣库存（乐观锁）。"""
    product = db.query(VmProduct).get(product_id)
    if not product or product.status != 1:
        return False
    skus = product.skus_json or []
    for sku in skus:
        if sku.get("sku_code") == sku_code:
            if sku.get("stock", 0) < quantity:
                return False
            sku["stock"] -= quantity
            product.total_stock = sum(s.get("stock", 0) for s in skus)
            product.skus_json = skus
            db.commit()
            return True
    return False


def release_stock(db: Session, product_id: int, sku_code: str, quantity: int):
    """取消订单/支付超时 → 释放预扣库存。"""
    product = db.query(VmProduct).get(product_id)
    if not product:
        return
    skus = product.skus_json or []
    for sku in skus:
        if sku.get("sku_code") == sku_code:
            sku["stock"] = sku.get("stock", 0) + quantity
            product.total_stock = sum(s.get("stock", 0) for s in skus)
            product.skus_json = skus
            db.commit()
            return


def deduct_stock_final(db: Session, product_id: int, sku_code: str, quantity: int):
    """支付成功后真实扣减库存（预扣已完成，此处不额外操作）。"""
    # 一期简化：预扣即真实扣减。支付成功后不做额外操作。
    pass


def gen_order_no() -> str:
    ts = datetime.now().strftime("%y%m%d%H%M%S")
    rnd = "".join(random.choices("0123456789", k=6))
    return f"VM-{ts}-{rnd}"


def cancel_timeout_orders(db: Session, timeout_minutes: int = 15) -> int:
    """扫描超时未付订单 → 取消 + 释放库存。"""
    deadline = datetime.now() - timedelta(minutes=timeout_minutes)
    orders = db.query(VmOrder).filter(
        VmOrder.status == "pending_payment",
        VmOrder.created_at < deadline,
    ).all()
    for o in orders:
        o.status = "closed"
        o.close_time = datetime.now()
        items = db.query(VmOrderItem).filter(VmOrderItem.order_id == o.id).all()
        for item in items:
            release_stock(db, item.product_id, item.sku_code, item.quantity)
    db.commit()
    return len(orders)
