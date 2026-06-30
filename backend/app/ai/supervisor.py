"""
SupervisorAgent — 主管-专家协作架构

LangGraph StateGraph 实现:
  1. Intent Classification (意图识别) → 决定路由到哪些专家
  2. Task Dispatch (任务分发) → 并行/串行调用专家
  3. Result Aggregation (结果聚合) → ReplyAgent 合成最终回复

State 定义:
  question: str          - 原始买家问题
  intent: str            - 识别到的意图
  routed_experts: list   - 被路由到的专家列表
  expert_results: dict   - {expert_name: result}
  final_reply: str       - 最终回复
  trace: list            - 全链路追踪日志
"""
from typing import TypedDict, Annotated, Sequence
import operator
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage


# ===== State 定义 =====
class SupervisorState(TypedDict):
    question: str
    chat_history: list
    intent: str
    intents: list  # 多意图
    routed_experts: list
    expert_results: dict
    final_reply: str
    final_confidence: float
    replan_count: int  # 重规划次数
    trace: Annotated[list, operator.add]  # append-only


# ===== 意图分类规则 =====
INTENT_RULES = {
    "order": {
        "keywords": ["订单", "买", "拍了", "支付", "付款", "退款", "退货", "售后", "多少钱", "金额", "order", "refund"],
        "expert": "order",
    },
    "logistics": {
        "keywords": ["物流", "快递", "发货", "到哪", "运输", "配送", "收货", "单号", "tracking", "logistics", "shipping"],
        "expert": "logistics",
    },
    "product": {
        "keywords": ["商品", "产品", "有货", "库存", "价格", "推荐", "哪个好", "有什么", "product", "inventory"],
        "expert": "product",
    },
    "ticket": {
        "keywords": ["工单", "投诉", "问题", "处理", "进展", "ticket"],
        "expert": "ticket",
    },
    "knowledge": {
        "keywords": ["怎么", "如何", "为什么", "是什么", "教程", "说明", "文档", "帮助", "how", "what", "why"],
        "expert": "rag",
    },
}


