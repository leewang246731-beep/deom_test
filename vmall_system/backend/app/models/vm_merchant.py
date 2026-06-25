"""vMall 商户（店铺主）"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, SmallInteger, String, Text, Boolean, func
from app.database.session import Base


class VmMerchant(Base):
    __tablename__ = "vm_merchants"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    shop_name = Column(String(100), nullable=False)
    shop_logo = Column(String(500), nullable=True)
    shop_desc = Column(Text, nullable=True)
    contact_name = Column(String(50), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    contact_email = Column(String(100), nullable=True)
    saas_bound = Column(Boolean, default=False)
    saas_shop_id = Column(Integer, nullable=True, comment="SaaS 平台中对应的 shop ID")
    saas_url = Column(String(500), nullable=True, comment="绑定的 SaaS 平台地址")
    saas_bind_time = Column(DateTime, nullable=True)
    status = Column(SmallInteger, default=1, comment="1=正常 0=禁用")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
