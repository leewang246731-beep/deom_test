"""买家会话表（客服工作台核心）"""
from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)

from app.database.session import Base


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conv_shop_status", "shop_id", "handled_status"),
        Index("idx_conv_assigned", "assigned_to"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    shop_id = Column(BigInteger, ForeignKey("platform_shops.id"), nullable=False)
    platform_conversation_id = Column(String(100), nullable=False)
    product_id = Column(
        BigInteger, ForeignKey("external_products.id"), nullable=True,
        comment="关联咨询商品，可空",
    )
    buyer_nick = Column(String(100), nullable=False)
    messages_json = Column(
        JSON, nullable=False,
        comment='[{"role":"buyer","content":..,"time":..}]',
    )
    ai_suggest_reply = Column(Text, nullable=True, comment="AI 推荐的最新话术")
    last_message_at = Column(DateTime, nullable=True)
    handled_status = Column(String(20), default="pending", comment="pending/replied/closed")
    assigned_to = Column(
        BigInteger, ForeignKey("merchant_users.id"), nullable=True,
        comment="分配的客服 user_id",
    )
    created_at = Column(DateTime, server_default=func.now())
