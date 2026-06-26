"""统一响应封装：{code, msg, data}"""
from typing import Any


def ok(data: Any = None, msg: str = "ok") -> dict:
    return {"code": 200, "msg": msg, "data": data}


def page(items: list, total: int, page: int, page_size: int) -> dict:
    """分页响应体。自动修正非法分页参数。"""
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 20)))
    return {
        "code": 200,
        "msg": "ok",
        "data": {"total": total, "page": page, "page_size": page_size, "items": items},
    }


def clamp_pagination(page: int, page_size: int) -> tuple[int, int]:
    """修正非法分页参数：page>=1, 1<=page_size<=200。"""
    return max(1, int(page or 1)), max(1, min(200, int(page_size or 20)))
