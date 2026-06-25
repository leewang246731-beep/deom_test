"""AI 话术采纳记录（agent-design.md 五：采纳反馈闭环）"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, SmallInteger, Text, func

from app.database.session import Base


class AISuggestionLog(Base):
    __tablename__ = "ai_suggestion_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, ForeignKey("conversations.id"), nullable=False)
    buyer_question = Column(Text, nullable=False)
    ai_suggestion = Column(Text, nullable=False)
    was_adopted = Column(SmallInteger, default=0, comment="0:忽略 1:采纳 2:修改后发送")
    quality_score = Column(SmallInteger, nullable=True, comment="1-5 质量评分")
    feedback_note = Column(Text, nullable=True, comment="评分备注")
    final_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
