"""
平台连接器包
对外暴露 PlatformConnector 基类、各实现类、以及工厂函数 get_platform_connector。
"""
from sqlalchemy.orm import Session

from app.models.platform_shop import PlatformShop

from .base import PlatformConnector
from .mock import MockPlatformConnector
from .vmall import V3Connector


def get_platform_connector(shop_id: int, db: Session) -> PlatformConnector:
    """
    工厂函数：按店铺 platform_type 返回连接器实例（per-shop 模式）。
    - platform_type=mock → MockPlatformConnector
    - platform_type=vmall + access_token → V3Connector
    - platform_type=vmall 无 token → MockPlatformConnector + warning
    - taobao/jd → MockPlatformConnector + warning（未对接真实平台）
    """
    import logging
    _log = logging.getLogger(__name__)

    shop = db.query(PlatformShop).filter(PlatformShop.id == shop_id).first()
    if shop is None:
        raise ValueError(f"店铺不存在: shop_id={shop_id}")

    if shop.platform_type == "mock":
        return MockPlatformConnector()

    if shop.platform_type == "vmall":
        if shop.access_token:
            base_url = shop.shop_url or "http://127.0.0.1:8020"
            return V3Connector(base_url, shop.access_token)
        _log.warning(f"shop {shop_id}: vmall 店铺无 access_token，降级 mock")
        return MockPlatformConnector()

    if shop.platform_type in ("taobao", "jd"):
        _log.warning(f"shop {shop_id}: {shop.platform_type} 未对接真实平台，降级 mock")
        return MockPlatformConnector()

    raise NotImplementedError(f"平台 {shop.platform_type} 暂未支持")


__all__ = [
    "PlatformConnector", "MockPlatformConnector", "V3Connector",
    "get_platform_connector",
]
