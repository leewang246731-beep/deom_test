"""
V3Connector — 对接 vMall OpenAPI 的连接器 (tuozhan.md 集成)
替换 Mock 为真实 vMall 数据源。
"""
import httpx
from datetime import datetime
from typing import List

from .base import PlatformConnector


class V3Connector(PlatformConnector):
    """对接 vMall OpenAPI 的连接器。"""

    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url.rstrip("/")
        self.token = access_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def _get(self, path: str, params: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(f"{self.base_url}{path}", params=params, headers=self._headers())
            r.raise_for_status()
            return r.json().get("data", r.json())

    async def _post(self, path: str, body: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self.base_url}{path}", json=body or {}, headers=self._headers())
            r.raise_for_status()
            return r.json().get("data", r.json())

    # ---- PlatformConnector 抽象方法 ----
    async def fetch_products(self, shop_id: int) -> List[dict]:
        data = await self._get("/openapi/products", {"page": 1, "page_size": 200})
        return [self._map_product(p) for p in (data.get("items", []) or [])]

    async def fetch_orders(self, shop_id: int, start_time: datetime) -> List[dict]:
        data = await self._get("/openapi/orders", {
            "page": 1, "page_size": 200,
            "start_time": start_time.isoformat() if start_time else None,
        })
        return [self._map_order(o) for o in (data.get("items", []) or [])]

    async def send_message(self, shop_id: int, buyer_openid: str, content: str) -> bool:
        await self._post("/openapi/messages", {"text": content, "buyer_openid": buyer_openid})
        return True

    async def get_conversations(self, shop_id: int) -> List[dict]:
        data = await self._get("/openapi/conversations", {"page": 1, "page_size": 200})
        return [self._map_conversation(c) for c in (data.get("items", []) or [])]

    # ---- 物流查询 + 操作 (新增) ----
    async def get_logistics(self, order_id: int) -> dict | None:
        """查询 vMall 订单物流状态（含完整轨迹）。"""
        try:
            return await self._get(f"/openapi/logistics/{order_id}")
        except Exception:
            return None

    async def deliver_order(self, order_id: int, company: str, tracking_no: str) -> dict | None:
        """调用 vMall OpenAPI 发货。"""
        try:
            return await self._post(f"/openapi/orders/{order_id}/deliver", {"company": company, "tracking_no": tracking_no})
        except Exception:
            return None

    async def approve_after_sale(self, sale_id: int, action: str, remark: str = "") -> dict | None:
        """调用 vMall OpenAPI 审核售后。"""
        try:
            return await self._post(f"/openapi/after-sales/{sale_id}/approve", {"action": action, "remark": remark})
        except Exception:
            return None

    async def send_notification(self, buyer_id: int, order_id: int, content: str) -> dict:
        """调用 vMall /openapi/notifications 推送买家通知。"""
        return await self._post("/openapi/notifications", {
            "buyer_id": buyer_id,
            "order_id": order_id,
            "content": content,
            "msg_type": "reminder",
        })

    # ---- 字段映射 ----
    def _map_product(self, p: dict) -> dict:
        return {
            "platform_product_id": str(p.get("id", "")),
            "title": p.get("title", ""),
            "price": p.get("price_min", p.get("price_max", 0)),
            "stock": p.get("total_stock", 0),
            "description": p.get("description", ""),
            "images_json": [p.get("main_image", "")],
            "category_path": p.get("category_path", ""),
            "status": 1 if p.get("status") else 0,
            "last_sync_at": datetime.now(),
        }

    def _map_order(self, o: dict) -> dict:
        sku_list = o.get("sku_details", [])
        return {
            "platform_order_id": str(o.get("order_no", o.get("id", ""))),
            "buyer_openid": str(o.get("buyer_id", "")),
            "buyer_nick": o.get("buyer_nick", f"买家#{o.get('buyer_id','')}"),
            "total_amount": o.get("total_amount", 0),
            "discount_amount": o.get("discount_amount", 0),
            "pay_amount": o.get("pay_amount", 0),
            "status": self._map_order_status(o.get("status", ""), o.get("after_sale_status")),
            "sku_details_json": sku_list,
            "product_title": sku_list[0].get("title", "") if sku_list else "",
            "receiver_name": o.get("receiver_name", ""),
            "receiver_phone": o.get("receiver_phone", ""),
            "receiver_address": o.get("receiver_address", ""),
            "pay_time": o.get("pay_time"),
            "ship_time": o.get("ship_time"),
            "created_at": o.get("created_at"),
        }

    @staticmethod
    def _map_order_status(status: str, after_sale: str | None) -> str:
        if after_sale in ("refunding", "returned"): return "refunding"
        if after_sale == "refunded": return "refunded"
        return {
            "pending_payment": "pending", "paying": "pending", "paid": "paid",
            "shipped": "shipped", "received": "shipped", "completed": "completed",
            "closed": "completed",
        }.get(status, "pending")

    def _map_conversation(self, c: dict) -> dict:
        return {
            "platform_conversation_id": str(c.get("id", "")),
            "buyer_nick": c.get("buyer_nick", ""),
            "messages_json": c.get("messages_json", []),
            "last_message_at": c.get("last_message_at"),
            "handled_status": "pending" if c.get("status") == "open" else "closed",
        }
