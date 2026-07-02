"""优惠券管理接口 — 补偿策略 / 营销活动 / 发放日志"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, get_effective_merchant_id
from app.core.response import ok, page, clamp_pagination
from app.database.session import get_db
from app.models.coupon import CompensationPolicy, CouponGrantLog, MarketingCampaign
from app.schemas import (
    CompensationPolicyCreate,
    CompensationPolicyUpdate,
    MarketingCampaignCreate,
    MarketingCampaignUpdate,
)
from app.services.coupon_engine import MarketingEngine

router = APIRouter(prefix="/coupons", tags=["优惠券"])


# ===== 售后补偿策略 CRUD =====

@router.get("/compensation-policies")
def list_compensation_policies(
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    policies = db.query(CompensationPolicy).filter(
        CompensationPolicy.merchant_id == mid,
    ).order_by(CompensationPolicy.created_at.desc()).all()
    return ok([
        {
            "id": p.id,
            "scenario": p.scenario,
            "coupon_template_id": p.coupon_template_id,
            "max_amount": float(p.max_amount) if p.max_amount else None,
            "max_times_per_order": p.max_times_per_order,
            "cooldown_hours": p.cooldown_hours,
            "require_manual": p.require_manual,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in policies
    ])


@router.post("/compensation-policies")
def create_compensation_policy(
    body: CompensationPolicyCreate,
    current: CurrentUser = Depends(get_current_merchant),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    policy = CompensationPolicy(
        merchant_id=mid,
        scenario=body.scenario,
        coupon_template_id=body.coupon_template_id,
        max_amount=body.max_amount,
        max_times_per_order=body.max_times_per_order or 1,
        cooldown_hours=body.cooldown_hours or 24,
        require_manual=body.require_manual or False,
        is_active=body.is_active if body.is_active is not None else True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return ok({"id": policy.id, "scenario": policy.scenario}, msg="补偿策略已创建")


@router.put("/compensation-policies/{policy_id}")
def update_compensation_policy(
    policy_id: int,
    body: CompensationPolicyUpdate,
    current: CurrentUser = Depends(get_current_merchant),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    policy = db.query(CompensationPolicy).filter(
        CompensationPolicy.id == policy_id,
        CompensationPolicy.merchant_id == mid,
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "补偿策略不存在"})

    update_data = body.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(policy, key, val)
    db.commit()
    return ok({"id": policy.id}, msg="补偿策略已更新")


@router.delete("/compensation-policies/{policy_id}")
def delete_compensation_policy(
    policy_id: int,
    current: CurrentUser = Depends(get_current_merchant),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    policy = db.query(CompensationPolicy).filter(
        CompensationPolicy.id == policy_id,
        CompensationPolicy.merchant_id == mid,
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "补偿策略不存在"})
    db.delete(policy)
    db.commit()
    return ok(msg="补偿策略已删除")


# ===== 售前营销活动 CRUD =====

@router.get("/marketing-campaigns")
def list_marketing_campaigns(
    include_inactive: bool = Query(False),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    q = db.query(MarketingCampaign).filter(MarketingCampaign.merchant_id == mid)
    if not include_inactive:
        q = q.filter(MarketingCampaign.is_active == True)
    campaigns = q.order_by(MarketingCampaign.created_at.desc()).all()
    return ok([
        {
            "id": c.id,
            "campaign_name": c.campaign_name,
            "coupon_template_id": c.coupon_template_id,
            "target_user_type": c.target_user_type,
            "max_issue_total": c.max_issue_total,
            "max_issue_per_user": c.max_issue_per_user,
            "start_time": c.start_time.isoformat() if c.start_time else None,
            "end_time": c.end_time.isoformat() if c.end_time else None,
            "require_manual": c.require_manual,
            "is_active": c.is_active,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in campaigns
    ])


@router.post("/marketing-campaigns")
def create_marketing_campaign(
    body: MarketingCampaignCreate,
    current: CurrentUser = Depends(get_current_merchant),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    campaign = MarketingCampaign(
        merchant_id=mid,
        campaign_name=body.campaign_name or "",
        coupon_template_id=body.coupon_template_id,
        target_user_type=body.target_user_type or "all",
        max_issue_total=body.max_issue_total,
        max_issue_per_user=body.max_issue_per_user or 1,
        start_time=datetime.fromisoformat(body.start_time) if body.start_time else datetime.now(),
        end_time=datetime.fromisoformat(body.end_time) if body.end_time else None,
        require_manual=body.require_manual or False,
        is_active=body.is_active if body.is_active is not None else True,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return ok({"id": campaign.id, "campaign_name": campaign.campaign_name}, msg="营销活动已创建")


@router.put("/marketing-campaigns/{campaign_id}")
def update_marketing_campaign(
    campaign_id: int,
    body: MarketingCampaignUpdate,
    current: CurrentUser = Depends(get_current_merchant),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    campaign = db.query(MarketingCampaign).filter(
        MarketingCampaign.id == campaign_id,
        MarketingCampaign.merchant_id == mid,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "营销活动不存在"})

    update_data = body.model_dump(exclude_unset=True)
    # 处理时间字段
    for time_field in ("start_time", "end_time"):
        if time_field in update_data and update_data[time_field] is not None:
            update_data[time_field] = datetime.fromisoformat(update_data[time_field])
    for key, val in update_data.items():
        setattr(campaign, key, val)
    db.commit()
    return ok({"id": campaign.id}, msg="营销活动已更新")


@router.delete("/marketing-campaigns/{campaign_id}")
def delete_marketing_campaign(
    campaign_id: int,
    current: CurrentUser = Depends(get_current_merchant),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    campaign = db.query(MarketingCampaign).filter(
        MarketingCampaign.id == campaign_id,
        MarketingCampaign.merchant_id == mid,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "营销活动不存在"})
    db.delete(campaign)
    db.commit()
    return ok(msg="营销活动已删除")


# ===== 发放日志查询 =====

@router.get("/grant-logs")
def list_grant_logs(
    type: str = Query(None),
    user_id: str = Query(None),
    order_id: str = Query(None),
    campaign_id: int = Query(None),
    page_num: int = Query(1, alias="page"),
    page_size: int = Query(20),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    p, ps = clamp_pagination(page_num, page_size)
    q = db.query(CouponGrantLog).filter(CouponGrantLog.merchant_id == mid)
    if type:
        q = q.filter(CouponGrantLog.type == type)
    if user_id:
        q = q.filter(CouponGrantLog.user_id == user_id)
    if order_id:
        q = q.filter(CouponGrantLog.order_id == order_id)
    if campaign_id:
        q = q.filter(CouponGrantLog.campaign_id == campaign_id)

    total = q.count()
    logs = q.order_by(CouponGrantLog.created_at.desc()).offset((p - 1) * ps).limit(ps).all()
    items = [
        {
            "id": l.id,
            "user_id": l.user_id,
            "order_id": l.order_id,
            "campaign_id": l.campaign_id,
            "type": l.type,
            "scenario": l.scenario,
            "coupon_code": l.coupon_code,
            "amount": float(l.amount) if l.amount else None,
            "reason": l.reason,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]
    return page(items, total, p, ps)


# ===== 活跃活动查询（供 Agent / 前端使用）=====

@router.get("/active-campaigns")
def active_campaigns(
    mid: int = Depends(get_effective_merchant_id),
):
    """返回当前有效的营销活动列表，供 Agent 推荐使用"""
    engine = MarketingEngine(mid)
    return ok(engine.list_active_campaigns())
