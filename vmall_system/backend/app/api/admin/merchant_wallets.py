"""运营后台 - 商户钱包监控（风控只读）"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_merchant import VmMerchant
from app.models.vm_merchant_wallet import VmMerchantWallet, VmMerchantWalletTransaction

router = APIRouter(prefix="/admin/merchant-wallets", tags=["运营-商户钱包监控"])


def _get_admin(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "admin":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需运营后台登录"})
    return payload


@router.get("")
def list_merchant_wallets(negative_only: bool = Query(False), page_no: int = Query(1, alias="page"),
                          page_size: int = Query(20), authorization: str = Header(None),
                          db: Session = Depends(get_db)):
    """平台查看所有商户钱包状态（监控负余额/冻结，风控用）。"""
    _get_admin(authorization)
    q = db.query(VmMerchantWallet)
    if negative_only:
        q = q.filter(VmMerchantWallet.balance < 0)
    total = q.count()
    items = q.order_by(VmMerchantWallet.balance.asc()).offset(
        (page_no - 1) * page_size).limit(page_size).all()
    result = []
    for w in items:
        m = db.query(VmMerchant).get(w.merchant_id)
        result.append({"merchant_id": w.merchant_id, "shop_name": m.shop_name if m else "",
                        "balance": float(w.balance), "frozen": float(w.frozen or 0),
                        "available": float(w.balance - (w.frozen or 0)),
                        "total_revenue": float(w.total_revenue), "total_withdrawn": float(w.total_withdrawn),
                        "total_refunded": float(w.total_refunded), "status": w.status,
                        "negative": w.balance < 0})
    return page(result, total, page_no, page_size)


@router.get("/{merchant_id}/transactions")
def merchant_transactions(merchant_id: int, page_no: int = Query(1, alias="page"),
                          page_size: int = Query(20), authorization: str = Header(None),
                          db: Session = Depends(get_db)):
    """平台查看指定商户钱包流水（监管）。"""
    _get_admin(authorization)
    q = db.query(VmMerchantWalletTransaction).filter(
        VmMerchantWalletTransaction.merchant_id == merchant_id)
    total = q.count()
    items = q.order_by(VmMerchantWalletTransaction.created_at.desc()).offset(
        (page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": t.id, "type": t.type, "amount": float(t.amount),
                  "balance_before": float(t.balance_before), "balance_after": float(t.balance_after),
                  "order_no": t.order_no, "remark": t.remark,
                  "created_at": t.created_at.isoformat() if t.created_at else None}
                 for t in items], total, page_no, page_size)
