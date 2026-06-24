"""外部平台同步订单表"""
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    DECIMAL,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)

from app.database.session import Base


class ExternalOrder(Base):
    __tablename__ = "external_orders"
    __table_args__ = (
        UniqueConstraint("shop_id", "platform_order_id", name="uk_shop_order"),
        Index("idx_order_shop_status", "shop_id", "status"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    shop_id = Column(BigInteger, ForeignKey("platform_shops.id"), nullable=False)
    platform_order_id = Column(String(100), nullable=False)
    buyer_openid = Column(String(100), nullable=False)
    buyer_nick = Column(String(100), nullable=True)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    discount_amount = Column(DECIMAL(10, 2), default=0)
    pay_amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(
        String(20),
        nullable=False,
        comment="pending/paid/shipped/completed/refunding/refunded",
    )
    sku_details_json = Column(JSON, nullable=True, comment='[{"title":..,"price":..,"qty":1}]')
    receiver_name = Column(String(50), nullable=True)
    receiver_phone = Column(String(20), nullable=True)
    receiver_address = Column(String(500), nullable=True)
    pay_time = Column(DateTime, nullable=True)
    ship_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
