"""
Redis 客户端 + 多租户 Key 前缀工具
Key 规范：m:{merchant_id}:...（architecture.md 多租户隔离）
"""
import redis

from app.core.config import settings

_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD or None,
    decode_responses=True,
    socket_connect_timeout=2,
)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


def mkey(merchant_id: int, *parts: str) -> str:
    """拼多租户 Key：m:{mid}:part1:part2..."""
    return ":".join(["m", str(merchant_id), *parts])
