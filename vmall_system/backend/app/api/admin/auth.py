"""运营后台认证"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import verify_password, create_token
from app.core.response import ok
from app.database.session import get_db
from app.models.vm_platform_setting import VmPlatformAdmin

router = APIRouter(prefix="/admin/auth", tags=["运营-认证"])


@router.post("/login")
def login(body: dict, db: Session = Depends(get_db)):
    u = db.query(VmPlatformAdmin).filter(VmPlatformAdmin.username == body["username"]).first()
    if not u or not verify_password(body["password"], u.password_hash):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "用户名或密码错误"})
    token = create_token({"sub": str(u.id), "type": "admin", "username": u.username}, 120)
    return ok({"access_token": token, "user": {"id": u.id, "username": u.username, "role": u.role}})
