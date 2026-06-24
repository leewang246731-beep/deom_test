"""买家偏好画像（REQUIREMENTS-V2 §9.3.3）"""
from sqlalchemy import JSON, BigInteger, Column, DateTime, DECIMAL, ForeignKey, Integer, String, UniqueConstraint, func

from app.database.session import Base


class BuyerProfile(Base):
    __tablename__ = "buyer_profiles"
    __table_args__ = (UniqueConstraint("merchant_id", "buyer_openid", name="uk_merchant_buyer"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    buyer_openid = Column(String(100), nullable=False, comment="外部平台买家标识")
    total_orders = Column(Integer, default=0)
    total_spent = Column(DECIMAL(12, 2), default=0)
    favorite_categories = Column(JSON, nullable=True, comment='["数码","耳机"]')
    favorite_price_range = Column(String(20), nullable=True, comment="100-500")
    last_order_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
