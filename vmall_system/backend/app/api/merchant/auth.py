"""商户认证"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import verify_password, create_token
from app.core.response import ok
from app.database.session import get_db
from app.models.vm_merchant import VmMerchant

router = APIRouter(prefix="/merchant/auth", tags=["商户-认证"])


@router.post("/login")
def login(body: dict, db: Session = Depends(get_db)):
    u = db.query(VmMerchant).filter(VmMerchant.username == body["username"]).first()
    if not u or not verify_password(body["password"], u.password_hash):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "用户名或密码错误"})
    if u.status != 1:
        raise HTTPException(status_code=403, detail={"code": 40301, "msg": "账号已被禁用"})
    token = create_token({"sub": str(u.id), "type": "merchant", "username": u.username}, 120)
    return ok({
        "access_token": token,
        "merchant": {
            "id": u.id, "username": u.username, "shop_name": u.shop_name,
            "shop_logo": u.shop_logo, "shop_desc": u.shop_desc,
            "contact_name": u.contact_name, "contact_phone": u.contact_phone,
            "contact_email": u.contact_email, "saas_bound": u.saas_bound,
            "saas_shop_id": u.saas_shop_id, "saas_url": u.saas_url,
            "saas_bind_time": u.saas_bind_time.isoformat() if u.saas_bind_time else None,
        }
    })
