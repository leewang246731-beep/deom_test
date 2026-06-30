"""
平台连接器抽象基类
所有电商平台（mock / taobao / jd / douyin）连接器的统一契约。

返回 dict 的字段形状对齐 ORM 模型，便于种子脚本/同步任务直接落库：
- fetch_products → external_products 字段
- fetch_orders   → external_orders 字段（含催单所需 status/buyer_nick/buyer_openid/product_title）
- get_conversations → conversations 字段
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List


class PlatformConnector(ABC):
    """Abstract base for all e-commerce platform connectors."""

    @abstractmethod
    async def fetch_products(self, shop_id: int) -> List[dict]:
        """拉取平台最新商品。返回 external_products 字段形状的 dict 列表。"""
        ...

    @abstractmethod
    async def fetch_orders(self, shop_id: int, start_time: datetime) -> List[dict]:
        """拉取指定时间以来的订单。返回 external_orders 字段形状的 dict 列表。"""
        ...

    @abstractmethod
    async def send_message(self, shop_id: int, buyer_openid: str, content: str) -> bool:
        """向买家发送一条消息。返回是否成功。"""
        ...

    @abstractmethod
    async def get_conversations(self, shop_id: int) -> List[dict]:
        """获取活跃客服会话。返回 conversations 字段形状的 dict 列表。"""
        ...

    @abstractmethod
    async def send_notification(self, buyer_id: int, order_id: int, content: str) -> dict:
        """向买家推送通知（催单等）。返回 {id, conversation_id}。"""
        ...
