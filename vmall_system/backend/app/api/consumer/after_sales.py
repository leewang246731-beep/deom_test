"""消费者端 - 售后"""
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db, SessionLocal
from app.models.vm_after_sale import VmAfterSale
from app.models.vm_order import VmOrder
from app.services.webhook import dispatch, dispatch_sync

router = APIRouter(prefix="/consumer/after-sales", tags=["消费者-售后"])


def _get_buyer(auth: str) -> int:
    payload = decode_token(auth.split(" ", 1)[1])
    return int(payload["sub"])


@router.post("")
def apply(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    order = db.query(VmOrder).filter(VmOrder.id == body["order_id"],
                                      VmOrder.buyer_id == buyer_id).first()
    if not order: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    if order.status not in ("received", "completed", "shipped"):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "当前状态不可申请售后"})
    a = VmAfterSale(order_id=order.id, buyer_id=buyer_id,
                     type=body.get("type", "refund_only"), reason=body.get("reason", ""),
                     refund_amount=body.get("refund_amount", float(order.pay_amount)))
    db.add(a); order.after_sale_status = "refunding"; db.commit()
    dispatch_sync(db, "AFTER_SALE_CREATED",
             {"id": a.id, "order_id": order.id, "order_no": order.order_no, "_merchant_id": order.merchant_id, "type": a.type, "reason": a.reason,
              "refund_amount": float(a.refund_amount), "status": a.status})
    return ok({"id": a.id}, msg="售后申请已提交")


@router.get("/{sale_id}")
def detail(sale_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    a = db.query(VmAfterSale).filter(VmAfterSale.id == sale_id, VmAfterSale.buyer_id == buyer_id).first()
    if not a: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "售后单不存在"})
    return ok({"id": a.id, "order_id": a.order_id, "type": a.type, "reason": a.reason,
               "refund_amount": float(a.refund_amount), "status": a.status,
               "review_remark": a.review_remark, "refund_time": a.refund_time.isoformat() if a.refund_time else None})


@router.post("/{sale_id}/ship-return")
def ship_return(sale_id: int, body: dict, authorization: str = Header(None),
                db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    a = db.query(VmAfterSale).filter(VmAfterSale.id == sale_id, VmAfterSale.buyer_id == buyer_id).first()
    if not a: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "售后单不存在"})
    if a.status != "approved":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "需先等待平台审核通过"})
    a.return_logistics_company = body.get("company", "")
    a.return_tracking_no = body.get("tracking_no", "")
    a.buyer_ship_time = datetime.now(); a.status = "buyer_shipped"; db.commit()
    return ok({"id": a.id, "status": a.status}, msg="退货物流已填写")
