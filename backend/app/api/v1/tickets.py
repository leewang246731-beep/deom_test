"""
工单管理接口（PHASE3-PLAN §9）
CRUD + 状态机流转 + 分配/领取 + AI 分类/话术/总结
"""
import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, get_current_user, require_roles
from app.core.redis_client import get_redis, mkey
from app.core.response import ok, page
from app.database.session import get_db
from app.models.merchant_user import MerchantUser
from app.models.skill_group import SkillGroup, SkillMember
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_category import TicketCategory
from app.models.ticket_comment import TicketComment
from app.schemas import (
    TicketCreate, TicketUpdate, TicketStatusUpdate, TicketAssign,
    TicketCommentCreate, TicketCategoryCreate, TicketCategoryUpdate,
    TicketBatchOperation, TicketAutoClassifyRequest,
)

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
    page_no: int = Query(1, alias="page", ge=1), page_size: int = Query(20, ge=1, le=200),
    current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    q = db.query(Ticket)
    if current.merchant_id is not None:
        q = q.filter(Ticket.merchant_id == current.merchant_id)
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
def create_ticket(body: TicketCreate, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    """创建工单。必填: title。可选: description, priority, category_id, source_id, buyer_openid, ticket_tags。"""
    # 分类存在性校验（防止 FK 违规导致 500）
    if body.category_id is not None:
        cat = db.query(TicketCategory).filter(
            TicketCategory.id == body.category_id,
            TicketCategory.merchant_id == current.merchant_id,
        ).first()
        if not cat:
            raise HTTPException(
                status_code=400,
                detail={"code": 40001, "msg": f"工单分类不存在: {body.category_id}"},
            )

    ticket_no = _gen_ticket_no(db, current.merchant_id)
    t = Ticket(
        merchant_id=current.merchant_id, ticket_no=ticket_no,
        title=body.title, description=body.description or "",
        priority=body.priority or "P3", source=body.source or "manual",
        source_id=body.source_id, buyer_openid=body.buyer_openid,
        category_id=body.category_id, created_by=current.user_id,
        ticket_tags=body.ticket_tags,
    )
    db.add(t)
    db.flush()
    # 分配日志
    db.add(TicketAssignment(ticket_id=t.id, action="created", to_user_id=current.user_id))
    # 智能分配：仅在分类有效时尝试
    if body.category_id is not None:
        try:
            _auto_assign(db, current.merchant_id, t)
        except Exception:
            pass
    db.commit()

    # 后台向量化工单（不阻塞响应）
    try:
        import threading
        def _backfill():
            from app.database.session import SessionLocal
            db2 = SessionLocal()
            try:
                from app.services.ticket_ai import backfill_tickets
                backfill_tickets(db2, current.merchant_id)
            except Exception:
                pass
            finally:
                db2.close()
        threading.Thread(target=_backfill, daemon=True).start()
    except Exception:
        pass

    return ok({"id": t.id, "ticket_no": t.ticket_no}, msg="工单已创建")


@router.get("/export")
def export_tickets(
    status: str = Query(None), priority: str = Query(None),
    assigned_to: int = Query(None),
    current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    q = db.query(Ticket)
    if current.merchant_id is not None:
        q = q.filter(Ticket.merchant_id == current.merchant_id)
    if status: q = q.filter(Ticket.status == status)
    if priority: q = q.filter(Ticket.priority == priority)
    if assigned_to: q = q.filter(Ticket.assigned_to == assigned_to)
    rows = q.order_by(Ticket.created_at.desc()).all()
    uids = {t.assigned_to for t in rows if t.assigned_to}
    unames = {u.id: u.display_name for u in db.query(MerchantUser).filter(MerchantUser.id.in_(uids)).all()} if uids else {}
    out = io.StringIO()
    out.write('﻿')
    w = csv.writer(out)
    w.writerow(["ID", "编号", "标题", "优先级", "状态", "来源", "处理人", "SLA超时", "创建时间"])
    for t in rows:
        w.writerow([t.id, t.ticket_no, t.title, t.priority, t.status, t.source,
                     unames.get(t.assigned_to, ""), "是" if t.sla_breached else "否",
                     t.created_at.isoformat() if t.created_at else ""])
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=tickets.csv"})


# ---- 分类树（必须在 /{ticket_id} 之前，防止 "categories" 被当作 ticket_id） ----
@router.get("/categories")
def list_categories(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(TicketCategory)
    if current.merchant_id is not None:
        q = q.filter(TicketCategory.merchant_id == current.merchant_id)
    cats = q.order_by(TicketCategory.level, TicketCategory.sort_order).all()

    def build(parent_id=None):
        return [{"id": c.id, "name": c.name, "level": c.level,
                 "children": build(c.id)} for c in cats if c.parent_id == parent_id]
    return ok(build())


@router.post("/categories")
def create_category(
    body: TicketCategoryCreate,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    cat = TicketCategory(
        merchant_id=current.merchant_id,
        name=body.name,
        parent_id=body.parent_id,
        level=2 if body.parent_id else 1,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return ok({"id": cat.id, "name": cat.name, "level": cat.level}, msg="分类已创建")


@router.put("/categories/{cat_id}")
def update_category(
    cat_id: int,
    body: TicketCategoryUpdate,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    cat = db.query(TicketCategory).filter(
        TicketCategory.id == cat_id,
        TicketCategory.merchant_id == current.merchant_id,
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "分类不存在"})
    if body.name is not None:
        cat.name = body.name
    db.commit()
    return ok({"id": cat.id, "name": cat.name}, msg="分类已更新")


@router.delete("/categories/{cat_id}")
def delete_category(
    cat_id: int,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    cat = db.query(TicketCategory).filter(
        TicketCategory.id == cat_id,
        TicketCategory.merchant_id == current.merchant_id,
    ).first()
    if not cat:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "分类不存在"})
    children = db.query(TicketCategory).filter(TicketCategory.parent_id == cat_id).count()
    if children:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "请先删除子分类"})
    db.delete(cat)
    db.commit()
    return ok(None, msg="分类已删除")


# ---- 预分类 / 批量（必须在 /{ticket_id} 之前） ----
@router.post("/auto-classify")
def auto_classify_create(body: TicketAutoClassifyRequest, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    """创建前预分类：给定标题+描述，返回 AI 建议的分类和优先级。"""
    from app.services.ticket_ai import classify_ticket
    return ok(classify_ticket(db, current.merchant_id, body.title, body.description or ""))


@router.post("/batch")
def batch_operation(
    body: TicketBatchOperation,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    """批量操作工单: { action: "assign"|"close", ticket_ids: [...], to_user_id?: int }"""
    if not body.ticket_ids:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "请提供 ticket_ids"})
    tickets = db.query(Ticket).filter(
        Ticket.id.in_(body.ticket_ids), Ticket.merchant_id == current.merchant_id
    ).all()
    if not tickets:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "未找到工单"})
    if body.action == "assign":
        to_uid = body.to_user_id or current.user_id
        for t in tickets:
            t.assigned_to = to_uid
            if t.status == "pending":
                t.status = "in_progress"
        db.commit()
        return ok({"count": len(tickets)}, msg=f"已分配 {len(tickets)} 个工单")
    elif body.action == "close":
        for t in tickets:
            t.status = "closed"
            t.closed_at = datetime.now()
        db.commit()
        return ok({"count": len(tickets)}, msg=f"已关闭 {len(tickets)} 个工单")
    raise HTTPException(status_code=400, detail={"code": 40002, "msg": "action 必须为 assign 或 close"})


