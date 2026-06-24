"""买家钱包 + 充值/消费记录"""
from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, ForeignKey, Integer, String, func
from app.database.session import Base


class VmWallet(Base):
    __tablename__ = "vm_wallets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    buyer_id = Column(BigInteger, ForeignKey("vm_buyers.id"), nullable=False, unique=True)
    balance = Column(DECIMAL(12, 2), default=0, comment="余额(元)")
    total_recharged = Column(DECIMAL(12, 2), default=0, comment="累计充值")
    total_spent = Column(DECIMAL(12, 2), default=0, comment="累计消费")
    status = Column(Integer, default=1, comment="1:正常 0:冻结")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class VmWalletTransaction(Base):
    __tablename__ = "vm_wallet_transactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    wallet_id = Column(BigInteger, ForeignKey("vm_wallets.id"), nullable=False)
    buyer_id = Column(BigInteger, ForeignKey("vm_buyers.id"), nullable=False)
    type = Column(String(20), nullable=False, comment="recharge/payment/refund/adjustment")
    amount = Column(DECIMAL(12, 2), nullable=False)
    balance_before = Column(DECIMAL(12, 2), nullable=False)
    balance_after = Column(DECIMAL(12, 2), nullable=False)
    order_no = Column(String(30), nullable=True, comment="关联订单号")
    remark = Column(String(300), nullable=True)
    operator_id = Column(BigInteger, nullable=True, comment="操作人(admin端充值时)")
    created_at = Column(DateTime, server_default=func.now())
