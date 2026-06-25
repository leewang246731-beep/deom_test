"""
平台连接器包
对外暴露 PlatformConnector 基类、各实现类、以及工厂函数 get_platform_connector。
"""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.platform_shop import PlatformShop

from .base import PlatformConnector
from .jd import JdConnector
from .mock import MockPlatformConnector
from .taobao import TaobaoConnector
from .vmall import V3Connector


def get_platform_connector(shop_id: int, db: Session) -> PlatformConnector:
    """
    工厂函数：按全局 PLATFORM_MODE 与店铺 platform_type 返回连接器实例。
    - PLATFORM_MODE=mock 或店铺 mock → MockPlatformConnector
    - platform_type=vmall → V3Connector(vmall API + access_token)
    - platform_type=taobao → TaobaoConnector
    - platform_type=jd → JdConnector
    """
    if settings.PLATFORM_MODE == "mock":
        return MockPlatformConnector()

    shop = db.query(PlatformShop).filter(PlatformShop.id == shop_id).first()
    if shop is None:
        raise ValueError(f"店铺不存在: shop_id={shop_id}")

    if shop.platform_type == "mock":
        return MockPlatformConnector()
    if shop.platform_type == "vmall":
        base_url = shop.shop_url or "http://127.0.0.1:8020"
        return V3Connector(base_url, shop.access_token or "")
    if shop.platform_type == "taobao":
        return TaobaoConnector(shop.app_key or "", shop.app_secret or "", shop.access_token or "")
    if shop.platform_type == "jd":
        return JdConnector(shop.app_key or "", shop.app_secret or "", shop.access_token or "")
    raise NotImplementedError(f"平台 {shop.platform_type} 暂未支持")


__all__ = [
    "PlatformConnector", "MockPlatformConnector", "TaobaoConnector", "JdConnector", "V3Connector",
    "get_platform_connector",
]
