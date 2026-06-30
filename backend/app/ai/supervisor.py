"""
SupervisorAgent — 主管-专家协作架构 (v3: LLM Structured Output + DAG + Clarify)

LangGraph StateGraph 实现:
  1. Intent Classification (意图识别) → LLM Structured Output 替代关键词
  2. Task Planning (任务规划) → 生成带依赖的 DAG 执行计划
  3. Task Dispatch (任务分发) → 按 DAG 串行/并行调用专家
  4. Result Aggregation (结果聚合) → ReplyAgent 合成最终回复
  5. Clarify Check (澄清检查) → 低置信度时生成追问

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
    plan: list  # LLM 生成的执行计划 (E.1)
    routed_experts: list
    expert_results: dict
    final_reply: str
    final_confidence: float
    needs_clarification: bool  # 是否需要追问买家 (E.3)
    clarification_question: str  # 追问内容
    replan_count: int  # 重规划次数
    trace: Annotated[list, operator.add]  # append-only


# ===== LLM Structured Output 规划 (E.1) =====

PLANNING_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_clarification": {
            "type": "boolean",
            "description": "问题是否过于模糊，需要反问买家澄清"
        },
        "clarification_question": {
            "type": "string",
            "description": "如果需要澄清，生成的追问"
        },
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "expert": {"type": "string", "enum": ["order", "logistics", "product", "ticket", "rag", "web"]},
                    "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                    "depends_on": {"type": "array", "items": {"type": "string"},
                                   "description": "依赖的前置专家名（空数组=可并行）"},
                    "reason": {"type": "string", "description": "为什么需要这个专家"},
                },
                "required": ["expert", "priority", "depends_on"],
            },
            "description": "需要调用的专家列表（按依赖排序）",
        },
    },
    "required": ["needs_clarification", "tasks"],
}

PLANNING_PROMPT = """你是电商客服任务规划器。分析买家问题，输出执行计划。

可用专家:
- order: 订单查询、退款处理
- logistics: 物流轨迹查询
- product: 商品搜索、库存、推荐
- ticket: 工单查询和创建
- rag: 通用知识库检索
- web: 联网搜索公开信息（知识库无结果时的补充源）

规则:
1. 如果问题模糊（无法确定意图），设置 needs_clarification=true 并给出追问
2. 如果有多个步骤有依赖关系（如先查订单才能查物流），在 depends_on 中标明
3. 独立任务可以并行（depends_on=[]）
4. priority 1=最高, 5=最低

输出 JSON（严格按 schema）。"""


# ===== 意图分类规则 (fallback) =====
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
    "web": {
        "keywords": ["搜索", "查一下", "网上", "百度", "谷歌", "最新", "新闻", "评价", "测评", "图片", "识别", "search", "review"],
        "expert": "web",
    },
}


class SupervisorAgent:
    """主管 Agent — 意图分类 + 任务分发 + 结果聚合。"""

    def __init__(self, merchant_id: int, llm=None, role_prompt: str = ""):
        self.merchant_id = merchant_id
        self.role_prompt = role_prompt
        # 确保 ToolRegistry 已初始化（OrderAgent/LogisticsAgent 依赖共享工具）
        from app.ai.tool_registry import init_registry
        init_registry(merchant_id)

        # Lazy init LLM
        if llm is None:
            from app.services.llm import ChatDashScope
            llm = ChatDashScope()
        self.llm = llm

    # ===== 节点函数 =====

    def classify_intent(self, state: SupervisorState) -> SupervisorState:
        """节点 1: 意图分类 — LLM Structured Output (E.1) + 关键词 fallback。"""
        question = state["question"]
        trace_entry = {"ts": datetime.now().isoformat(), "node": "classify_intent", "question": question[:100]}
        matched = []

        # E.1: 尝试 LLM Structured Output 规划
        try:
            import json as _json
            from langchain_core.messages import SystemMessage, HumanMessage
            schema_str = _json.dumps(PLANNING_SCHEMA, ensure_ascii=False)
            llm_prompt = f"{PLANNING_PROMPT}\n\n买家问题: {question[:300]}\n\nJSON Schema:\n{schema_str}"
            response = self.llm.invoke([SystemMessage(content=llm_prompt)])
            text = response.content if hasattr(response, 'content') else str(response)
            # 提取 JSON（可能被 markdown 包裹）
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            plan = _json.loads(text.strip())

            if plan.get("needs_clarification"):
                state["needs_clarification"] = True
                state["clarification_question"] = plan.get("clarification_question", "能再详细描述一下您的问题吗？")
                trace_entry["clarification"] = state["clarification_question"]

            tasks = plan.get("tasks", [])
            if tasks:
                # 按依赖排序：先执行无依赖的，再执行有依赖的
                state["plan"] = tasks
                for t in tasks:
                    expert = t.get("expert", "")
                    if expert not in matched:
                        matched.append(expert)
                trace_entry["planner"] = "llm_structured"
        except Exception:
            pass  # LLM 规划失败 → 降级到关键词

        # Fallback: 关键词匹配
        if not matched:
            for intent_name, rule in INTENT_RULES.items():
                if any(kw in question.lower() for kw in rule["keywords"]):
                    matched.append(intent_name)
            if not matched:
                # LLM 意图分类
                try:
                    prompt = f"""分析以下买家问题的意图，从以下类别中选择（可多选）：
