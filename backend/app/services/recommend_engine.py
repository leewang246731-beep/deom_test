"""增强推荐引擎 — 基于多维画像的多路召回 + 策略排序 + 个性化理由

召回路径:
  1. 兴趣标签匹配（商品标签倒排索引）
  2. 历史行为协同过滤（Item-based CF）
  3. 实时需求语义匹配（向量检索）
  4. 肤质/偏好事实规则匹配
  5. 冷启动热门兜底

排序权重（可配）:
  - 个性化匹配度  × 0.40
  - 消费带匹配    × 0.20
  - 商户运营策略  × 0.20
  - 时效性/新品   × 0.20
"""
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.external_order import ExternalOrder
from app.models.external_product import ExternalProduct
from app.models.platform_shop import PlatformShop
from app.models.product_co_purchase import ProductCoPurchase
from app.models.product_recommendation_rule import ProductRecommendationRule


def _shop_ids(db: Session, merchant_id: int) -> list:
    return [r[0] for r in db.query(PlatformShop.id).filter(
        PlatformShop.merchant_id == merchant_id, PlatformShop.is_active == 1).all()]


def _product_dict(p: ExternalProduct) -> dict:
    return {
        "id": p.id, "shop_id": p.shop_id, "title": p.title,
        "price": float(p.price), "stock": p.stock,
        "category_path": p.category_path or "",
        "images_json": p.images_json,
    }


# ===== 多路召回 =====

class ProductRecall:
    """多路召回器 — 闭包绑定 merchant_id"""

    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id

    def recall(self, profile: dict, need_tags: list[str], top_n: int = 50) -> list[int]:
        """多路召回，返回候选商品 ID 列表。"""
        candidate_ids: set[int] = set()
        db = SessionLocal()
        try:
            sids = _shop_ids(db, self.merchant_id)
            if not sids:
                return []

            # 路1: 兴趣标签 + 需求标签 → 商品向量检索
            all_tags = list(set(
                (profile.get("tags", []) or []) + (need_tags or [])
            ))
            if all_tags:
                vec_ids = self._vector_recall(all_tags, sids, top_n=20)
                candidate_ids.update(vec_ids)

            # 路2: 协同过滤（基于最近购买的商品）
            cf_ids = self._cf_recall(profile, sids, db)
            candidate_ids.update(cf_ids)

            # 路3: 肤质/偏好事实规则匹配
            facts = profile.get("facts", {}) or {}
            if "skin_type" in facts:
                rule_ids = self._rule_recall(facts, sids, db)
                candidate_ids.update(rule_ids)

            # 路4: 消费带内商品
            consumption = profile.get("consumption", {}) or {}
            price_range = consumption.get("preferred_price_range", "")
            if price_range:
                price_ids = self._price_recall(price_range, sids, db)
                candidate_ids.update(price_ids)

            # 路5: 热门兜底
            if len(candidate_ids) < 10:
                hot_ids = self._hot_recall(sids, db, top_n=20)
                candidate_ids.update(hot_ids)

            return list(candidate_ids)[:top_n]
        finally:
            db.close()

    def _vector_recall(self, tags: list[str], sids: list[int], top_n: int) -> list[int]:
        """向量语义检索。"""
        try:
            from app.services.chroma_client import query_products
            from app.services.embedding import embed_query

            vec = embed_query(" ".join(tags[:5]))
            results = query_products(self.merchant_id, vec, n_results=top_n)
            ids = []
            for meta in results.get("metadatas", [[]])[0]:
                pid = meta.get("product_id")
                if pid and meta.get("shop_id") in sids:
                    ids.append(pid)
            return ids
        except Exception:
            return []

    def _cf_recall(self, profile: dict, sids: list[int], db: Session) -> list[int]:
        """协同过滤：最近购买商品 → 相似商品。"""
        consumption = profile.get("consumption", {}) or {}
        last_orders = []
        if consumption.get("order_count", 0) > 0:
            last_orders = db.query(ExternalOrder).filter(
                ExternalOrder.shop_id.in_(sids),
                ExternalOrder.status != "pending",
            ).order_by(ExternalOrder.created_at.desc()).limit(3).all()

        cf_ids = set()
        for o in last_orders:
            for sku in (o.sku_details_json or [])[:3]:
                title = sku.get("title", "") if isinstance(sku, dict) else ""
                if title:
                    prod = db.query(ExternalProduct.id).filter(
                        ExternalProduct.title == title,
                        ExternalProduct.shop_id.in_(sids),
                    ).first()
                    if prod:
                        co_rows = db.query(ProductCoPurchase).filter(
                            ProductCoPurchase.product_id == prod[0],
                        ).order_by(ProductCoPurchase.co_count.desc()).limit(5).all()
                        for cr in co_rows:
                            cf_ids.add(cr.co_product_id)

        return list(cf_ids)[:15]

    def _rule_recall(self, facts: dict, sids: list[int], db: Session) -> list[int]:
        """基于用户事实的规则匹配。"""
        rule_ids = set()
        skin_type = facts.get("skin_type", "")
        if skin_type:
            # 搜索适合该肤质的商品（通过标题关键词）
            skin_kw_map = {
                "油性": ["清爽", "控油", "油皮", "哑光", "无油"],
                "干性": ["保湿", "滋润", "干皮", "补水", "水润"],
                "敏感": ["温和", "舒缓", "敏感肌", "无添加", "修护"],
            }
            keywords = skin_kw_map.get(skin_type, [])
            for kw in keywords[:3]:
                prods = db.query(ExternalProduct.id).filter(
                    ExternalProduct.shop_id.in_(sids),
                    ExternalProduct.title.like(f"%{kw}%"),
                ).limit(10).all()
                for p in prods:
                    rule_ids.add(p[0])

        # 预算匹配
        budget = facts.get("budget", "")
        if budget:
            try:
                budget_val = float(budget.replace("以内", "").strip())
                prods = db.query(ExternalProduct.id).filter(
                    ExternalProduct.shop_id.in_(sids),
                    ExternalProduct.price <= budget_val * 1.2,
                ).order_by(ExternalProduct.price.desc()).limit(10).all()
                for p in prods:
                    rule_ids.add(p[0])
            except ValueError:
                pass

        return list(rule_ids)[:15]

    def _price_recall(self, price_range: str, sids: list[int], db: Session) -> list[int]:
        """消费带内商品召回。"""
        try:
            parts = price_range.split("-")
            lo, hi = float(parts[0]), float(parts[1])
            prods = db.query(ExternalProduct.id).filter(
                ExternalProduct.shop_id.in_(sids),
                ExternalProduct.price >= lo * 0.7,
                ExternalProduct.price <= hi * 1.3,
            ).order_by(ExternalProduct.stock.desc()).limit(10).all()
            return [p[0] for p in prods]
        except (ValueError, IndexError):
            return []

    def _hot_recall(self, sids: list[int], db: Session, top_n: int = 20) -> list[int]:
        """热门商品兜底。"""
        since = datetime.now() - timedelta(days=30)
        rows = db.query(ExternalOrder).filter(
            ExternalOrder.shop_id.in_(sids),
            ExternalOrder.status != "pending",
            ExternalOrder.created_at >= since,
        ).all()

        hot = defaultdict(int)
        for o in rows:
            for sku in (o.sku_details_json or []):
                title = sku.get("title", "") if isinstance(sku, dict) else ""
                hot[title] += 1

        ranked = sorted(hot.items(), key=lambda x: x[1], reverse=True)[:top_n]
        ids = []
        for title, _ in ranked:
            p = db.query(ExternalProduct.id).filter(
                ExternalProduct.title == title,
                ExternalProduct.shop_id.in_(sids),
            ).first()
            if p:
                ids.append(p[0])
        return ids


