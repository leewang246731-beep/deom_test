"""商户 - 店铺设置"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_merchant import VmMerchant

router = APIRouter(prefix="/merchant/settings", tags=["商户-设置"])


def _get_merchant(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "merchant":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需商户登录"})
    return payload


@router.get("")
def get_settings(authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    u = db.query(VmMerchant).get(int(merchant["sub"]))
    if not u: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "商户不存在"})
    return ok({"shop_name": u.shop_name, "shop_logo": u.shop_logo or "", "shop_desc": u.shop_desc or "",
               "contact_name": u.contact_name or "", "contact_phone": u.contact_phone or "",
               "contact_email": u.contact_email or ""})


@router.put("")
def update_settings(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    u = db.query(VmMerchant).get(int(merchant["sub"]))
    if not u: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "商户不存在"})
    for f in ["shop_name", "shop_logo", "shop_desc", "contact_name", "contact_phone", "contact_email"]:
        if f in body: setattr(u, f, body[f])
    db.commit()
    return ok(msg="保存成功")
