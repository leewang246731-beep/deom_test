"""工单评论/时间线"""
from sqlalchemy import JSON, BigInteger, Column, DateTime, ForeignKey, Index, SmallInteger, Text, func

from app.database.session import Base


class TicketComment(Base):
    __tablename__ = "ticket_comments"
    __table_args__ = (Index("idx_comment_ticket", "ticket_id", "created_at"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("merchant_users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_internal = Column(SmallInteger, default=0, comment="0:对外 1:内部笔记")
    attachments = Column(JSON, nullable=True, comment='[{"name":"img.jpg","url":"..."}]')
    created_at = Column(DateTime, server_default=func.now())
