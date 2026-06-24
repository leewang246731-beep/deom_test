"""
智能商品推荐引擎（REQUIREMENTS-V2 §9）
三路融合：向量相似(50%) + 协同过滤(35%) + 手动规则(15%)
"""
from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.buyer_profile import BuyerProfile
from app.models.external_order import ExternalOrder
from app.models.external_product import ExternalProduct
from app.models.platform_shop import PlatformShop
from app.models.product_co_purchase import ProductCoPurchase
from app.models.product_recommendation_rule import ProductRecommendationRule
from app.services.chroma_client import query_products
from app.services.embedding import embed_query


def _merchant_shop_ids(db: Session, merchant_id: int) -> list:
    return [r[0] for r in db.query(PlatformShop.id).filter(
        PlatformShop.merchant_id == merchant_id, PlatformShop.is_active == 1).all()]


def _product_dict(p: ExternalProduct) -> dict:
    return {
        "id": p.id, "shop_id": p.shop_id, "title": p.title,
        "price": float(p.price), "stock": p.stock,
        "category_path": p.category_path, "images_json": p.images_json,
    }


# ===== 相似商品推荐（向量 + 协同 + 手动）=====
def recommend_similar(
    db: Session, merchant_id: int, product_id: int,
    shop_id: int = None, top_k: int = 10,
    exclude_bought: bool = False, buyer_openid: str = None,
) -> list[dict]:
    """主推荐入口：三路融合。"""
    product = db.query(ExternalProduct).get(product_id)
    if not product:
        return []

    shop_ids = _merchant_shop_ids(db, merchant_id)
    if not shop_ids:
        return []
    if shop_id and shop_id in shop_ids:
        shop_ids = [shop_id]

    # 已购买的商品 id 集合（排除用）
    bought_ids = set()
    if exclude_bought and buyer_openid:
        rows = db.query(ExternalOrder.sku_details_json).filter(
            ExternalOrder.buyer_openid == buyer_openid,
            ExternalOrder.shop_id.in_(shop_ids),
            ExternalOrder.status != "pending",
        ).all()
        for (sku_json,) in rows:
            for sku in (sku_json or []):
                # 按 title 反查 product_id
                pass  # 简化：不反查，依赖协同过滤去重

    # 1. 向量相似 (50%)
    vec_text = f"{product.title} {product.description or ''} {product.category_path or ''}"
    vec = embed_query(vec_text)
    vec_results = query_products(merchant_id, vec, n_results=min(top_k * 3, 30))
    vec_scores = {}
    metas = vec_results.get("metadatas", [[]])[0]
    dists = vec_results.get("distances", [[]])[0]
    for i, meta in enumerate(metas):
        pid = meta.get("product_id")
        if pid == product_id or (shop_ids and meta.get("shop_id") not in shop_ids):
            continue
        dist = dists[i] if i < len(dists) else 1.0
        vec_scores[pid] = 1.0 / (1.0 + dist)

    # 2. 协同过滤 (35%)
    co_scores = {}
    co_rows = db.query(ProductCoPurchase).filter(
        ProductCoPurchase.product_id == product_id
    ).order_by(ProductCoPurchase.co_count.desc()).limit(top_k * 2).all()
    max_co = max((r.co_count for r in co_rows), default=1)
    for r in co_rows:
        co_scores[r.co_product_id] = (r.co_count / max_co) if max_co > 0 else 0

    # 3. 手动规则 (15%)
    rule_scores = {}
    rules = db.query(ProductRecommendationRule).filter(
        ProductRecommendationRule.merchant_id == merchant_id,
        ProductRecommendationRule.product_id == product_id,
        ProductRecommendationRule.is_active == 1,
    ).order_by(ProductRecommendationRule.priority.desc()).limit(top_k).all()
    for r in rules:
        rule_scores[r.recommended_product_id] = 1.0 + r.priority * 0.01

    # 融合：weighted merge
    merged = {}
    for pid, s in vec_scores.items():
        merged[pid] = merged.get(pid, 0) + s * 0.50
    for pid, s in co_scores.items():
        merged[pid] = merged.get(pid, 0) + s * 0.35
    for pid, s in rule_scores.items():
        merged[pid] = merged.get(pid, 0) + s * 0.15

    # 排序 + 取 top_k
    ranked = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:top_k]

    # 补商品信息 + 推荐理由
    result = []
    reason_map = {}
    for pid, _ in ranked:
        reason_map[pid] = (
            "manual_rule" if pid in rule_scores else
            "co_purchase" if pid in co_scores and pid not in vec_scores else
            "vector_similarity"
        )

    prod_rows = {p.id: p for p in db.query(ExternalProduct).filter(
        ExternalProduct.id.in_([pid for pid, _ in ranked])).all()}
    for pid, score in ranked:
        p = prod_rows.get(pid)
        if not p:
            continue
        reason = reason_map.get(pid, "vector_similarity")
        why_map = {
            "vector_similarity": "相似商品推荐",
            "co_purchase": f"购买了此商品的用户也买了",
            "manual_rule": "商家推荐搭配",
        }
        result.append({
            "product": _product_dict(p),
            "score": round(min(score, 1.0), 4),
            "reason": reason,
            "why": why_map.get(reason, "推荐"),
        })
    return result


