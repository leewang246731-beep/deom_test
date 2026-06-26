"""OrderAgent — 订单查询与售后处理专家"""
from app.ai.agents.base_agent import BaseExpertAgent
from app.database.session import SessionLocal
from app.models.external_order import ExternalOrder
from app.models.platform_shop import PlatformShop
from langchain_core.tools import tool


class OrderAgent(BaseExpertAgent):
    name = "order"
    description = "订单查询、退款处理、催付话术"

    def _build_tools(self) -> list:
        mid = self.merchant_id

        @tool
        def query_order(query: str) -> str:
            """根据订单号(数字)、买家昵称或订单ID查询订单。返回订单详情。"""
            db = SessionLocal()
            try:
                sids = [r[0] for r in db.query(PlatformShop.id).filter(PlatformShop.merchant_id == mid).all()]
                if not sids: return "该商户暂无店铺"
                q = db.query(ExternalOrder).filter(ExternalOrder.shop_id.in_(sids))
                if query.isdigit():
                    q = q.filter((ExternalOrder.id == int(query)) | (ExternalOrder.platform_order_id == query))
                else:
                    q = q.filter(ExternalOrder.buyer_nick.like(f"%{query}%"))
                orders = q.order_by(ExternalOrder.created_at.desc()).limit(5).all()
                if not orders: return f"未找到与'{query}'相关的订单"
                lines = [f"订单ID:{o.id} 号:{o.platform_order_id} 买家:{o.buyer_nick} 金额:¥{float(o.pay_amount):.2f} 状态:{o.status} 地址:{o.receiver_address or '无'}" for o in orders]
                return "\n".join(lines)
            finally:
                db.close()

        @tool
        def process_refund(order_id: int) -> str:
            """处理订单退款。order_id 为订单数字ID。返回退款结果。"""
            db = SessionLocal()
            try:
                sids = [r[0] for r in db.query(PlatformShop.id).filter(PlatformShop.merchant_id == mid).all()]
                o = db.query(ExternalOrder).filter(ExternalOrder.id == order_id, ExternalOrder.shop_id.in_(sids)).first() if sids else None
                if not o: return f"订单{order_id}不存在"
                if o.status in ("refunded", "refunding"): return f"订单{o.id}已在售后流程"
                o.status = "refunded"
                db.commit()
                return f"订单{o.id}已退款成功 (金额:¥{float(o.pay_amount):.2f})"
            finally:
                db.close()

        return [query_order, process_refund]

    def _build_prompt(self) -> str:
        return f"""你是电商订单处理专家。你可以：
1. 查询订单（按订单号、买家昵称、订单ID）
2. 处理退款

{self.role_prompt}
规则：必须调用工具获取真实数据。回复简洁（<200字）。"""
