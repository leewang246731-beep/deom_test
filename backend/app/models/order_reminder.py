"""催单发送记录"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, func

from app.database.session import Base


class OrderReminder(Base):
    __tablename__ = "order_reminders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False, index=True)
    shop_id = Column(BigInteger, nullable=False)
    order_id = Column(BigInteger, nullable=False)
    buyer_openid = Column(String(100), nullable=True)
    content = Column(Text, nullable=True)
    channel = Column(String(20), default="vmall", comment="vmall / local")
    sent_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
