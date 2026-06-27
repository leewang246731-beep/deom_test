"""
LLM 服务 — DashScope OpenAI 兼容模式 (qwen-plus)
通过 OpenAI SDK 调用 DashScope 兼容端点，支持工具调用、自动重试、降级兜底。
"""
import json
import time
from typing import Any

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
from openai import OpenAI

from app.core.config import settings

_client = OpenAI(
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.LLM_API_BASE,
    timeout=settings.LLM_TIMEOUT,
)

ROLE_MAP = {
    "system": "system",
    "assistant": "assistant",
}


def _lc_to_openai(messages: list[BaseMessage]) -> list[dict]:
    """将 LangChain 消息列表转为 OpenAI 兼容格式。"""
    payload = []
    for m in messages:
        if isinstance(m, SystemMessage):
            payload.append({"role": "system", "content": m.content})
        elif isinstance(m, AIMessage):
            item = {"role": "assistant", "content": str(m.content) if m.content else ""}
            if hasattr(m, "tool_calls") and m.tool_calls:
                item["tool_calls"] = m.tool_calls
            payload.append(item)
        elif isinstance(m, ToolMessage):
            payload.append({
                "role": "tool",
                "content": str(m.content),
                "tool_call_id": getattr(m, "tool_call_id", ""),
            })
        else:
            payload.append({"role": "user", "content": str(m.content)})
    return payload


class ChatDashScope(BaseChatModel):
    """LangChain 兼容的 DashScope ChatModel（OpenAI 兼容模式），支持工具调用。"""
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
        payload = _lc_to_openai(messages)

        call_kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": payload,
            "stream": False,
        }

        if self._bound_tools:
            call_kwargs["tools"] = self._bound_tools

        last_error = None
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                resp = _client.chat.completions.create(**call_kwargs)
                choice = resp.choices[0]
                msg = choice.message

                tool_calls = []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                        except Exception:
                            args = {}
                        tool_calls.append({
                            "name": tc.function.name,
                            "id": tc.id,
                            "args": args,
                            "type": "tool_call",
                        })

                ai_msg = AIMessage(content=msg.content or "")
                if tool_calls:
                    ai_msg.tool_calls = tool_calls
                    ai_msg.additional_kwargs = {"tool_calls": tool_calls}

                return ChatResult(generations=[ChatGeneration(message=ai_msg)])
            except Exception as e:
                last_error = e
                if attempt < settings.LLM_MAX_RETRIES:
                    time.sleep(1.0 * (attempt + 1))  # 指数退避
                continue

        raise RuntimeError(f"LLM 调用失败 (已重试 {settings.LLM_MAX_RETRIES} 次): {last_error}")

    def bind_tools(self, tools: list, **kwargs: Any) -> "ChatDashScope":
        """绑定工具：将 LangChain Tool 转为 OpenAI 兼容格式。"""
        cloned = self.__class__(model=self.model, api_key=self.api_key)
        openai_tools = []
        for t in tools:
            if hasattr(t, "name") and hasattr(t, "description"):
                params = {"type": "object", "properties": {}}
                if hasattr(t, "args_schema") and t.args_schema:
                    try:
                        schema = t.args_schema.schema()
                        params = {
                            "type": "object",
                            "properties": schema.get("properties", {}),
                            "required": schema.get("required", []),
                        }
                    except Exception:
                        pass
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": (t.description or "")[:300],
                        "parameters": params,
                    },
                })
        cloned._bound_tools = openai_tools
        return cloned

    @property
    def _llm_type(self) -> str:
        return "dashscope-openai-compat"


_llm = ChatDashScope()


def chat(messages: list[dict]) -> str:
    """
    保持原签名，内部走 LangChain ChatModel。
    失败时返回降级兜底话术，不抛异常。
    """
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
    try:
        return _llm.invoke(lc_msgs).content
    except Exception as e:
        # 降级：返回友好兜底话术
        user_msg = next((m.content for m in lc_msgs if isinstance(m, HumanMessage)), "")
        return _fallback_reply(user_msg, str(e))


async def achat(messages: list[dict]) -> str:
    """
    chat() 的异步安全版本 — 在默认线程池执行同步调用，避免阻塞事件循环。
    用于 async def 端点中调用 LLM。
    """
    import asyncio
    return await asyncio.to_thread(chat, messages)


def _fallback_reply(user_question: str, error: str = "") -> str:
    """LLM 调用失败时的模板降级话术。"""
    q = user_question.lower() if user_question else ""
    if any(kw in q for kw in ["物流", "快递", "发货", "到哪", "tracking", "shipping"]):
        return "您好，您的订单正在配送中，预计1-3天送达。如需查询具体物流进度，请提供订单号，我会为您查询~"
    if any(kw in q for kw in ["退款", "退货", "售后", "refund"]):
        return "您好，如需申请退款/退货，请在订单详情页点击「申请售后」按钮，我们会在24小时内为您处理。"
    if any(kw in q for kw in ["价格", "优惠", "折扣", "price", "discount"]):
        return "您好，目前店铺有满减活动，具体优惠信息请查看商品详情页或联系店铺客服。"
    if any(kw in q for kw in ["质量", "坏了", "破损", "damage"]):
        return "非常抱歉给您带来不便！请拍照留存后联系售后客服，我们会尽快为您处理退换货。"
    return "亲，感谢您的咨询~ 我是您的专属客服助手，正在为您查询相关信息，请稍等片刻。如有紧急需求，可联系人工客服。"
