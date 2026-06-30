"""
Agent 工具集：5 个 @tool 供 LangChain Agent 调用。
v2: 委托到 ToolRegistry，避免工具定义重复。
"""
from app.ai.tool_registry import init_registry


def get_agent_tools(merchant_id: int) -> list:
    """返回绑定到指定商户的 Agent 工具列表（委托 ToolRegistry）。"""
    registry = init_registry(merchant_id)
    return registry.list_all()
