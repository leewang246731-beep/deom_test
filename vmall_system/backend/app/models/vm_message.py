"""消息明细"""
from sqlalchemy import JSON, BigInteger, Column, DateTime, ForeignKey, String, func
from app.database.session import Base


class VmMessage(Base):
    __tablename__ = "vm_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, ForeignKey("vm_conversations.id", ondelete="CASCADE"), nullable=False)
    sender_role = Column(String(10), nullable=False, comment="buyer / admin / system")
    msg_type = Column(String(20), default="text", comment="text / image / product_card")
    content_json = Column(JSON, nullable=False, comment='{"text":"..."} 或 {"image_url":"...","product_id":...}')
    created_at = Column(DateTime, server_default=func.now())
