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


# ===== Phase C 新增业务工具 =====

def build_deliver_order_tool(merchant_id: int):
    """客服发货。tag: order, action"""
    @langchain_tool
    def deliver_order(order_id: int, company: str, tracking_no: str) -> str:
        """为订单发货。order_id为订单ID，company为快递公司，tracking_no为运单号。返回发货结果。"""
        from app.core.platform_connector.runner import run_connector

        db = SessionLocal()
        try:
            sids = _shop_ids(db, merchant_id)
            o = db.query(ExternalOrder).filter(
                ExternalOrder.id == order_id,
                ExternalOrder.shop_id.in_(sids),
            ).first() if sids else None
            if not o:
                return f"订单{order_id}不存在"
            if o.status != "paid":
                return f"订单{order_id}状态为{o.status}，只能对待付款订单发货"

            shop = db.query(PlatformShop).filter(
                PlatformShop.id == o.shop_id,
                PlatformShop.platform_type == "vmall",
            ).first()
            if shop and shop.access_token:
                from app.core.platform_connector.vmall import V3Connector
                connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
                ok, data, err = run_connector(connector.deliver_order(order_id, company, tracking_no))
                if ok:
                    o.status = "shipped"
                    db.commit()
                    return f"订单{o.id}已发货 (快递:{company} 单号:{tracking_no})"
                return f"发货失败: {err}"
            else:
                # Mock 降级
                o.status = "shipped"
                db.commit()
                return f"订单{o.id}已发货 (快递:{company} 单号:{tracking_no}) (演示模式)"
        finally:
            db.close()
    return deliver_order


def build_send_message_tool(merchant_id: int):
    """向买家发送消息。tag: message, action"""
    @langchain_tool
    def send_buyer_message(buyer_id: int, content: str) -> str:
        """向买家发送消息。buyer_id为买家ID，content为消息内容。返回发送结果。"""
        from app.core.platform_connector.runner import run_connector

        db = SessionLocal()
        try:
            shop = db.query(PlatformShop).filter(
                PlatformShop.merchant_id == merchant_id,
                PlatformShop.platform_type == "vmall",
            ).first()
            if shop and shop.access_token:
                from app.core.platform_connector.vmall import V3Connector
                connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
                ok, data, err = run_connector(
                    connector.send_notification(buyer_id, 0, content)
                )
                if ok:
                    return f"消息已发送给买家{buyer_id}"
                return f"消息发送失败: {err}"
            return f"消息已记录 (演示模式)"
        finally:
            db.close()
    return send_buyer_message