# ===== 策略排序 =====

class ProductRanker:
    """排序器 — 多因子加权"""

    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id
        # 权重配置（后续可从商户配置读取）
        self.weights = {
            "personalization": 0.40,
            "price_match": 0.20,
            "merchant_strategy": 0.20,
            "freshness": 0.20,
        }

    def rank(self, candidate_ids: list[int], profile: dict, need_tags: list[str],
             top_k: int = 3) -> list[dict]:
        """对候选商品排序并返回 Top-K。"""
        if not candidate_ids:
            return []

        db = SessionLocal()
        try:
            products = db.query(ExternalProduct).filter(
                ExternalProduct.id.in_(candidate_ids),
                ExternalProduct.status == 1,
            ).all()

            scored = []
            profile_tags = set(profile.get("tags", []) or [])
            facts = profile.get("facts", {}) or {}
            consumption = profile.get("consumption", {}) or {}
            avg_amount = consumption.get("avg_order_amount", 0)
            price_range_str = consumption.get("preferred_price_range", "")
            skin_type = facts.get("skin_type", "")

            # 解析价格带
            price_lo, price_hi = 0, float("inf")
            if price_range_str:
                try:
                    parts = price_range_str.split("-")
                    price_lo, price_hi = float(parts[0]), float(parts[1])
                except (ValueError, IndexError):
                    pass

            for p in products:
                score = 0.0

                # 1. 个性化匹配度 (0.40)
                prod_tags = set(self._extract_tags(p.title))
                if profile_tags:
                    jaccard = len(prod_tags & profile_tags) / max(1, len(prod_tags | profile_tags))
                    score += jaccard * self.weights["personalization"]

                # 需求标签额外加分
                need_tag_match = any(t in p.title for t in (need_tags or []))
                if need_tag_match:
                    score += 0.15

                # 2. 消费带匹配 (0.20)
                if price_lo > 0 and price_lo <= float(p.price) <= price_hi:
                    score += self.weights["price_match"]
                elif avg_amount > 0 and float(p.price) <= avg_amount * 1.2:
                    score += self.weights["price_match"] * 0.7

                # 3. 商户策略 (0.20) — 库存优先 + 手动规则加权
                strategy_score = 0.0
                if p.stock and p.stock > 50:
                    strategy_score += 0.10
                # 检查是否有手动规则提权
                rule = db.query(ProductRecommendationRule).filter(
                    ProductRecommendationRule.merchant_id == self.merchant_id,
                    ProductRecommendationRule.recommended_product_id == p.id,
                    ProductRecommendationRule.is_active == 1,
                ).first()
                if rule:
                    strategy_score += 0.10 + rule.priority * 0.01
                score += strategy_score * (self.weights["merchant_strategy"] / 0.20)

                # 4. 时效性 (0.20) — 新品/有库存
                freshness = 0.0
                if p.created_at and (datetime.now() - p.created_at).days < 30:
                    freshness += 0.15
                if p.stock and p.stock > 0:
                    freshness += 0.05
                score += freshness * (self.weights["freshness"] / 0.20)

                scored.append({
                    "product": _product_dict(p),
                    "score": round(min(score, 1.0), 4),
                    "skin_type": skin_type,
                })

            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:top_k]
        finally:
            db.close()

    @staticmethod
    def _extract_tags(title: str) -> list[str]:
        """从标题提取品类标签。"""
        keywords = ["护肤", "彩妆", "面霜", "防晒", "洁面", "精华", "面膜",
                     "口红", "粉底", "眼霜", "水乳", "卸妆", "隔离", "洗面奶",
                     "控油", "保湿", "美白", "修护", "抗老", "清爽", "滋润"]
        return [kw for kw in keywords if kw in title]


