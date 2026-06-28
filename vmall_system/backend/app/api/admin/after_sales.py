"""运营后台 - 售后审核"""
from datetime import datetime

from fastapi import Header,APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db, SessionLocal
from app.models.vm_after_sale import VmAfterSale
from app.models.vm_order import VmOrder
from app.models.vm_wallet import VmWallet, VmWalletTransaction
from app.services.webhook import dispatch, dispatch_sync

router = APIRouter(prefix="/admin/after-sales", tags=["运营-售后"])


def _get_admin(auth: str) -> dict:
    payload = decode_token(auth.split(" ", 1)[1])
    return payload


@router.get("")
def list_sales(status: str = Query(None), page_no: int = Query(1, alias="page"),
               page_size: int = Query(20), authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    q = db.query(VmAfterSale)
    if status: q = q.filter(VmAfterSale.status == status)
    total = q.count()
    items = q.order_by(VmAfterSale.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": a.id, "order_id": a.order_id, "type": a.type, "reason": a.reason,
                   "refund_amount": float(a.refund_amount), "status": a.status,
                   "return_logistics_company": a.return_logistics_company,
                   "return_tracking_no": a.return_tracking_no,
                   "created_at": a.created_at.isoformat() if a.created_at else None}
                  for a in items], total, page_no, page_size)


@router.post("/{sale_id}/review")
def review(sale_id: int, body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    payload = _get_admin(authorization)
    a = db.query(VmAfterSale).get(sale_id)
    if not a:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "售后单不存在"})
    action = body.get("action")
    if action == "approve":
        a.status = "approved"
        a.reviewed_by = int(payload["sub"])
        a.reviewed_at = datetime.now()
        a.review_remark = body.get("remark", "审核通过")
    elif action == "reject":
        a.status = "rejected"
        a.reviewed_by = int(payload["sub"])
        a.reviewed_at = datetime.now()
        a.review_remark = body.get("remark", "审核拒绝")
        order = db.query(VmOrder).get(a.order_id)
        if order:
            order.after_sale_status = None
    else:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "action 必须为 approve 或 reject"})
    db.commit()
    if a.status == "approved":
        dispatch_sync(db, "AFTER_SALE_APPROVED", {"id": a.id, "order_id": a.order_id, "status": a.status})
    return ok({"id": a.id, "status": a.status}, msg="已审核")


@router.post("/{sale_id}/confirm-receive")
def confirm_receive(sale_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    a = db.query(VmAfterSale).get(sale_id)
    if not a:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "售后单不存在"})
    if a.status != "buyer_shipped":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "买家尚未寄回"})
    a.status = "refunded"
    a.platform_receive_time = datetime.now()
    a.refund_time = datetime.now()
    order = db.query(VmOrder).get(a.order_id)
    if order:
        order.after_sale_status = "refunded"
    # 退款回补买家钱包（与支付扣款对称：加余额 + 流水 + 冲减累计消费）
    if order:
        wallet = db.query(VmWallet).filter(VmWallet.buyer_id == order.buyer_id).first()
        if wallet:
            before = wallet.balance
            wallet.balance = before + a.refund_amount
            wallet.total_spent = max((wallet.total_spent or 0) - a.refund_amount, 0)
            db.add(VmWalletTransaction(
                wallet_id=wallet.id, buyer_id=order.buyer_id, type="refund",
                amount=a.refund_amount, balance_before=before, balance_after=wallet.balance,
                order_no=order.order_no, remark="售后退款"))
    db.commit()
    dispatch_sync(db, "REFUND_SUCCESS", {"_merchant_id": (order.merchant_id if order else None), "id": a.id, "order_id": a.order_id, "order_no": (order.order_no if order else None),
                                               "refund_amount": float(a.refund_amount)})
    return ok({"id": a.id, "status": "refunded"}, msg="退款完成")
