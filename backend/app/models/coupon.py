"""优惠券模块：售后补偿策略 + 售前营销活动 + 发放日志"""
from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, Integer, String, Text, Boolean, func

from app.database.session import Base


class CompensationPolicy(Base):
    """售后补偿策略表 — 商户按场景配置补偿券模板"""
    __tablename__ = "compensation_policies"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False, index=True)
    scenario = Column(String(50), nullable=False, comment="logistics_delay / quality_issue / service_complaint")
    coupon_template_id = Column(String(100), nullable=False, comment="券系统模板ID")
    max_amount = Column(DECIMAL(8, 2), comment="券面额上限，实际金额以券系统为准")
    max_times_per_order = Column(Integer, default=1)
    cooldown_hours = Column(Integer, default=24, comment="同一用户冷却期，0 表示无限制")
    require_manual = Column(Boolean, default=False, comment="是否必须人工审核")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class MarketingCampaign(Base):
    """售前营销活动表 — 商户配置的领券活动"""
    __tablename__ = "marketing_campaigns"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False, index=True)
    campaign_name = Column(String(100))
    coupon_template_id = Column(String(100), nullable=False)
    target_user_type = Column(String(20), default="all", comment="all / new_user / vip")
    max_issue_total = Column(Integer, comment="活动券总库存，NULL 表示不限")
    max_issue_per_user = Column(Integer, default=1)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    require_manual = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class CouponGrantLog(Base):
    """优惠券发放日志表 — 售前+售后共用"""
    __tablename__ = "coupon_grant_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(String(50), nullable=False, comment="买家 openid 或 user_id")
    order_id = Column(String(50), comment="售后关联订单号")
    campaign_id = Column(BigInteger, comment="售前关联活动ID")
    type = Column(String(20), nullable=False, comment="compensation 或 marketing")
    scenario = Column(String(50), comment="售后场景")
    coupon_code = Column(String(100), nullable=False)
    amount = Column(DECIMAL(8, 2))
    reason = Column(Text, comment="发放理由，来自 LLM 或系统")
    session_id = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())

    # 复合索引建在 __table_args__ 更符合现有项目风格，这里先用单列索引保证查询
    # idx_merchant_user / idx_order / idx_campaign 分别覆盖常规查询
