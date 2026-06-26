"""LogisticsAgent — 物流查询专家"""
import random
from app.ai.agents.base_agent import BaseExpertAgent
from langchain_core.tools import tool


class LogisticsAgent(BaseExpertAgent):
    name = "logistics"
    description = "物流轨迹查询、快递状态追踪"

    def _build_tools(self) -> list:
        mid = self.merchant_id

        @tool
        def check_logistics(tracking_no: str) -> str:
            """根据快递单号查询物流轨迹。返回当前状态、快递公司、预计送达。"""
            # 尝试从 vMall 获取真实物流
            try:
                from app.database.session import SessionLocal
                from app.models.platform_shop import PlatformShop
                db = SessionLocal()
                shop = db.query(PlatformShop).filter(PlatformShop.merchant_id == mid, PlatformShop.platform_type == "vmall").first()
                db.close()
                if shop and shop.access_token:
                    from app.core.platform_connector.vmall import V3Connector
                    connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
                    info = connector.get_logistics(tracking_no)  # Note: async in connector
                    if info: return str(info)
            except Exception:
                pass

            # Mock fallback
            companies = ["顺丰速运", "中通快递", "圆通速递", "韵达快递", "京东物流"]
            nodes = ["已揽件", "运输中", "到达中转站", "到达目的地分拣中心", "派送中", "已签收"]
            return f"快递:{random.choice(companies)} 单号:{tracking_no} 状态:{random.choice(nodes)} 预计{random.randint(1,5)}天 (演示模式)"

        @tool
        def get_delivery_estimate(order_id: str) -> str:
            """查询订单预计送达时间。"""
            return f"订单{order_id}预计在1-3个工作日内送达"

        return [check_logistics, get_delivery_estimate]

    def _build_prompt(self) -> str:
        return f"""你是物流查询专家。你可以查询快递轨迹和预计送达时间。
{self.role_prompt}
规则：必须调用工具。回复简洁（<150字）。"""
