"""售后表"""
from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, ForeignKey, String, Text, func
from app.database.session import Base


class VmAfterSale(Base):
    __tablename__ = "vm_after_sales"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(BigInteger, ForeignKey("vm_orders.id"), nullable=False)
    buyer_id = Column(BigInteger, ForeignKey("vm_buyers.id"), nullable=False)
    type = Column(String(20), nullable=False, comment="refund_only / return_refund")
    reason = Column(Text, nullable=False)
    refund_amount = Column(DECIMAL(10, 2), nullable=False)
    status = Column(String(20), nullable=False, default="pending_review",
                    comment="pending_review→approved→buyer_shipped→platform_received→refunded / rejected→closed")
    review_remark = Column(String(300), nullable=True)
    reviewed_by = Column(BigInteger, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    return_logistics_company = Column(String(50), nullable=True)
    return_tracking_no = Column(String(50), nullable=True)
    buyer_ship_time = Column(DateTime, nullable=True)
    platform_receive_time = Column(DateTime, nullable=True)
    refund_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
