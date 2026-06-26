"""
安全工具：bcrypt 密码哈希 + JWT 签发/校验
JWT Payload 携带多租户信息：sub(user_id) / merchant_id / role
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ===== 密码 =====
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ===== JWT =====
def _create_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload.update({"exp": datetime.now(timezone.utc) + expires_delta})
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int, merchant_id: int, role: str) -> str:
    """签发 access token，内含多租户身份。"""
    return _create_token(
        {
            "sub": str(user_id),
            "merchant_id": merchant_id,
            "role": role,
            "type": "access",
        },
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_platform_token(user_id: int, role: str) -> str:
    """签发平台运营账号 token（无 merchant_id，可跨租户）。"""
    return _create_token(
        {"sub": str(user_id), "role": role, "type": "platform"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int, merchant_id: int) -> str:
    return _create_token(
        {"sub": str(user_id), "merchant_id": merchant_id, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> Optional[dict]:
    """解析并校验 token，失败返回 None。"""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
