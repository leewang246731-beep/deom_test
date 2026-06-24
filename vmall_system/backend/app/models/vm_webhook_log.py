"""Webhook 推送失败日志"""
from sqlalchemy import JSON, BigInteger, Column, DateTime, SmallInteger, String, Text, func
from app.database.session import Base


class VmWebhookLog(Base):
    __tablename__ = "vm_webhook_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type = Column(String(30), nullable=False)
    payload = Column(JSON, nullable=True)
    target_url = Column(String(500), nullable=True)
    status = Column(String(10), nullable=False, default="success", comment="success / failed")
    response_code = Column(SmallInteger, nullable=True)
    response_body = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(SmallInteger, default=0)
    created_at = Column(DateTime, server_default=func.now())
