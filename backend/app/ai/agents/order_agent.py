"""OrderAgent — 订单查询与售后处理专家（v2: 用 ToolRegistry 消除工具重复）"""
from app.ai.agents.base_agent import BaseExpertAgent
from app.ai.tool_registry import ToolRegistry
from app.database.session import SessionLocal
from app.models.external_order import ExternalOrder
from app.models.platform_shop import PlatformShop
from langchain_core.tools import tool


class OrderAgent(BaseExpertAgent):
    name = "order"
    description = "订单查询、退款处理、催付话术"

    def _build_tools(self) -> list:
        mid = self.merchant_id
        registry = ToolRegistry.get()

        # 从 registry 获取 query_order（消除与 tools.py 的重复）
        query_tool = registry.get_tool("query_order")
        tools = [query_tool] if query_tool else []

        @tool
        def process_refund(order_id: int) -> str:
            """处理订单退款。order_id 为订单数字ID。返回退款结果。"""
            db = SessionLocal()
            try:
                sids = [r[0] for r in db.query(PlatformShop.id).filter(PlatformShop.merchant_id == mid).all()]
                o = db.query(ExternalOrder).filter(
                    ExternalOrder.id == order_id, ExternalOrder.shop_id.in_(sids)
                ).first() if sids else None
                if not o: return f"订单{order_id}不存在"
                if o.status in ("refunded", "refunding"): return f"订单{o.id}已在售后流程"
                o.status = "refunded"
                db.commit()
                return f"订单{o.id}已退款成功 (金额:¥{float(o.pay_amount):.2f})"
            finally:
                db.close()

        tools.append(process_refund)
        return tools

    def _build_prompt(self) -> str:
        return f"""你是电商订单处理专家。你可以：
1. 查询订单（按订单号、买家昵称、订单ID）
2. 处理退款

{self.role_prompt}
规则：必须调用工具获取真实数据。回复简洁（<200字）。"""
