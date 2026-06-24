"""
工单管理接口（PHASE3-PLAN §9）
CRUD + 状态机流转 + 分配/领取 + AI 分类/话术/总结
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, require_roles
from app.core.redis_client import get_redis, mkey
from app.core.response import ok, page
from app.database.session import get_db
from app.models.merchant_user import MerchantUser
from app.models.skill_group import SkillGroup, SkillMember
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_category import TicketCategory
from app.models.ticket_comment import TicketComment

router = APIRouter(prefix="/tickets", tags=["工单管理"])

# 合法状态流转
VALID_TRANSITIONS = {
    "pending": ["in_progress", "closed"],
    "in_progress": ["waiting_customer", "resolved", "closed"],
    "waiting_customer": ["in_progress"],
    "resolved": ["closed", "in_progress"],
    "closed": [],
}


def _gen_ticket_no(db: Session, merchant_id: int) -> str:
    """工单编号：TK-{mid}-{5位自增序号}（Redis 锁防并发）。"""
    r = get_redis()
    lock_key = mkey(merchant_id, "lock", "ticket_seq")
    if not r.set(lock_key, "1", nx=True, ex=5):
        raise HTTPException(status_code=409, detail={"code": 40901, "msg": "工单编号生成中，请重试"})
    try:
        last = db.query(Ticket.ticket_no).filter(
            Ticket.merchant_id == merchant_id
        ).order_by(Ticket.id.desc()).first()
        if last and last[0]:
            seq = int(last[0].split("-")[-1]) + 1
        else:
            seq = 1
        return f"TK-{merchant_id}-{seq:05d}"
    finally:
        r.delete(lock_key)


def _ticket_brief(t: Ticket, assignee_name: str = None) -> dict:
    return {
        "id": t.id, "ticket_no": t.ticket_no, "title": t.title,
        "priority": t.priority, "status": t.status,
        "source": t.source, "source_id": t.source_id,
        "category_id": t.category_id, "assigned_to": t.assigned_to,
        "assignee_name": assignee_name, "sla_due_at": t.sla_due_at.isoformat() if t.sla_due_at else None,
        "sla_breached": t.sla_breached, "ticket_tags": t.ticket_tags,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("")
def list_tickets(
    status: str = Query(None), priority: str = Query(None),
    assigned_to: int = Query(None), category_id: int = Query(None),
    page_no: int = Query(1, alias="page"), page_size: int = Query(20),
    current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db),
):
    q = db.query(Ticket).filter(Ticket.merchant_id == current.merchant_id)
    if status: q = q.filter(Ticket.status == status)
    if priority: q = q.filter(Ticket.priority == priority)
    if assigned_to: q = q.filter(Ticket.assigned_to == assigned_to)
    if category_id: q = q.filter(Ticket.category_id == category_id)
    total = q.count()
    items = q.order_by(Ticket.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    # resolve assignee names
    uids = {t.assigned_to for t in items if t.assigned_to}
    unames = {u.id: u.display_name for u in db.query(MerchantUser).filter(
        MerchantUser.id.in_(uids)).all()} if uids else {}
    return page([_ticket_brief(t, unames.get(t.assigned_to)) for t in items], total, page_no, page_size)


@router.post("")
def create_ticket(body: dict, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    """创建工单。必填: title, source。 可选: description, priority, category_id, source_id, buyer_openid。"""
    title = body.get("title")
    if not title:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "工单标题不能为空"})
    source = body.get("source", "manual")
    ticket_no = _gen_ticket_no(db, current.merchant_id)
    t = Ticket(
        merchant_id=current.merchant_id, ticket_no=ticket_no,
        title=title, description=body.get("description", ""),
        priority=body.get("priority", "P3"), source=source,
        source_id=body.get("source_id"), buyer_openid=body.get("buyer_openid"),
        category_id=body.get("category_id"), created_by=current.user_id,
        ticket_tags=body.get("ticket_tags"),
    )
    db.add(t)
    db.flush()
    # 分配日志
    db.add(TicketAssignment(ticket_id=t.id, action="created", to_user_id=current.user_id))
    # 智能分配：尝试自动路由
    try:
        _auto_assign(db, current.merchant_id, t)
    except Exception:
        pass
    db.commit()
    return ok({"id": t.id, "ticket_no": t.ticket_no}, msg="工单已创建")


@router.get("/{ticket_id}")
def ticket_detail(ticket_id: int, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    assignee = db.query(MerchantUser).get(t.assigned_to) if t.assigned_to else None
    creator = db.query(MerchantUser).get(t.created_by) if t.created_by else None
    comments = db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).order_by(
        TicketComment.created_at).all()
    assignments = db.query(TicketAssignment).filter(TicketAssignment.ticket_id == ticket_id).order_by(
        TicketAssignment.created_at).all()
    cat = db.query(TicketCategory).get(t.category_id) if t.category_id else None
    return ok({
        "id": t.id, "ticket_no": t.ticket_no, "title": t.title, "description": t.description,
        "priority": t.priority, "status": t.status, "source": t.source, "source_id": t.source_id,
        "category_id": t.category_id, "category_name": cat.name if cat else None,
        "assigned_to": t.assigned_to, "assignee_name": assignee.display_name if assignee else None,
        "created_by": t.created_by, "creator_name": creator.display_name if creator else None,
        "ticket_tags": t.ticket_tags, "sla_due_at": t.sla_due_at.isoformat() if t.sla_due_at else None,
        "sla_breached": t.sla_breached, "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
        "resolved_notes": t.resolved_notes, "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "comments": [{"id": c.id, "user_id": c.user_id, "content": c.content,
                       "is_internal": c.is_internal, "created_at": c.created_at.isoformat() if c.created_at else None}
                      for c in comments],
        "assignments": [{"id": a.id, "action": a.action, "from_user_id": a.from_user_id,
                          "to_user_id": a.to_user_id, "remark": a.remark,
                          "created_at": a.created_at.isoformat() if a.created_at else None} for a in assignments],
    })


@router.put("/{ticket_id}")
def update_ticket(ticket_id: int, body: dict, current: CurrentUser = Depends(get_current_merchant),
                  db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    for field in ("title", "description", "priority", "category_id", "ticket_tags"):
        if field in body:
            setattr(t, field, body[field])
    db.commit()
    return ok({"id": t.id}, msg="已更新")


@router.post("/{ticket_id}/status")
def update_status(ticket_id: int, body: dict, current: CurrentUser = Depends(get_current_merchant),
                  db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    new_status = body.get("status")
    if new_status not in VALID_TRANSITIONS.get(t.status, []):
        raise HTTPException(status_code=400, detail={
            "code": 40001, "msg": f"""不允许从 {t.status} 转到 {new_status}"""})
    if new_status == "closed" and not body.get("resolved_notes") and not t.resolved_notes:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "关闭工单需填写处理纪要"})

    # SLA pause/resume
    now = datetime.now()
    if new_status == "waiting_customer":
        t.sla_paused_at = now
    elif t.status == "waiting_customer" and new_status == "in_progress" and t.sla_due_at and t.sla_paused_at:
        paused_secs = (now - t.sla_paused_at).total_seconds()
        t.sla_due_at = t.sla_due_at + timedelta(seconds=paused_secs)

    t.status = new_status
    if new_status == "resolved":
        t.resolved_at = now
        if body.get("resolved_notes"):
            t.resolved_notes = body["resolved_notes"]
    elif new_status == "closed":
        t.closed_at = now
        if body.get("resolved_notes"):
            t.resolved_notes = body["resolved_notes"]
    db.commit()
    return ok({"id": t.id, "status": t.status}, msg="状态已更新")


@router.post("/{ticket_id}/assign")
def assign_ticket(ticket_id: int, body: dict, current: CurrentUser = Depends(require_roles("admin", "manager")),
                  db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    to_id = body.get("to_user_id")
    user = db.query(MerchantUser).filter(MerchantUser.id == to_id,
                                          MerchantUser.merchant_id == current.merchant_id).first()
    if not user:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "目标用户不存在"})
    db.add(TicketAssignment(ticket_id=ticket_id, from_user_id=t.assigned_to, to_user_id=to_id,
                             action="reassigned", remark=body.get("remark", "")))
    t.assigned_to = to_id
    if t.status == "pending":
        t.status = "in_progress"
    db.commit()
    return ok({"id": t.id, "assigned_to": t.assigned_to}, msg="已改派")


@router.post("/{ticket_id}/claim")
def claim_ticket(ticket_id: int, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    if t.assigned_to:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "工单已被分配"})
    db.add(TicketAssignment(ticket_id=ticket_id, to_user_id=current.user_id, action="claimed"))
    t.assigned_to = current.user_id
    t.status = "in_progress"
    db.commit()
    return ok({"id": t.id, "assigned_to": t.assigned_to}, msg="已领取")


# ---- AI ----
@router.post("/{ticket_id}/auto-classify")
def auto_classify(ticket_id: int, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    from app.services.ticket_ai import classify_ticket
    result = classify_ticket(db, current.merchant_id, t.title, t.description or "")
    if result.get("suggested_priority"):
        t.priority = result["suggested_priority"]
        db.commit()
    return ok(result)


@router.post("/{ticket_id}/auto-summarize")
def auto_summarize(ticket_id: int, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    from app.services.ticket_ai import summarize_ticket
    summary = summarize_ticket(db, ticket_id)
    return ok({"summary": summary})


@router.post("/auto-classify")
def auto_classify_create(body: dict, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    """创建前预分类：给定标题+描述，返回 AI 建议的分类和优先级。"""
    from app.services.ticket_ai import classify_ticket
    return ok(classify_ticket(db, current.merchant_id, body.get("title", ""), body.get("description", "")))


# ---- 评论 ----
@router.get("/{ticket_id}/comments")
def list_comments(ticket_id: int, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    comments = db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).order_by(
        TicketComment.created_at.desc()).all()
    return ok([{"id": c.id, "user_id": c.user_id, "content": c.content,
                "is_internal": c.is_internal, "attachments": c.attachments,
                "created_at": c.created_at.isoformat() if c.created_at else None} for c in comments])


@router.post("/{ticket_id}/comments")
def add_comment(ticket_id: int, body: dict, current: CurrentUser = Depends(get_current_merchant),
                db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    c = TicketComment(ticket_id=ticket_id, user_id=current.user_id, content=body["content"],
                      is_internal=body.get("is_internal", 0), attachments=body.get("attachments"))
    db.add(c)
    db.commit()
    return ok({"id": c.id}, msg="已添加")


# ---- 分类树 ----
@router.get("/categories")
def list_categories(current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    cats = db.query(TicketCategory).filter(
        TicketCategory.merchant_id == current.merchant_id
    ).order_by(TicketCategory.level, TicketCategory.sort_order).all()

    def build(parent_id=None):
        return [{"id": c.id, "name": c.name, "level": c.level,
                 "children": build(c.id)} for c in cats if c.parent_id == parent_id]
    return ok(build())


# ---- AI 话术 ----
@router.post("/{ticket_id}/ai-suggest")
def ticket_ai_suggest(ticket_id: int, current: CurrentUser = Depends(get_current_merchant),
                      db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    from app.services.ticket_ai import suggest_ticket_reply
    suggestions = suggest_ticket_reply(current.merchant_id, t.title, t.description or "", t.status)
    return ok({"suggestions": suggestions})


# ===== 内部：智能分配引擎 =====
def _auto_assign(db: Session, merchant_id: int, ticket: Ticket):
    """智能分配：技能匹配 → 负载均衡 → 兜底给管理员。"""
    if not ticket.category_id:
        return
    cat = db.query(TicketCategory).get(ticket.category_id)
    if not cat:
        return
    # 找匹配的技能组（按分类名模糊匹配）
    groups = db.query(SkillGroup).filter(
        SkillGroup.merchant_id == merchant_id, SkillGroup.is_active == 1
    ).all()
    matched_members = []
    for g in groups:
        # 简单规则：技能组名包含分类名关键词
        if cat.name in g.name or any(t in g.description or "" for t in cat.name.split("/")):
            members = db.query(SkillMember).filter(SkillMember.group_id == g.id).all()
            for m in members:
                matched_members.append(m.user_id)

    if not matched_members:
        # 兜底：找 admin
        admin = db.query(MerchantUser).filter(
            MerchantUser.merchant_id == merchant_id, MerchantUser.role == "admin",
            MerchantUser.status == 1).first()
        if admin:
            matched_members = [admin.id]

    if not matched_members:
        return

    # 负载均衡：选处理中工单最少的
    loads = {}
    for uid in matched_members:
        loads[uid] = db.query(Ticket).filter(
            Ticket.assigned_to == uid, Ticket.status.in_(["in_progress", "pending"])
        ).count()
    best = min(loads, key=loads.get)
    ticket.assigned_to = best
    ticket.status = "in_progress"
    db.add(TicketAssignment(ticket_id=ticket.id, to_user_id=best, action="auto_routed"))
