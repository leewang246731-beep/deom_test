"""
Multi-Agent System Entry Point — SaaS v2.1.0

架构:
  create_service_agent() → 传统单 ReAct Agent (向后兼容)
  create_supervisor_agent() → Supervisor-Worker 多智能体 (NEW)
  run_agent() → 统一执行入口 (自动选择模式)
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate

from app.ai.tools import get_agent_tools
from app.services.llm import ChatDashScope


# ===== 传统单 Agent (向后兼容) =====

def create_service_agent(merchant_id: int, role_prompt: str = ""):
    """创建传统单 ReAct Agent。保留向后兼容。"""
    llm = ChatDashScope()
    tools = get_agent_tools(merchant_id)

    system_prompt = (
        "你是专业电商客服助手，为客户提供准确、亲切的服务。"
        f"{role_prompt}\n"
        "你有以下工具可用:\n"
        "- query_order(query): 查询订单\n"
        "- check_logistics(tracking_no): 查询物流\n"
        "- search_product_kb(query): 搜索商品\n"
        "- check_inventory(product_id): 查库存\n"
        "- search_ticket_history(query): 搜索工单\n\n"
        "规则：必须调用工具获取真实数据。回复<200字。"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    return create_react_agent(model=llm, tools=tools, prompt=prompt)


def _run_legacy_agent(agent, question: str, chat_history: list | None = None) -> dict:
    """运行传统单 Agent (内部)。"""
    from langchain_core.messages import HumanMessage, AIMessage

    msgs = []
    if chat_history:
        for item in chat_history:
            if isinstance(item, tuple):
                role, content = item
            elif isinstance(item, dict):
                role, content = item.get("role", "user"), item.get("content", "")
            else:
                continue
            if role in ("assistant", "ai"):
                msgs.append(AIMessage(content=content))
            else:
                msgs.append(HumanMessage(content=content))

    msgs.append(HumanMessage(content=question))
    result = agent.invoke({"messages": msgs})

    output_msgs = result.get("messages", [])
    reply, steps = "", []

    for i, m in enumerate(output_msgs):
        if m.__class__.__name__ == "ToolMessage":
            tool_call = {}
            for prev in reversed(output_msgs[:i]):
                if hasattr(prev, "tool_calls") and prev.tool_calls:
                    tc_id = getattr(m, "tool_call_id", "")
                    for tc in prev.tool_calls:
                        if tc.get("id") == tc_id or not tc_id:
                            tool_call = tc; break
                    if not tool_call and prev.tool_calls:
                        tool_call = prev.tool_calls[0]
                    break
            steps.append({"tool": tool_call.get("name", "?"), "tool_input": str(tool_call.get("args", {})),
                          "observation": str(m.content)[:300]})

    for m in reversed(output_msgs):
        if m.__class__.__name__ == "AIMessage" and m.content and not (hasattr(m, "tool_calls") and m.tool_calls):
            reply = m.content; break

    if not reply and steps:
        reply = steps[-1]["observation"]
    return {"reply": reply or "已查询", "intermediate_steps": steps}


# ===== 多智能体 Supervisor (新入口) =====

def create_supervisor_agent(merchant_id: int, role_prompt: str = ""):
    """创建 Supervisor-Worker 多智能体系统。"""
    from app.ai.supervisor import SupervisorAgent
    return SupervisorAgent(merchant_id, role_prompt=role_prompt)


# ===== 统一执行入口 =====

def run_agent(agent, question: str, chat_history: list | None = None) -> dict:
    """
    统一执行入口 — 自动检测 Agent 类型:

    - SupervisorAgent → 多智能体管线 (classify → route → dispatch → aggregate)
    - LangGraph Graph (传统) → 单 Agent ReAct 执行

    Returns:
        {"reply": str, "intermediate_steps": list, "trace": list (Supervisor only)}
    """
    # 检测是否为 SupervisorAgent
    if hasattr(agent, 'process'):
        result = agent.process(question, chat_history)
        # 兼容旧接口字段
        if "intermediate_steps" not in result:
            result["intermediate_steps"] = []
        return result

    # 传统单 Agent
    return _run_legacy_agent(agent, question, chat_history)
