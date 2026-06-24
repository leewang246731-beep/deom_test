"""运营后台 - 物流管理 (tuozhan.md §2.5)"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_logistics import VmLogistics
from app.services.logistics_engine import (
    advance_logistics, set_exception, resolve_exception,
    get_full_timeline, ship_order,
)
from app.services.fake_logistics import generate_tracking_no

router = APIRouter(prefix="/admin/logistics", tags=["运营-物流管理"])


def _get_admin(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "admin":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需运营后台登录"})
    return payload


@router.get("/{order_id}")
def get_logistics(order_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    log = db.query(VmLogistics).filter(VmLogistics.order_id == order_id).first()
    if not log:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "该订单暂无物流信息"})
    tracks = get_full_timeline(db, log.id)
    return ok({
        "id": log.id, "order_id": log.order_id, "company": log.company,
        "tracking_no": log.tracking_no, "status": log.status, "status_label": log.status_label,
        "estimated_days": log.estimated_days, "exception_code": log.exception_code,
        "exception_detail": log.exception_detail, "courier_name": log.courier_name,
        "courier_phone": log.courier_phone, "current_city": log.current_city,
        "tracks": tracks,
    })


@router.post("/{order_id}/ship")
def do_ship(order_id: int, body: dict, authorization: str = Header(None),
            db: Session = Depends(get_db)):
    _get_admin(authorization)
    company = body.get("company", "顺丰速运")
    tracking_no = body.get("tracking_no") or generate_tracking_no(company)
    log = ship_order(db, order_id, company, tracking_no)
    tracks = get_full_timeline(db, log.id)
    return ok({"id": log.id, "order_id": order_id, "company": company,
               "tracking_no": tracking_no, "status": "PICKED", "tracks": tracks}, msg="发货成功")


@router.post("/{logistics_id}/advance")
def do_advance(logistics_id: int, authorization: str = Header(None),
               db: Session = Depends(get_db)):
    """手动推进一个节点（管理员强制干预）。"""
    _get_admin(authorization)
    result = advance_logistics(db, logistics_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": result["error"]})
    tracks = get_full_timeline(db, logistics_id)
    return ok({**result, "tracks": tracks})


@router.post("/{logistics_id}/exception")
def do_exception(logistics_id: int, body: dict, authorization: str = Header(None),
                 db: Session = Depends(get_db)):
    """设置异常 (FAILED / STUCK)。"""
    _get_admin(authorization)
    code = body.get("exception_code", "FAILED")
    detail = body.get("detail", body.get("exception_detail", f"管理员设置异常: {code}"))
    result = set_exception(db, logistics_id, code, detail)
    if result.get("error"):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": result["error"]})
    tracks = get_full_timeline(db, logistics_id)
    return ok({**result, "tracks": tracks}, msg="异常已设置")


@router.post("/{logistics_id}/resolve")
def do_resolve(logistics_id: int, authorization: str = Header(None),
               db: Session = Depends(get_db)):
    """解决异常，恢复正常流转。"""
    _get_admin(authorization)
    result = resolve_exception(db, logistics_id)
    if result.get("error"):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": result["error"]})
    tracks = get_full_timeline(db, logistics_id)
    return ok({**result, "tracks": tracks}, msg="异常已解决")
