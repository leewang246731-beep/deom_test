"""
客服工作台模式管理接口 (SERVICE-MODE-PLAN §6)
配置 CRUD + 会话模式切换 + 接管 + 自动回复日志
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, require_roles
from app.core.response import ok, page
from app.database.session import get_db
from app.models.conversation import Conversation
from app.models.service_mode import AutoReplyLog, ServiceModeConfig
from app.services.mode_engine import get_mode_config, switch_mode, clear_pending_timeout

router = APIRouter(prefix="/service-mode", tags=["客服模式"])


@router.get("/config")
def get_config(current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    cfg = get_mode_config(db, current.merchant_id)
    return ok({
        "id": cfg.id, "default_mode": cfg.default_mode,
        "auto_mode_hours": cfg.auto_mode_hours,
        "auto_confidence_threshold": float(cfg.auto_confidence_threshold or 0.80),
        "fallback_confidence_threshold": float(cfg.fallback_confidence_threshold or 0.50),
        "human_response_timeout_seconds": cfg.human_response_timeout_seconds,
        "fallback_escalate_timeout_seconds": cfg.fallback_escalate_timeout_seconds,
        "fallback_template": cfg.fallback_template,
        "busy_template": cfg.busy_template,
        "offline_template": cfg.offline_template,
    })


@router.put("/config")
def update_config(body: dict, current: CurrentUser = Depends(require_roles("admin", "manager")),
                  db: Session = Depends(get_db)):
    cfg = get_mode_config(db, current.merchant_id)
    for field in ("default_mode", "auto_mode_hours", "auto_confidence_threshold",
                  "fallback_confidence_threshold", "human_response_timeout_seconds",
                  "fallback_escalate_timeout_seconds", "fallback_template", "busy_template", "offline_template"):
        if field in body:
            setattr(cfg, field, body[field])
    db.commit()
    return ok({"id": cfg.id}, msg="配置已更新")


@router.post("/conversations/{conv_id}/mode")
def set_conv_mode(conv_id: int, body: dict, current: CurrentUser = Depends(get_current_merchant),
                  db: Session = Depends(get_db)):
    """切换单个会话模式。"""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    mode = body.get("mode")
    if mode not in ("manual", "copilot", "auto"):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "模式必须为 manual/copilot/auto"})
    result = switch_mode(db, conv, mode, body.get("reason", "手动切换"))
    return ok(result, msg=f"已切换为 {mode}")


@router.post("/conversations/{conv_id}/takeover")
def takeover(conv_id: int, current: CurrentUser = Depends(get_current_merchant),
             db: Session = Depends(get_db)):
    """人工接管：从 auto/copilot 切为 copilot，清除超时。"""
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    switch_mode(db, conv, "copilot", "人工接管")
    clear_pending_timeout(db, conv)
    conv.assigned_to = current.user_id
    db.commit()
    return ok({"conversation_id": conv.id, "mode": "copilot", "assigned_to": current.user_id}, msg="已接管")


@router.get("/auto-reply-logs")
def list_logs(page_no: int = Query(1, alias="page"), page_size: int = Query(20),
              action: str = Query(None),
              current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    q = db.query(AutoReplyLog).filter(AutoReplyLog.merchant_id == current.merchant_id)
    if action:
        q = q.filter(AutoReplyLog.action_taken == action)
    total = q.count()
    items = q.order_by(AutoReplyLog.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([{
        "id": r.id, "conversation_id": r.conversation_id, "mode": r.mode,
        "buyer_question": r.buyer_question[:50], "ai_reply": r.ai_reply[:80],
        "confidence": float(r.confidence) if r.confidence else None,
        "action_taken": r.action_taken, "human_override": r.human_override,
        "response_time_ms": r.response_time_ms,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in items], total, page_no, page_size)


@router.get("/stats")
def auto_reply_stats(current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    """自动回复统计。"""
    mid = current.merchant_id
    total = db.query(AutoReplyLog).filter(AutoReplyLog.merchant_id == mid).count()
    auto_sent = db.query(AutoReplyLog).filter(AutoReplyLog.merchant_id == mid, AutoReplyLog.action_taken == "auto_sent").count()
    fallback = db.query(AutoReplyLog).filter(AutoReplyLog.merchant_id == mid, AutoReplyLog.action_taken == "fallback_sent").count()
    transferred = db.query(AutoReplyLog).filter(AutoReplyLog.merchant_id == mid, AutoReplyLog.action_taken == "transferred").count()
    return ok({
        "total": total,
        "auto_sent": auto_sent,
        "fallback_sent": fallback,
        "transferred": transferred,
        "auto_rate": round(auto_sent / max(total, 1), 2),
        "transfer_rate": round(transferred / max(total, 1), 2),
    })
