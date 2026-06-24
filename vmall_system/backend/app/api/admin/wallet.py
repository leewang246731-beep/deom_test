"""运营后台 - 钱包充值管理"""
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_buyer import VmBuyer
from app.models.vm_wallet import VmWallet, VmWalletTransaction

router = APIRouter(prefix="/admin/wallets", tags=["运营-钱包管理"])


def _get_admin(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "admin":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需运营后台登录"})
    return payload


@router.get("")
def list_wallets(keyword: str = Query(None), page_no: int = Query(1, alias="page"),
                 page_size: int = Query(20), authorization: str = Header(None),
                 db: Session = Depends(get_db)):
    _get_admin(authorization)
    q = db.query(VmWallet).join(VmBuyer)
    if keyword:
        q = q.filter((VmBuyer.username.like(f"%{keyword}%")) | (VmBuyer.nickname.like(f"%{keyword}%")))
    total = q.count()
    items = q.order_by(VmWallet.id).offset((page_no - 1) * page_size).limit(page_size).all()
    result = []
    for w in items:
        buyer = db.query(VmBuyer).get(w.buyer_id)
        result.append({"id": w.id, "buyer_id": w.buyer_id, "username": buyer.username if buyer else "",
                        "nickname": buyer.nickname or "" if buyer else "",
                        "balance": float(w.balance), "total_recharged": float(w.total_recharged),
                        "total_spent": float(w.total_spent), "status": w.status})
    return page(result, total, page_no, page_size)


@router.get("/{buyer_id}")
def get_wallet(buyer_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    wallet = db.query(VmWallet).filter(VmWallet.buyer_id == buyer_id).first()
    if not wallet:
        wallet = VmWallet(buyer_id=buyer_id, balance=0, total_recharged=0, total_spent=0, status=1)
        db.add(wallet); db.commit(); db.refresh(wallet)
    buyer = db.query(VmBuyer).get(buyer_id)
    return ok({"id": wallet.id, "buyer_id": wallet.buyer_id,
               "username": buyer.username if buyer else "", "nickname": buyer.nickname or "" if buyer else "",
               "balance": float(wallet.balance), "total_recharged": float(wallet.total_recharged),
               "total_spent": float(wallet.total_spent), "status": wallet.status})


@router.post("/{buyer_id}/recharge")
def recharge(buyer_id: int, body: dict, authorization: str = Header(None),
             db: Session = Depends(get_db)):
    payload = _get_admin(authorization)
    amount = Decimal(str(body.get("amount", 0)))
    if amount <= 0:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "充值金额必须大于0"})
    wallet = db.query(VmWallet).filter(VmWallet.buyer_id == buyer_id).first()
    if not wallet:
        wallet = VmWallet(buyer_id=buyer_id, balance=0, total_recharged=0, total_spent=0, status=1)
        db.add(wallet); db.flush()
    before = float(wallet.balance)
    wallet.balance = wallet.balance + amount
    wallet.total_recharged = wallet.total_recharged + amount
    after = float(wallet.balance)
    tx = VmWalletTransaction(wallet_id=wallet.id, buyer_id=buyer_id, type="recharge",
                              amount=float(amount), balance_before=before,
                              balance_after=after,
                              remark=body.get("remark", f"管理员充值 {amount}元"),
                              operator_id=int(payload["sub"]))
    db.add(tx)
    db.commit()
    return ok({"id": wallet.id, "buyer_id": buyer_id, "balance": after, "recharged": float(amount)},
              msg=f"充值成功: +{amount}元")


@router.get("/{buyer_id}/transactions")
def get_transactions(buyer_id: int, page_no: int = Query(1, alias="page"),
                     page_size: int = Query(20), authorization: str = Header(None),
                     db: Session = Depends(get_db)):
    _get_admin(authorization)
    q = db.query(VmWalletTransaction).filter(VmWalletTransaction.buyer_id == buyer_id)
    total = q.count()
    items = q.order_by(VmWalletTransaction.created_at.desc()).offset(
        (page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": t.id, "type": t.type, "amount": float(t.amount),
                   "balance_before": float(t.balance_before), "balance_after": float(t.balance_after),
                   "order_no": t.order_no, "remark": t.remark,
                   "created_at": t.created_at.isoformat() if t.created_at else None}
                 for t in items], total, page_no, page_size)
