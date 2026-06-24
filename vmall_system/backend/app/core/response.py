"""vMall 统一响应"""
from typing import Any


def ok(data: Any = None, msg: str = "ok") -> dict:
    return {"code": 200, "msg": msg, "data": data}


def page(items: list, total: int, page: int, page_size: int) -> dict:
    return {"code": 200, "msg": "ok", "data": {"total": total, "page": page, "page_size": page_size, "items": items}}
