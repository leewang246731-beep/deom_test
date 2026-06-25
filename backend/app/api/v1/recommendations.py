"""
智能推荐接口（REQUIREMENTS-V2 §9.4）
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, require_roles
from app.core.response import ok
from app.database.session import get_db
from app.models.product_recommendation_rule import ProductRecommendationRule
from app.schemas import RecommendationRuleCreate

router = APIRouter(prefix="/recommendations", tags=["推荐"])


@router.post("/similar")
def similar_products(
    body: dict,
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """相似商品推荐（三路融合）。"""
    from app.services.recommendation import recommend_similar
    results = recommend_similar(
        db, current.merchant_id,
        product_id=body.get("product_id"),
        shop_id=body.get("shop_id"),
        top_k=body.get("top_k", 10),
        exclude_bought=body.get("exclude_bought", False),
        buyer_openid=body.get("buyer_openid"),
    )
    return ok({"source_product": {"id": body.get("product_id")}, "recommendations": results})


@router.post("/for-buyer")
def buyer_recommendations(
    body: dict,
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """基于买家画像推荐。"""
    from app.services.recommendation import recommend_for_buyer
    results = recommend_for_buyer(
        db, current.merchant_id,
        buyer_openid=body.get("buyer_openid"),
        shop_id=body.get("shop_id"),
        top_k=body.get("top_k", 10),
    )
    return ok({"recommendations": results})


@router.get("/hot")
def hot_products(
    shop_id: int = Query(None),
    top_k: int = Query(10),
    range_days: int = Query(7),
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """热门商品榜单。"""
    from app.services.recommendation import recommend_hot
    results = recommend_hot(db, current.merchant_id, shop_id, top_k, range_days)
    return ok({"recommendations": results})


@router.get("/rules")
def list_rules(
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    rules = db.query(ProductRecommendationRule).filter(
        ProductRecommendationRule.merchant_id == current.merchant_id
    ).order_by(ProductRecommendationRule.priority.desc()).all()
    return ok([{
        "id": r.id, "product_id": r.product_id,
        "recommended_product_id": r.recommended_product_id,
        "rule_type": r.rule_type, "priority": r.priority, "is_active": r.is_active,
    } for r in rules])


@router.post("/rules")
def create_rule(
    body: RecommendationRuleCreate,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    rule = ProductRecommendationRule(
        merchant_id=current.merchant_id,
        product_id=body.product_id,
        recommended_product_id=body.recommended_product_id,
        rule_type=body.rule_type or "manual",
        priority=body.priority or 0,
    )
    db.add(rule)
    db.commit()
    return ok({"id": rule.id}, msg="已创建")


@router.put("/rules/{rule_id}")
def update_rule(
    rule_id: int,
    body: dict,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    rule = db.query(ProductRecommendationRule).filter(
        ProductRecommendationRule.id == rule_id,
        ProductRecommendationRule.merchant_id == current.merchant_id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "规则不存在"})
    for field in ("rule_type", "priority", "is_active"):
        if field in body:
            setattr(rule, field, body[field])
    db.commit()
    return ok({"id": rule.id, "rule_type": rule.rule_type, "priority": rule.priority, "is_active": rule.is_active}, msg="已更新")


@router.post("/rules/auto-generate")
def auto_generate_rules(
    top_k: int = Query(20, ge=5, le=100),
    current: CurrentUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """从共购矩阵自动生成关联规则"""
    from app.models.product_co_purchase import ProductCoPurchase
    pairs = db.query(ProductCoPurchase).filter(
        ProductCoPurchase.co_count >= 2
    ).order_by(ProductCoPurchase.score.desc()).limit(top_k).all()
    created = 0
    for p in pairs:
        exist = db.query(ProductRecommendationRule).filter(
            ProductRecommendationRule.merchant_id == current.merchant_id,
            ProductRecommendationRule.product_id == p.product_id,
            ProductRecommendationRule.recommended_product_id == p.co_product_id,
        ).first()
        if not exist:
            db.add(ProductRecommendationRule(
                merchant_id=current.merchant_id,
                product_id=p.product_id,
                recommended_product_id=p.co_product_id,
                rule_type="auto",
                priority=int(p.score * 100),
            ))
            created += 1
    db.commit()
    return ok({"created_rules": created}, msg=f"自动生成 {created} 条规则")


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    rule = db.query(ProductRecommendationRule).filter(
        ProductRecommendationRule.id == rule_id,
        ProductRecommendationRule.merchant_id == current.merchant_id,
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "规则不存在"})
    db.delete(rule)
    db.commit()
    return ok(msg="已删除")


@router.post("/rebuild-co-purchase")
def rebuild_co_purchase(
    current: CurrentUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """重建协同过滤矩阵（仅 admin）。"""
    from app.services.recommendation import rebuild_co_purchase, rebuild_buyer_profiles
    co = rebuild_co_purchase(db, current.merchant_id)
    bp = rebuild_buyer_profiles(db, current.merchant_id)
    return ok({"co_purchase_pairs": co, "buyer_profiles": bp}, msg="重建完成")
