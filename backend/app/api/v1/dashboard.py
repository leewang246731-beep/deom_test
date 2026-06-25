"""数据看板接口（api.md 3.7 + REQUIREMENTS-V2 + PHASE3）"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, require_roles
from app.core.response import ok
from app.database.session import get_db
from app.models.ai_suggestion_log import AISuggestionLog
from app.models.conversation import Conversation
from app.models.external_order import ExternalOrder
from app.models.merchant_user import MerchantUser
from app.models.platform_shop import PlatformShop
from app.models.ticket import Ticket
from app.models.service_mode import AutoReplyLog

router = APIRouter(prefix="/dashboard", tags=["数据看板"])


def _shop_ids(db: Session, merchant_id: int) -> list:
    return [r[0] for r in db.query(PlatformShop.id).filter(PlatformShop.merchant_id == merchant_id).all()]


@router.get("/metrics")
def metrics(
    start: str = Query(None),
    end: str = Query(None),
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    mid = current.merchant_id
    shop_ids = _shop_ids(db, mid)
    today = datetime.now().strftime("%Y-%m-%d")

    def _date_filter(q, col):
        if start:
            q = q.filter(col >= start)
        if end:
            q = q.filter(col <= end + " 23:59:59")
        return q

    if shop_ids:
        base_orders = db.query(ExternalOrder).filter(ExternalOrder.shop_id.in_(shop_ids))
        total_orders = _date_filter(base_orders, ExternalOrder.created_at).count()
        today_orders = base_orders.filter(func.date(ExternalOrder.created_at) == today).count()
        base_convs = db.query(Conversation).filter(Conversation.shop_id.in_(shop_ids))
        pending_convs = _date_filter(base_convs, Conversation.created_at).filter(Conversation.handled_status == "pending").count()
    else:
        total_orders = today_orders = pending_convs = 0

    active_shops = db.query(PlatformShop).filter(
        PlatformShop.merchant_id == mid, PlatformShop.is_active == 1).count()

    sugg_q = db.query(AISuggestionLog)
    if start:
        sugg_q = sugg_q.filter(AISuggestionLog.created_at >= start)
    if end:
        sugg_q = sugg_q.filter(AISuggestionLog.created_at <= end + " 23:59:59")
    total_suggs = sugg_q.count()
    adopted = sugg_q.filter(AISuggestionLog.was_adopted > 0).count()
    adoption_rate = round(adopted / total_suggs, 2) if total_suggs > 0 else 0

    ticket_q = db.query(Ticket).filter(Ticket.merchant_id == mid)
    total_tickets = _date_filter(ticket_q, Ticket.created_at).count()
    pending_tickets = _date_filter(db.query(Ticket).filter(Ticket.merchant_id == mid, Ticket.status == "pending"), Ticket.created_at).count()
    today_tickets = db.query(Ticket).filter(Ticket.merchant_id == mid, func.date(Ticket.created_at) == today).count()
    sla_breached = db.query(Ticket).filter(Ticket.merchant_id == mid, Ticket.sla_breached == 1).count()

    return ok({
        "total_orders": total_orders, "today_orders": today_orders,
        "pending_conversations": pending_convs, "active_shops": active_shops,
        "ai_adoption_rate": adoption_rate,
        "total_tickets": total_tickets, "pending_tickets": pending_tickets,
        "today_tickets": today_tickets, "sla_breached": sla_breached,
    })


@router.get("/order-trend")
def order_trend(
    range: str = Query("week"),
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    shop_ids = _shop_ids(db, current.merchant_id)
    if not shop_ids:
        return ok({"range": range, "points": [], "summary": {"total_orders": 0, "total_amount": 0, "avg_daily": 0}})

    days = {"day": 1, "week": 7, "month": 30}.get(range, 7)
    since = datetime.now() - timedelta(days=days)
    fmt = "%Y-%m-%d %H:00" if range == "day" else "%Y-%m-%d"
    group = func.date_format(ExternalOrder.created_at, fmt)

    rows = db.query(group, func.count(), func.sum(ExternalOrder.pay_amount)).filter(
        ExternalOrder.shop_id.in_(shop_ids),
        ExternalOrder.created_at >= since,
    ).group_by(group).order_by(group).all()

    points = [{"date": r[0], "count": r[1], "amount": float(r[2] or 0)} for r in rows]
    total_orders = sum(p["count"] for p in points)
    total_amount = round(sum(p["amount"] for p in points), 2)
    avg_daily = round(total_orders / max(len(points), 1), 1)

    return ok({"range": range, "points": points, "summary": {
        "total_orders": total_orders, "total_amount": total_amount, "avg_daily": avg_daily,
    }})


@router.get("/service-stats")
def service_stats(
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    shop_ids = _shop_ids(db, current.merchant_id)
    if not shop_ids:
        return ok({"total_conversations": 0, "pending": 0, "replied": 0, "closed": 0, "ai_adoption_rate": 0, "avg_response_minutes": 0, "per_service": []})

    convs = db.query(Conversation).filter(Conversation.shop_id.in_(shop_ids))
    total_convs = convs.count()
    status_counts = {r[0]: r[1] for r in convs.with_entities(
        Conversation.handled_status, func.count()).group_by(Conversation.handled_status).all()}

    total_suggs = db.query(AISuggestionLog).count()
    adopted = db.query(AISuggestionLog).filter(AISuggestionLog.was_adopted > 0).count()
    adoption_rate = round(adopted / total_suggs, 2) if total_suggs > 0 else 0

    # 每人统计
    users = db.query(MerchantUser).filter(MerchantUser.merchant_id == current.merchant_id).all()
    per_service = []
    for u in users:
        handled = convs.filter(Conversation.assigned_to == u.id).count()
        per_service.append({"user_id": u.id, "display_name": u.display_name or u.username, "handled": handled, "role": u.role})
    per_service.sort(key=lambda x: x["handled"], reverse=True)

    return ok({
        "total_conversations": total_convs,
        "pending": status_counts.get("pending", 0),
        "replied": status_counts.get("replied", 0),
        "closed": status_counts.get("closed", 0),
        "ai_adoption_rate": adoption_rate,
        "avg_response_minutes": 0,
        "per_service": per_service,
    })


@router.get("/ticket-stats")
def ticket_stats(current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    mid = current.merchant_id
    total = db.query(Ticket).filter(Ticket.merchant_id == mid).count()
    pending = db.query(Ticket).filter(Ticket.merchant_id == mid, Ticket.status == "pending").count()
    in_progress = db.query(Ticket).filter(Ticket.merchant_id == mid, Ticket.status == "in_progress").count()
    waiting = db.query(Ticket).filter(Ticket.merchant_id == mid, Ticket.status == "waiting_customer").count()
    resolved_today = db.query(Ticket).filter(Ticket.merchant_id == mid, Ticket.status == "resolved",
                                              func.date(Ticket.resolved_at) == datetime.now().strftime("%Y-%m-%d")).count()
    breached = db.query(Ticket).filter(Ticket.merchant_id == mid, Ticket.sla_breached == 1).count()
    return ok({"total": total, "pending": pending, "in_progress": in_progress,
               "waiting_customer": waiting, "resolved_today": resolved_today, "sla_breached": breached})


@router.get("/live-monitor")
def live_monitor(current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    mid = current.merchant_id
    shop_ids = _shop_ids(db, mid)

    users = db.query(MerchantUser).filter(MerchantUser.merchant_id == mid, MerchantUser.status == 1).all()
    agents = []
    for u in users:
        active_convs = db.query(Conversation).filter(
            Conversation.shop_id.in_(shop_ids) if shop_ids else False,
            Conversation.assigned_to == u.id,
            Conversation.handled_status.in_(["pending", "replied"]),
        ).count()
        open_tickets = db.query(Ticket).filter(
            Ticket.merchant_id == mid, Ticket.assigned_to == u.id,
            Ticket.status.in_(["pending", "in_progress", "waiting_customer"]),
        ).count()
        agents.append({
            "user_id": u.id, "display_name": u.display_name or u.username,
            "role": u.role, "active_convs": active_convs, "open_tickets": open_tickets,
            "total_load": active_convs + open_tickets,
        })
    agents.sort(key=lambda x: x["total_load"], reverse=True)

    queue_convs = db.query(Conversation).filter(
        Conversation.shop_id.in_(shop_ids) if shop_ids else False,
        Conversation.handled_status == "pending", Conversation.assigned_to.is_(None),
    ).count()
    queue_tickets = db.query(Ticket).filter(
        Ticket.merchant_id == mid, Ticket.status == "pending", Ticket.assigned_to.is_(None),
    ).count()

    return ok({
        "agents": agents,
        "queue": {"unassigned_convs": queue_convs, "unassigned_tickets": queue_tickets},
        "total_agents": len(agents),
    })


@router.get("/ticket-trend")
def ticket_trend(range: str = Query("week"), current: CurrentUser = Depends(require_roles("admin", "manager")),
                 db: Session = Depends(get_db)):
    days = {"day": 1, "week": 7, "month": 30}.get(range, 7)
    since = datetime.now() - timedelta(days=days)
    fmt = "%Y-%m-%d %H:00" if range == "day" else "%Y-%m-%d"
    group = func.date_format(Ticket.created_at, fmt)
    rows = db.query(group, func.count()).filter(
        Ticket.merchant_id == current.merchant_id, Ticket.created_at >= since
    ).group_by(group).order_by(group).all()
    points = [{"date": r[0], "count": r[1]} for r in rows]
    return ok({"range": range, "points": points})
