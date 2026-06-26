"""技能组管理接口（PHASE3-PLAN §7）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, get_current_user, require_roles
from app.core.response import ok
from app.database.session import get_db
from app.models.merchant_user import MerchantUser
from app.models.skill_group import SkillGroup, SkillMember
from app.models.ticket import Ticket
from app.schemas import SkillGroupCreate, SkillGroupUpdate, SkillMemberAdd

router = APIRouter(prefix="/skill-groups", tags=["技能组"])


@router.get("")
def list_groups(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    groups = db.query(SkillGroup).filter(SkillGroup.merchant_id == current.merchant_id).all()
    result = []
    for g in groups:
        members = db.query(SkillMember).filter(SkillMember.group_id == g.id).all()
        member_list = []
        for m in members:
            u = db.query(MerchantUser).get(m.user_id)
            load = db.query(Ticket).filter(
                Ticket.assigned_to == m.user_id, Ticket.status.in_(["in_progress", "pending"])
            ).count()
            member_list.append({"user_id": m.user_id, "display_name": u.display_name if u else "",
                                "skill_tags": (m.skill_tags or "").split("，") if m.skill_tags else [],
                                "current_load": load})
        result.append({"id": g.id, "name": g.name, "description": g.description,
                        "is_active": g.is_active, "members": member_list})
    return ok(result)


@router.post("")
def create_group(body: SkillGroupCreate, current: CurrentUser = Depends(require_roles("admin", "manager")),
                 db: Session = Depends(get_db)):
    g = SkillGroup(merchant_id=current.merchant_id, name=body.name,
                    description=body.description or "")
    db.add(g)
    db.commit()
    return ok({"id": g.id}, msg="已创建")


@router.put("/{group_id}")
def update_group(group_id: int, body: SkillGroupUpdate, current: CurrentUser = Depends(require_roles("admin", "manager")),
                 db: Session = Depends(get_db)):
    g = db.query(SkillGroup).filter(SkillGroup.id == group_id,
                                     SkillGroup.merchant_id == current.merchant_id).first()
    if not g:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "技能组不存在"})
    for field in ("name", "description", "is_active"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(g, field, val)
    db.commit()
    return ok({"id": g.id}, msg="已更新")


@router.delete("/{group_id}")
def delete_group(group_id: int, current: CurrentUser = Depends(require_roles("admin", "manager")),
                 db: Session = Depends(get_db)):
    g = db.query(SkillGroup).filter(SkillGroup.id == group_id,
                                     SkillGroup.merchant_id == current.merchant_id).first()
    if not g:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "技能组不存在"})
    db.query(SkillMember).filter(SkillMember.group_id == group_id).delete(synchronize_session=False)
    db.delete(g)
    db.commit()
    return ok(msg="已删除")


@router.post("/{group_id}/members")
def add_member(group_id: int, body: SkillMemberAdd, current: CurrentUser = Depends(require_roles("admin", "manager")),
               db: Session = Depends(get_db)):
    g = db.query(SkillGroup).filter(SkillGroup.id == group_id,
                                     SkillGroup.merchant_id == current.merchant_id).first()
    if not g:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "技能组不存在"})
    uid = body.user_id
    u = db.query(MerchantUser).filter(MerchantUser.id == uid,
                                       MerchantUser.merchant_id == current.merchant_id).first()
    if not u:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "用户不存在"})
    tags = body.skill_tags or []
    tag_str = "，".join(tags) if isinstance(tags, list) else tags
    m = db.query(SkillMember).filter(SkillMember.group_id == group_id,
                                      SkillMember.user_id == uid).first()
    if m:
        m.skill_tags = tag_str
    else:
        db.add(SkillMember(group_id=group_id, user_id=uid, skill_tags=tag_str))
    db.commit()
    return ok(msg="已添加")


@router.delete("/{group_id}/members/{user_id}")
def remove_member(group_id: int, user_id: int,
                  current: CurrentUser = Depends(require_roles("admin", "manager")),
                  db: Session = Depends(get_db)):
    db.query(SkillMember).filter(SkillMember.group_id == group_id,
                                  SkillMember.user_id == user_id).delete(synchronize_session=False)
    db.commit()
    return ok(msg="已移除")
