"""订单主表"""
from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, ForeignKey, Integer, String, func
from app.database.session import Base


class VmOrder(Base):
    __tablename__ = "vm_orders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(Integer, nullable=False, default=1, comment="商户ID")
    order_no = Column(String(30), nullable=False, unique=True)
    buyer_id = Column(BigInteger, ForeignKey("vm_buyers.id"), nullable=False)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    discount_amount = Column(DECIMAL(10, 2), default=0)
    pay_amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default="pending_payment",
                    comment="pending_payment→paying→paid→shipped→received→completed→closed / after_sale")
    after_sale_status = Column(String(20), nullable=True,
                               comment="refunding/returned/refunded/rejected")
    receiver_name = Column(String(50), nullable=True)
    receiver_phone = Column(String(20), nullable=True)
    receiver_address = Column(String(500), nullable=True)
    pay_time = Column(DateTime, nullable=True)
    ship_time = Column(DateTime, nullable=True)
    receive_time = Column(DateTime, nullable=True)
    complete_time = Column(DateTime, nullable=True)
    close_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
