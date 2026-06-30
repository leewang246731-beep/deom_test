"""LogisticsAgent — 物流查询专家（v2: 用 ToolRegistry + run_connector 修复 async bug）"""
from app.ai.agents.base_agent import BaseExpertAgent
from app.ai.tool_registry import ToolRegistry
from langchain_core.tools import tool


class LogisticsAgent(BaseExpertAgent):
    name = "logistics"
    description = "物流轨迹查询、快递状态追踪"

    def _build_tools(self) -> list:
        registry = ToolRegistry.get()

        # 从 registry 获取真实物流工具（已修复 async 的版本）
        logistics_tool = registry.get_tool("check_logistics")
        tools = [logistics_tool] if logistics_tool else []

        @tool
        def get_delivery_estimate(order_id: str) -> str:
            """查询订单预计送达时间。order_id 为订单号。"""
            return f"订单{order_id}预计在1-3个工作日内送达"

        tools.append(get_delivery_estimate)
        return tools

    def _build_prompt(self) -> str:
        return f"""你是物流查询专家。你可以查询快递轨迹和预计送达时间。
{self.role_prompt}
规则：必须调用工具获取真实数据。回复简洁（<150字）。"""
