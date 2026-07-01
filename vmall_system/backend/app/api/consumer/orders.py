"""消费者端 - 订单"""
import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db, SessionLocal
from app.models.vm_order import VmOrder
from app.models.vm_buyer import VmBuyer
from app.models.vm_order_item import VmOrderItem
from app.models.vm_product import VmProduct
from app.models.vm_wallet import VmWallet, VmWalletTransaction
from app.services.order_state import gen_order_no, pre_deduct_stock, validate_transition
from app.services.webhook import dispatch

router = APIRouter(prefix="/consumer/orders", tags=["消费者-订单"])


def _get_buyer_id(auth: str) -> int:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "buyer":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "Token 无效"})
    return int(payload["sub"])


@router.post("")
def create_order(body: dict, authorization: str = Header(None),
                 db: Session = Depends(get_db)):
    buyer_id = _get_buyer_id(authorization)
    product_id = body.get("product_id")
    sku_code = body.get("sku_code")
    quantity = body.get("quantity", 1)
    product = db.query(VmProduct).get(product_id)
    if not product or product.status != 1:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "商品不存在"})
    skus = product.skus_json or []
    sku_info = next((s for s in skus if s.get("sku_code") == sku_code), None)
    if not sku_info:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "SKU 不存在"})
    if sku_info.get("stock", 0) < quantity:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "库存不足"})
    unit_price = float(sku_info["price"])
    total_amount = unit_price * quantity
    if not pre_deduct_stock(db, product_id, sku_code, quantity):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "库存扣减失败"})

    order = VmOrder(
        order_no=gen_order_no(), buyer_id=buyer_id,
        total_amount=total_amount, pay_amount=total_amount, status="pending_payment",
        receiver_name=body.get("receiver_name", ""),
        receiver_phone=body.get("receiver_phone", ""),
        receiver_address=body.get("receiver_address", ""),
    )
    db.add(order); db.flush()
    db.add(VmOrderItem(order_id=order.id, product_id=product_id, sku_code=sku_code,
                        sku_spec=sku_info.get("spec", ""), unit_price=unit_price, quantity=quantity))
    db.commit()
    return ok({"id": order.id, "order_no": order.order_no, "total_amount": float(total_amount)}, msg="下单成功")


@router.post("/{order_id}/pay")
async def pay_order(order_id: int, authorization: str = Header(None),
                    db: Session = Depends(get_db)):
    buyer_id = _get_buyer_id(authorization)
    order = db.query(VmOrder).filter(VmOrder.id == order_id, VmOrder.buyer_id == buyer_id).first()
    if not order:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    if not validate_transition(order.status, "paying"):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "当前状态不可支付"})
    # 支付前校验钱包余额（即时反馈余额不足）
    wallet = db.query(VmWallet).filter(VmWallet.buyer_id == buyer_id).first()
    if not wallet or wallet.balance < order.pay_amount:
        raise HTTPException(status_code=400, detail={"code": 40002, "msg": "钱包余额不足"})
    order.status = "paying"; db.commit()
    asyncio.create_task(_async_pay(order_id))
    return ok({"id": order.id, "order_no": order.order_no, "status": "paying"}, msg="支付处理中...")


async def _async_pay(order_id: int):
    await asyncio.sleep(2)
    db = SessionLocal()
    try:
        order = db.query(VmOrder).get(order_id)
        if not order or order.status != "paying": return
        # 钱包结算：扣余额 + 记流水 + 累计消费（余额不足则支付失败回滚）
        wallet = db.query(VmWallet).filter(VmWallet.buyer_id == order.buyer_id).first()
        if not wallet or wallet.balance < order.pay_amount:
            order.status = "pending_payment"; db.commit(); return
        before = wallet.balance
        wallet.balance = before - order.pay_amount
        wallet.total_spent = (wallet.total_spent or 0) + order.pay_amount
        db.add(VmWalletTransaction(
            wallet_id=wallet.id, buyer_id=order.buyer_id, type="payment",
            amount=order.pay_amount, balance_before=before, balance_after=wallet.balance,
            order_no=order.order_no, remark="订单支付"))
        order.status = "paid"; order.pay_time = datetime.now()
        items = db.query(VmOrderItem).filter(VmOrderItem.order_id == order.id).all()
        for item in items:
            p = db.query(VmProduct).get(item.product_id)
            if p: p.total_sales = (p.total_sales or 0) + item.quantity
        db.commit()
        await dispatch(SessionLocal, "ORDER_PAID", _order_json(order, items, db))
    finally:
        db.close()


def _order_json(order: VmOrder, items: list, db: Session) -> dict:
    sku_details = [{"title": "", "sku_code": i.sku_code, "sku_spec": i.sku_spec,
                     "unit_price": float(i.unit_price), "quantity": i.quantity, "product_id": i.product_id}
                    for i in items]
    buyer = db.query(VmBuyer).get(order.buyer_id)
    return {"id": order.id, "order_no": order.order_no, "buyer_id": order.buyer_id,
            "buyer_nick": buyer.nickname if buyer else "",
            "total_amount": float(order.total_amount), "pay_amount": float(order.pay_amount),
            "discount_amount": float(order.discount_amount or 0),
            "status": order.status, "after_sale_status": order.after_sale_status,
            "receiver_name": order.receiver_name, "receiver_phone": order.receiver_phone,
            "receiver_address": order.receiver_address,
            "pay_time": order.pay_time.isoformat() if order.pay_time else None,
            "ship_time": order.ship_time.isoformat() if order.ship_time else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "sku_details": sku_details}


@router.get("")
def my_orders(status: str = Query(None), page_no: int = Query(1, alias="page"),
              page_size: int = Query(20), authorization: str = Header(None),
              db: Session = Depends(get_db)):
    buyer_id = _get_buyer_id(authorization)
    q = db.query(VmOrder).filter(VmOrder.buyer_id == buyer_id)
    if status: q = q.filter(VmOrder.status == status)
    total = q.count()
    orders = q.order_by(VmOrder.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    result = []
    for o in orders:
        items = db.query(VmOrderItem).filter(VmOrderItem.order_id == o.id).all()
        skus = [{"sku_code": i.sku_code, "spec": i.sku_spec, "qty": i.quantity, "price": float(i.unit_price)} for i in items]
        result.append({"id": o.id, "order_no": o.order_no, "total_amount": float(o.total_amount),
                        "pay_amount": float(o.pay_amount), "status": o.status,
                        "after_sale_status": o.after_sale_status, "skus": skus,
                        "created_at": o.created_at.isoformat() if o.created_at else None})
    return page(result, total, page_no, page_size)


@router.get("/{order_id}")
def order_detail(order_id: int, authorization: str = Header(None),
                 db: Session = Depends(get_db)):
    buyer_id = _get_buyer_id(authorization)
    o = db.query(VmOrder).filter(VmOrder.id == order_id, VmOrder.buyer_id == buyer_id).first()
    if not o:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    items = db.query(VmOrderItem).filter(VmOrderItem.order_id == o.id).all()
    return ok(_order_json(o, items, db))