# ===== 个性化推荐理由 =====

def generate_reason(profile: dict, product: dict, score: float) -> str:
    """基于画像和商品属性生成个性化推荐理由（规则模板，无 LLM 幻觉）。"""
    reasons = []
    consumption = profile.get("consumption", {}) or {}
    tags = profile.get("tags", []) or []
    facts = profile.get("facts", {}) or {}
    skin_type = facts.get("skin_type", "")
    title = product.get("title", "")
    price = product.get("price", 0)

    # 品类匹配
    top_cats = consumption.get("top_categories", []) or []
    for cat in top_cats[:3]:
        if cat[:6] in title:
            reasons.append(f"您常买的品类")
            break

    # 肤质匹配
    if skin_type:
        skin_kw_map = {
            "油性": ["清爽", "控油", "油皮"],
            "干性": ["保湿", "滋润", "水润"],
            "敏感": ["温和", "舒缓", "修护", "无添加"],
        }
        match_kw = skin_kw_map.get(skin_type, [])
        if any(kw in title for kw in match_kw):
            reasons.append(f"适合{skin_type}肌肤")

    # 价格合适
    avg_amount = consumption.get("avg_order_amount", 0)
    if avg_amount > 0 and price <= avg_amount * 1.2:
        reasons.append("价格合适")

    # 标签匹配
    tag_match = [t for t in tags if t in title]
    if tag_match:
        reasons.append("符合您的偏好")

    # 不重复
    seen = set()
    unique = []
    for r in reasons:
        if r not in seen:
            unique.append(r)
            seen.add(r)

    return "、".join(unique) if unique else "热销推荐"


# ===== 统一入口 =====

class ProductRecommendEngine:
    """增强推荐引擎入口 — 闭包绑定 merchant_id"""

    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id
        self.recall = ProductRecall(merchant_id)
        self.ranker = ProductRanker(merchant_id)

    def recommend(self, profile: dict, need_tags: list[str] = None,
                  top_k: int = 3) -> list[dict]:
        """主推荐流程：召回 → 排序 → 附加理由。"""
        need_tags = need_tags or []

        # 1. 多路召回
        candidates = self.recall.recall(profile, need_tags, top_n=50)

        # 2. 策略排序
        ranked = self.ranker.rank(candidates, profile, need_tags, top_k)

        # 3. 附加理由
        for item in ranked:
            item["reason"] = generate_reason(profile, item["product"], item["score"])

        # 4. 补充热门兜底（如果召回不足）
        if len(ranked) < top_k:
            db = SessionLocal()
            try:
                from app.services.recommendation import recommend_hot
                sids = _shop_ids(db, self.merchant_id)
                hot = recommend_hot(db, self.merchant_id, sids[0] if sids else None,
                                   top_k=top_k - len(ranked))
                for h in hot:
                    h["reason"] = "热销推荐"
                    h["score"] = 0.3
                ranked.extend(hot)
            finally:
                db.close()

        return ranked[:top_k]
