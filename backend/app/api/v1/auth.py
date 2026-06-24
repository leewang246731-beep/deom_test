"""
认证接口（PHASE1-PLAN 4.1 / api.md 3.1）
仅 admin / manager / service 可登录。JWT 含 merchant_id + role。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.response import ok
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.database.session import get_db
from app.models.merchant_user import MerchantUser
from app.schemas import LoginRequest, RefreshRequest

router = APIRouter(prefix="/auth", tags=["认证"])

ALLOWED_ROLES = {"admin", "manager", "service"}


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(MerchantUser).filter(MerchantUser.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "用户名或密码错误"})
    if user.status != 1:
        raise HTTPException(status_code=403, detail={"code": 40301, "msg": "账号已禁用"})
    if user.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=403, detail={"code": 40301, "msg": "无登录权限"})

    user.last_login_at = datetime.now()
    db.commit()

    return ok({
        "access_token": create_access_token(user.id, user.merchant_id, user.role),
        "refresh_token": create_refresh_token(user.id, user.merchant_id),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "merchant_id": user.merchant_id,
        },
    })


@router.post("/refresh")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "refresh token 无效"})
    user = db.query(MerchantUser).filter(MerchantUser.id == int(payload["sub"])).first()
    if not user or user.status != 1:
        raise HTTPException(status_code=401, detail={"code": 40102, "msg": "用户不存在或禁用"})
    return ok({
        "access_token": create_access_token(user.id, user.merchant_id, user.role),
        "token_type": "bearer",
    })


@router.post("/logout")
def logout():
    # 无状态 JWT，登出由前端丢弃 token；此处仅作占位返回。
    return ok(msg="已登出")
