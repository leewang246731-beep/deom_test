"""vMall Redis 客户端"""
import redis
from app.core.config import settings

_pool = redis.ConnectionPool(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT,
    password=settings.REDIS_PASSWORD or None, decode_responses=True,
    socket_connect_timeout=2,
)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)
