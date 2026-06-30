"""
ToolRegistry — 统一 Agent 工具注册中心。

所有 @tool 在此注册，Agent 按名称或能力标签拉取。
消除 tools.py / OrderAgent / LogisticsAgent 等文件中的工具重复定义。
"""
from typing import Callable, Optional
from langchain_core.tools import tool as langchain_tool

from app.database.session import SessionLocal
from app.models.external_order import ExternalOrder
from app.models.external_product import ExternalProduct
from app.models.platform_shop import PlatformShop


class ToolRegistry:
    """单例工具注册中心。"""

    _instance: Optional["ToolRegistry"] = None

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._tags: dict[str, list[str]] = {}

    @classmethod
    def get(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, func: Callable, tags: list[str] = None):
        """注册一个工具函数。"""
        self._tools[func.name] = func
        if tags:
            self._tags[func.name] = tags

    def get_tool(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def get_by_tags(self, tags: list[str]) -> list[Callable]:
        """按能力标签拉取工具。返回匹配任一标签的工具列表。"""
        result = []
        seen = set()
        for name, tool_tags in self._tags.items():
            if any(t in tool_tags for t in tags):
                if name not in seen:
                    result.append(self._tools[name])
                    seen.add(name)
        return result

    def get_by_names(self, names: list[str]) -> list[Callable]:
        """按名称拉取工具。"""
        return [self._tools[n] for n in names if n in self._tools]

    def list_all(self) -> list[Callable]:
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        return list(self._tools.keys())


# ===== 工具工厂：为指定 merchant_id 生成工具实例 =====

def _shop_ids(db, merchant_id):
    return [r[0] for r in db.query(PlatformShop.id).filter(
        PlatformShop.merchant_id == merchant_id).all()]


def build_query_order_tool(merchant_id: int):
    """查询订单（按订单号/买家昵称/订单ID）。tag: order"""
    @langchain_tool
    def query_order(query: str) -> str:
        """根据订单号或买家昵称查询订单状态。返回订单详情包括状态、金额、收货地址。"""
        db = SessionLocal()
        try:
            sids = _shop_ids(db, merchant_id)
            if not sids:
                return "该商户暂无店铺"
            q = db.query(ExternalOrder).filter(ExternalOrder.shop_id.in_(sids))
            if query.isdigit():
                q = q.filter(
                    (ExternalOrder.id == int(query)) |
                    (ExternalOrder.platform_order_id == query)
                )
            else:
                q = q.filter(ExternalOrder.buyer_nick.like(f"%{query}%"))
            orders = q.order_by(ExternalOrder.created_at.desc()).limit(5).all()
            if not orders:
                return f"未找到与'{query}'相关的订单"
            lines = []
            for o in orders:
                lines.append(
                    f"订单ID:{o.id} 号:{o.platform_order_id} 买家:{o.buyer_nick} "
                    f"金额:¥{float(o.pay_amount):.2f} 状态:{o.status} "
                    f"地址:{o.receiver_address or '无'} 时间:{o.created_at}"
                )
            return "\n".join(lines)
        finally:
            db.close()
    return query_order


def build_check_inventory_tool(merchant_id: int):
    """查询商品库存。tag: product"""
    @langchain_tool
    def check_inventory(product_id: int) -> str:
        """查询商品库存。product_id 为商品数字ID。返回标题、库存量和上下架状态。"""
        db = SessionLocal()
        try:
            sids = _shop_ids(db, merchant_id)
            p = db.query(ExternalProduct).filter(
                ExternalProduct.id == product_id,
                ExternalProduct.shop_id.in_(sids),
            ).first() if sids else None
            if not p:
                return f"未找到商品ID:{product_id}"
            status = "在售" if p.status == 1 else "下架"
            return f"商品:{p.title} 库存:{p.stock}件 状态:{status} 价格:¥{float(p.price):.2f}"
        finally:
            db.close()
    return check_inventory


def build_search_product_tool(merchant_id: int):
    """语义搜索商品知识库。tag: product, knowledge"""
    @langchain_tool
    def search_product_kb(query: str) -> str:
        """语义搜索商品知识库。query 为买家问题或商品关键词。返回匹配商品的标题、价格、评分。"""
        try:
            from app.services.ai_suggest import semantic_search_products
            results = semantic_search_products(merchant_id, query, shop_ids=[], top_k=5)
            if not results:
                return "未找到相关商品信息"
            lines = []
            for r in results:
                price = f"¥{r['price']}" if r.get("price") else "暂无"
                lines.append(f"商品:{r['title']} 价格:{price} 匹配度:{r.get('score', 0)}")
            return "\n".join(lines)
        except Exception as e:
            return f"商品搜索失败: {e}"
    return search_product_kb


def build_search_ticket_tool(merchant_id: int):
    """搜索历史工单。tag: ticket, knowledge"""
    @langchain_tool
    def search_ticket_history(query: str) -> str:
        """搜索历史工单处理方案。返回相似工单的标题和处理方案。"""
        try:
            from app.services.chroma_client import get_collection
            from app.services.embedding import embed_query
            vec = embed_query(query)
            col = get_collection(merchant_id)
            result = col.query(query_embeddings=[vec], n_results=5,
                               where={"type": "ticket_case"})
            metas = result.get("metadatas", [[]])[0]
            docs = result.get("documents", [[]])[0]
            if not metas:
                return "暂无历史工单参考"
            lines = []
            for m, d in zip(metas, docs):
                lines.append(
                    f"标题:{m.get('title', '?')} 分类:{m.get('category', '?')} "
                    f"优先级:{m.get('priority', '?')} 状态:{m.get('status', '?')} "
                    f"描述:{d[:100]}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"工单搜索失败: {e}"
    return search_ticket_history


def build_check_logistics_tool(merchant_id: int):
    """查询物流轨迹（真实 vmall + mock 降级）。tag: logistics"""
    @langchain_tool
    def check_logistics(tracking_no: str) -> str:
        """根据快递单号查询物流轨迹。返回当前物流节点、预计送达时间和快递公司。"""
        from app.core.platform_connector.runner import run_connector

        # 尝试从 vmall 获取真实物流
        try:
            db = SessionLocal()
            shop = db.query(PlatformShop).filter(
                PlatformShop.merchant_id == merchant_id,
                PlatformShop.platform_type == "vmall",
            ).first()
            db.close()
            if shop and shop.access_token:
                from app.core.platform_connector.vmall import V3Connector
                connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
                ok, data, err = run_connector(connector.get_logistics(tracking_no))
                if ok and data:
                    return str(data)
        except Exception:
            pass

        # Mock fallback
        import random
        companies = ["顺丰速运", "中通快递", "圆通速递", "韵达快递", "京东物流"]
        nodes = ["已揽件", "运输中", "到达中转站", "到达目的地分拣中心", "派送中", "已签收"]
        return (
            f"快递:{random.choice(companies)} 单号:{tracking_no} "
            f"状态:{random.choice(nodes)} 预计{random.randint(1,5)}天 "
            f"（注：当前为Mock演示模式）"
        )
    return check_logistics


# ===== 初始化全局注册表 =====

def init_registry(merchant_id: int) -> ToolRegistry:
    """为指定商户初始化工具注册表。每次调用重新生成（工具闭包绑定 merchant_id）。"""
    registry = ToolRegistry.get()
    registry._tools.clear()
    registry._tags.clear()

    registry.register(build_query_order_tool(merchant_id), tags=["order", "query"])
    registry.register(build_check_logistics_tool(merchant_id), tags=["logistics", "query"])
    registry.register(build_search_product_tool(merchant_id), tags=["product", "knowledge", "search"])
    registry.register(build_check_inventory_tool(merchant_id), tags=["product", "inventory"])
    registry.register(build_search_ticket_tool(merchant_id), tags=["ticket", "knowledge", "search"])

    return registry