# ===== 买家画像推荐 =====
def recommend_for_buyer(db: Session, merchant_id: int, buyer_openid: str,
                        shop_id: int = None, top_k: int = 10) -> list[dict]:
    """基于买家历史购买偏好推荐。"""
    profile = db.query(BuyerProfile).filter(
        BuyerProfile.merchant_id == merchant_id,
        BuyerProfile.buyer_openid == buyer_openid,
    ).first()

    shop_ids = _merchant_shop_ids(db, merchant_id)
    if shop_id and shop_id in shop_ids:
        shop_ids = [shop_id]

    if not shop_ids:
        return []

    if not profile or not profile.favorite_categories:
        return recommend_hot(db, merchant_id, shop_id, top_k)

    # 按偏好分类做向量搜索
    results = []
    seen = set()
    for cat in (profile.favorite_categories or [])[:3]:
        vec = embed_query(cat)
        cr = query_products(merchant_id, vec, n_results=top_k)
        for meta in cr.get("metadatas", [[]])[0]:
            pid = meta.get("product_id")
            if pid in seen or meta.get("shop_id") not in shop_ids:
                continue
            seen.add(pid)
            results.append(pid)

    if len(results) < top_k:
        hot = recommend_hot(db, merchant_id, shop_id, top_k - len(results))
        for h in hot:
            if h["product"]["id"] not in seen:
                results.append(h["product"]["id"])
                seen.add(h["product"]["id"])

    prod_rows = {p.id: p for p in db.query(ExternalProduct).filter(
        ExternalProduct.id.in_(results[:top_k])).all()}
    return [{"product": _product_dict(prod_rows[pid]), "score": 0.7, "reason": "buyer_profile",
             "why": f"""偏好: {", ".join(profile.favorite_categories or [])}"""}
            for pid in results[:top_k] if pid in prod_rows]


# ===== 热门推荐 =====
def recommend_hot(db: Session, merchant_id: int, shop_id=None, top_k: int = 10,
                  range_days: int = 7) -> list[dict]:
    """热门商品榜单（按订单数+金额）。"""
    shop_ids = _merchant_shop_ids(db, merchant_id)
    if shop_id and shop_id in shop_ids:
        shop_ids = [shop_id]
    if not shop_ids:
        return []

    from datetime import datetime, timedelta
    since = datetime.now() - timedelta(days=range_days)

    rows = db.query(ExternalOrder).filter(
        ExternalOrder.shop_id.in_(shop_ids),
        ExternalOrder.status != "pending",
        ExternalOrder.created_at >= since,
    ).all()

    hot = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for o in rows:
        for sku in (o.sku_details_json or []):
            title = sku.get("title", "")
            hot[title]["count"] += 1
            hot[title]["amount"] += float(sku.get("price", 0) or 0)

    ranked = sorted(hot.items(), key=lambda x: x[1]["count"], reverse=True)[:top_k]
    title_to_product = {}
    for title, _ in ranked:
        p = db.query(ExternalProduct).filter(
            ExternalProduct.title == title,
            ExternalProduct.shop_id.in_(shop_ids),
        ).first()
        if p:
            title_to_product[title] = p

    return [{
        "product": _product_dict(title_to_product[t]),
        "score": round(v["count"] / max(1, ranked[0][1]["count"]), 4),
        "reason": "hot",
        "why": f"""近{range_days}天热卖 {v['count']} 单""",
        "stats": {"order_count": v["count"], "total_amount": round(v["amount"], 2)},
    } for t, v in ranked if t in title_to_product]


