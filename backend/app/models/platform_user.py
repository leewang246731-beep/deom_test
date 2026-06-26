"""SaaS 平台运营账号（跨租户，无 merchant_id）"""
from sqlalchemy import BigInteger, Column, DateTime, SmallInteger, String, func

from app.database.session import Base


class PlatformUser(Base):
    __tablename__ = "platform_users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, comment="登录名")
    password_hash = Column(String(255), nullable=False, comment="bcrypt 哈希")
    display_name = Column(String(50), nullable=True, comment="显示名称")
    role = Column(String(20), nullable=False, comment="super_admin / manager")
    status = Column(SmallInteger, nullable=False, default=1, comment="1:正常 0:禁用")
    created_at = Column(DateTime, server_default=func.now())
