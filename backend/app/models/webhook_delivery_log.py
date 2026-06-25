"""Webhook 投递日志"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, SmallInteger, String, Text, func

from app.database.session import Base


class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    source_shop_id = Column(Integer, nullable=True)
    payload_json = Column(Text, nullable=True)
    response_code = Column(SmallInteger, nullable=True)
    response_body = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="success", comment="success/failed/retrying")
    created_at = Column(DateTime, server_default=func.now())
