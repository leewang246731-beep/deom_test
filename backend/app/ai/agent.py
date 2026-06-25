"""
LangChain Agent 工厂：langgraph create_react_agent。
"""
from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate

from app.ai.tools import get_agent_tools
from app.services.llm import ChatDashScope


def create_service_agent(merchant_id: int, role_prompt: str = ""):
    """创建客服 Agent，绑定商户工具 + 角色 Prompt。"""
    llm = ChatDashScope()
    tools = get_agent_tools(merchant_id)

    system_prompt = (
        "你是专业电商客服助手，为客户提供准确、亲切的服务。"
        f"{role_prompt}\n"
        "你有以下工具可用，遇到物流/订单/库存/售后问题时请主动调用：\n"
        "- query_order(query): 查询订单状态。query 是订单号、订单ID或买家昵称\n"
        "- check_logistics(tracking_no): 查询物流轨迹\n"
        "- search_product_kb(query): 搜索商品信息\n"
        "- check_inventory(product_id): 查询商品库存\n"
        "- search_ticket_history(query): 搜索历史工单处理方案\n\n"
        "规则：\n"
        "1. 买家问物流/订单时，必须调用工具获取真实信息再回复\n"
        "2. 回复语气亲切自然，每条不超过200字\n"
        "3. 工具返回'未找到'时诚实告知，建议联系人工客服"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{messages}"),
    ])

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=prompt,
    )


def run_agent(agent, question: str, chat_history: list | None = None) -> dict:
    """运行 Agent 并返回结构化结果。"""
    from langchain_core.messages import HumanMessage

    msgs = []
    if chat_history:
        for item in chat_history:
            if isinstance(item, tuple):
                role, content = item
            elif isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", "")
            else:
                continue
            if role in ("assistant", "ai"):
                from langchain_core.messages import AIMessage as AIm
                msgs.append(AIm(content=content))
            else:
                msgs.append(HumanMessage(content=content))

    msgs.append(HumanMessage(content=question))
    result = agent.invoke({"messages": msgs})

    output_msgs = result.get("messages", [])
    reply = ""
    steps = []

    for i, m in enumerate(output_msgs):
        cls_name = m.__class__.__name__
        if cls_name == "ToolMessage":
            # Find the preceding AIMessage with tool_calls
            tool_call = {}
            for prev in reversed(output_msgs[:i]):
                if hasattr(prev, "tool_calls") and prev.tool_calls:
                    # Match by tool_call_id
                    tc_id = getattr(m, "tool_call_id", "")
                    for tc in prev.tool_calls:
                        if tc.get("id") == tc_id or not tc_id:
                            tool_call = tc
                            break
                    if not tool_call and prev.tool_calls:
                        tool_call = prev.tool_calls[0]
                    break
            steps.append({
                "tool": tool_call.get("name", "unknown"),
                "tool_input": str(tool_call.get("args", {})),
                "observation": str(m.content)[:300],
            })

    # Extract final AIMessage reply (after all tool calls)
    for m in reversed(output_msgs):
        cls_name = m.__class__.__name__
        content = str(m.content) if hasattr(m, "content") and m.content else ""
        has_tool_calls = hasattr(m, "tool_calls") and m.tool_calls
        if cls_name == "AIMessage" and content and not has_tool_calls:
            reply = content
            break

    if not reply and steps:
        # Fallback: use last tool observation as reply
        reply = steps[-1]["observation"] if steps else "已为您查询相关信息。"

    return {"reply": reply, "intermediate_steps": steps}
