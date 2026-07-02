"""多维用户画像引擎 — 融合长期记忆 + 订单行为 + 订单统计

维度：
  1. basic       — 基础属性（从 facts 提取）
  2. tags        — 兴趣标签（长期记忆 tags + 行为分析）
  3. consumption — 消费特征（统计聚合）
  4. facts       — 用户透露的偏好事实
  5. intents     — 近期意图（对话摘要）
  6. activity    — 活跃度等级
"""
from datetime import datetime
from typing import Optional

from app.database.session import SessionLocal
from app.models.external_order import ExternalOrder
from app.models.platform_shop import PlatformShop
from app.services.memory_compressor import get_long_term_memory


class UserProfileEngine:
    """多维用户画像引擎 — 闭包绑定 merchant_id"""

    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id

    def get_full_profile(self, user_id: str) -> dict:
        """获取完整多维画像。"""
        long_mem = get_long_term_memory(self.merchant_id, user_id)
        order_stats = self._get_order_stats(user_id)

        # 合并订单统计到长期记忆
        if order_stats["order_count"] > 0 and not long_mem.stats:
            long_mem.stats = order_stats
            from app.services.memory_compressor import save_long_term_memory
            save_long_term_memory(long_mem)

        # 从行为分析补充标签
        behavior_tags = self._analyze_behavior(user_id)

        # 活跃度
        activity = self._calc_activity(user_id, order_stats, long_mem)

        return {
            "basic": self._get_basic_info(user_id, long_mem),
            "tags": list(set((long_mem.tags or []) + behavior_tags)),
            "facts": long_mem.facts or {},
            "consumption": {
                "order_count": order_stats["order_count"],
                "total_spent": order_stats["total_spent"],
                "avg_order_amount": order_stats["avg_order_amount"],
                "top_categories": order_stats["top_categories"],
                "preferred_price_range": order_stats["preferred_price_range"],
                "last_order_at": order_stats["last_order_at"],
            },
            "intents": [s.get("text", "") for s in (long_mem.snippets or [])[-3:]],
            "activity_level": activity,
        }

    def _get_basic_info(self, user_id: str, long_mem) -> dict:
        """基础属性：从 facts 提取 + 订单收货信息推断。"""
        facts = long_mem.facts or {}
        basic = {
            "user_id": user_id,
            "skin_type": facts.get("skin_type", ""),
            "budget": facts.get("budget", ""),
            "allergies": facts.get("allergies", ""),
            "identity": facts.get("identity", ""),
        }

        # 从收货地址推断城市
        db = SessionLocal()
        try:
            sids = [r[0] for r in db.query(PlatformShop.id).filter(
                PlatformShop.merchant_id == self.merchant_id).all()]
            if sids:
                last_order = db.query(ExternalOrder).filter(
                    ExternalOrder.shop_id.in_(sids),
                    ExternalOrder.buyer_openid == user_id,
                ).order_by(ExternalOrder.created_at.desc()).first()
                if last_order and last_order.receiver_address:
                    basic["city"] = last_order.receiver_address[:10]
        finally:
            db.close()

        return basic

    def _get_order_stats(self, user_id: str) -> dict:
        """订单行为统计聚合。"""
        db = SessionLocal()
        default = {"order_count": 0, "total_spent": 0.0, "avg_order_amount": 0.0,
                    "top_categories": [], "preferred_price_range": "", "last_order_at": None}

        try:
            sids = [r[0] for r in db.query(PlatformShop.id).filter(
                PlatformShop.merchant_id == self.merchant_id).all()]
            if not sids:
                return default

            orders = db.query(ExternalOrder).filter(
                ExternalOrder.shop_id.in_(sids),
                ExternalOrder.buyer_openid == user_id,
                ExternalOrder.status != "pending",
            ).order_by(ExternalOrder.created_at.desc()).all()

            if not orders:
                return default

            total_spent = sum(float(o.pay_amount or 0) for o in orders)
            amounts = sorted([float(o.pay_amount or 0) for o in orders])
            mid_price = amounts[len(amounts) // 2] if amounts else 0
            price_range = f"{int(mid_price * 0.5)}-{int(mid_price * 1.5)}"

            categories = set()
            product_ids = []
            for o in orders[:10]:
                for sku in (o.sku_details_json or []):
                    title = sku.get("title", "") if isinstance(sku, dict) else ""
                    if title:
                        categories.add(title[:20])

            return {
                "order_count": len(orders),
                "total_spent": round(total_spent, 2),
                "avg_order_amount": round(total_spent / len(orders), 2),
                "top_categories": list(categories)[:5],
                "preferred_price_range": price_range,
                "last_order_at": str(orders[0].created_at) if orders else None,
            }
        finally:
            db.close()

    def _analyze_behavior(self, user_id: str) -> list[str]:
        """从订单行为分析提取标签。"""
        from collections import Counter

        db = SessionLocal()
        tags = []
        try:
            sids = [r[0] for r in db.query(PlatformShop.id).filter(
                PlatformShop.merchant_id == self.merchant_id).all()]
            if not sids:
                return tags

            orders = db.query(ExternalOrder).filter(
                ExternalOrder.shop_id.in_(sids),
                ExternalOrder.buyer_openid == user_id,
                ExternalOrder.status != "pending",
            ).all()

            cat_counter = Counter()
            for o in orders:
                for sku in (o.sku_details_json or []):
                    title = sku.get("title", "") if isinstance(sku, dict) else ""
                    if title:
                        # 简化的品类提取
                        for kw in ["护肤", "彩妆", "面霜", "防晒", "洁面", "精华", "面膜",
                                    "口红", "粉底", "眼霜", "水乳", "卸妆", "隔离", "洗面奶"]:
                            if kw in title:
                                cat_counter[kw] += 1

            tags = [kw for kw, _ in cat_counter.most_common(8)]
        finally:
            db.close()

        return tags

    def _calc_activity(self, user_id: str, order_stats: dict, long_mem) -> str:
        """计算用户活跃度。"""
        if long_mem.activity_level and long_mem.activity_level != "new":
            return long_mem.activity_level

        if order_stats["order_count"] == 0:
            return "new"

        last_at = order_stats.get("last_order_at")
        if last_at:
            try:
                last_dt = datetime.fromisoformat(last_at) if isinstance(last_at, str) else last_at
                days = (datetime.now() - last_dt).days
                if days > 90:
                    return "lost"
                if days > 30:
                    return "dormant"
            except (ValueError, TypeError):
                pass

        if order_stats["order_count"] >= 5:
            return "active"
        return "new"

    def update_fact(self, user_id: str, key: str, value: str) -> dict:
        """更新单个用户事实，持久化到长期记忆。"""
        from app.services.memory_compressor import save_long_term_memory

        long_mem = get_long_term_memory(self.merchant_id, user_id)
        facts = dict(long_mem.facts or {})
        facts[key] = value
        long_mem.facts = facts
        save_long_term_memory(long_mem)

        return {"status": "success", "key": key, "value": value}

    def get_profile_summary(self, user_id: str) -> str:
        """生成画像文本摘要，供 Agent 上下文使用。"""
        profile = self.get_full_profile(user_id)

        parts = []
        # 基础属性
        basic = profile["basic"]
        attr_parts = []
        if basic.get("skin_type"):
            attr_parts.append(f"{basic['skin_type']}肌肤")
        if basic.get("budget"):
            attr_parts.append(f"预算{basic['budget']}")
        if basic.get("allergies"):
            attr_parts.append(f"过敏源:{basic['allergies']}")
        if basic.get("identity"):
            attr_parts.append(basic["identity"])
        if attr_parts:
            parts.append("属性: " + "、".join(attr_parts))

        # 消费
        c = profile["consumption"]
        if c["order_count"] > 0:
            parts.append(
                f"消费: {c['order_count']}笔订单/¥{c['total_spent']:.0f}, "
                f"客单价¥{c['avg_order_amount']:.0f}, "
                f"偏好价位{c['preferred_price_range']}"
            )

        # 兴趣标签
        tags = profile["tags"]
        if tags:
            parts.append(f"兴趣: {', '.join(tags[:10])}")

        # 近期意图
        intents = profile["intents"]
        if intents:
            parts.append(f"近期: {'; '.join(intents)}")

        # 活跃度
        activity_map = {"new": "新用户", "active": "活跃", "dormant": "沉默", "lost": "流失"}
        parts.append(f"活跃度: {activity_map.get(profile['activity_level'], profile['activity_level'])}")

        return "\n".join(parts) if parts else f"用户 {user_id} 暂无画像数据"
