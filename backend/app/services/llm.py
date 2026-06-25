"""
LangChain BaseChatModel 封装 DashScope (qwen-max)
保持 chat(messages) -> str 签名不变，内部用 LangChain 标准接口。
支持 bind_tools 实现 Agent 工具调用。
"""
import json
from typing import Any

import dashscope
from dashscope import Generation
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.core.config import settings

dashscope.api_key = settings.DASHSCOPE_API_KEY

ROLE_MAP = {
    "system": "system",
    "assistant": "assistant",
}


def _lc_to_dashscope(messages: list[BaseMessage]) -> list[dict]:
    """将 LangChain 消息列表转为 DashScope 格式。"""
    payload = []
    for m in messages:
        if isinstance(m, SystemMessage):
            payload.append({"role": "system", "content": m.content})
        elif isinstance(m, AIMessage):
            item = {"role": "assistant", "content": str(m.content) if m.content else ""}
            if hasattr(m, "tool_calls") and m.tool_calls:
                # 将 LangGraph/OpenAI 格式转回 DashScope 格式
                ds_calls = []
                for tc in m.tool_calls:
                    fn = {"name": tc.get("name", ""), "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False)}
                    ds_calls.append({"id": tc.get("id", ""), "type": "function", "function": fn})
                item["tool_calls"] = ds_calls
            payload.append(item)
        elif isinstance(m, ToolMessage):
            payload.append({
                "role": "tool",
                "content": str(m.content),
                "name": getattr(m, "name", ""),
                "tool_call_id": getattr(m, "tool_call_id", ""),
            })
        else:
            payload.append({"role": "user", "content": str(m.content)})
    return payload


class ChatDashScope(BaseChatModel):
    """LangChain 兼容的 DashScope ChatModel，支持工具调用。"""
    model: str = settings.LLM_MODEL
    api_key: str = settings.DASHSCOPE_API_KEY
    _bound_tools: list | None = None

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = _lc_to_dashscope(messages)

        call_kwargs = {
            "model": self.model,
            "messages": payload,
            "result_format": "message",
            "stream": False,
        }

        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools

        resp = Generation.call(**call_kwargs)
        if resp.status_code != 200:
            raise RuntimeError(f"DashScope LLM 调用失败: {resp.status_code} {resp.message}")

        choice = resp.output["choices"][0]
        msg = choice["message"]

        # 检测工具调用 — 将 DashScope 格式转为 OpenAI/LangGraph 兼容格式
        tool_calls = []
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            args_str = fn.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except Exception:
                args = {}
            tool_calls.append({
                "name": fn.get("name", ""),
                "id": tc.get("id", ""),
                "args": args,
                "type": "tool_call",
            })

        ai_msg = AIMessage(content=msg.get("content", "") or "")
        if tool_calls:
            ai_msg.tool_calls = tool_calls
            ai_msg.additional_kwargs = {"tool_calls": tool_calls}

        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    def bind_tools(self, tools: list, **kwargs: Any) -> "ChatDashScope":
        """绑定工具：将 LangChain Tool 转为 DashScope 兼容格式。"""
        cloned = self.__class__(model=self.model, api_key=self.api_key)
        ds_tools = []
        for t in tools:
            if hasattr(t, "name") and hasattr(t, "description"):
                params = {}
                if hasattr(t, "args_schema") and t.args_schema:
                    try:
                        schema = t.args_schema.schema()
                        params = {
                            "type": "object",
                            "properties": schema.get("properties", {}),
                            "required": schema.get("required", []),
                        }
                    except Exception:
                        params = {"type": "object", "properties": {}}
                ds_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description[:300] if t.description else "",
                        "parameters": params,
                    },
                })
        cloned._bound_tools = ds_tools
        return cloned

    @property
    def _llm_type(self) -> str:
        return "dashscope-chat"


_llm = ChatDashScope()


def chat(messages: list[dict]) -> str:
    """保持原签名，内部走 LangChain ChatModel。"""
    lc_msgs = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            lc_msgs.append(SystemMessage(content=content))
        elif role == "assistant":
            lc_msgs.append(AIMessage(content=content))
        else:
            lc_msgs.append(HumanMessage(content=content))
    return _llm.invoke(lc_msgs).content
