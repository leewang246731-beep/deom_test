"""商户店铺钱包 + 钱包流水 + 提现申请"""
from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, SmallInteger, String, func
from app.database.session import Base


class VmMerchantWallet(Base):
    __tablename__ = "vm_merchant_wallets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False, unique=True, comment="商户ID")
    balance = Column(DECIMAL(12, 2), default=0, comment="可用余额(允许负数:平台垫付退款)")
    total_revenue = Column(DECIMAL(12, 2), default=0, comment="累计订单实收")
    total_withdrawn = Column(DECIMAL(12, 2), default=0, comment="累计提现")
    total_refunded = Column(DECIMAL(12, 2), default=0, comment="累计退款支出")
    frozen = Column(DECIMAL(12, 2), default=0, comment="提现申请中冻结金额")
    status = Column(SmallInteger, default=1, comment="1:正常 0:冻结")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class VmMerchantWalletTransaction(Base):
    __tablename__ = "vm_merchant_wallet_transactions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    wallet_id = Column(BigInteger, nullable=False)
    merchant_id = Column(BigInteger, nullable=False)
    type = Column(String(20), nullable=False, comment="order_income/refund_out/withdraw/adjustment")
    amount = Column(DECIMAL(12, 2), nullable=False)
    balance_before = Column(DECIMAL(12, 2), nullable=False)
    balance_after = Column(DECIMAL(12, 2), nullable=False)
    order_no = Column(String(30), nullable=True, comment="关联订单号")
    remark = Column(String(300), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class VmWithdrawalRequest(Base):
    __tablename__ = "vm_withdrawal_requests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False)
    amount = Column(DECIMAL(12, 2), nullable=False)
    account_type = Column(String(20), nullable=False, comment="bank/alipay/wechat")
    account_info = Column(String(500), nullable=False, comment="收款账户信息(JSON)")
    status = Column(String(20), default="pending", comment="pending/approved/rejected/completed")
    operator_id = Column(BigInteger, nullable=True, comment="审核人(平台运营)")
    reject_reason = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)
