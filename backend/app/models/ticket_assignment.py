"""工单分配流转日志"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, func

from app.database.session import Base


class TicketAssignment(Base):
    __tablename__ = "ticket_assignments"
    __table_args__ = (Index("idx_assign_ticket", "ticket_id", "created_at"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    from_user_id = Column(BigInteger, ForeignKey("merchant_users.id"), nullable=True)
    to_user_id = Column(BigInteger, ForeignKey("merchant_users.id"), nullable=False)
    action = Column(String(20), nullable=False, comment="assigned/reassigned/claimed/auto_routed")
    remark = Column(String(300), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