class SupervisorAgent:
    """主管 Agent — 意图分类 + 任务分发 + 结果聚合。"""

    def __init__(self, merchant_id: int, llm=None, role_prompt: str = ""):
        self.merchant_id = merchant_id
        self.role_prompt = role_prompt

        # Lazy init LLM
        if llm is None:
            from app.services.llm import ChatDashScope
            llm = ChatDashScope()
        self.llm = llm

    # ===== 节点函数 =====

    def classify_intent(self, state: SupervisorState) -> SupervisorState:
        """节点 1: 意图分类 — 规则 + LLM 双重判断。"""
        question = state["question"]
        trace_entry = {"ts": datetime.now().isoformat(), "node": "classify_intent", "question": question[:100]}
        matched = []

        for intent_name, rule in INTENT_RULES.items():
            if any(kw in question.lower() for kw in rule["keywords"]):
                matched.append(intent_name)

        if not matched:
            # 无关键词匹配 → 使用 LLM 进行意图分类
            try:
                prompt = f"""分析以下买家问题的意图，从以下类别中选择（可多选）：
order(订单), logistics(物流), product(商品), ticket(工单), knowledge(知识库)

只输出类别名，用逗号分隔。例如: "order,logistics"

买家问题: {question[:200]}"""
                response = self.llm.invoke([{"role": "user", "content": prompt}])
                text = response.content if hasattr(response, 'content') else str(response)
                matched = [i.strip() for i in text.split(",") if i.strip() in INTENT_RULES]
            except Exception:
                matched = ["knowledge"]  # 默认走知识库

        intents = matched if matched else ["knowledge"]
        trace_entry["intents"] = intents
        state["intents"] = intents
        state["intent"] = intents[0]  # 主意图
        state["trace"].append(trace_entry)

        return state

    def route_experts(self, state: SupervisorState) -> SupervisorState:
        """节点 2: 根据意图路由到专家。"""
        intents = state["intents"]
        experts = []
        seen = set()
        for intent in intents:
            rule = INTENT_RULES.get(intent)
            if rule:
                expert = rule["expert"]
                if expert not in seen:
                    experts.append(expert)
                    seen.add(expert)

        state["routed_experts"] = experts
        state["trace"].append({
            "ts": datetime.now().isoformat(), "node": "route_experts",
            "intents": intents, "routed": experts,
        })
        return state

    def dispatch_experts(self, state: SupervisorState) -> SupervisorState:
        """节点 3: 串行执行专家（可升级为并行）。传递 chat_history 给子 Agent。"""
        question = state["question"]
        chat_history = state.get("chat_history", [])
        experts = state["routed_experts"]
        results = {}

        for expert_name in experts:
            try:
                agent = self._get_expert(expert_name)
                result = agent.process(question, context={"chat_history": chat_history})
                results[expert_name] = result
                state["trace"].append({
                    "ts": datetime.now().isoformat(), "node": f"expert_{expert_name}",
                    "steps": result.get("steps", []),
                    "reply_preview": result.get("reply", "")[:100],
                })
            except Exception as e:
                results[expert_name] = {"reply": f"专家{expert_name}调用失败: {e}", "steps": [], "confidence": 0.0}
                state["trace"].append({
                    "ts": datetime.now().isoformat(), "node": f"expert_{expert_name}",
                    "error": str(e),
                })

        state["expert_results"] = results
        return state

    def aggregate_reply(self, state: SupervisorState) -> SupervisorState:
        """节点 4: 聚合专家结果 → 生成最终回复。"""
        from app.ai.agents.reply_agent import ReplyAgent

        reply_agent = ReplyAgent(self.merchant_id, self.llm, self.role_prompt)
        result = reply_agent.synthesize(state["question"], state["expert_results"])

        state["final_reply"] = result["reply"]
        state["final_confidence"] = result["confidence"]
        state["trace"].append({
            "ts": datetime.now().isoformat(), "node": "aggregate_reply",
            "confidence": result["confidence"],
            "sources": result.get("sources", []),
        })
        return state

    def replan_check(self, state: SupervisorState) -> SupervisorState:
        """节点 3.5: 检查专家结果质量 → 决定是否需要重规划。"""
        results = state.get("expert_results", {})
        if not results:
            state["trace"].append({"ts": datetime.now().isoformat(), "node": "replan",
                                    "decision": "skip", "reason": "no expert results"})
            return state

        # 判断是否有有效结果
        has_useful = False
        for name, result in results.items():
            reply = result.get("reply", "") if result else ""
            confidence = result.get("confidence", 0) if result else 0
            if reply and "无法处理" not in str(reply) and "异常" not in str(reply) and confidence > 0:
                has_useful = True
                break

        if not has_useful and state.get("replan_count", 0) < 1:
            # 首轮无有效结果 → 触发一次重规划（降级到 knowledge 专家）
            state["replan_count"] = state.get("replan_count", 0) + 1
            state["intents"] = ["knowledge"]
            state["routed_experts"] = ["rag"]
            state["trace"].append({"ts": datetime.now().isoformat(), "node": "replan",
                                    "decision": "retry_knowledge", "reason": "no useful expert results"})
            # 重新执行专家调度
            return self.dispatch_experts(state)

        state["trace"].append({"ts": datetime.now().isoformat(), "node": "replan",
                                "decision": "proceed", "has_useful": has_useful})
        return state

    # ===== 管线构建 =====

    def build_graph(self):
        """构建 LangGraph StateGraph（含 RePlan 节点）。"""
        workflow = StateGraph(SupervisorState)

        # 添加节点
        workflow.add_node("classify_intent", self.classify_intent)
        workflow.add_node("route_experts", self.route_experts)
        workflow.add_node("dispatch_experts", self.dispatch_experts)
        workflow.add_node("replan_check", self.replan_check)
        workflow.add_node("aggregate_reply", self.aggregate_reply)

        # 定义流程: classify → route → dispatch → replan → aggregate
        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "route_experts")
        workflow.add_edge("route_experts", "dispatch_experts")
        workflow.add_edge("dispatch_experts", "replan_check")
        workflow.add_edge("replan_check", "aggregate_reply")
        workflow.add_edge("aggregate_reply", END)

        return workflow.compile()

    # ===== 公开接口 =====

    def process(self, question: str, chat_history: list = None) -> dict:
        """
        主管处理入口：意图分类 → 路由 → 专家执行 → 聚合回复。

        Returns:
            {
                "reply": str,           # 最终回复文本
                "confidence": float,    # 置信度
                "intents": list,        # 识别到的意图
                "expert_results": dict, # 各专家原始结果
                "trace": list,          # 全链路追踪日志
            }
        """
        graph = self.build_graph()
        initial_state: SupervisorState = {
            "question": question,
            "chat_history": chat_history or [],
            "intent": "",
            "intents": [],
            "routed_experts": [],
            "expert_results": {},
            "final_reply": "",
            "final_confidence": 0.0,
            "replan_count": 0,
            "trace": [],
        }

        try:
            final_state = graph.invoke(initial_state)
        except Exception as e:
            # 图执行失败 → 降级到单 Agent 模式
            return {
                "reply": f"系统繁忙，请稍后重试",
                "confidence": 0.0,
                "intents": [],
                "expert_results": {},
                "trace": [{"error": str(e), "fallback": True}],
                "intermediate_steps": [],
            }

        return {
            "reply": final_state["final_reply"],
            "confidence": final_state["final_confidence"],
            "intents": final_state["intents"],
            "expert_results": final_state.get("expert_results", {}),
            "trace": final_state["trace"],
            # 向后兼容 agent.py 接口
            "intermediate_steps": [
                {"tool": t.get("node", "?"), "tool_input": {}, "observation": t.get("reply_preview", "")}
                for t in final_state["trace"]
                if "reply_preview" in t or "error" in t
            ],
        }

    # ===== 内部方法 =====

    def _get_expert(self, name: str):
        """懒加载专家实例。"""
        expert_map = {
            "order": lambda: __import__('app.ai.agents.order_agent', fromlist=['OrderAgent']).OrderAgent(self.merchant_id, self.llm, self.role_prompt),
            "logistics": lambda: __import__('app.ai.agents.logistics_agent', fromlist=['LogisticsAgent']).LogisticsAgent(self.merchant_id, self.llm, self.role_prompt),
            "product": lambda: __import__('app.ai.agents.product_agent', fromlist=['ProductAgent']).ProductAgent(self.merchant_id, self.llm, self.role_prompt),
            "ticket": lambda: __import__('app.ai.agents.ticket_agent', fromlist=['TicketAgent']).TicketAgent(self.merchant_id, self.llm, self.role_prompt),
            "rag": lambda: __import__('app.ai.agents.rag_agent', fromlist=['RAGAgent']).RAGAgent(self.merchant_id, self.llm, self.role_prompt),
        }
        factory = expert_map.get(name)
        if factory:
            return factory()
        # 默认使用 RAG Agent
        return __import__('app.ai.agents.rag_agent', fromlist=['RAGAgent']).RAGAgent(self.merchant_id, self.llm, self.role_prompt)