order(订单), logistics(物流), product(商品), ticket(工单), knowledge(知识库)

只输出类别名，用逗号分隔。例如: "order,logistics"

买家问题: {question[:200]}"""
                    response = self.llm.invoke([{"role": "user", "content": prompt}])
                    text = response.content if hasattr(response, 'content') else str(response)
                    matched = [i.strip() for i in text.split(",") if i.strip() in INTENT_RULES]
                except Exception:
                    matched = ["knowledge"]
            trace_entry["planner"] = "keyword_fallback"

        intents = matched if matched else ["knowledge"]
        trace_entry["intents"] = intents

        # D.3: 查询执行记忆
        try:
            from app.ai.memory import recall_best_strategy
            best = recall_best_strategy(self.merchant_id, question)
            if best:
                trace_entry["strategy_hint"] = best
        except Exception:
            pass

        state["intents"] = intents
        state["intent"] = intents[0]
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
        """节点 3: DAG 调度 (E.2)。优先执行无依赖专家，串行依赖链。"""
        question = state["question"]
        chat_history = state.get("chat_history", [])
        plan = state.get("plan", [])
        results = {}

        if plan:
            # DAG 模式：按依赖拓扑排序执行
            completed = set()
            pending = list(plan)
            prev_result = None

            while pending:
                # 找到已完成依赖的任务
                ready = [t for t in pending
                         if all(d in completed for d in t.get("depends_on", []))]
                if not ready:
                    # 死锁降级：执行所有剩余
                    ready = pending

                for task in ready[:3]:  # 最多 3 个并行
                    expert_name = task["expert"]
                    if expert_name in results:
                        continue
                    try:
                        ctx = {"chat_history": chat_history}
                        if task.get("depends_on"):
                            # 传递前置专家的结果
                            for dep in task["depends_on"]:
                                if dep in results:
                                    ctx[f"from_{dep}"] = results[dep].get("reply", "")
                        agent = self._get_expert(expert_name)
                        result = agent.process(question, context=ctx)
                        results[expert_name] = result
                        completed.add(expert_name)
                        pending = [t for t in pending if t["expert"] != expert_name]
                        state["trace"].append({
                            "ts": datetime.now().isoformat(), "node": f"dag_{expert_name}",
                            "priority": task.get("priority", 0),
                            "deps": task.get("depends_on", []),
                            "reply_preview": result.get("reply", "")[:100],
                        })
                    except Exception as e:
                        results[expert_name] = {"reply": f"专家{expert_name}失败: {e}", "steps": [], "confidence": 0.0}
                        completed.add(expert_name)
                        pending = [t for t in pending if t["expert"] != expert_name]
        else:
            # Fallback: 简单串行
            for expert_name in state["routed_experts"]:
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

    def clarify_check(self, state: SupervisorState) -> SupervisorState:
        """节点 5 (E.3): 检查是否需要追问买家。"""
        # 如果 classify 阶段已标记需要澄清
        if state.get("needs_clarification") and state.get("clarification_question"):
            state["final_reply"] = f"🤔 {state['clarification_question']}"
            state["final_confidence"] = 0.0
            state["trace"].append({
                "ts": datetime.now().isoformat(), "node": "clarify",
                "question": state["clarification_question"],
            })
            return state

        # 如果聚合后置信度过低
        if state.get("final_confidence", 1.0) < 0.3 and state.get("final_reply", "").startswith("抱歉"):
            try:
                prompt = f"""买家问题: {state['question']}
