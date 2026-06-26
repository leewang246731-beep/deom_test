"""数据看板接口（支持平台跨租户 + 商户租户隔离）"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_user
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


def _shop_ids(db: Session, merchant_id: int | None) -> list:
    """merchant_id=None 时返回所有活跃店铺ID（平台跨租户视角）。"""
    q = db.query(PlatformShop.id)
    if merchant_id is not None:
        q = q.filter(PlatformShop.merchant_id == merchant_id)
    return [r[0] for r in q.all()]


def _merchant_ids(current: CurrentUser, db: Session) -> list | None:
    """返回当前用户可见的 merchant_id 列表；None 表示跨全部租户（平台视角）。"""
    if current.token_type == "platform":
        return None
    return [current.merchant_id]


@router.get("/metrics")
def metrics(
    start: str = Query(None),
    end: str = Query(None),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mid = current.merchant_id  # None for platform
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

    active_shops_q = db.query(PlatformShop).filter(PlatformShop.is_active == 1)
    if mid is not None:
        active_shops_q = active_shops_q.filter(PlatformShop.merchant_id == mid)
    active_shops = active_shops_q.count()

    # AI 采纳率（跨全部数据）
    sugg_q = db.query(AISuggestionLog)
    if start:
        sugg_q = sugg_q.filter(AISuggestionLog.created_at >= start)
    if end:
        sugg_q = sugg_q.filter(AISuggestionLog.created_at <= end + " 23:59:59")
    total_suggs = sugg_q.count()
    adopted = sugg_q.filter(AISuggestionLog.was_adopted > 0).count()
    adoption_rate = round(adopted / total_suggs, 2) if total_suggs > 0 else 0

    ticket_q = db.query(Ticket)
    if mid is not None:
        ticket_q = ticket_q.filter(Ticket.merchant_id == mid)
    total_tickets = _date_filter(ticket_q, Ticket.created_at).count()
    pending_tickets = _date_filter(
        db.query(Ticket).filter(Ticket.status == "pending") if mid is None
        else db.query(Ticket).filter(Ticket.merchant_id == mid, Ticket.status == "pending"),
        Ticket.created_at,
    ).count()
    today_tickets_q = db.query(Ticket)
    if mid is not None:
        today_tickets_q = today_tickets_q.filter(Ticket.merchant_id == mid)
    today_tickets = today_tickets_q.filter(func.date(Ticket.created_at) == today).count()
    breached_q = db.query(Ticket).filter(Ticket.sla_breached == 1)
    if mid is not None:
        breached_q = breached_q.filter(Ticket.merchant_id == mid)
    sla_breached = breached_q.count()

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
    current: CurrentUser = Depends(get_current_user),
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
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mid = current.merchant_id
    shop_ids = _shop_ids(db, mid)
    if not shop_ids:
        return ok({"total_conversations": 0, "pending": 0, "replied": 0, "closed": 0, "ai_adoption_rate": 0, "avg_response_minutes": 0, "per_service": []})

    convs = db.query(Conversation).filter(Conversation.shop_id.in_(shop_ids))
    total_convs = convs.count()
    status_counts = {r[0]: r[1] for r in convs.with_entities(
        Conversation.handled_status, func.count()).group_by(Conversation.handled_status).all()}

    total_suggs = db.query(AISuggestionLog).count()
    adopted = db.query(AISuggestionLog).filter(AISuggestionLog.was_adopted > 0).count()
    adoption_rate = round(adopted / total_suggs, 2) if total_suggs > 0 else 0

    # 每人统计（平台视角看全部客服，商户视角只看自己）
    users_q = db.query(MerchantUser)
    if mid is not None:
        users_q = users_q.filter(MerchantUser.merchant_id == mid)
    users = users_q.all()
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
def ticket_stats(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    mid = current.merchant_id
    def _tq(status=None):
        q = db.query(Ticket)
        if mid is not None:
            q = q.filter(Ticket.merchant_id == mid)
        if status:
            q = q.filter(Ticket.status == status)
        return q
    total = _tq().count()
    pending = _tq("pending").count()
    in_progress = _tq("in_progress").count()
    waiting = _tq("waiting_customer").count()
    resolved_today = _tq("resolved").filter(func.date(Ticket.resolved_at) == datetime.now().strftime("%Y-%m-%d")).count()
    breached_q = db.query(Ticket).filter(Ticket.sla_breached == 1)
    if mid is not None:
        breached_q = breached_q.filter(Ticket.merchant_id == mid)
    breached = breached_q.count()
    return ok({"total": total, "pending": pending, "in_progress": in_progress,
               "waiting_customer": waiting, "resolved_today": resolved_today, "sla_breached": breached})


@router.get("/live-monitor")
def live_monitor(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    mid = current.merchant_id
    shop_ids = _shop_ids(db, mid)

    users_q = db.query(MerchantUser).filter(MerchantUser.status == 1)
    if mid is not None:
        users_q = users_q.filter(MerchantUser.merchant_id == mid)
    users = users_q.all()
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
    queue_tickets_q = db.query(Ticket).filter(Ticket.status == "pending", Ticket.assigned_to.is_(None))
    if mid is not None:
        queue_tickets_q = queue_tickets_q.filter(Ticket.merchant_id == mid)
    queue_tickets = queue_tickets_q.count()

    return ok({
        "agents": agents,
        "queue": {"unassigned_convs": queue_convs, "unassigned_tickets": queue_tickets},
        "total_agents": len(agents),
    })


@router.get("/ticket-trend")
def ticket_trend(range: str = Query("week"), current: CurrentUser = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    days = {"day": 1, "week": 7, "month": 30}.get(range, 7)
    since = datetime.now() - timedelta(days=days)
    fmt = "%Y-%m-%d %H:00" if range == "day" else "%Y-%m-%d"
    group = func.date_format(Ticket.created_at, fmt)
    q = db.query(group, func.count()).filter(Ticket.created_at >= since)
    if current.merchant_id is not None:
        q = q.filter(Ticket.merchant_id == current.merchant_id)
    rows = q.group_by(group).order_by(group).all()
    points = [{"date": r[0], "count": r[1]} for r in rows]
    return ok({"range": range, "points": points})
