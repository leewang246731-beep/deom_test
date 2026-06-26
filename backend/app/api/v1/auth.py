"""
认证接口（PHASE1-PLAN 4.1 / api.md 3.1）
商户员工 + 平台运营 两条登录通道。JWT 含 merchant_id + role 或 type=platform。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis_client import get_redis
from app.core.response import ok
from app.core.security import (
    create_access_token,
    create_platform_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.database.session import get_db
from app.models.merchant_user import MerchantUser
from app.models.platform_user import PlatformUser
from app.schemas import LoginRequest, RefreshRequest

router = APIRouter(prefix="/auth", tags=["认证"])

ALLOWED_ROLES = {"admin", "manager", "service"}
PLATFORM_ROLES = {"super_admin", "manager"}


def _check_login_rate(request: Request):
    """登录频率限制：每 IP 每分钟最多 N 次。"""
    try:
        r = get_redis()
        ip = request.client.host if request.client else "unknown"
        key = f"rate:login:{ip}"
        count = r.incr(key)
        if count == 1:
            r.expire(key, settings.LOGIN_RATE_WINDOW)
        if count > settings.LOGIN_RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail={"code": 42901, "msg": f"登录尝试过于频繁，请 {settings.LOGIN_RATE_WINDOW} 秒后重试"},
            )
    except HTTPException:
        raise
    except Exception:
        pass  # Redis 不可用时放行


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db), _rate: None = Depends(_check_login_rate)):
    q = db.query(MerchantUser).filter(MerchantUser.username == body.username)
    if body.merchant_id is not None:
        q = q.filter(MerchantUser.merchant_id == body.merchant_id)

    users = q.all()
    if len(users) > 1 and body.merchant_id is None:
        # 多个同名用户但未指定商户 → 返回可用商户列表让前端选择
        merchants = [
            {"merchant_id": u.merchant_id, "display_name": u.display_name, "role": u.role}
            for u in users
        ]
        raise HTTPException(
            status_code=400,
            detail={
                "code": 40002,
                "msg": "该用户名在多个商户中存在，请在登录时指定 merchant_id",
                "available_merchants": merchants,
            },
        )

    user = users[0] if users else None
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


@router.post("/platform/login")
def platform_login(body: LoginRequest, db: Session = Depends(get_db), _rate: None = Depends(_check_login_rate)):
    """平台运营账号登录（无 merchant_id，跨租户查看所有商户数据）。"""
    user = db.query(PlatformUser).filter(PlatformUser.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "用户名或密码错误"})
    if user.status != 1:
        raise HTTPException(status_code=403, detail={"code": 40301, "msg": "账号已禁用"})
    if user.role not in PLATFORM_ROLES:
        raise HTTPException(status_code=403, detail={"code": 40301, "msg": "无平台登录权限"})

    return ok({
        "access_token": create_platform_token(user.id, user.role),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
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
