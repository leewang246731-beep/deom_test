"""长期记忆模型 — 跨会话用户画像存储（每个商户独立）"""
from sqlalchemy import JSON, BigInteger, Column, DateTime, Integer, String, Text, UniqueConstraint, func

from app.database.session import Base


class LongTermMemory(Base):
    """长期记忆 — 压缩后的跨会话用户画像。

    facts:        稳定事实，如 {"skin_type": "敏感偏干", "allergies": "花粉", "budget": "150以内"}
    tags:         兴趣标签，如 ["护肤", "防晒", "有机", "敏感肌"]
    snippets:     关键对话摘要，最多保留 5 条，按时间淘汰
    stats:        行为摘要，如 {"top_categories": ["护肤","彩妆"], "avg_order_amount": 150, "order_count": 12}
    """

    __tablename__ = "long_term_memories"
    __table_args__ = (
        UniqueConstraint("merchant_id", "user_id", name="uk_merchant_user_memory"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False, index=True)
    user_id = Column(String(100), nullable=False, comment="买家 openid")
    facts = Column(JSON, default=dict, comment='{"skin_type":"油性","budget":"150以内"}')
    tags = Column(JSON, default=list, comment='["护肤","防晒","敏感肌"]')
    snippets = Column(JSON, default=list, comment='对话摘要列表，最多5条')
    stats = Column(JSON, default=dict, comment='行为聚合统计')
    activity_level = Column(String(20), default="new", comment="new / active / dormant / lost")
    last_conversation_at = Column(DateTime, comment="最近一次对话时间")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