当前回复: {state.get('final_reply', '')[:200]}
信息不足。生成一条友好的追问，帮助买家缩小问题范围（<50字）。"""
                response = self.llm.invoke([{"role": "user", "content": prompt}])
                clarify = response.content if hasattr(response, 'content') else str(response)
                state["final_reply"] = f"🤔 {clarify.strip()}"
                state["final_confidence"] = 0.0
                state["trace"].append({"ts": datetime.now().isoformat(), "node": "clarify", "low_confidence": True})
            except Exception:
                pass

        return state

    # ===== 管线构建 =====

    def build_graph(self):
        """构建 LangGraph StateGraph（v3: +DAG +Clarify）。"""
        workflow = StateGraph(SupervisorState)

        workflow.add_node("classify_intent", self.classify_intent)
        workflow.add_node("route_experts", self.route_experts)
        workflow.add_node("dispatch_experts", self.dispatch_experts)
        workflow.add_node("replan_check", self.replan_check)
        workflow.add_node("aggregate_reply", self.aggregate_reply)
        workflow.add_node("clarify_check", self.clarify_check)

        # 流程: classify → route → dispatch → replan → aggregate → clarify → END
        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "route_experts")
        workflow.add_edge("route_experts", "dispatch_experts")
        workflow.add_edge("dispatch_experts", "replan_check")
        workflow.add_edge("replan_check", "aggregate_reply")
        workflow.add_edge("aggregate_reply", "clarify_check")
        workflow.add_edge("clarify_check", END)

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
            "plan": [],
            "routed_experts": [],
            "expert_results": {},
            "final_reply": "",
            "final_confidence": 0.0,
            "needs_clarification": False,
            "clarification_question": "",
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

        reply = final_state["final_reply"]
        confidence = final_state["final_confidence"]
        intents = final_state["intents"]
        trace = final_state["trace"]

        # D.1: 会话持久化（非关键路径）
        try:
            from app.ai.memory import save_conversation_turn, record_execution
            tools_used = [
                t.get("node", "") for t in trace
                if "expert_" in str(t.get("node", ""))
            ]
            save_conversation_turn(
                merchant_id=self.merchant_id,
                user_id=0,  # 从 chat_history 中提取 user_id 的 TODO
                question=question,
                reply=reply,
                intent=intents[0] if intents else "",
                confidence=confidence,
                trace=trace,
            )
            # D.3: 记录执行记忆
            record_execution(
                merchant_id=self.merchant_id,
                question=question,
                intent=intents[0] if intents else "unknown",
                intents=intents,
                tools_used=[{"tool": t} for t in tools_used],
                success=confidence > 0.3,
                confidence=confidence,
            )
        except Exception:
            pass

        return {
            "reply": reply,
            "confidence": confidence,
            "intents": intents,
            "expert_results": final_state.get("expert_results", {}),
            "trace": trace,
            "intermediate_steps": [
                {"tool": t.get("node", "?"), "tool_input": {}, "observation": t.get("reply_preview", "")}
                for t in trace
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
            "web": lambda: __import__('app.ai.agents.web_agent', fromlist=['WebSearchAgent']).WebSearchAgent(self.merchant_id, self.llm, self.role_prompt),
        }
        factory = expert_map.get(name)
        if factory:
            return factory()
        # 默认使用 RAG Agent
        return __import__('app.ai.agents.rag_agent', fromlist=['RAGAgent']).RAGAgent(self.merchant_id, self.llm, self.role_prompt)
