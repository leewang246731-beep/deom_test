"""
Multi-Agent System Entry Point — SaaS v2.1.0

架构:
  create_service_agent() → 传统单 ReAct Agent (向后兼容)
  create_supervisor_agent() → Supervisor-Worker 多智能体 (NEW)
  run_agent() → 统一执行入口 (自动选择模式)
  _use_multi_agent() / _build_agent() → 单/多 Agent 二选一开关 (USE_MULTI_AGENT)
"""
import logging
import os

from langgraph.prebuilt import create_react_agent
from langchain_core.prompts import ChatPromptTemplate

from app.ai.tools import get_agent_tools
from app.services.llm import ChatDashScope


# ===== 单/多 Agent 二选一开关 =====

def _use_multi_agent() -> bool:
    """唯一开关：USE_MULTI_AGENT 环境变量，严格布尔归一化。

    仅当值为 "true" / "1" / "yes"(忽略大小写与前后空白)时判为开启;
    其余一切值(空字符串、None、拼写错误)一律判为关闭。
    """
    raw = os.getenv("USE_MULTI_AGENT", "false")
    return raw.strip().lower() in ("true", "1", "yes")


def _build_agent(merchant_id: int, role_prompt: str = ""):
    """根据 USE_MULTI_AGENT 创建 Agent 实例，保证任意时刻有且仅有一个实例。

    分支结构:
      - USE_MULTI_AGENT=true  → create_supervisor_agent (多智能体)
      - USE_MULTI_AGENT=false → create_service_agent   (单智能体, 默认)
      - 构造失败              → 自动回退到 create_service_agent + 告警日志
    """
    if _use_multi_agent():
        try:
            return create_supervisor_agent(merchant_id, role_prompt)
        except Exception as e:
            logging.warning("Supervisor 构造失败，回退单 Agent: %s", e)
    return create_service_agent(merchant_id, role_prompt)


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
        "- search_ticket_history(query): 搜索工单\n"
        "- web_search(query): 联网搜索公开信息（知识库无结果时的补充）\n\n"
        "【思维链 (CoT)】处理每个问题时，请按以下步骤思考:\n"
        "1. 分析问题：买家在问什么？需要什么信息？\n"
        "2. 确定所需：需要调用哪（几）个工具？\n"
        "3. 执行查询：调用工具获取真实数据\n"
        "4. 解读结果：工具返回了什么？有没有异常？\n"
        "5. 形成回复：用亲切自然的语言回答\n\n"
        "规则：\n"
        "- 必须先调用工具再回答。\n"
        "- 回复<200字。\n"
        "- 工具没返回的商品/订单/物流信息，绝对禁止凭空编造。\n"
        "- 所有搜索均无结果时，如实告知买家「暂未查到相关信息，建议联系人工客服」。\n"
        "- 禁止在回复中提及任何工具未返回的具体商品名、价格或订单号。"
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
