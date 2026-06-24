"""SLA 策略"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func

from app.database.session import Base


class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    __table_args__ = (UniqueConstraint("merchant_id", "priority", "category_id", name="uk_sla_priority_cat"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    priority = Column(String(4), nullable=False, comment="P0/P1/P2/P3")
    category_id = Column(Integer, ForeignKey("ticket_categories.id"), nullable=True, comment="NULL=通用策略")
    response_minutes = Column(Integer, nullable=False, comment="首次响应时限(分钟)")
    resolve_minutes = Column(Integer, nullable=False, comment="解决时限(分钟)")
    escalate_minutes = Column(Integer, nullable=True, comment="超时升级时限")
    escalate_to = Column(BigInteger, ForeignKey("merchant_users.id"), nullable=True, comment="升级对象")
    is_active = Column(SmallInteger, default=1)
    created_at = Column(DateTime, server_default=func.now())
