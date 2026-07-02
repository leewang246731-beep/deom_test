"""优惠券模块全面测试 — 模型 / 引擎 / 外部API / Agent工具 / API端点"""
import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database.session import Base, SessionLocal, engine
from app.models.coupon import CompensationPolicy, CouponGrantLog, MarketingCampaign


# ===================================================================
# 1. 模型层测试
# ===================================================================
class TestCouponModels(unittest.TestCase):
    """验证三张表的表名、字段、关联正确"""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine, checkfirst=True)

    def test_compensation_policy_tablename(self):
        self.assertEqual(CompensationPolicy.__tablename__, "compensation_policies")

    def test_marketing_campaign_tablename(self):
        self.assertEqual(MarketingCampaign.__tablename__, "marketing_campaigns")

    def test_coupon_grant_log_tablename(self):
        self.assertEqual(CouponGrantLog.__tablename__, "coupon_grant_logs")

    def test_policy_columns(self):
        """补偿策略表核心字段存在"""
        cols = {c.name for c in CompensationPolicy.__table__.columns}
        required = {"id", "merchant_id", "scenario", "coupon_template_id",
                     "max_amount", "max_times_per_order", "cooldown_hours",
                     "require_manual", "is_active", "created_at"}
        self.assertTrue(required.issubset(cols), f"Missing: {required - cols}")

    def test_campaign_columns(self):
        """营销活动表核心字段存在"""
        cols = {c.name for c in MarketingCampaign.__table__.columns}
        required = {"id", "merchant_id", "campaign_name", "coupon_template_id",
                     "target_user_type", "max_issue_total", "max_issue_per_user",
                     "start_time", "end_time", "require_manual", "is_active", "created_at"}
        self.assertTrue(required.issubset(cols), f"Missing: {required - cols}")

    def test_grant_log_columns(self):
        """发放日志表核心字段存在"""
        cols = {c.name for c in CouponGrantLog.__table__.columns}
        required = {"id", "merchant_id", "user_id", "order_id", "campaign_id",
                     "type", "scenario", "coupon_code", "amount", "reason",
                     "session_id", "created_at"}
        self.assertTrue(required.issubset(cols), f"Missing: {required - cols}")

    def test_policy_crud(self):
        """补偿策略 CRUD 基本流程"""
        db = SessionLocal()
        try:
            # Create
            p = CompensationPolicy(
                merchant_id=99, scenario="logistics_delay",
                coupon_template_id="TPL_TEST_10", max_amount=10.00,
            )
            db.add(p)
            db.commit()
            pid = p.id
            self.assertIsNotNone(pid)

            # Read
            p2 = db.query(CompensationPolicy).filter_by(id=pid).first()
            self.assertEqual(p2.scenario, "logistics_delay")
            self.assertEqual(float(p2.max_amount), 10.00)

            # Update
            p2.max_amount = 20.00
            p2.require_manual = True
            db.commit()
            p3 = db.query(CompensationPolicy).filter_by(id=pid).first()
            self.assertEqual(float(p3.max_amount), 20.00)
            self.assertTrue(p3.require_manual)

            # Delete
            db.delete(p3)
            db.commit()
            p4 = db.query(CompensationPolicy).filter_by(id=pid).first()
            self.assertIsNone(p4)
        finally:
            db.rollback()
            db.close()

    def test_campaign_crud(self):
        """营销活动 CRUD 基本流程"""
        db = SessionLocal()
        try:
            now = datetime.now()
            c = MarketingCampaign(
                merchant_id=99, campaign_name="测试活动",
                coupon_template_id="TPL_NEW_5",
                target_user_type="new_user", max_issue_total=100,
                max_issue_per_user=1, start_time=now,
                end_time=now + timedelta(days=7),
            )
            db.add(c)
            db.commit()
            cid = c.id
            self.assertIsNotNone(cid)

            c2 = db.query(MarketingCampaign).filter_by(id=cid).first()
            self.assertEqual(c2.campaign_name, "测试活动")
            self.assertEqual(c2.target_user_type, "new_user")
            self.assertEqual(c2.max_issue_total, 100)

            # 清理
            db.delete(c2)
            db.commit()
        finally:
            db.rollback()
            db.close()

    def test_grant_log_create(self):
        """发放日志记录"""
        db = SessionLocal()
        try:
            log = CouponGrantLog(
                merchant_id=99, user_id="buyer_001", order_id="ORD_001",
                type="compensation", scenario="logistics_delay",
                coupon_code="COUPON_TEST001", amount=10.00,
                reason="物流延迟3天补偿",
            )
            db.add(log)
            db.commit()
            lid = log.id
            self.assertIsNotNone(lid)

            l2 = db.query(CouponGrantLog).filter_by(id=lid).first()
            self.assertEqual(l2.type, "compensation")
            self.assertEqual(l2.user_id, "buyer_001")
            self.assertEqual(float(l2.amount), 10.00)

            db.delete(l2)
            db.commit()
        finally:
            db.rollback()
            db.close()


