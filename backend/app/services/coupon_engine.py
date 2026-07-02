"""优惠券业务引擎 — 售后补偿 + 售前营销"""
from datetime import datetime, timedelta
from typing import Optional

from app.database.session import SessionLocal
from app.models.coupon import CompensationPolicy, CouponGrantLog, MarketingCampaign


class PolicyEngine:
    """售后补偿策略引擎 — 校验用户是否有资格领取补偿券"""

    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id

    def get_policy(self, scenario: str) -> Optional[CompensationPolicy]:
        db = SessionLocal()
        try:
            return db.query(CompensationPolicy).filter_by(
                merchant_id=self.merchant_id,
                scenario=scenario,
                is_active=True,
            ).first()
        finally:
            db.close()

    def check_eligibility(self, user_id: str, order_id: str, scenario: str):
        """校验补偿资格。

        Returns:
            (allowed: bool, message: str, policy: CompensationPolicy | None)
        """
        policy = self.get_policy(scenario)
        if not policy:
            return False, "该场景未配置补偿策略", None

        db = SessionLocal()
        try:
            # 同一订单该场景发放次数
            count = db.query(CouponGrantLog).filter_by(
                merchant_id=self.merchant_id,
                order_id=order_id,
                scenario=scenario,
            ).count()
            if count >= policy.max_times_per_order:
                return False, f"该订单已补偿过{count}次，已达上限", policy

            # 用户冷却期
            if policy.cooldown_hours > 0:
                cooldown_start = datetime.now() - timedelta(hours=policy.cooldown_hours)
                recent = db.query(CouponGrantLog).filter(
                    CouponGrantLog.merchant_id == self.merchant_id,
                    CouponGrantLog.user_id == user_id,
                    CouponGrantLog.created_at >= cooldown_start,
                ).first()
                if recent:
                    return False, f"您刚刚已领取过补偿券，请{policy.cooldown_hours}小时后再试", policy

            # 人工审核标记
            if policy.require_manual:
                return False, "该场景需人工审核，已为您转接专员处理", policy

            return True, "ok", policy
        finally:
            db.close()


class MarketingEngine:
    """售前营销引擎 — 校验活动有效性和用户资格，含库存扣减"""

    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id

    def get_active_campaign(self, campaign_id: int) -> Optional[MarketingCampaign]:
        db = SessionLocal()
        try:
            now = datetime.now()
            return db.query(MarketingCampaign).filter(
                MarketingCampaign.id == campaign_id,
                MarketingCampaign.merchant_id == self.merchant_id,
                MarketingCampaign.is_active == True,
                MarketingCampaign.start_time <= now,
                MarketingCampaign.end_time >= now,
            ).first()
        finally:
            db.close()

    def check_and_deduct(self, user_id: str, campaign: MarketingCampaign):
        """验证用户资格并原子扣减库存。

        Returns:
            (allowed: bool, message: str)
        """
        from app.services.external_apis import UserProfileService

        db = SessionLocal()
        try:
            # 用户资格
            if campaign.target_user_type != "all":
                profile = UserProfileService.get_profile(self.merchant_id, user_id)
                if campaign.target_user_type == "new_user" and not profile.is_new:
                    return False, "该活动仅限新用户参与"
                if campaign.target_user_type == "vip" and not profile.is_vip:
                    return False, "该活动仅限VIP用户参与"

            # 每人限领次数
            user_count = db.query(CouponGrantLog).filter_by(
                merchant_id=self.merchant_id,
                user_id=user_id,
                campaign_id=campaign.id,
            ).count()
            if user_count >= campaign.max_issue_per_user:
                return False, f"您已领取过该优惠，每人限领{campaign.max_issue_per_user}次"

            # 总库存
            if campaign.max_issue_total is not None:
                total_issued = db.query(CouponGrantLog).filter_by(
                    campaign_id=campaign.id,
                ).count()
                if total_issued >= campaign.max_issue_total:
                    return False, "抱歉，该优惠已领完"

            return True, "ok"
        finally:
            db.close()

    def list_active_campaigns(self) -> list[dict]:
        """列出当前有效的营销活动，供 Agent 推荐使用。"""
        db = SessionLocal()
        try:
            now = datetime.now()
            campaigns = db.query(MarketingCampaign).filter(
                MarketingCampaign.merchant_id == self.merchant_id,
                MarketingCampaign.is_active == True,
                MarketingCampaign.start_time <= now,
                MarketingCampaign.end_time >= now,
            ).all()
            return [
                {
                    "id": c.id,
                    "name": c.campaign_name,
                    "target_user_type": c.target_user_type,
                    "max_issue_total": c.max_issue_total,
                    "max_issue_per_user": c.max_issue_per_user,
                    "end_time": c.end_time.strftime("%Y-%m-%d %H:%M") if c.end_time else "",
                }
                for c in campaigns
            ]
        finally:
            db.close()
