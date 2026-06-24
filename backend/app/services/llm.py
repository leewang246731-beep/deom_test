"""
DashScope LLM 封装（qwen-max）
非流式调用，用于话术生成与催单话术。
"""
import dashscope
from dashscope import Generation

from app.core.config import settings

dashscope.api_key = settings.DASHSCOPE_API_KEY
MODEL = settings.LLM_MODEL


def chat(messages: list[dict]) -> str:
    """非流式调用 qwen-max，返回完整回答文本。"""
    resp = Generation.call(
        model=MODEL,
        messages=messages,
        result_format="message",
        stream=False,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"LLM 调用失败: {resp.status_code} {resp.message}")
    return resp.output["choices"][0]["message"]["content"]
