"""商户自定义商品分类表"""
from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
)

from app.database.session import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    name = Column(String(50), nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    level = Column(SmallInteger, default=1)
    sort_order = Column(Integer, default=0)
