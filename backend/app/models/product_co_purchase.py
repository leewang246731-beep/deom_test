"""商品共购矩阵（协同过滤用，REQUIREMENTS-V2 §9.3.1）"""
from sqlalchemy import (
    BigInteger, Column, DateTime, DECIMAL, ForeignKey, Integer, UniqueConstraint, func,
)

from app.database.session import Base


class ProductCoPurchase(Base):
    __tablename__ = "product_co_purchase"
    __table_args__ = (UniqueConstraint("product_id", "co_product_id", name="uk_co_pair"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, ForeignKey("external_products.id", ondelete="CASCADE"), nullable=False)
    co_product_id = Column(BigInteger, ForeignKey("external_products.id", ondelete="CASCADE"), nullable=False)
    co_count = Column(Integer, default=0, comment="共购次数")
    score = Column(DECIMAL(8, 6), default=0, comment="归一化评分 0~1")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
