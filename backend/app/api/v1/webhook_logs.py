"""Webhook 投递日志接口（平台端：跨租户查看）"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_platform_user
from app.core.response import ok, page
from app.database.session import get_db
from app.models.webhook_delivery_log import WebhookDeliveryLog

router = APIRouter(prefix="/webhook-logs", tags=["Webhook日志"])


@router.get("")
def list_logs(
    page_no: int = Query(1, alias="page"), page_size: int = Query(20),
    event_type: str = Query(None), status: str = Query(None),
    merchant_id: int = Query(None),
    current: CurrentUser = Depends(get_platform_user),
    db: Session = Depends(get_db),
):
    q = db.query(WebhookDeliveryLog)
    if merchant_id:
        q = q.filter(WebhookDeliveryLog.merchant_id == merchant_id)
    if event_type:
        q = q.filter(WebhookDeliveryLog.event_type == event_type)
    if status:
        q = q.filter(WebhookDeliveryLog.status == status)
    total = q.count()
    items = q.order_by(WebhookDeliveryLog.id.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([{
        "id": l.id, "event_type": l.event_type, "source_shop_id": l.source_shop_id,
        "payload_json": l.payload_json, "response_code": l.response_code,
        "response_body": l.response_body, "duration_ms": l.duration_ms,
        "status": l.status, "created_at": str(l.created_at) if l.created_at else None,
    } for l in items], total, page_no, page_size)


@router.post("/{log_id}/retry")
def retry_delivery(
    log_id: int,
    current: CurrentUser = Depends(get_platform_user),
    db: Session = Depends(get_db),
):
    log = db.query(WebhookDeliveryLog).filter(
        WebhookDeliveryLog.id == log_id,
    ).first()
    if not log:
        return ok(None, msg="记录不存在")
    if log.status != "failed":
        return ok(None, msg="只有失败的投递才可重试")
    # 标记为 retrying，实际重试由 webhook 消费者处理
    log.status = "retrying"
    db.commit()
    return ok({"id": log_id, "status": "retrying"}, msg="已加入重试队列")