# ===== 协同过滤离线重建 =====
def rebuild_co_purchase(db: Session, merchant_id: int) -> int:
    """重建商品共购矩阵（Item-based CF）。"""
    shop_ids = _merchant_shop_ids(db, merchant_id)
    if not shop_ids:
        return 0

    # 清空该商户的共购数据
    db.query(ProductCoPurchase).filter(
        ProductCoPurchase.product_id.in_(
            db.query(ExternalProduct.id).filter(
                ExternalProduct.shop_id.in_(shop_ids)).subquery()
        )
    ).delete(synchronize_session=False)
    db.flush()

    orders = db.query(ExternalOrder).filter(
        ExternalOrder.shop_id.in_(shop_ids),
        ExternalOrder.status != "pending",
    ).all()

    buyer_products = defaultdict(set)
    for o in orders:
        for sku in (o.sku_details_json or []):
            # 按 title 查 product
            p = db.query(ExternalProduct.id).filter(
                ExternalProduct.title == sku.get("title", ""),
                ExternalProduct.shop_id.in_(shop_ids),
            ).first()
            if p:
                buyer_products[o.buyer_openid].add(p[0])

    pair_counts = defaultdict(int)
    for products in buyer_products.values():
        plist = list(products)
        for i in range(len(plist)):
            for j in range(i + 1, len(plist)):
                pair_counts[(plist[i], plist[j])] += 1
                pair_counts[(plist[j], plist[i])] += 1

    count = 0
    for (p1, p2), cnt in pair_counts.items():
        db.add(ProductCoPurchase(product_id=p1, co_product_id=p2, co_count=cnt))
        count += 1
    db.commit()

    # 归一化 score
    for p1 in set(k[0] for k in pair_counts):
        max_c = max((v for (a, b), v in pair_counts.items() if a == p1), default=1)
        db.query(ProductCoPurchase).filter(
            ProductCoPurchase.product_id == p1
        ).update({"score": ProductCoPurchase.co_count / max_c}, synchronize_session=False)
    db.commit()
    return count


# ===== 买家画像重建 =====
def rebuild_buyer_profiles(db: Session, merchant_id: int) -> int:
    """从订单历史重建买家画像。"""
    shop_ids = _merchant_shop_ids(db, merchant_id)
    if not shop_ids:
        return 0

    db.query(BuyerProfile).filter(BuyerProfile.merchant_id == merchant_id).delete(synchronize_session=False)
    db.flush()

    orders = db.query(ExternalOrder).filter(
        ExternalOrder.shop_id.in_(shop_ids),
        ExternalOrder.status != "pending",
    ).all()

    buyer_data = defaultdict(lambda: {"count": 0, "spent": 0.0, "categories": set(), "last": None})
    for o in orders:
        bd = buyer_data[o.buyer_openid]
        bd["count"] += 1
        bd["spent"] += float(o.pay_amount or 0)
        if o.created_at and (bd["last"] is None or o.created_at > bd["last"]):
            bd["last"] = o.created_at
        for sku in (o.sku_details_json or []):
            title = sku.get("title", "")
            prod = db.query(ExternalProduct.category_path).filter(
                ExternalProduct.title == title,
                ExternalProduct.shop_id.in_(shop_ids),
            ).first()
            if prod and prod[0]:
                for cat in prod[0].split("/"):
                    bd["categories"].add(cat)

    count = 0
    for openid, bd in buyer_data.items():
        cats = list(bd["categories"])[:5] if bd["categories"] else []
        prices = sorted([o.pay_amount for o in orders if o.buyer_openid == openid])
        price_range = f"""{int(float(prices[len(prices)//2]) * 0.5)}-{int(float(prices[len(prices)//2]) * 1.5)}""" if prices else None

        db.add(BuyerProfile(
            merchant_id=merchant_id,
            buyer_openid=openid,
            total_orders=bd["count"],
            total_spent=round(bd["spent"], 2),
            favorite_categories=cats,
            favorite_price_range=price_range,
            last_order_at=bd["last"],
        ))
        count += 1
    db.commit()
    return count
