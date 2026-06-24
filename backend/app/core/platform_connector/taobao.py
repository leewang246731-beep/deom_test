"""
淘宝平台连接器（二期）
类结构已预留，一期不实现，调用即抛 NotImplementedError。
"""
from datetime import datetime
from typing import List

from .base import PlatformConnector


class TaobaoConnector(PlatformConnector):
    """淘宝开放平台连接器，二期对接 Open API。"""

    def __init__(self, app_key: str, app_secret: str, access_token: str = None):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token

    async def fetch_products(self, shop_id: int) -> List[dict]:
        raise NotImplementedError("淘宝连接器为二期内容，暂未实现")

    async def fetch_orders(self, shop_id: int, start_time: datetime) -> List[dict]:
        raise NotImplementedError("淘宝连接器为二期内容，暂未实现")

    async def send_message(self, shop_id: int, buyer_openid: str, content: str) -> bool:
        raise NotImplementedError("淘宝连接器为二期内容，暂未实现")

    async def get_conversations(self, shop_id: int) -> List[dict]:
        raise NotImplementedError("淘宝连接器为二期内容，暂未实现")