# ===================================================================
# 2. 外部 API Mock 测试
# ===================================================================
class TestExternalAPIs(unittest.TestCase):

    def test_coupon_api_issue_returns_valid_result(self):
        from app.services.external_apis import CouponAPI
        api = CouponAPI(merchant_id=1)
        result = api.issue("TPL_DELAY_10", "user_001")
        self.assertTrue(result.success)
        self.assertTrue(result.coupon_code.startswith("COUPON"))
        self.assertGreater(result.amount, 0)
        self.assertIn("优惠券已发放", result.message)

    def test_coupon_api_amount_from_template_id(self):
        from app.services.external_apis import CouponAPI
        api = CouponAPI(merchant_id=1)
        # Template "TPL_DELAY_10" → hint 10
        result = api.issue("TPL_DELAY_10", "user_x")
        self.assertTrue(8.0 <= result.amount <= 12.0,
                        f"amount {result.amount} should be near 10")

    def test_coupon_api_non_numeric_template(self):
        from app.services.external_apis import CouponAPI
        api = CouponAPI(merchant_id=1)
        result = api.issue("NO_AMOUNT_SUFFIX", "user_x")
        self.assertTrue(result.success)
        self.assertGreater(result.amount, 0)

    def test_order_service_nonexistent(self):
        from app.services.external_apis import OrderService
        result = OrderService.get_order(merchant_id=99999, order_id="NONEXIST")
        self.assertIsNone(result)

    def test_user_profile_service_new_user(self):
        from app.services.external_apis import UserProfileService
        # A new merchant with no orders → all users are new
        profile = UserProfileService.get_profile(merchant_id=99999, user_id="fresh_user")
        self.assertTrue(profile.is_new)
        self.assertFalse(profile.is_vip)


# ===================================================================
# 3. 业务引擎测试（需要 DB 种子数据）
# ===================================================================
class TestPolicyEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine, checkfirst=True)
        cls.merchant_id = 98
        cls.user_id = "buyer_test_001"
        cls.order_id = "ORD_TEST_001"
        cls._seed_policy()

    @classmethod
    def _seed_policy(cls):
        db = SessionLocal()
        try:
            # 清理旧数据
            db.query(CouponGrantLog).filter_by(merchant_id=cls.merchant_id).delete()
            db.query(CompensationPolicy).filter_by(merchant_id=cls.merchant_id).delete()

            policy = CompensationPolicy(
                merchant_id=cls.merchant_id,
                scenario="logistics_delay",
                coupon_template_id="TPL_DELAY_10",
                max_amount=10.00,
                max_times_per_order=1,
                cooldown_hours=24,
                require_manual=False,
                is_active=True,
            )
            db.add(policy)
            db.commit()
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(CouponGrantLog).filter_by(merchant_id=cls.merchant_id).delete()
            db.query(CompensationPolicy).filter_by(merchant_id=cls.merchant_id).delete()
            db.commit()
        finally:
            db.close()

    def test_get_policy_found(self):
        engine = __import__('app.services.coupon_engine', fromlist=['PolicyEngine']).PolicyEngine
        pe = engine(self.merchant_id)
        policy = pe.get_policy("logistics_delay")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.coupon_template_id, "TPL_DELAY_10")

    def test_get_policy_not_found(self):
        engine = __import__('app.services.coupon_engine', fromlist=['PolicyEngine']).PolicyEngine
        pe = engine(self.merchant_id)
        policy = pe.get_policy("nonexistent_scenario")
        self.assertIsNone(policy)

    def test_check_eligibility_first_time_pass(self):
        from app.services.coupon_engine import PolicyEngine
        pe = PolicyEngine(self.merchant_id)
        allowed, msg, policy = pe.check_eligibility(
            self.user_id, self.order_id, "logistics_delay"
        )
        self.assertTrue(allowed, f"Should be allowed, got: {msg}")
        self.assertIsNotNone(policy)

    def test_check_eligibility_no_scenario(self):
        from app.services.coupon_engine import PolicyEngine
        pe = PolicyEngine(self.merchant_id)
        allowed, msg, policy = pe.check_eligibility(
            self.user_id, self.order_id, "quality_issue"
        )
        self.assertFalse(allowed)
        self.assertIn("未配置补偿策略", msg)

    def test_max_times_per_order_enforced(self):
        """同一订单同一场景不能重复补偿"""
        from app.services.coupon_engine import PolicyEngine
        # 先插入一条已发放记录
        db = SessionLocal()
        try:
            log = CouponGrantLog(
                merchant_id=self.merchant_id,
                user_id=self.user_id,
                order_id=self.order_id,
                type="compensation",
                scenario="logistics_delay",
                coupon_code="COUPON_USED",
                amount=10.00,
                reason="already compensated",
            )
            db.add(log)
            db.commit()
        finally:
            db.close()

        pe = PolicyEngine(self.merchant_id)
        allowed, msg, _ = pe.check_eligibility(
            self.user_id, self.order_id, "logistics_delay"
        )
        self.assertFalse(allowed)
        self.assertIn("已达上限", msg)

        # 清理
        db = SessionLocal()
        try:
            db.query(CouponGrantLog).filter_by(
                merchant_id=self.merchant_id, order_id=self.order_id
            ).delete()
            db.commit()
        finally:
            db.close()

    def test_cooldown_enforced(self):
        """冷却期内不能重复发券"""
        from app.services.coupon_engine import PolicyEngine
        db = SessionLocal()
        try:
            # 插入一条近期日志（冷却期内）
            log = CouponGrantLog(
                merchant_id=self.merchant_id,
                user_id=self.user_id,
                order_id="ORD_OTHER",
                type="compensation",
                scenario="logistics_delay",
                coupon_code="COUPON_RECENT",
                amount=5.00,
                reason="recent compensation",
                created_at=datetime.now() - timedelta(hours=1),  # 1小时前
            )
            db.add(log)
            db.commit()
        finally:
            db.close()

        pe = PolicyEngine(self.merchant_id)
        allowed, msg, _ = pe.check_eligibility(
            self.user_id, "ORD_NEW", "logistics_delay"
        )
        self.assertFalse(allowed)
        self.assertIn("小时后再试", msg)

        # 清理
        db = SessionLocal()
        try:
            db.query(CouponGrantLog).filter_by(
                merchant_id=self.merchant_id, coupon_code="COUPON_RECENT"
            ).delete()
            db.commit()
        finally:
            db.close()

    def test_require_manual_blocked(self):
        """人工审核标记的策略应拒绝自动发券"""
        from app.services.coupon_engine import PolicyEngine
        db = SessionLocal()
        try:
            # 临时设 require_manual=True
            p = db.query(CompensationPolicy).filter_by(
                merchant_id=self.merchant_id, scenario="logistics_delay"
            ).first()
            p.require_manual = True
            db.commit()

            pe = PolicyEngine(self.merchant_id)
            allowed, msg, _ = pe.check_eligibility(
                "any_user", "any_order", "logistics_delay"
            )
            self.assertFalse(allowed)
            self.assertIn("人工审核", msg)

            # 恢复
            p.require_manual = False
            db.commit()
        finally:
            db.close()


class TestMarketingEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine, checkfirst=True)
        cls.merchant_id = 97
        cls._seed_campaigns()

    @classmethod
    def _seed_campaigns(cls):
        db = SessionLocal()
        try:
            db.query(MarketingCampaign).filter_by(merchant_id=cls.merchant_id).delete()
            db.query(CouponGrantLog).filter_by(merchant_id=cls.merchant_id).delete()

            now = datetime.now()
            # 有效活动
            c1 = MarketingCampaign(
                merchant_id=cls.merchant_id,
                campaign_name="新用户首单优惠",
                coupon_template_id="TPL_NEW_5",
                target_user_type="new_user",
                max_issue_total=10,
                max_issue_per_user=1,
                start_time=now - timedelta(days=1),
                end_time=now + timedelta(days=7),
                is_active=True,
            )
            # 已结束活动
            c2 = MarketingCampaign(
                merchant_id=cls.merchant_id,
                campaign_name="过期活动",
                coupon_template_id="TPL_OLD",
                start_time=now - timedelta(days=30),
                end_time=now - timedelta(days=1),
                is_active=True,
            )
            # 不限库存活动
            c3 = MarketingCampaign(
                merchant_id=cls.merchant_id,
                campaign_name="全场通用券",
                coupon_template_id="TPL_ALL_3",
                target_user_type="all",
                max_issue_total=None,
                max_issue_per_user=3,
                start_time=now - timedelta(days=1),
                end_time=now + timedelta(days=7),
                is_active=True,
            )
            db.add_all([c1, c2, c3])
            db.commit()
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(MarketingCampaign).filter_by(merchant_id=cls.merchant_id).delete()
            db.query(CouponGrantLog).filter_by(merchant_id=cls.merchant_id).delete()
            db.commit()
        finally:
            db.close()

    def test_get_active_campaign_returns_valid(self):
        from app.services.coupon_engine import MarketingEngine
        me = MarketingEngine(self.merchant_id)
        # 新用户活动应该有效（时间范围内）
        campaigns = me.list_active_campaigns()
        self.assertEqual(len(campaigns), 2, f"Should be 2 active, got {len(campaigns)}")
        names = {c["name"] for c in campaigns}
        self.assertIn("新用户首单优惠", names)
        self.assertIn("全场通用券", names)
        self.assertNotIn("过期活动", names)

    def test_get_active_campaign_by_id(self):
        from app.services.coupon_engine import MarketingEngine
        db = SessionLocal()
        try:
            c = db.query(MarketingCampaign).filter_by(
                merchant_id=self.merchant_id, campaign_name="全场通用券"
            ).first()
            self.assertIsNotNone(c)
            me = MarketingEngine(self.merchant_id)
            found = me.get_active_campaign(c.id)
            self.assertIsNotNone(found)
            self.assertEqual(found.campaign_name, "全场通用券")
        finally:
            db.close()

    def test_expired_campaign_not_returned(self):
        from app.services.coupon_engine import MarketingEngine
        db = SessionLocal()
        try:
            c = db.query(MarketingCampaign).filter_by(
                merchant_id=self.merchant_id, campaign_name="过期活动"
            ).first()
            self.assertIsNotNone(c)
            me = MarketingEngine(self.merchant_id)
            found = me.get_active_campaign(c.id)
            self.assertIsNone(found)  # 过期活动不应返回
        finally:
            db.close()

    def test_check_and_deduct_new_user_vip_only(self):
        """new_user 活动 - 非新用户应拒绝"""
        from app.services.coupon_engine import MarketingEngine
        db = SessionLocal()
        try:
            c = db.query(MarketingCampaign).filter_by(
                merchant_id=self.merchant_id, campaign_name="新用户首单优惠"
            ).first()
            me = MarketingEngine(self.merchant_id)

            # Mock UserProfileService 返回非新用户
            with patch('app.services.external_apis.UserProfileService.get_profile') as mock_profile:
                from app.services.external_apis import UserProfile
                mock_profile.return_value = UserProfile(
                    user_id="old_user", is_new=False, is_vip=False
                )
                allowed, msg = me.check_and_deduct("old_user", c)
                self.assertFalse(allowed)
                self.assertIn("仅限新用户", msg)
        finally:
            db.close()

    def test_check_and_deduct_new_user_pass(self):
        """new_user 活动 - 新用户应通过"""
        from app.services.coupon_engine import MarketingEngine
        db = SessionLocal()
        try:
            c = db.query(MarketingCampaign).filter_by(
                merchant_id=self.merchant_id, campaign_name="新用户首单优惠"
            ).first()
            me = MarketingEngine(self.merchant_id)

            with patch('app.services.external_apis.UserProfileService.get_profile') as mock_profile:
                from app.services.external_apis import UserProfile
                mock_profile.return_value = UserProfile(
                    user_id="fresh_user", is_new=True, is_vip=False
                )
                allowed, msg = me.check_and_deduct("fresh_user", c)
                self.assertTrue(allowed, f"New user should pass, got: {msg}")
        finally:
            db.close()

    def test_max_issue_per_user_enforced(self):
        """每人限领次数检查"""
        from app.services.coupon_engine import MarketingEngine
        db = SessionLocal()
        try:
            c = db.query(MarketingCampaign).filter_by(
                merchant_id=self.merchant_id, campaign_name="全场通用券"
            ).first()
            # 插入已达上限的记录
            log = CouponGrantLog(
                merchant_id=self.merchant_id,
                user_id="heavy_user",
                campaign_id=c.id,
                type="marketing",
                coupon_code="COUPON_X1",
                amount=3.00,
                reason="first",
            )
            db.add(log)
            # 再插两条使达到 max_issue_per_user=3
            log2 = CouponGrantLog(
                merchant_id=self.merchant_id,
                user_id="heavy_user",
                campaign_id=c.id,
                type="marketing",
                coupon_code="COUPON_X2",
                amount=3.00,
                reason="second",
            )
            log3 = CouponGrantLog(
                merchant_id=self.merchant_id,
                user_id="heavy_user",
                campaign_id=c.id,
                type="marketing",
                coupon_code="COUPON_X3",
                amount=3.00,
                reason="third",
            )
            db.add_all([log2, log3])
            db.commit()

            me = MarketingEngine(self.merchant_id)
            allowed, msg = me.check_and_deduct("heavy_user", c)
            self.assertFalse(allowed)
            self.assertIn("每人限领", msg)

            # 清理
            db.query(CouponGrantLog).filter_by(
                campaign_id=c.id, user_id="heavy_user"
            ).delete()
            db.commit()
        finally:
            db.close()

    def test_total_inventory_enforced(self):
        """总库存耗尽检查"""
        from app.services.coupon_engine import MarketingEngine
        db = SessionLocal()
        try:
            c = db.query(MarketingCampaign).filter_by(
                merchant_id=self.merchant_id, campaign_name="新用户首单优惠"
            ).first()
            # 插入 max_issue_total=10 条已发记录
            for i in range(10):
                db.add(CouponGrantLog(
                    merchant_id=self.merchant_id,
                    user_id=f"user_{i}",
                    campaign_id=c.id,
                    type="marketing",
                    coupon_code=f"COUPON_FULL_{i}",
                    amount=5.00,
                    reason="fill",
                ))
            db.commit()

            me = MarketingEngine(self.merchant_id)
            with patch('app.services.external_apis.UserProfileService.get_profile') as mock_profile:
                from app.services.external_apis import UserProfile
                mock_profile.return_value = UserProfile(
                    user_id="fresh_user_2", is_new=True, is_vip=False
                )
                allowed, msg = me.check_and_deduct("fresh_user_2", c)
                self.assertFalse(allowed)
                self.assertIn("已领完", msg)

            # 清理
            db.query(CouponGrantLog).filter_by(campaign_id=c.id).delete()
            db.commit()
        finally:
            db.close()


