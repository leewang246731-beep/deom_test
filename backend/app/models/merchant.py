"""商户表（SaaS 租户）"""
from sqlalchemy import BigInteger, Column, DateTime, SmallInteger, String, func

from app.database.session import Base


class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="商户名称")
    contact = Column(String(50), nullable=True, comment="联系方式")
    status = Column(SmallInteger, nullable=False, default=1, comment="1:正常 0:停用")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
