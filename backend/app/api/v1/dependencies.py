"""
API 依赖：JWT 多租户身份解析 + 角色校验
所有业务接口通过 get_current_merchant 强制携带 merchant_id，实现租户隔离。
"""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.session import get_db
from app.models.merchant_user import MerchantUser


@dataclass
class CurrentUser:
    user_id: int
    merchant_id: int
    role: str
    username: str


def get_current_merchant(
    authorization: str = Header(None),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """从 Bearer Token 解析当前登录员工，返回 CurrentUser（含 merchant_id）。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "缺少或非法的 Token"})
    token = authorization.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "Token 无效或过期"})

    user_id = int(payload.get("sub", 0))
    merchant_id = payload.get("merchant_id")
    role = payload.get("role")
    if not merchant_id:
        raise HTTPException(status_code=401, detail={"code": 40102, "msg": "不是商户员工"})

    user = db.query(MerchantUser).filter(
        MerchantUser.id == user_id,
        MerchantUser.merchant_id == merchant_id,
        MerchantUser.status == 1,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail={"code": 40102, "msg": "用户不存在或已禁用"})

    return CurrentUser(user_id=user.id, merchant_id=user.merchant_id, role=user.role, username=user.username)


def require_roles(*roles: str):
    """角色守卫工厂：service 不能访问店铺管理/看板等。"""
    def checker(current: CurrentUser = Depends(get_current_merchant)) -> CurrentUser:
        if roles and current.role not in roles:
            raise HTTPException(status_code=403, detail={"code": 40301, "msg": "权限不足"})
        return current
    return checker
