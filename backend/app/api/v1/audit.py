"""操作审计日志接口"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, require_roles
from app.core.response import ok, page
from app.database.session import get_db
from app.models.audit_log import AuditLog

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])


@router.get("")
def list_audit_logs(
    page_no: int = Query(1, alias="page"), page_size: int = Query(20),
    action: str = Query(None), target_type: str = Query(None),
    user_id: int = Query(None),
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog).filter(AuditLog.merchant_id == current.merchant_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    total = q.count()
    items = q.order_by(AuditLog.id.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([{
        "id": a.id, "user_id": a.user_id, "username": a.username,
        "action": a.action, "target_type": a.target_type, "target_id": a.target_id,
        "detail_json": a.detail_json, "ip": a.ip, "created_at": str(a.created_at) if a.created_at else None,
    } for a in items], total, page_no, page_size)


def record_audit(
    db: Session, merchant_id: int, user_id: int, username: str,
    action: str, target_type: str = None, target_id: int = None,
    detail: str = None, ip: str = None,
):
    """便捷记录审计日志"""
    try:
        db.add(AuditLog(
            merchant_id=merchant_id, user_id=user_id, username=username,
            action=action, target_type=target_type, target_id=target_id,
            detail_json=detail, ip=ip,
        ))
        db.commit()
    except Exception:
        pass
