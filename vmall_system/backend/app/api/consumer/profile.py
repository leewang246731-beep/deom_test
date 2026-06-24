"""消费者端 - 个人中心 + 钱包"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_buyer import VmBuyer
from app.models.vm_wallet import VmWallet, VmWalletTransaction

router = APIRouter(prefix="/consumer", tags=["消费者-个人中心"])


def _get_buyer(auth: str) -> int:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "buyer":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "Token 无效"})
    return int(payload["sub"])


@router.get("/profile")
def get_profile(authorization: str = Header(None), db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    buyer = db.query(VmBuyer).get(buyer_id)
    if not buyer:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "用户不存在"})
    # 确保钱包存在
    wallet = db.query(VmWallet).filter(VmWallet.buyer_id == buyer_id).first()
    if not wallet:
        wallet = VmWallet(buyer_id=buyer_id, balance=0, total_recharged=0, total_spent=0, status=1)
        db.add(wallet); db.commit(); db.refresh(wallet)
    return ok({"id": buyer.id, "username": buyer.username, "nickname": buyer.nickname or buyer.username,
               "phone": buyer.phone or "", "avatar": buyer.avatar or "",
               "source": buyer.source, "status": buyer.status,
               "wallet": {"id": wallet.id, "balance": float(wallet.balance),
                          "total_recharged": float(wallet.total_recharged),
                          "total_spent": float(wallet.total_spent),
                          "status": wallet.status}})


@router.put("/profile")
def update_profile(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    buyer = db.query(VmBuyer).get(buyer_id)
    if not buyer:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "用户不存在"})
    for field in ("nickname", "phone", "avatar"):
        if field in body:
            setattr(buyer, field, body[field])
    db.commit()
    return ok({"id": buyer.id, "nickname": buyer.nickname}, msg="已更新")


@router.get("/wallet")
def get_wallet(authorization: str = Header(None), db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    wallet = db.query(VmWallet).filter(VmWallet.buyer_id == buyer_id).first()
    if not wallet:
        wallet = VmWallet(buyer_id=buyer_id, balance=0, total_recharged=0, total_spent=0, status=1)
        db.add(wallet); db.commit(); db.refresh(wallet)
    return ok({"id": wallet.id, "balance": float(wallet.balance),
               "total_recharged": float(wallet.total_recharged),
               "total_spent": float(wallet.total_spent), "status": wallet.status})


@router.get("/wallet/transactions")
def get_transactions(page_no: int = Query(1, alias="page"), page_size: int = Query(20),
                     authorization: str = Header(None), db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    wallet = db.query(VmWallet).filter(VmWallet.buyer_id == buyer_id).first()
    if not wallet:
        return page([], 0, page_no, page_size)
    q = db.query(VmWalletTransaction).filter(VmWalletTransaction.wallet_id == wallet.id)
    total = q.count()
    items = q.order_by(VmWalletTransaction.created_at.desc()).offset(
        (page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": t.id, "type": t.type, "amount": float(t.amount),
                   "balance_before": float(t.balance_before), "balance_after": float(t.balance_after),
                   "order_no": t.order_no, "remark": t.remark,
                   "created_at": t.created_at.isoformat() if t.created_at else None}
                 for t in items], total, page_no, page_size)
