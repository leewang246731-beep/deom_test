"""物流状态机引擎 (tuozhan.md §2.2)"""
from datetime import datetime
from enum import Enum
from sqlalchemy.orm import Session

from app.models.vm_logistics import VmLogistics, VmLogisticsTrack


class LogisticsStatus(Enum):
    PENDING = "PENDING"
    PICKED = "PICKED"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    STUCK = "STUCK"
    CANCELLED = "CANCELLED"

    @property
    def label(self) -> str:
        return {
            "PENDING": "待发货", "PICKED": "已揽收",
            "IN_TRANSIT": "运输中", "OUT_FOR_DELIVERY": "派送中",
            "DELIVERED": "已签收", "FAILED": "派送失败",
            "STUCK": "异常滞留", "CANCELLED": "已取消",
        }.get(self.value, self.value)


TRANSITIONS = {
    "PENDING": ["PICKED", "CANCELLED"],
    "PICKED": ["IN_TRANSIT"],
    "IN_TRANSIT": ["OUT_FOR_DELIVERY", "STUCK"],
    "OUT_FOR_DELIVERY": ["DELIVERED", "FAILED"],
    "FAILED": ["OUT_FOR_DELIVERY", "STUCK"],
    "STUCK": ["OUT_FOR_DELIVERY", "CANCELLED"],
    "DELIVERED": [],
    "CANCELLED": [],
}

NORMAL_PATH = ["PICKED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]


def validate_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, [])


def get_next_normal(current: str) -> str | None:
    """获取正常路径中的下一个状态。"""
    try:
        idx = NORMAL_PATH.index(current)
        return NORMAL_PATH[idx + 1] if idx + 1 < len(NORMAL_PATH) else None
    except ValueError:
        return None


def advance_logistics(db: Session, logistics_id: int, fake_data: dict | None = None) -> dict:
    """将物流推进到下一个正常节点。返回变更信息。"""
    log = db.query(VmLogistics).get(logistics_id)
    if not log:
        return {"error": "物流单不存在"}

    next_status = get_next_normal(log.status)
    if not next_status:
        return {"skipped": True, "status": log.status, "reason": "已是终态"}

    return _set_status(db, log, next_status, fake_data)


def set_exception(db: Session, logistics_id: int, exception_code: str, detail: str) -> dict:
    """设置异常状态 (FAILED / STUCK)。"""
    log = db.query(VmLogistics).get(logistics_id)
    if not log:
        return {"error": "物流单不存在"}
    if exception_code not in ("FAILED", "STUCK"):
        return {"error": f"无效异常码: {exception_code}"}

    old_status = log.status
    log.status = exception_code
    log.status_label = LogisticsStatus[exception_code].label
    log.exception_code = exception_code
    log.exception_detail = detail
    db.commit()

    track = VmLogisticsTrack(
        logistics_id=logistics_id, status_code=exception_code,
        node_name=f"异常: {exception_code}",
        node_desc=detail, node_time=datetime.now(),
        city=log.current_city, is_current=1, is_exception=1,
    )
    _clear_current(db, logistics_id)
    db.add(track)
    db.commit()

    return {"action": "set_exception", "from": old_status, "to": exception_code, "detail": detail}


def resolve_exception(db: Session, logistics_id: int) -> dict:
    """解决异常，恢复到派送中。"""
    log = db.query(VmLogistics).get(logistics_id)
    if not log:
        return {"error": "物流单不存在"}
    if log.status not in ("FAILED", "STUCK"):
        return {"error": "当前非异常状态"}

    old = log.status
    log.status = "OUT_FOR_DELIVERY"
    log.status_label = "派送中"
    log.exception_code = None
    log.exception_detail = None
    db.commit()

    track = VmLogisticsTrack(
        logistics_id=logistics_id, status_code="OUT_FOR_DELIVERY",
        node_name="异常已解决，恢复派送", node_desc="快递恢复正常派送",
        node_time=datetime.now(), city=log.current_city, is_current=1,
    )
    _clear_current(db, logistics_id)
    db.add(track)
    db.commit()

    return {"action": "resolve", "from": old, "to": "OUT_FOR_DELIVERY"}


