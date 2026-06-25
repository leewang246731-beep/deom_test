"""
Agent 工具集：5 个 @tool 供 LangChain Agent 调用。
每个工具通过 merchant_id 闭包获取数据，自管理 DB session。
"""
from langchain_core.tools import tool

from app.database.session import SessionLocal
from app.models.external_order import ExternalOrder
from app.models.external_product import ExternalProduct
from app.models.platform_shop import PlatformShop


def get_agent_tools(merchant_id: int) -> list:
    """返回绑定到指定商户的 Agent 工具列表。"""

    def _shop_ids(db):
        return [r[0] for r in db.query(PlatformShop.id).filter(
            PlatformShop.merchant_id == merchant_id).all()]

    @tool
    def query_order(query: str) -> str:
        """根据订单号或买家昵称查询订单状态。query 可以是平台订单号、买家昵称或订单ID。返回订单详情包括状态、金额、收货地址。"""
        db = SessionLocal()
        try:
            sids = _shop_ids(db)
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

    @tool
    def check_logistics(tracking_no: str) -> str:
        """根据快递单号查询物流轨迹。返回当前物流节点、预计送达时间和快递公司。"""
        # Mock 模式：返回模拟物流数据
        import random
        companies = ["顺丰速运", "中通快递", "圆通速递", "韵达快递", "京东物流"]
        nodes = [
            "已揽件", "运输中", "到达中转站", "到达目的地分拣中心",
            "派送中", "已签收",
        ]
        company = random.choice(companies)
        node = random.choice(nodes)
        days = random.randint(1, 5)
        return (
            f"快递公司:{company} 单号:{tracking_no} "
            f"当前状态:{node} 预计{'-'.join(str(days) for _ in [1])}天送达 "
            f"（注：当前为Mock演示模式）"
        )

    @tool
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

    @tool
    def check_inventory(product_id: int) -> str:
        """查询商品库存。product_id 为商品数字ID。返回标题、库存量和上下架状态。"""
        db = SessionLocal()
        try:
            sids = _shop_ids(db)
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

    @tool
    def search_ticket_history(query: str) -> str:
        """搜索历史工单处理方案。query 为问题描述关键词。返回相似工单的标题和处理方案。"""
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

    return [
        query_order,
        check_logistics,
        search_product_kb,
        check_inventory,
        search_ticket_history,
    ]
