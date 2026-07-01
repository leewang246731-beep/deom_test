"""vmall 商品 ID 还原（纯函数，无副作用）。"""


def restore_vm_product_id(platform_product_id: str | None) -> int | None:
    """从 'vm_785' 还原 vmall 商品 ID 785。非 'vm_' 前缀或非数字尾部返回 None。"""
    if not platform_product_id or not platform_product_id.startswith("vm_"):
        return None
    tail = platform_product_id[len("vm_"):]
    return int(tail) if tail.isdigit() else None
