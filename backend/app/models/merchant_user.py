"""商户员工表（admin / manager / service）"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)

from app.database.session import Base


class MerchantUser(Base):
    __tablename__ = "merchant_users"
    __table_args__ = (
        UniqueConstraint("merchant_id", "username", name="uk_merchant_username"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    username = Column(String(50), nullable=False, comment="登录账号")
    password_hash = Column(String(255), nullable=False, comment="bcrypt 哈希")
    display_name = Column(String(50), nullable=True)
    role = Column(String(20), nullable=False, comment="admin / manager / service")
    status = Column(SmallInteger, nullable=False, default=1, comment="1:正常 0:禁用")
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
