"""商户工作台"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_product import VmProduct
from app.models.vm_order import VmOrder

router = APIRouter(prefix="/merchant/dashboard", tags=["商户-工作台"])


def _get_merchant(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "merchant":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需商户登录"})
    return payload


@router.get("")
def dashboard(authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    mid = int(merchant["sub"])
    product_count = db.query(VmProduct).filter(VmProduct.merchant_id == mid).count()
    today_orders = db.query(VmOrder).filter(VmOrder.merchant_id == mid).count()
    pending_orders = db.query(VmOrder).filter(VmOrder.merchant_id == mid, VmOrder.status == "paid").count()
    recent = db.query(VmOrder).filter(VmOrder.merchant_id == mid).order_by(VmOrder.created_at.desc()).limit(5).all()
    return ok({
        "stats": {"product_count": product_count, "today_orders": today_orders, "pending_orders": pending_orders},
        "recent_orders": [{"id": o.id, "buyer_name": o.receiver_name, "total_amount": float(o.total_amount),
                           "status": o.status, "created_at": o.created_at.isoformat() if o.created_at else None}
                          for o in recent],
    })
