"""
BaseExpertAgent — 所有专家 Agent 的抽象基类。

每个专家负责一个领域，拥有自己的工具集和系统提示。
Supervisor 通过路由将任务分发给对应的专家。
"""
from abc import ABC, abstractmethod
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent


class BaseExpertAgent(ABC):
    """专家 Agent 基类。"""

    # 子类必须定义
    name: str = "base"
    description: str = ""
    system_prompt: str = ""
    tools: list = []

    def __init__(self, merchant_id: int, llm: BaseChatModel, role_prompt: str = ""):
        self.merchant_id = merchant_id
        self.llm = llm
        self.role_prompt = role_prompt
        self._agent = None

    @abstractmethod
    def _build_tools(self) -> list:
        """构建本专家专属工具列表。子类必须实现。"""
        ...

    @abstractmethod
    def _build_prompt(self) -> str:
        """构建系统提示。子类必须实现。"""
        ...

    def get_agent(self):
        """获取或创建 LangGraph ReAct Agent。"""
        if self._agent is None:
            tools = self._build_tools()
            prompt = self._build_prompt()
            from langchain_core.prompts import ChatPromptTemplate
            template = ChatPromptTemplate.from_messages([
                ("system", prompt),
                ("placeholder", "{messages}"),
            ])
            self._agent = create_react_agent(
                model=self.llm, tools=tools, prompt=template,
            )
        return self._agent

    def process(self, question: str, context: dict = None) -> dict:
        """
        执行专家处理流程。

        Returns:
            {"reply": str, "steps": list, "confidence": float}
        """
        agent = self.get_agent()
        msgs = [{"role": "user", "content": question}]

        # 注入上下文（如订单号、物流单号等）
        if context:
            ctx_str = "\n".join(f"{k}: {v}" for k, v in context.items())
            msgs.insert(0, {"role": "system", "content": f"已知上下文:\n{ctx_str}"})

        try:
            result = agent.invoke({"messages": [("user", question)]})
            messages = result.get("messages", [])

            # 提取最终回复
            reply = ""
            steps = []
            for msg in messages:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        steps.append({"tool": tc.get("name", "?"), "input": tc.get("args", {})})
                if hasattr(msg, "content") and msg.content and not hasattr(msg, "tool_calls"):
                    reply = msg.content

            if not reply:
                # 回退：使用最后一条 ToolMessage 的 observation
                for msg in reversed(messages):
                    if hasattr(msg, "content") and hasattr(msg, "tool_call_id"):
                        reply = str(msg.content)[:300]
                        break

            return {"reply": reply or "无法处理该请求", "steps": steps, "confidence": 0.8 if reply else 0.0}
        except Exception as e:
            return {"reply": f"[{self.name}] 处理异常: {e}", "steps": [], "confidence": 0.0}
