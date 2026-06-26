"""
API 依赖：JWT 双通道身份解析 + 角色校验
- 平台运营（platform_users）：token type=platform，无 merchant_id，跨租户
- 商户员工（merchant_users）：token type=access，含 merchant_id，租户隔离
"""
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.session import get_db
from app.models.merchant_user import MerchantUser
from app.models.platform_user import PlatformUser


@dataclass
class CurrentUser:
    user_id: int
    merchant_id: Optional[int]  # None 表示平台运营（跨租户）
    role: str
    username: str
    token_type: str  # "platform" | "access"


def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """通用身份解析：接受 platform 或 access token，返回 CurrentUser。
    merchant_id 仅在 access token 下存在；platform token 下为 None。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "缺少或非法的 Token"})
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "Token 无效或过期"})

    token_type = payload.get("type")
    if token_type not in ("access", "platform"):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "Token 类型非法"})

    user_id = int(payload.get("sub", 0))
    role = payload.get("role", "")

    if token_type == "platform":
        user = db.query(PlatformUser).filter(
            PlatformUser.id == user_id, PlatformUser.status == 1
        ).first()
        if not user:
            raise HTTPException(status_code=401, detail={"code": 40102, "msg": "平台账号不存在或已禁用"})
        return CurrentUser(
            user_id=user.id, merchant_id=None, role=user.role,
            username=user.username, token_type="platform",
        )

    # access token — 商户员工
    merchant_id = payload.get("merchant_id")
    if not merchant_id:
        raise HTTPException(status_code=401, detail={"code": 40102, "msg": "不是商户员工"})

    user = db.query(MerchantUser).filter(
        MerchantUser.id == user_id,
        MerchantUser.merchant_id == merchant_id,
        MerchantUser.status == 1,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail={"code": 40102, "msg": "用户不存在或已禁用"})

    return CurrentUser(
        user_id=user.id, merchant_id=user.merchant_id, role=user.role,
        username=user.username, token_type="access",
    )


def get_platform_user(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """平台运营专属依赖：仅允许 platform token。"""
    if current.token_type != "platform":
        raise HTTPException(status_code=403, detail={"code": 40301, "msg": "仅平台运营账号可访问"})
    return current


def get_current_merchant(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """商户员工专属依赖：仅允许 access token，必须有 merchant_id。"""
    if current.token_type != "access":
        raise HTTPException(status_code=403, detail={"code": 40301, "msg": "平台账号不可访问商户接口，请使用商户账号"})
    if current.merchant_id is None:
        raise HTTPException(status_code=401, detail={"code": 40102, "msg": "不是商户员工"})
    return current


def require_roles(*roles: str):
    """角色守卫工厂（商户端）：检查 merchant user 的 role 是否在允许列表中。"""
    def checker(current: CurrentUser = Depends(get_current_merchant)) -> CurrentUser:
        if roles and current.role not in roles:
            raise HTTPException(status_code=403, detail={"code": 40301, "msg": "权限不足"})
        return current
    return checker


def require_platform_roles(*roles: str):
    """角色守卫工厂（平台端）：检查 platform user 的 role 是否在允许列表中。"""
    def checker(current: CurrentUser = Depends(get_platform_user)) -> CurrentUser:
        if roles and current.role not in roles:
            raise HTTPException(status_code=403, detail={"code": 40301, "msg": "权限不足"})
        return current
    return checker