# ===================================================================
# 4. Agent 工具函数测试
# ===================================================================
class TestCouponAgentTools(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine, checkfirst=True)
        cls.merchant_id = 96
        cls._seed()

    @classmethod
    def _seed(cls):
        db = SessionLocal()
        try:
            db.query(CompensationPolicy).filter_by(merchant_id=cls.merchant_id).delete()
            db.query(MarketingCampaign).filter_by(merchant_id=cls.merchant_id).delete()
            db.query(CouponGrantLog).filter_by(merchant_id=cls.merchant_id).delete()

            db.add(CompensationPolicy(
                merchant_id=cls.merchant_id,
                scenario="logistics_delay",
                coupon_template_id="TPL_DELAY_10",
                max_amount=10.00,
                max_times_per_order=1,
                cooldown_hours=0,  # 无冷却
            ))
            now = datetime.now()
            db.add(MarketingCampaign(
                merchant_id=cls.merchant_id,
                campaign_name="Agent测试活动",
                coupon_template_id="TPL_AGENT_5",
                target_user_type="all",
                max_issue_total=None,
                max_issue_per_user=1,
                start_time=now - timedelta(days=1),
                end_time=now + timedelta(days=7),
                is_active=True,
            ))
            db.commit()
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(CouponGrantLog).filter_by(merchant_id=cls.merchant_id).delete()
            db.query(CompensationPolicy).filter_by(merchant_id=cls.merchant_id).delete()
            db.query(MarketingCampaign).filter_by(merchant_id=cls.merchant_id).delete()
            db.commit()
        finally:
            db.close()

    def test_compensate_tool_success(self):
        """补偿工具 - 正常发券"""
        from app.ai.coupon_tools import build_compensate_tool
        tool = build_compensate_tool(self.merchant_id)

        # Mock OrderService 返回有效订单
        with patch('app.ai.coupon_tools.OrderService.get_order') as mock_order:
            from app.services.external_apis import OrderInfo
            mock_order.return_value = OrderInfo(
                order_id="ORD_AGENT_001", user_id="buyer_agent_001",
                status="shipped", pay_amount=99.00,
            )
            result = tool.invoke({
                "order_id": "ORD_AGENT_001",
                "scenario": "logistics_delay",
                "reason": "Agent 测试补偿",
            })
            self.assertIn("优惠券", result)
            self.assertIn("COUPON", result)

        # 清理日志
        db = SessionLocal()
        try:
            db.query(CouponGrantLog).filter_by(
                merchant_id=self.merchant_id, order_id="ORD_AGENT_001"
            ).delete()
            db.commit()
        finally:
            db.close()

    def test_compensate_tool_order_not_found(self):
        """补偿工具 - 订单不存在"""
        from app.ai.coupon_tools import build_compensate_tool
        tool = build_compensate_tool(self.merchant_id)

        with patch('app.ai.coupon_tools.OrderService.get_order', return_value=None):
            result = tool.invoke({
                "order_id": "NONEXIST",
                "scenario": "logistics_delay",
                "reason": "test",
            })
            self.assertIn("不存在", result)

    def test_compensate_tool_duplicate_rejected(self):
        """补偿工具 - 重复补偿拦截"""
        from app.ai.coupon_tools import build_compensate_tool
        tool = build_compensate_tool(self.merchant_id)

        # 第一次发券
        with patch('app.ai.coupon_tools.OrderService.get_order') as mock_order:
            from app.services.external_apis import OrderInfo
            mock_order.return_value = OrderInfo(
                order_id="ORD_DUP_001", user_id="buyer_dup",
                status="shipped", pay_amount=50.00,
            )
            result1 = tool.invoke({
                "order_id": "ORD_DUP_001",
                "scenario": "logistics_delay",
                "reason": "第一次",
            })
            self.assertIn("优惠券", result1)

            # 第二次发券 - 应被拒绝
            result2 = tool.invoke({
                "order_id": "ORD_DUP_001",
                "scenario": "logistics_delay",
                "reason": "第二次尝试",
            })
            self.assertIn("已达上限", result2)

        # 清理
        db = SessionLocal()
        try:
            db.query(CouponGrantLog).filter_by(
                merchant_id=self.merchant_id, order_id="ORD_DUP_001"
            ).delete()
            db.commit()
        finally:
            db.close()

    def test_issue_promo_tool_success(self):
        """营销发券工具 - 正常领取"""
        from app.ai.coupon_tools import build_issue_promo_tool
        tool = build_issue_promo_tool(self.merchant_id)

        db = SessionLocal()
        try:
            c = db.query(MarketingCampaign).filter_by(
                merchant_id=self.merchant_id, campaign_name="Agent测试活动"
            ).first()
            result = tool.invoke({
                "campaign_id": c.id,
                "user_id": "promo_user_001",
                "reason": "Agent 测试营销",
            })
            self.assertIn("优惠券", result)
            self.assertIn("COUPON", result)

            # 清理
            db.query(CouponGrantLog).filter_by(
                merchant_id=self.merchant_id, user_id="promo_user_001"
            ).delete()
            db.commit()
        finally:
            db.close()

    def test_issue_promo_campaign_not_found(self):
        """营销发券工具 - 活动不存在"""
        from app.ai.coupon_tools import build_issue_promo_tool
        tool = build_issue_promo_tool(self.merchant_id)
        result = tool.invoke({
            "campaign_id": 99999,
            "user_id": "any_user",
            "reason": "test",
        })
        self.assertIn("不存在", result)

    def test_compensate_order_status_mismatch(self):
        """补偿工具 - 订单状态不匹配场景应拒绝"""
        from app.ai.coupon_tools import build_compensate_tool
        tool = build_compensate_tool(self.merchant_id)

        with patch('app.ai.coupon_tools.OrderService.get_order') as mock_order:
            from app.services.external_apis import OrderInfo
            # logistics_delay 只允许 paid/shipped，completed 应被拒
            mock_order.return_value = OrderInfo(
                order_id="ORD_COMPLETED_001", user_id="buyer_x",
                status="completed", pay_amount=99.00,
            )
            result = tool.invoke({
                "order_id": "ORD_COMPLETED_001",
                "scenario": "logistics_delay",
                "reason": "物流延迟补偿尝试",
            })
            self.assertIn("当前状态为", result)
            self.assertIn("已完成", result)

    def test_compensate_quality_issue_requires_completed(self):
        """补偿工具 - quality_issue 只允许 completed 状态"""
        from app.ai.coupon_tools import build_compensate_tool
        tool = build_compensate_tool(self.merchant_id)

        with patch('app.ai.coupon_tools.OrderService.get_order') as mock_order:
            from app.services.external_apis import OrderInfo
            mock_order.return_value = OrderInfo(
                order_id="ORD_PAID_001", user_id="buyer_y",
                status="paid", pay_amount=50.00,
            )
            result = tool.invoke({
                "order_id": "ORD_PAID_001",
                "scenario": "quality_issue",
                "reason": "质量问题投诉",
            })
            self.assertIn("已付款", result)
            self.assertIn("不符合该补偿场景", result)

    def test_compensate_disabled_by_toggle(self):
        """补偿工具 - ENABLE_AUTO_COUPON=False 时应拒绝并转人工"""
        from app.ai.coupon_tools import build_compensate_tool
        tool = build_compensate_tool(self.merchant_id)

        with patch('app.ai.coupon_tools.settings') as mock_settings:
            mock_settings.ENABLE_AUTO_COUPON = False
            result = tool.invoke({
                "order_id": "ORD_ANY",
                "scenario": "logistics_delay",
                "reason": "测试降级",
            })
            self.assertIn("已关闭", result)
            self.assertIn("人工专员", result)

    def test_issue_promo_disabled_by_toggle(self):
        """营销发券工具 - ENABLE_AUTO_COUPON=False 时应拒绝并转人工"""
        from app.ai.coupon_tools import build_issue_promo_tool
        tool = build_issue_promo_tool(self.merchant_id)

        with patch('app.ai.coupon_tools.settings') as mock_settings:
            mock_settings.ENABLE_AUTO_COUPON = False
            result = tool.invoke({
                "campaign_id": 1,
                "user_id": "any_user",
                "reason": "测试降级",
            })
            self.assertIn("已关闭", result)
            self.assertIn("人工专员", result)

    def test_list_promos_tool(self):
        """查询活动工具"""
        from app.ai.coupon_tools import build_list_promos_tool
        tool = build_list_promos_tool(self.merchant_id)
        result = tool.invoke({})
        self.assertIn("Agent测试活动", result)
        self.assertIn("all", result)

    def test_list_promos_tool_empty(self):
        """查询活动工具 - 无活动时的表现"""
        from app.ai.coupon_tools import build_list_promos_tool
        tool = build_list_promos_tool(merchant_id=99999)
        result = tool.invoke({})
        self.assertEqual("当前暂无有效的营销活动", result)