def get_current_node(logistics_id: int, db: Session) -> dict | None:
    track = db.query(VmLogisticsTrack).filter(
        VmLogisticsTrack.logistics_id == logistics_id,
        VmLogisticsTrack.is_current == 1,
    ).first()
    if not track:
        return None
    return {"status_code": track.status_code, "node_name": track.node_name,
            "node_desc": track.node_desc, "node_time": track.node_time.isoformat() if track.node_time else None,
            "city": track.city, "is_exception": track.is_exception}


def get_full_timeline(db: Session, logistics_id: int) -> list[dict]:
    tracks = db.query(VmLogisticsTrack).filter(
        VmLogisticsTrack.logistics_id == logistics_id
    ).order_by(VmLogisticsTrack.node_time).all()
    return [{"status_code": t.status_code, "node_name": t.node_name, "node_desc": t.node_desc,
             "node_time": t.node_time.isoformat() if t.node_time else None,
             "city": t.city, "operator": t.operator, "is_exception": t.is_exception} for t in tracks]


def ship_order(db: Session, order_id: int, company: str, tracking_no: str) -> VmLogistics:
    """发货：创建物流单，状态 → PICKED。"""
    from app.models.vm_order import VmOrder
    from app.services.fake_logistics import generate_courier

    order = db.query(VmOrder).get(order_id)
    courier = generate_courier()
    log = VmLogistics(
        order_id=order_id, company=company, tracking_no=tracking_no,
        status="PICKED", status_label="已揽收", estimated_days=3,
        courier_name=courier["name"], courier_phone=courier["phone"],
        current_city=courier["city"],
        events_json=[{"time": datetime.now().isoformat(), "status": "已揽收",
                       "location": courier["city"], "operator": courier["name"]}]
    )
    db.add(log)
    db.flush()

    track = VmLogisticsTrack(
        logistics_id=log.id, status_code="PICKED", node_name="已揽收",
        node_desc=f"快递员{courier['name']}({courier['phone']})已取件",
        node_time=datetime.now(), city=courier["city"], operator=courier["name"], is_current=1,
    )
    db.add(track)
    if order:
        order.status = "shipped"
        order.ship_time = datetime.now()
    db.commit()
    return log


def _set_status(db: Session, log: VmLogistics, new_status: str, fake_data: dict | None = None) -> dict:
    old = log.status
    log.status = new_status
    log.status_label = LogisticsStatus[new_status].label
    if new_status == "DELIVERED":
        order = __import__("app").models.vm_order.VmOrder
        o = db.query(order).get(log.order_id)
        if o:
            o.status = "completed"
            o.complete_time = datetime.now()
    db.commit()

    if fake_data is None:
        from app.services.fake_logistics import generate_node_data
        fake_data = generate_node_data(log.id, new_status)

    track = VmLogisticsTrack(
        logistics_id=log.id, status_code=new_status,
        node_name=fake_data.get("node_name", ""),
        node_desc=fake_data.get("node_desc", ""),
        node_time=datetime.now(),
        city=fake_data.get("city", ""),
        operator=fake_data.get("operator", ""),
        is_current=1,
    )
    _clear_current(db, log.id)
    db.add(track)
    log.current_city = fake_data.get("city", log.current_city)
    log.courier_name = fake_data.get("operator", log.courier_name)
    db.commit()
    return {"action": "advance", "from": old, "to": new_status, "node": fake_data}


def _clear_current(db: Session, logistics_id: int):
    db.query(VmLogisticsTrack).filter(
        VmLogisticsTrack.logistics_id == logistics_id,
        VmLogisticsTrack.is_current == 1,
    ).update({"is_current": 0}, synchronize_session=False)
