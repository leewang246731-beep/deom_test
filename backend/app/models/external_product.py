"""外部平台同步商品表"""
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    DECIMAL,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.database.session import Base


class ExternalProduct(Base):
    __tablename__ = "external_products"
    __table_args__ = (
        UniqueConstraint("shop_id", "platform_product_id", name="uk_shop_product"),
        Index("idx_shop_status", "shop_id", "status"),
        Index("idx_embedding_id", "embedding_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    shop_id = Column(BigInteger, ForeignKey("platform_shops.id"), nullable=False)
    platform_product_id = Column(String(100), nullable=False)
    title = Column(String(300), nullable=False)
    price = Column(DECIMAL(10, 2), nullable=False)
    stock = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    images_json = Column(JSON, nullable=True, comment='["url1","url2"]')
    category_path = Column(String(300), nullable=True, comment="女装/连衣裙/韩版")
    embedding_status = Column(String(20), default="pending", comment="pending/done/error")
    embedding_id = Column(String(100), nullable=True, comment="ChromaDB 向量ID")
    status = Column(SmallInteger, default=1, comment="1:在售 0:下架")
    last_sync_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
