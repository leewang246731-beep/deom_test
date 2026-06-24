"""工单主表（PHASE3-PLAN §3.2）"""
from sqlalchemy import (
    JSON, BigInteger, Column, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, func,
)

from app.database.session import Base


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("idx_tickets_status", "merchant_id", "status"),
        Index("idx_tickets_priority", "merchant_id", "priority"),
        Index("idx_tickets_assigned", "assigned_to", "status"),
        Index("idx_tickets_source", "merchant_id", "source", "source_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    ticket_no = Column(String(30), nullable=False, comment="TK-{mid}-{序号} 如 TK-1-00042")
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("ticket_categories.id"), nullable=True)
    priority = Column(String(4), default="P3", comment="P0/P1/P2/P3")
    status = Column(String(20), default="pending", comment="pending→in_progress→waiting_customer→resolved→closed")
    source = Column(String(20), nullable=False, comment="manual/conversation/order")
    source_id = Column(BigInteger, nullable=True, comment="conversation_id 或 order_id")
    buyer_openid = Column(String(100), nullable=True)
    assigned_to = Column(BigInteger, ForeignKey("merchant_users.id"), nullable=True)
    created_by = Column(BigInteger, ForeignKey("merchant_users.id"), nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    resolved_notes = Column(Text, nullable=True, comment="处理纪要")
    sla_due_at = Column(DateTime, nullable=True)
    sla_paused_at = Column(DateTime, nullable=True)
    sla_breached = Column(SmallInteger, default=0)
    ticket_tags = Column(JSON, nullable=True, comment='["#紧急","#高客单价"]')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
