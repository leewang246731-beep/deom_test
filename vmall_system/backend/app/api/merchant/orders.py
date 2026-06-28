"""商户 - 订单管理"""
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db, SessionLocal
from app.models.vm_order import VmOrder
from app.models.vm_order_item import VmOrderItem
from app.models.vm_logistics import VmLogistics
from app.services.webhook import dispatch, dispatch_sync

router = APIRouter(prefix="/merchant/orders", tags=["商户-订单"])


def _get_merchant(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "merchant":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需商户登录"})
    return payload


@router.get("")
def list_orders(status: str = Query(None), page_no: int = Query(1, alias="page"),
                page_size: int = Query(20), authorization: str = Header(None),
                db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    mid = int(merchant["sub"])
    q = db.query(VmOrder).filter(VmOrder.merchant_id == mid)
    if status: q = q.filter(VmOrder.status == status)
    total = q.count()
    orders = q.order_by(VmOrder.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": o.id, "order_no": o.order_no, "status": o.status,
                  "total_amount": float(o.total_amount), "receiver_name": o.receiver_name,
                  "buyer_name": o.receiver_name,
                  "created_at": o.created_at.isoformat() if o.created_at else None}
                 for o in orders], total, page_no, page_size)


@router.get("/{order_id}")
def order_detail(order_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    o = db.query(VmOrder).filter(VmOrder.id == order_id, VmOrder.merchant_id == int(merchant["sub"])).first()
    if not o: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    items = db.query(VmOrderItem).filter(VmOrderItem.order_id == o.id).all()
    return ok({"id": o.id, "order_no": o.order_no, "status": o.status,
               "total_amount": float(o.total_amount), "pay_amount": float(o.pay_amount),
               "buyer_name": o.receiver_name, "receiver_name": o.receiver_name,
               "receiver_phone": o.receiver_phone, "receiver_address": o.receiver_address,
               "pay_time": o.pay_time.isoformat() if o.pay_time else None,
               "ship_time": o.ship_time.isoformat() if o.ship_time else None,
               "created_at": o.created_at.isoformat() if o.created_at else None,
               "items": [{"id": i.id, "product_name": i.sku_spec, "unit_price": float(i.unit_price),
                           "quantity": i.quantity} for i in items]})


@router.post("/{order_id}/ship")
def ship_order(order_id: int, body: dict, authorization: str = Header(None),
               db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    o = db.query(VmOrder).filter(VmOrder.id == order_id, VmOrder.merchant_id == int(merchant["sub"])).first()
    if not o: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    if o.status != "paid":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "只能对待发货订单操作"})
    o.status = "shipped"; o.ship_time = datetime.now()
    tracking_no = body.get("tracking_no", "")
    log = VmLogistics(order_id=order_id, company="商户自配送", tracking_no=tracking_no,
                       status="picked_up",
                       events_json=[{"time": datetime.now().isoformat(), "status": "已揽收", "location": "商户"}])
    db.add(log); db.commit()
    dispatch_sync(db, "ORDER_SHIPPED", {"merchant_id": o.merchant_id, "_merchant_id": o.merchant_id, "order_id": o.id, "order_no": o.order_no, "status": "shipped",
                                              "logistics": {"company": "商户自配送", "tracking_no": tracking_no}})
    return ok({"id": o.id, "status": "shipped"}, msg="发货成功")
