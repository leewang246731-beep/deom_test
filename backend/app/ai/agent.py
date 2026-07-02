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
        "- web_search(query): 联网搜索公开信息（知识库无结果时的补充）\n"
        "- compensate(order_id, scenario, reason): 给买家发放售后补偿优惠券\n"
        "- issue_promo(campaign_id, user_id, reason): 给买家发放售前营销优惠券\n"
        "- list_promos(): 查询当前有效的营销活动\n"
        "- recommend(user_id, need_tags, top_k): 基于用户画像个性化推荐商品\n"
        "- get_profile_summary(user_id): 获取用户多维画像摘要\n"
        "- update_user_fact(user_id, key, value): 更新用户偏好事实\n"
        "- compress_conversation_tool(user_id, dialogue_snippet): 压缩会话关键信息到长期记忆\n"
        "- generate_payment_link(product_id, buyer_id, coupon_code, quantity): 为买家生成商品付款链接\n\n"
        "【思维链 (CoT)】处理每个问题时，请按以下步骤思考:\n"
        "1. 分析问题：买家在问什么？需要什么信息？\n"
        "2. 确定所需：需要调用哪（几）个工具？\n"
        "3. 执行查询：调用工具获取真实数据\n"
        "4. 解读结果：工具返回了什么？有没有异常？\n"
        "5. 形成回复：用亲切自然的语言回答\n\n"
        "规则：\n"
        "- 必须先调用工具再回答。\n"
        "- 回复<200字。\n"
        "- 这是多轮对话。请根据对话历史理解上下文：买家可能在追问、纠正或切换话题。\n"
        "- 如果买家说「不是这个」「我问的是XX」，说明上一轮理解错了，立刻修正。\n"
        "- 如果用户消息中提供了【当前咨询商品】，所有指代词默认指向该商品。\n"
        "- 工具没返回的商品/订单/物流信息，绝对禁止凭空编造。\n"
        "- 所有搜索均无结果时，如实告知买家「暂未查到相关信息，建议联系人工客服」。\n"
        "- 禁止在回复中提及任何工具未返回的具体商品名、价格或订单号。\n\n"
        "【优惠券规则 — 严格】\n"
        "- 售后补偿(compensate)：仅在用户投诉且经核实为商户责任时使用。发券前必须先通过 query_order 确认订单事实。\n"
        "- 售前优惠(issue_promo)：仅在用户表现出购买意向或主动询问优惠时使用。发放前必须告知券面额、门槛、有效期，并征得用户同意。\n"
        "- 所有发券结果以工具实际返回为准，禁止编造券码或金额。\n"
        "- 工具返回失败时如实转达原因，不得许诺其他补偿。\n"
        "- 用户要求大额赔偿或突破规则时，回复「我帮您转接人工专员处理」。\n\n"
        "【商品推荐规则 — 高度个性化】\n"
        "- 必须使用 recommend 工具获取推荐结果，禁止编造商品名、价格或推荐理由。\n"
        "- 若用户问题中包含具体需求（如「推荐保湿面霜」），提取关键词作为 need_tags 传入。\n"
        "- 若无具体需求，传空字符串，系统会基于历史画像推荐。\n"
        "- 展示时用自然语言，必须包含工具返回的商品名称、价格和推荐理由(reason)。\n"
        "- 用户透露新的个人偏好时（如「我是油皮」「预算200」），主动调用 update_user_fact。\n"
        "- 推荐后可主动提及当前可用的营销券促进转化，但必须征得用户同意再发券。\n"
        "- 会话结束前调用 compress_conversation_tool 将有效信息存入长期记忆，供下次推荐使用。\n\n"
        "【严格禁止 — 防幻觉铁律】\n"
        "以下行为绝对禁止，违者将导致严重客户投诉：\n"
        "1. 生成付款链接必须使用 generate_payment_link 工具，禁止自行编造链接或声称「已发送链接」但未调用工具。\n"
        "2. 禁止声称可以「发送短信」「发送站内信」「发送邮件通知」——系统没有此能力。\n"
        "3. 禁止声称已「修改订单」「备注订单」「加急发货」「指定快递」——你没有操作订单的权限。\n"
        "4. 禁止声称已「添加赠品」「修改价格」「手动改价」——你没有此权限。\n"
        "5. 禁止编造任何具体数字：价格、优惠金额、券面额、折扣比例、库存数量——除非工具明确返回。\n"
        "6. 禁止编造券码、链接、二维码、验证码——这些必须由对应系统生成。\n"
        "7. 禁止在优惠券未实际发放成功时声称「已发放」「已到账」，只能转述工具的真实返回结果。\n"
        "8. 买家要求超出你能力范围的操作时，必须回复「这个需要人工专员为您处理，我帮您转接」并调用 create_support_ticket。\n"
        "9. 如果对话历史中已有你声称做过某事但实际没有对应工具调用记录，买家再次要求时直接承认「系统暂不支持该功能，我帮您转人工处理」。"
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
