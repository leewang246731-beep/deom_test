"""平台店铺表（taobao / jd / douyin / mock）"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    func,
)

from app.database.session import Base


class PlatformShop(Base):
    __tablename__ = "platform_shops"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False, index=True)
    platform_type = Column(String(20), nullable=False, comment="taobao/jd/douyin/mock")
    shop_name = Column(String(100), nullable=False)
    shop_url = Column(String(500), nullable=True)
    app_key = Column(String(100), nullable=True)
    app_secret = Column(String(200), nullable=True)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expire_at = Column(DateTime, nullable=True)
    sync_status = Column(String(20), default="idle", comment="idle/syncing/error")
    last_sync_at = Column(DateTime, nullable=True)
    is_active = Column(SmallInteger, default=1)
    created_at = Column(DateTime, server_default=func.now())
