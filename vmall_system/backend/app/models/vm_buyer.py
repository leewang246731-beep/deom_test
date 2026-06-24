"""买家表"""
from sqlalchemy import BigInteger, Column, DateTime, SmallInteger, String, func
from app.database.session import Base


class VmBuyer(Base):
    __tablename__ = "vm_buyers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(100), nullable=True)
    avatar = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)
    source = Column(String(20), default="h5")
    status = Column(SmallInteger, default=1)
    created_at = Column(DateTime, server_default=func.now())
