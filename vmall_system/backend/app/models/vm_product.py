"""商品表（含多规格 SKU）"""
from sqlalchemy import JSON, BigInteger, Column, DateTime, DECIMAL, Integer, SmallInteger, String, Text, func
from app.database.session import Base


class VmProduct(Base):
    __tablename__ = "vm_products"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(300), nullable=False)
    main_image = Column(String(500), nullable=True)
    images_json = Column(JSON, nullable=True, comment='["url1","url2"]')
    price_min = Column(DECIMAL(10, 2), nullable=False)
    price_max = Column(DECIMAL(10, 2), nullable=False)
    category_path = Column(String(300), nullable=False, comment='"数码/手机/华为"')
    description = Column(Text, nullable=True)
    skus_json = Column(JSON, nullable=False, comment='[{spec,price,stock,sku_code}]')
    total_stock = Column(Integer, default=0)
    total_sales = Column(Integer, default=0)
    status = Column(SmallInteger, default=1, comment="1:在售 0:下架")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
