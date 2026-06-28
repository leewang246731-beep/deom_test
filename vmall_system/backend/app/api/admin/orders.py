"""运营后台 - 订单处理"""
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db, SessionLocal
from app.models.vm_logistics import VmLogistics
from app.models.vm_order import VmOrder
from app.models.vm_order_item import VmOrderItem
from app.services.webhook import dispatch, dispatch_sync

router = APIRouter(prefix="/admin/orders", tags=["运营-订单"])


def _get_admin(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "admin":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需运营后台登录"})
    return payload


@router.get("")
def list_orders(status: str = Query(None), page_no: int = Query(1, alias="page"),
                page_size: int = Query(20), authorization: str = Header(None),
                db: Session = Depends(get_db)):
    _get_admin(authorization)
    q = db.query(VmOrder)
    if status: q = q.filter(VmOrder.status == status)
    total = q.count()
    orders = q.order_by(VmOrder.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    result = [{"id": o.id, "order_no": o.order_no, "status": o.status,
                "after_sale_status": o.after_sale_status, "total_amount": float(o.total_amount),
                "pay_amount": float(o.pay_amount), "receiver_name": o.receiver_name,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "sku_count": db.query(VmOrderItem).filter(VmOrderItem.order_id == o.id).count()}
              for o in orders]
    return page(result, total, page_no, page_size)


@router.get("/{order_id}")
def order_detail(order_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    o = db.query(VmOrder).get(order_id)
    if not o: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    items = db.query(VmOrderItem).filter(VmOrderItem.order_id == o.id).all()
    log = db.query(VmLogistics).filter(VmLogistics.order_id == o.id).first()
    return ok({"id": o.id, "order_no": o.order_no, "status": o.status,
               "after_sale_status": o.after_sale_status,
               "total_amount": float(o.total_amount), "pay_amount": float(o.pay_amount),
               "receiver_name": o.receiver_name, "receiver_phone": o.receiver_phone,
               "receiver_address": o.receiver_address,
               "pay_time": o.pay_time.isoformat() if o.pay_time else None,
               "ship_time": o.ship_time.isoformat() if o.ship_time else None,
               "created_at": o.created_at.isoformat() if o.created_at else None,
               "items": [{"id": i.id, "sku_spec": i.sku_spec, "unit_price": float(i.unit_price),
                           "quantity": i.quantity} for i in items],
               "logistics": {"company": log.company, "tracking_no": log.tracking_no,
                              "status": log.status} if log else None})


@router.post("/{order_id}/ship")
def ship_order(order_id: int, body: dict, authorization: str = Header(None),
               db: Session = Depends(get_db)):
    _get_admin(authorization)
    o = db.query(VmOrder).get(order_id)
    if not o: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    if o.status != "paid":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "只能对待发货订单操作"})
    o.status = "shipped"; o.ship_time = datetime.now()
    log = VmLogistics(order_id=order_id, company=body["company"],
                       tracking_no=body["tracking_no"], status="picked_up",
                       events_json=[{"time": datetime.now().isoformat(), "status": "已揽收", "location": "发货地"}])
    db.add(log); db.commit()
    dispatch_sync(db, "ORDER_SHIPPED", {"merchant_id": o.merchant_id, "_merchant_id": o.merchant_id, "order_id": o.id, "order_no": o.order_no,
                                              "status": "shipped",
                                              "logistics": {"company": body["company"],
                                                             "tracking_no": body["tracking_no"]}})
    return ok({"id": o.id, "status": "shipped"}, msg="发货成功")
