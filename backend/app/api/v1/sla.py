"""SLA 策略管理接口（PHASE3-PLAN §6）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_effective_merchant_id, get_current_user, require_roles
from app.core.response import ok
from app.database.session import get_db
from app.models.sla_policy import SLAPolicy
from app.schemas import SLAPolicyCreate, SLAPolicyUpdate

router = APIRouter(prefix="/sla", tags=["SLA"])


@router.get("/policies")
def list_policies(current: CurrentUser = Depends(get_current_user),
                  mid: int = Depends(get_effective_merchant_id), db: Session = Depends(get_db)):
    policies = db.query(SLAPolicy).filter(SLAPolicy.merchant_id == mid).order_by(
        SLAPolicy.priority).all()
    return ok([{"id": p.id, "priority": p.priority, "category_id": p.category_id,
                "response_minutes": p.response_minutes, "resolve_minutes": p.resolve_minutes,
                "escalate_minutes": p.escalate_minutes, "escalate_to": p.escalate_to,
                "is_active": p.is_active} for p in policies])


@router.post("/policies")
def create_policy(body: SLAPolicyCreate, current: CurrentUser = Depends(require_roles("admin", "manager")),
                  mid: int = Depends(get_effective_merchant_id), db: Session = Depends(get_db)):
    if body.priority not in ("P0", "P1", "P2", "P3"):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "优先级必须为 P0/P1/P2/P3"})
    p = SLAPolicy(merchant_id=mid, priority=body.priority,
                  response_minutes=body.response_minutes,
                  resolve_minutes=body.resolve_minutes,
                  escalate_minutes=body.escalate_minutes,
                  is_active=body.is_active if body.is_active is not None else 1)
    db.add(p)
    db.commit()
    return ok({"id": p.id}, msg="已创建")


@router.put("/policies/{policy_id}")
def update_policy(policy_id: int, body: SLAPolicyUpdate,
                  current: CurrentUser = Depends(require_roles("admin", "manager")),
                  mid: int = Depends(get_effective_merchant_id), db: Session = Depends(get_db)):
    p = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id,
                                    SLAPolicy.merchant_id == mid).first()
    if not p:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "策略不存在"})
    for f in ("response_minutes", "resolve_minutes", "escalate_minutes", "escalate_to", "is_active"):
        val = getattr(body, f, None)
        if val is not None:
            setattr(p, f, val)
    db.commit()
    return ok({"id": p.id}, msg="已更新")


@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: int, current: CurrentUser = Depends(require_roles("admin", "manager")),
                  mid: int = Depends(get_effective_merchant_id), db: Session = Depends(get_db)):
    p = db.query(SLAPolicy).filter(SLAPolicy.id == policy_id,
                                    SLAPolicy.merchant_id == mid).first()
    if not p:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "策略不存在"})
    db.delete(p)
    db.commit()
    return ok(msg="已删除")
