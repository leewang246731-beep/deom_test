"""运营后台 - 商户提现审核"""
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_merchant import VmMerchant
from app.models.vm_merchant_wallet import (
    VmMerchantWallet, VmMerchantWalletTransaction, VmWithdrawalRequest,
)

router = APIRouter(prefix="/admin/withdrawals", tags=["运营-提现审核"])


def _get_admin(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "admin":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需运营后台登录"})
    return payload


@router.get("")
def list_withdrawals(status: str = Query(None), page_no: int = Query(1, alias="page"),
                     page_size: int = Query(20), authorization: str = Header(None),
                     db: Session = Depends(get_db)):
    """平台查看所有商户提现申请。"""
    _get_admin(authorization)
    q = db.query(VmWithdrawalRequest)
    if status:
        q = q.filter(VmWithdrawalRequest.status == status)
    total = q.count()
    items = q.order_by(VmWithdrawalRequest.created_at.desc()).offset(
        (page_no - 1) * page_size).limit(page_size).all()
    result = []
    for r in items:
        m = db.query(VmMerchant).get(r.merchant_id)
        result.append({"id": r.id, "merchant_id": r.merchant_id,
                        "shop_name": m.shop_name if m else "", "amount": float(r.amount),
                        "account_type": r.account_type, "account_info": r.account_info,
                        "status": r.status, "reject_reason": r.reject_reason,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "processed_at": r.processed_at.isoformat() if r.processed_at else None})
    return page(result, total, page_no, page_size)


@router.post("/{req_id}/approve")
def approve_withdraw(req_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    """审核通过：扣减冻结与余额，记提现流水，标记 completed（线下打款）。"""
    payload = _get_admin(authorization)
    r = db.query(VmWithdrawalRequest).get(req_id)
    if not r:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "提现申请不存在"})
    if r.status != "pending":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "该申请已处理"})
    w = db.query(VmMerchantWallet).filter(VmMerchantWallet.merchant_id == r.merchant_id).first()
    if not w:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "商户钱包不存在"})
    before = w.balance
    w.balance = before - r.amount
    w.frozen = max((w.frozen or 0) - r.amount, 0)
    w.total_withdrawn = (w.total_withdrawn or 0) + r.amount
    db.add(VmMerchantWalletTransaction(
        wallet_id=w.id, merchant_id=r.merchant_id, type="withdraw",
        amount=r.amount, balance_before=before, balance_after=w.balance,
        remark=f"提现打款(申请#{r.id})"))
    r.status = "completed"
    r.operator_id = int(payload["sub"])
    r.processed_at = datetime.now()
    db.commit()
    return ok({"id": r.id, "status": "completed", "balance": float(w.balance)}, msg="提现已通过并打款")


@router.post("/{req_id}/reject")
def reject_withdraw(req_id: int, body: dict, authorization: str = Header(None),
                    db: Session = Depends(get_db)):
    """驳回提现：解冻金额，记录原因。"""
    payload = _get_admin(authorization)
    r = db.query(VmWithdrawalRequest).get(req_id)
    if not r:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "提现申请不存在"})
    if r.status != "pending":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "该申请已处理"})
    w = db.query(VmMerchantWallet).filter(VmMerchantWallet.merchant_id == r.merchant_id).first()
    if w:
        w.frozen = max((w.frozen or 0) - r.amount, 0)
    r.status = "rejected"
    r.reject_reason = body.get("reason", "")
    r.operator_id = int(payload["sub"])
    r.processed_at = datetime.now()
    db.commit()
    return ok({"id": r.id, "status": "rejected"}, msg="提现已驳回")