def build_create_ticket_tool(merchant_id: int):
    """创建工单。tag: ticket, action"""
    @langchain_tool
    def create_support_ticket(title: str, description: str, priority: str = "medium") -> str:
        """创建客服工单。title为标题，description为描述，priority为优先级(low/medium/high/urgent)。返回工单ID。"""
        from app.models.ticket import Ticket
        from app.models.ticket_category import TicketCategory

        db = SessionLocal()
        try:
            # 尝试自动匹配分类
            category_id = None
            cats = db.query(TicketCategory).filter(
                TicketCategory.merchant_id == merchant_id,
            ).all()
            if cats:
                category_id = cats[0].id  # 默认使用第一个分类

            ticket = Ticket(
                merchant_id=merchant_id,
                title=title,
                description=description,
                priority=priority if priority in ("low", "medium", "high", "urgent") else "medium",
                status="pending",
                category_id=category_id,
                created_at=__import__('datetime').datetime.now(),
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            return f"工单已创建 (ID:{ticket.id} 标题:{title} 优先级:{priority})"
        finally:
            db.close()
    return create_support_ticket


def build_recommend_products_tool(merchant_id: int):
    """推荐商品。tag: product, recommendation"""
    @langchain_tool
    def recommend_products(buyer_id: int = 0, query: str = "") -> str:
        """为买家推荐商品。buyer_id为买家ID（可选），query为偏好关键词（可选）。返回推荐商品列表。"""
        try:
            from app.services.recommendation import get_recommendations_for_buyer
            results = get_recommendations_for_buyer(merchant_id, buyer_id, top_k=5) if buyer_id else []
            if not results and query:
                from app.services.ai_suggest import semantic_search_products
                results = semantic_search_products(merchant_id, query, shop_ids=[], top_k=5)

            if not results:
                return "暂无推荐商品"

            lines = ["推荐商品:"]
            for i, r in enumerate(results[:5], 1):
                title = r.get("title", r.get("content", "?"))
                price = r.get("price", "暂无")
                lines.append(f"{i}. {title} (¥{price})")
            return "\n".join(lines)
        except Exception as e:
            return f"推荐服务暂时不可用: {e}"
    return recommend_products


def build_get_buyer_profile_tool(merchant_id: int):
    """查询买家画像。tag: buyer, query"""
    @langchain_tool
    def get_buyer_profile(buyer_id: int = 0, buyer_openid: str = "") -> str:
        """查询买家画像和购买历史。buyer_id为买家ID。返回累计订单、消费金额、偏好商品。"""
        from app.ai.memory import query_buyer_profile
        return query_buyer_profile(merchant_id, buyer_id, buyer_openid)
    return get_buyer_profile


def build_web_search_tool(merchant_id: int):
    """联网搜索 — 当知识库/商品库无结果时，搜索公开网页获取线索。tag: web, search, knowledge"""
    @langchain_tool
    def web_search(query: str) -> str:
        """联网搜索公开信息。query 为搜索关键词。返回网页标题和摘要。用于知识库无结果时的补充搜索。"""
        import re
        import urllib.request
        import urllib.parse
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            # 提取结果片段
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|div)>', html, re.DOTALL)
            titles = re.findall(r'class="result__title"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
            urls = re.findall(r'class="result__url"[^>]*>(.*?)</(?:a|div)>', html, re.DOTALL)
            if not snippets:
                return "未找到相关网页结果，建议尝试其他关键词或联系人工客服。"
            lines = ["以下是联网搜索结果："]
            for i in range(min(len(snippets), 5)):
                title = re.sub(r'<[^>]+>', '', titles[i] if i < len(titles) else '').strip() or "(无标题)"
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()[:250]
                lines.append(f"[{i+1}] {title}\n   摘要: {snippet}")
            return "\n\n".join(lines)
        except Exception as e:
            return f"联网搜索暂时不可用 ({e})，建议基于已有知识库回复或转人工。"
    return web_search


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
    # Phase C 新增业务工具
    registry.register(build_deliver_order_tool(merchant_id), tags=["order", "action"])
    registry.register(build_send_message_tool(merchant_id), tags=["message", "action"])
    registry.register(build_create_ticket_tool(merchant_id), tags=["ticket", "action"])
    registry.register(build_recommend_products_tool(merchant_id), tags=["product", "recommendation"])
    registry.register(build_get_buyer_profile_tool(merchant_id), tags=["buyer", "query"])
    registry.register(build_web_search_tool(merchant_id), tags=["web", "search", "knowledge"])

    # 优惠券工具
    from app.ai.coupon_tools import build_compensate_tool, build_issue_promo_tool, build_list_promos_tool
    registry.register(build_compensate_tool(merchant_id), tags=["coupon", "action", "compensation"])
    registry.register(build_issue_promo_tool(merchant_id), tags=["coupon", "action", "marketing"])
    registry.register(build_list_promos_tool(merchant_id), tags=["coupon", "query", "marketing"])

    # 增强推荐 + 画像工具
    from app.ai.recommend_tools import (
        build_recommend_tool,
        build_update_fact_tool,
        build_compress_memory_tool,
        build_profile_summary_tool,
    )
    registry.register(build_recommend_tool(merchant_id), tags=["product", "recommendation", "profile"])
    registry.register(build_update_fact_tool(merchant_id), tags=["profile", "action"])
    registry.register(build_compress_memory_tool(merchant_id), tags=["profile", "memory", "action"])
    registry.register(build_profile_summary_tool(merchant_id), tags=["profile", "query"])

    # 付款链接工具
    from app.ai.payment_tools import build_generate_payment_link_tool
    registry.register(build_generate_payment_link_tool(merchant_id), tags=["payment", "action", "order"])

    return registry
