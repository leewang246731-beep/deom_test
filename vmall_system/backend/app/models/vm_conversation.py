"""会话表"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, func
from app.database.session import Base


class VmConversation(Base):
    __tablename__ = "vm_conversations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    buyer_id = Column(BigInteger, ForeignKey("vm_buyers.id"), nullable=False)
    admin_id = Column(BigInteger, nullable=True, comment="分配的客服")
    order_id = Column(BigInteger, ForeignKey("vm_orders.id"), nullable=True)
    product_id = Column(BigInteger, ForeignKey("vm_products.id"), nullable=True)
    status = Column(String(20), default="open", comment="open / closed")
    last_message_at = Column(DateTime, nullable=True)
    buyer_last_online = Column(DateTime, nullable=True)
    buyer_ip_region = Column(String(50), nullable=True, comment="虚拟 IP 属地")
    created_at = Column(DateTime, server_default=func.now())
