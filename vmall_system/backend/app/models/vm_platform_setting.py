"""平台配置 + 管理员"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, SmallInteger, String, Text, func
from app.database.session import Base


class VmPlatformSetting(Base):
    __tablename__ = "vm_platform_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    shop_name = Column(String(100), nullable=False, default="vMall 官方旗舰店")
    logo_url = Column(String(500), nullable=True)
    access_token_secret = Column(String(64), nullable=False)
    saas_webhook_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class VmPlatformAdmin(Base):
    __tablename__ = "vm_platform_admins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(50), nullable=True)
    role = Column(String(20), default="operator", comment="admin / operator")
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime, server_default=func.now())
