"""商户 - 店铺钱包/收益/提现"""
import json
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_merchant_wallet import (
    VmMerchantWallet, VmMerchantWalletTransaction, VmWithdrawalRequest,
)

router = APIRouter(prefix="/merchant/wallet", tags=["商户-钱包"])


def _get_merchant(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "merchant":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需商户登录"})
    return payload


def _get_or_create_wallet(db: Session, mid: int) -> VmMerchantWallet:
    w = db.query(VmMerchantWallet).filter(VmMerchantWallet.merchant_id == mid).first()
    if not w:
        w = VmMerchantWallet(merchant_id=mid, balance=0, total_revenue=0,
                             total_withdrawn=0, total_refunded=0, frozen=0, status=1)
        db.add(w); db.commit(); db.refresh(w)
    return w


@router.get("")
def my_wallet(authorization: str = Header(None), db: Session = Depends(get_db)):
    """商户查看店铺钱包余额与累计收益。"""
    mid = int(_get_merchant(authorization)["sub"])
    w = _get_or_create_wallet(db, mid)
    return ok({
        "balance": float(w.balance),
        "available": float(w.balance - (w.frozen or 0)),
        "frozen": float(w.frozen or 0),
        "total_revenue": float(w.total_revenue),
        "total_withdrawn": float(w.total_withdrawn),
        "total_refunded": float(w.total_refunded),
        "status": w.status,
    })


@router.get("/transactions")
def my_transactions(type: str = Query(None), page_no: int = Query(1, alias="page"),
                    page_size: int = Query(20), authorization: str = Header(None),
                    db: Session = Depends(get_db)):
    """商户查看钱包流水（收入/退款/提现）。"""
    mid = int(_get_merchant(authorization)["sub"])
    q = db.query(VmMerchantWalletTransaction).filter(
        VmMerchantWalletTransaction.merchant_id == mid)
    if type:
        q = q.filter(VmMerchantWalletTransaction.type == type)
    total = q.count()
    items = q.order_by(VmMerchantWalletTransaction.created_at.desc()).offset(
        (page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": t.id, "type": t.type, "amount": float(t.amount),
                  "balance_before": float(t.balance_before), "balance_after": float(t.balance_after),
                  "order_no": t.order_no, "remark": t.remark,
                  "created_at": t.created_at.isoformat() if t.created_at else None}
                 for t in items], total, page_no, page_size)


@router.post("/withdraw")
def apply_withdraw(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    """商户申请提现：校验可用余额，冻结对应金额，生成 pending 申请。"""
    mid = int(_get_merchant(authorization)["sub"])
    amount = Decimal(str(body.get("amount", 0)))
    if amount <= 0:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "提现金额必须大于0"})
    account_type = body.get("account_type", "")
    if account_type not in ("bank", "alipay", "wechat"):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "account_type 必须为 bank/alipay/wechat"})
    account = body.get("account")
    if not account:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "缺少收款账户信息"})
    w = _get_or_create_wallet(db, mid)
    available = w.balance - (w.frozen or 0)
    if amount > available:
        raise HTTPException(status_code=400, detail={"code": 40002,
                            "msg": f"可提现余额不足（可用 {float(available)} 元）"})
    w.frozen = (w.frozen or 0) + amount
    req = VmWithdrawalRequest(
        merchant_id=mid, amount=amount, account_type=account_type,
        account_info=account if isinstance(account, str) else json.dumps(account, ensure_ascii=False),
        status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return ok({"id": req.id, "amount": float(amount), "status": "pending",
               "frozen": float(w.frozen)}, msg="提现申请已提交，等待平台审核")


@router.get("/withdrawals")
def my_withdrawals(status: str = Query(None), page_no: int = Query(1, alias="page"),
                   page_size: int = Query(20), authorization: str = Header(None),
                   db: Session = Depends(get_db)):
    """商户查看自己的提现申请记录。"""
    mid = int(_get_merchant(authorization)["sub"])
    q = db.query(VmWithdrawalRequest).filter(VmWithdrawalRequest.merchant_id == mid)
    if status:
        q = q.filter(VmWithdrawalRequest.status == status)
    total = q.count()
    items = q.order_by(VmWithdrawalRequest.created_at.desc()).offset(
        (page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": r.id, "amount": float(r.amount), "account_type": r.account_type,
                  "status": r.status, "reject_reason": r.reject_reason,
                  "created_at": r.created_at.isoformat() if r.created_at else None,
                  "processed_at": r.processed_at.isoformat() if r.processed_at else None}
                 for r in items], total, page_no, page_size)
