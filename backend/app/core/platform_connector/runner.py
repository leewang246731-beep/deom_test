"""run_connector — 同步 FastAPI 端点中安全执行 async connector 方法。"""
import asyncio
from typing import Any


def run_connector(coro) -> tuple[bool, Any, str | None]:
    """在同步端点中执行异步 connector 调用。

    返回 (ok, data, error_msg)。
    - ok=True: data 是 connector 方法的返回值
    - ok=False: data 是 None，error_msg 包含错误描述
    """
    try:
        result = asyncio.run(coro)
        return (True, result, None)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        return (False, None, error_msg)
