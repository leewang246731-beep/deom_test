"""用户画像分析 API — 商户工作台消费者画像分析与归类"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from collections import Counter

from app.api.v1.dependencies import get_effective_merchant_id
from app.core.response import ok, page, clamp_pagination
from app.database.session import get_db, SessionLocal
from app.models.long_term_memory import LongTermMemory
from app.models.buyer_profile import BuyerProfile
from app.models.external_order import ExternalOrder
from app.models.platform_shop import PlatformShop
from app.services.profile_engine import UserProfileEngine

router = APIRouter(prefix="/buyer-profiles", tags=["用户画像"])


def _shop_ids(db, merchant_id):
    return [r[0] for r in db.query(PlatformShop.id).filter(
        PlatformShop.merchant_id == merchant_id).all()]


# ===== 画像总览统计 =====

@router.get("/stats")
def profile_stats(
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    """用户画像总览统计：总量、活跃度分布、Top标签、消费分层。"""
    profiles = db.query(LongTermMemory).filter(
        LongTermMemory.merchant_id == mid
    ).all()

    total = len(profiles)
    if total == 0:
        return ok({"total": 0, "activity_breakdown": {}, "top_tags": [], "consumption_tiers": {}})

    # 活跃度分布
    activity_counter = Counter(p.activity_level or "new" for p in profiles)
    activity_map = {"new": "新用户", "active": "活跃", "dormant": "沉默", "lost": "流失"}

    # Top 标签（全量聚合）
    tag_counter = Counter()
    for p in profiles:
        for t in (p.tags or []):
            tag_counter[t] += 1

    # 消费分层
    tiers = {"low": 0, "mid": 0, "high": 0, "vip": 0}
    for p in profiles:
        stats = p.stats or {}
        total_spent = float(stats.get("total_spent", 0) or 0)
        if total_spent >= 5000:
            tiers["vip"] += 1
        elif total_spent >= 1000:
            tiers["high"] += 1
        elif total_spent >= 200:
            tiers["mid"] += 1
        else:
            tiers["low"] += 1

    return ok({
        "total": total,
        "activity_breakdown": {activity_map.get(k, k): v for k, v in activity_counter.most_common()},
        "top_tags": [{"tag": tag, "count": cnt} for tag, cnt in tag_counter.most_common(20)],
        "consumption_tiers": tiers,
    })


# ===== 画像列表 =====

@router.get("")
def list_profiles(
    activity_level: str = Query(None, description="new/active/dormant/lost"),
    tag: str = Query(None, description="按标签筛选"),
    order_count_min: int = Query(None),
    order_count_max: int = Query(None),
    sort_by: str = Query("updated_at", description="updated_at/order_count/total_spent"),
    page_num: int = Query(1, alias="page"),
    page_size: int = Query(20),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    """用户画像列表，支持多维度筛选和排序。"""
    p, ps = clamp_pagination(page_num, page_size)
    q = db.query(LongTermMemory).filter(LongTermMemory.merchant_id == mid)

    if activity_level:
        q = q.filter(LongTermMemory.activity_level == activity_level)
    if tag:
        # JSON 数组模糊匹配
        q = q.filter(LongTermMemory.tags.contains(tag))

    # 排序
    sort_map = {
        "updated_at": LongTermMemory.updated_at.desc(),
        "order_count": LongTermMemory.stats["order_count"].desc(),
        "total_spent": LongTermMemory.stats["total_spent"].desc(),
    }
    order_by = sort_map.get(sort_by, LongTermMemory.updated_at.desc())

    # 对 JSON 字段排序需要用 CASE 或先查后排
    if sort_by in ("order_count", "total_spent"):
        all_profiles = q.all()
        key_fn = lambda x: (
            float((x.stats or {}).get("total_spent", 0) or 0) if sort_by == "total_spent"
            else int((x.stats or {}).get("order_count", 0) or 0)
        )
        all_profiles.sort(key=key_fn, reverse=True)
        total = len(all_profiles)
        # 数量筛选（内存过滤）
        if order_count_min is not None:
            all_profiles = [x for x in all_profiles if int((x.stats or {}).get("order_count", 0) or 0) >= order_count_min]
            total = len(all_profiles)
        if order_count_max is not None:
            all_profiles = [x for x in all_profiles if int((x.stats or {}).get("order_count", 0) or 0) <= order_count_max]
            total = len(all_profiles)
        items = all_profiles[(p-1)*ps : p*ps]
    else:
        if order_count_min is not None:
            q = q.filter(LongTermMemory.stats["order_count"].as_integer() >= order_count_min)
        if order_count_max is not None:
            q = q.filter(LongTermMemory.stats["order_count"].as_integer() <= order_count_max)
        total = q.count()
        items = q.order_by(order_by).offset((p-1)*ps).limit(ps).all()

    profiles_list = []
    for profile in items:
        stats = profile.stats or {}
        profiles_list.append({
            "id": profile.id,
            "user_id": profile.user_id,
            "tags": profile.tags or [],
            "facts": profile.facts or {},
            "snippets": profile.snippets or [],
            "activity_level": profile.activity_level or "new",
            "order_count": stats.get("order_count", 0),
            "total_spent": float(stats.get("total_spent", 0) or 0),
            "avg_order_amount": float(stats.get("avg_order_amount", 0) or 0),
            "top_categories": stats.get("top_categories", []),
            "last_order_at": stats.get("last_order_at", ""),
            "last_conversation_at": profile.last_conversation_at.isoformat() if profile.last_conversation_at else None,
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        })

    return page(profiles_list, total, p, ps)


# ===== 画像详情 =====

@router.get("/{user_id}")
def profile_detail(
    user_id: str,
    mid: int = Depends(get_effective_merchant_id),
):
    """单个用户的完整多维画像，含 6 维度 + 订单明细。"""
    engine = UserProfileEngine(mid)
    profile = engine.get_full_profile(user_id)

    # 补充近期订单
    db = SessionLocal()
    try:
        sids = _shop_ids(db, mid)
        recent_orders = []
        if sids:
            orders = db.query(ExternalOrder).filter(
                ExternalOrder.shop_id.in_(sids),
                ExternalOrder.buyer_openid == user_id,
            ).order_by(ExternalOrder.created_at.desc()).limit(10).all()
            recent_orders = [{
                "id": o.id,
                "order_no": o.platform_order_id,
                "amount": float(o.pay_amount or 0),
                "status": o.status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            } for o in orders]
    finally:
        db.close()

    return ok({
        "user_id": user_id,
        "profile": profile,
        "recent_orders": recent_orders,
        "summary": engine.get_profile_summary(user_id),
    })


# ===== 画像标签管理 =====

@router.put("/{user_id}/tags")
def update_profile_tags(
    user_id: str,
    body: dict,
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    """更新用户标签（手动标注）。"""
    mem = db.query(LongTermMemory).filter(
        LongTermMemory.merchant_id == mid,
        LongTermMemory.user_id == user_id,
    ).first()
    if not mem:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "用户画像不存在"})

    tags = body.get("tags", [])
    if not isinstance(tags, list):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "tags 必须是数组"})

    mem.tags = tags[:20]  # 上限 20
    db.commit()
    return ok({"user_id": user_id, "tags": mem.tags}, msg="标签已更新")


@router.put("/{user_id}/facts")
def update_profile_facts(
    user_id: str,
    body: dict,
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    """更新用户事实（手动修正）。"""
    mem = db.query(LongTermMemory).filter(
        LongTermMemory.merchant_id == mid,
        LongTermMemory.user_id == user_id,
    ).first()
    if not mem:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "用户画像不存在"})

    facts = body.get("facts", {})
    current = dict(mem.facts or {})
    current.update(facts)
    mem.facts = current
    db.commit()
    return ok({"user_id": user_id, "facts": mem.facts}, msg="事实已更新")
