"""物流自动推进器 — asyncio 循环 (tuozhan.md §2.3)"""
import asyncio
from datetime import datetime
from app.database.session import SessionLocal
from app.models.vm_logistics import VmLogistics
from app.services.logistics_engine import advance_logistics, get_next_normal


async def run_simulator(interval: int = 30):
    """每 interval 秒扫描所有未签收物流并推进一个节点。"""
    while True:
        await asyncio.sleep(interval)
        try:
            count = advance_all()
            if count:
                print(f"[物流模拟器] 推进 {count} 个物流节点")
        except Exception as e:
            print(f"[物流模拟器] 错误: {e}")


def advance_all() -> int:
    """推进所有活跃物流单一个节点。返回推进数量。"""
    db = SessionLocal()
    count = 0
    try:
        active_logs = db.query(VmLogistics).filter(
            VmLogistics.status.in_(["PICKED", "IN_TRANSIT", "OUT_FOR_DELIVERY"])
        ).all()
        for log in active_logs:
            result = advance_logistics(db, log.id)
            if not result.get("skipped") and not result.get("error"):
                count += 1
                # Webhook 推送（导入放这里避免循环依赖）
                try:
                    from app.services.webhook import dispatch_sync
                    tracks = __import__("app.services.logistics_engine", fromlist=["get_full_timeline"]).get_full_timeline(db, log.id)
                    dispatch_sync(db, "LOGISTICS_UPDATED", {
                        "logistics_id": log.id, "order_id": log.order_id,
                        "status": log.status, "status_label": log.status_label,
                        "current_city": log.current_city,
                        "estimated_days": log.estimated_days,
                        "exception_code": log.exception_code,
                        "exception_detail": log.exception_detail,
                        "courier_name": log.courier_name,
                        "courier_phone": log.courier_phone,
                        "tracks": tracks[-3:],  # 最近 3 条
                    })
                    if log.status == "DELIVERED":
                        dispatch_sync(db, "ORDER_COMPLETED", {
                            "order_id": log.order_id, "status": "completed",
                            "deliver_time": datetime.now().isoformat(),
                        })
                except Exception:
                    pass
    finally:
        db.close()
    return count


def advance_single(logistics_id: int) -> dict:
    """手动推进单个物流单。"""
    db = SessionLocal()
    try:
        log = db.query(VmLogistics).get(logistics_id)
        if not log:
            return {"error": "物流单不存在"}
        return advance_logistics(db, logistics_id)
    finally:
        db.close()
