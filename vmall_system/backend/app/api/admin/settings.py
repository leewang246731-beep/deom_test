"""运营后台 - 平台设置 + 看板"""
from datetime import datetime

from fastapi import Header,APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_after_sale import VmAfterSale
from app.models.vm_order import VmOrder
from app.models.vm_platform_setting import VmPlatformSetting

router = APIRouter(prefix="/admin", tags=["运营-设置+看板"])


def _get_admin(auth: str) -> dict:
    return decode_token(auth.split(" ", 1)[1])


@router.get("/dashboard")
def dashboard(authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    today = datetime.now().strftime("%Y-%m-%d")
    today_orders = db.query(VmOrder).filter(VmOrder.created_at >= today).count()
    pending_ship = db.query(VmOrder).filter(VmOrder.status == "paid").count()
    pending_review = db.query(VmAfterSale).filter(VmAfterSale.status == "pending_review").count()
    today_amount = db.query(VmOrder).filter(VmOrder.created_at >= today, VmOrder.status != "closed")
    gmv = sum(float(o.pay_amount) for o in today_amount.all())
    return ok({"today_orders": today_orders, "pending_ship": pending_ship,
                "pending_review": pending_review, "today_gmv": round(gmv, 2)})


@router.put("/settings")
def update_settings(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    s = db.query(VmPlatformSetting).first()
    if not s:
        s = VmPlatformSetting(access_token_secret="vmall-secret-key-change-in-production")
        db.add(s)
    for field in ("shop_name", "logo_url", "saas_webhook_url", "access_token_secret"):
        if field in body:
            setattr(s, field, body[field])
    db.commit()
    return ok({"id": s.id}, msg="已更新")


@router.get("/settings")
def get_settings(authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    s = db.query(VmPlatformSetting).first()
    if not s:
        return ok({"shop_name": "vMall 官方旗舰店", "logo_url": "", "saas_webhook_url": "", "access_token_secret": ""})
    return ok({"id": s.id, "shop_name": s.shop_name, "logo_url": s.logo_url or "",
               "saas_webhook_url": s.saas_webhook_url or "", "access_token_secret": s.access_token_secret})
