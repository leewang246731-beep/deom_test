"""OpenAPI — SaaS 物流查询接口 (tuozhan.md §2.6)"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from jose import jwt

from app.core.config import settings
from app.core.response import ok
from app.database.session import get_db
from app.models.vm_logistics import VmLogistics
from app.models.vm_platform_setting import VmPlatformSetting
from app.services.logistics_engine import get_full_timeline

router = APIRouter(prefix="/openapi/logistics", tags=["OpenAPI-物流"])


def _verify_token(auth: str, db: Session):
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "缺少 Token"})
    token = auth.split(" ", 1)[1]
    s = db.query(VmPlatformSetting).first()
    secret = s.access_token_secret if s else settings.ACCESS_TOKEN_SECRET
    try:
        return jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "Token 无效"})


@router.get("/{order_id}")
def get_logistics(order_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    _verify_token(authorization, db)
    log = db.query(VmLogistics).filter(VmLogistics.order_id == order_id).first()
    if not log:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "该订单暂无物流信息"})
    tracks = get_full_timeline(db, log.id)
    current = tracks[-1] if tracks else None
    return ok({
        "order_id": order_id,
        "logistics_id": log.id,
        "company": log.company,
        "tracking_no": log.tracking_no,
        "status": log.status,
        "status_label": log.status_label,
        "current_node": current["node_desc"] if current else "",
        "estimated_days": log.estimated_days,
        "exception_code": log.exception_code,
        "exception_detail": log.exception_detail,
        "courier_name": log.courier_name,
        "courier_phone": log.courier_phone,
        "current_city": log.current_city,
        "tracks": tracks,
    })