# ---- 单个工单操作（参数化路由放在最后） ----
@router.get("/{ticket_id}")
def ticket_detail(ticket_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Ticket).filter(Ticket.id == ticket_id)
    if current.merchant_id is not None:
        q = q.filter(Ticket.merchant_id == current.merchant_id)
    t = q.first()
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
def update_ticket(ticket_id: int, body: TicketUpdate, current: CurrentUser = Depends(get_current_merchant),
                  db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    for field in ("title", "description", "priority", "category_id", "ticket_tags"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(t, field, val)
    db.commit()
    return ok({"id": t.id}, msg="已更新")


@router.post("/{ticket_id}/status")
def update_status(ticket_id: int, body: TicketStatusUpdate, current: CurrentUser = Depends(get_current_merchant),
                  db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    new_status = body.status
    if new_status not in VALID_TRANSITIONS.get(t.status, []):
        raise HTTPException(status_code=400, detail={
            "code": 40001, "msg": f"不允许从 {t.status} 转到 {new_status}"})
    if new_status == "closed" and not body.resolved_notes and not t.resolved_notes:
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
        if body.resolved_notes:
            t.resolved_notes = body.resolved_notes
    elif new_status == "closed":
        t.closed_at = now
        if body.resolved_notes:
            t.resolved_notes = body.resolved_notes
    db.commit()
    return ok({"id": t.id, "status": t.status}, msg="状态已更新")


@router.post("/{ticket_id}/assign")
def assign_ticket(ticket_id: int, body: TicketAssign, current: CurrentUser = Depends(require_roles("admin", "manager")),
                  db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    to_id = body.to_user_id
    user = db.query(MerchantUser).filter(MerchantUser.id == to_id,
                                          MerchantUser.merchant_id == current.merchant_id).first()
    if not user:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "目标用户不存在"})
    db.add(TicketAssignment(ticket_id=ticket_id, from_user_id=t.assigned_to, to_user_id=to_id,
                             action="reassigned", remark=body.remark or ""))
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


# ---- 评论 ----
@router.get("/{ticket_id}/comments")
def list_comments(ticket_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Ticket).filter(Ticket.id == ticket_id)
    if current.merchant_id is not None:
        q = q.filter(Ticket.merchant_id == current.merchant_id)
    t = q.first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    comments = db.query(TicketComment).filter(TicketComment.ticket_id == ticket_id).order_by(
        TicketComment.created_at.desc()).all()
    return ok([{"id": c.id, "user_id": c.user_id, "content": c.content,
                "is_internal": c.is_internal, "attachments": c.attachments,
                "created_at": c.created_at.isoformat() if c.created_at else None} for c in comments])


@router.post("/{ticket_id}/comments")
def add_comment(ticket_id: int, body: TicketCommentCreate, current: CurrentUser = Depends(get_current_merchant),
                db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.merchant_id == current.merchant_id).first()
    if not t:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "工单不存在"})
    c = TicketComment(ticket_id=ticket_id, user_id=current.user_id, content=body.content,
                      is_internal=body.is_internal or 0, attachments=body.attachments)
    db.add(c)
    db.commit()
    return ok({"id": c.id}, msg="已添加")


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
