"""操作审计日志"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, func

from app.database.session import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(BigInteger, nullable=True)
    username = Column(String(50), nullable=True)
    action = Column(String(50), nullable=False, comment="create/update/delete/status_change/login")
    target_type = Column(String(50), nullable=True, comment="ticket/product/user/order/shop")
    target_id = Column(BigInteger, nullable=True)
    detail_json = Column(Text, nullable=True)
    ip = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
