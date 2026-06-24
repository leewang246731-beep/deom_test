"""订单明细"""
from sqlalchemy import BigInteger, Column, DECIMAL, ForeignKey, Integer, String
from app.database.session import Base


class VmOrderItem(Base):
    __tablename__ = "vm_order_items"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(BigInteger, ForeignKey("vm_orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("vm_products.id"), nullable=False)
    sku_code = Column(String(50), nullable=False)
    sku_spec = Column(String(100), nullable=True)
    unit_price = Column(DECIMAL(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