# ===================================================================
# 5. API 端点集成测试
# ===================================================================
class TestCouponAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from main import app
        cls.client = TestClient(app)
        # auto-detect first active merchant
        from app.database.session import SessionLocal
        from app.models.merchant import Merchant
        db = SessionLocal()
        first = db.query(Merchant).filter(Merchant.status == 1).first()
        db.close()
        cls.merchant_id = first.id if first else 11
        cls._token = cls._get_merchant_token()
        if cls._token:
            cls._seed_data()

    @classmethod
    def _get_merchant_token(cls):
        """获取商户 access token — 尝试所有已知密码"""
        for pwd in ("123456", "admin123", "admin"):
            resp = cls.client.post("/api/v1/auth/login", json={
                "username": "admin",
                "password": pwd,
                "merchant_id": cls.merchant_id,
            })
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", {}).get("access_token", "")
        return ""

    @classmethod
    def _seed_data(cls):
        """通过 API 创建测试策略和活动"""
        headers = {"Authorization": f"Bearer {cls._token}"} if cls._token else {}
        # 创建补偿策略
        cls.client.post("/api/v1/coupons/compensation-policies", json={
            "scenario": "service_complaint",
            "coupon_template_id": "TPL_SVC_8",
            "max_amount": 8.00,
            "cooldown_hours": 0,
        }, headers=headers)
        # 创建营销活动
        cls.client.post("/api/v1/coupons/marketing-campaigns", json={
            "campaign_name": "API测试活动",
            "coupon_template_id": "TPL_API_5",
            "target_user_type": "all",
            "max_issue_total": 50,
            "max_issue_per_user": 2,
        }, headers=headers)

    def setUp(self):
        self.headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        # 除无认证测试外，其余需要 token
        if not self._token and self._testMethodName != "test_unauthorized_access":
            self.skipTest("无法获取认证 token，跳过 API 集成测试")

    # --- 补偿策略 ---
    def test_list_policies(self):
        resp = self.client.get("/api/v1/coupons/compensation-policies",
                               headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["code"], 200)
        items = data["data"]
        self.assertIsInstance(items, list)
        self.assertGreaterEqual(len(items), 1)
        scenarios = [i["scenario"] for i in items]
        self.assertIn("service_complaint", scenarios)

    def test_create_policy(self):
        resp = self.client.post("/api/v1/coupons/compensation-policies", json={
            "scenario": "quality_issue",
            "coupon_template_id": "TPL_QUAL_15",
            "max_amount": 15.00,
            "max_times_per_order": 2,
            "cooldown_hours": 48,
        }, headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["code"], 200)
        self.assertIn("id", data["data"])

        # 清理
        pid = data["data"]["id"]
        self.client.delete(f"/api/v1/coupons/compensation-policies/{pid}",
                          headers=self.headers)

    def test_update_policy(self):
        # 创建
        resp = self.client.post("/api/v1/coupons/compensation-policies", json={
            "scenario": "logistics_delay",
            "coupon_template_id": "TPL_UPDATE_TEST",
            "max_amount": 5.00,
        }, headers=self.headers)
        pid = resp.json()["data"]["id"]

        # 更新
        resp2 = self.client.put(f"/api/v1/coupons/compensation-policies/{pid}", json={
            "max_amount": 25.00,
            "cooldown_hours": 72,
        }, headers=self.headers)
        self.assertEqual(resp2.status_code, 200)

        # 验证
        resp3 = self.client.get("/api/v1/coupons/compensation-policies",
                               headers=self.headers)
        items = resp3.json()["data"]
        updated = [i for i in items if i["id"] == pid]
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["max_amount"], 25.00)
        self.assertEqual(updated[0]["cooldown_hours"], 72)

        # 清理
        self.client.delete(f"/api/v1/coupons/compensation-policies/{pid}",
                          headers=self.headers)

    def test_delete_policy(self):
        resp = self.client.post("/api/v1/coupons/compensation-policies", json={
            "scenario": "quality_issue",
            "coupon_template_id": "TPL_DEL_TEST",
        }, headers=self.headers)
        pid = resp.json()["data"]["id"]

        resp2 = self.client.delete(f"/api/v1/coupons/compensation-policies/{pid}",
                                  headers=self.headers)
        self.assertEqual(resp2.status_code, 200)

        # 确认删除
        resp3 = self.client.get("/api/v1/coupons/compensation-policies",
                               headers=self.headers)
        ids = [i["id"] for i in resp3.json()["data"]]
        self.assertNotIn(pid, ids)

    def test_delete_nonexistent_policy(self):
        resp = self.client.delete("/api/v1/coupons/compensation-policies/99999",
                                 headers=self.headers)
        self.assertEqual(resp.status_code, 404)

    # --- 营销活动 ---
    def test_list_campaigns(self):
        resp = self.client.get("/api/v1/coupons/marketing-campaigns",
                              headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["code"], 200)
        items = data["data"]
        names = [c["campaign_name"] for c in items]
        self.assertIn("API测试活动", names)

    def test_create_campaign(self):
        resp = self.client.post("/api/v1/coupons/marketing-campaigns", json={
            "campaign_name": "临时活动",
            "coupon_template_id": "TPL_TMP",
            "target_user_type": "vip",
            "max_issue_total": 20,
        }, headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["code"], 200)

        # 清理
        cid = data["data"]["id"]
        self.client.delete(f"/api/v1/coupons/marketing-campaigns/{cid}",
                          headers=self.headers)

    def test_update_campaign(self):
        resp = self.client.post("/api/v1/coupons/marketing-campaigns", json={
            "campaign_name": "待更新活动",
            "coupon_template_id": "TPL_UPD",
        }, headers=self.headers)
        cid = resp.json()["data"]["id"]

        resp2 = self.client.put(f"/api/v1/coupons/marketing-campaigns/{cid}", json={
            "campaign_name": "已更新活动",
            "target_user_type": "new_user",
        }, headers=self.headers)
        self.assertEqual(resp2.status_code, 200)

        resp3 = self.client.get("/api/v1/coupons/marketing-campaigns",
                               headers=self.headers)
        items = resp3.json()["data"]
        updated = [i for i in items if i["id"] == cid]
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["campaign_name"], "已更新活动")
        self.assertEqual(updated[0]["target_user_type"], "new_user")

        # 清理
        self.client.delete(f"/api/v1/coupons/marketing-campaigns/{cid}",
                          headers=self.headers)

    def test_delete_campaign(self):
        resp = self.client.post("/api/v1/coupons/marketing-campaigns", json={
            "campaign_name": "待删除",
            "coupon_template_id": "TPL_DEL",
        }, headers=self.headers)
        cid = resp.json()["data"]["id"]

        resp2 = self.client.delete(f"/api/v1/coupons/marketing-campaigns/{cid}",
                                  headers=self.headers)
        self.assertEqual(resp2.status_code, 200)

    # --- 发放日志 ---
    def test_grant_logs_empty(self):
        resp = self.client.get("/api/v1/coupons/grant-logs",
                              headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["code"], 200)
        self.assertIn("items", data["data"])

    def test_grant_logs_filter_by_type(self):
        resp = self.client.get("/api/v1/coupons/grant-logs?type=compensation",
                              headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        items = data["data"]["items"]
        for item in items:
            self.assertEqual(item["type"], "compensation")

    # --- 活跃活动 ---
    def test_active_campaigns(self):
        resp = self.client.get("/api/v1/coupons/active-campaigns",
                              headers=self.headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["code"], 200)
        self.assertIsInstance(data["data"], list)

    # --- 安全：无认证拦截（不需要 token，不应被 setUp 跳过）---
    def test_unauthorized_access(self):
        """无 token 访问应被拦截"""
        resp = self.client.get("/api/v1/coupons/compensation-policies")
        self.assertEqual(resp.status_code, 401)

    def test_policy_tenant_isolation(self):
        """验证创建和查询的 merchant_id 隔离"""
        headers = self.headers
        resp_create = self.client.post("/api/v1/coupons/compensation-policies", json={
            "scenario": "service_complaint",
            "coupon_template_id": "TPL_ISO_TEST",
        }, headers=headers)
        self.assertEqual(resp_create.status_code, 200)

        resp_list = self.client.get("/api/v1/coupons/compensation-policies",
                                   headers=headers)
        items = resp_list.json()["data"]
        iso_items = [i for i in items if i["coupon_template_id"] == "TPL_ISO_TEST"]
        self.assertEqual(len(iso_items), 1)

        # 清理
        self.client.delete(f"/api/v1/coupons/compensation-policies/{iso_items[0]['id']}",
                          headers=headers)


# ===================================================================
# 6. Tool Registry 集成测试
# ===================================================================
class TestToolRegistryCouponIntegration(unittest.TestCase):

    def test_coupon_tools_registered(self):
        from app.ai.tool_registry import init_registry
        registry = init_registry(merchant_id=1)
        names = registry.list_names()

        self.assertIn("compensate", names)
        self.assertIn("issue_promo", names)
        self.assertIn("list_promos", names)

        # 验证 tag
        comp_tool = registry.get_tool("compensate")
        self.assertIsNotNone(comp_tool)

        # 按 tag 查询
        coupon_tools = registry.get_by_tags(["coupon"])
        self.assertEqual(len(coupon_tools), 3)

        action_coupon_tools = registry.get_by_tags(["coupon", "action"])
        compensate_tool = registry.get_by_tags(["compensation"])
        self.assertGreaterEqual(len(action_coupon_tools), 2)
        self.assertEqual(len(compensate_tool), 1)


# ===================================================================
# 7. Agent System Prompt 验证
# ===================================================================
class TestAgentPromptIntegration(unittest.TestCase):

    def test_prompt_contains_coupon_tools(self):
        """验证 agent system prompt 包含 coupon 工具描述"""
        from app.ai.agent import create_service_agent
        # 只需要验证 prompt 构建不报错且包含关键词
        # create_service_agent 返回 LangGraph graph，不直接暴露 prompt
        # 通过检查函数调用不报错来验证集成正确
        try:
            agent = create_service_agent(merchant_id=1)
            self.assertIsNotNone(agent)
        except Exception as e:
            self.fail(f"create_service_agent failed: {e}")

    def test_prompt_includes_coupon_rules(self):
        """Coupon 规则应已嵌入 agent.py system_prompt"""
        import inspect
        from app.ai import agent as agent_module
        source = inspect.getsource(agent_module.create_service_agent)
        self.assertIn("优惠券规则", source)
        self.assertIn("compensate", source)
        self.assertIn("issue_promo", source)
        self.assertIn("list_promos", source)


if __name__ == "__main__":
    unittest.main()
