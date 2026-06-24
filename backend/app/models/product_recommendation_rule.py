"""商户手动关联推荐规则（REQUIREMENTS-V2 §9.3.2）"""
from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func,
)

from app.database.session import Base


class ProductRecommendationRule(Base):
    __tablename__ = "product_recommendation_rules"
    __table_args__ = (UniqueConstraint("product_id", "recommended_product_id", name="uk_rule"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    product_id = Column(BigInteger, ForeignKey("external_products.id", ondelete="CASCADE"), nullable=False)
    recommended_product_id = Column(BigInteger, ForeignKey("external_products.id", ondelete="CASCADE"), nullable=False)
    rule_type = Column(String(20), default="manual", comment="manual / upsell / cross_sell")
    priority = Column(Integer, default=0, comment="排序优先级")
    is_active = Column(SmallInteger, default=1)
    created_at = Column(DateTime, server_default=func.now())
