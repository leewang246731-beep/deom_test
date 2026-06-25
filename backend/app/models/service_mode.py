"""客服工作台模式配置 + 自动回复日志"""
from sqlalchemy import JSON, BigInteger, Column, DateTime, DECIMAL, ForeignKey, Integer, SmallInteger, String, Text, func

from app.database.session import Base


class ServiceModeConfig(Base):
    __tablename__ = "service_mode_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False, unique=True)
    default_mode = Column(String(20), default="copilot", comment="manual/copilot/auto")
    auto_mode_hours = Column(String(100), default="22:00-08:00", comment="自动模式时段")
    auto_confidence_threshold = Column(DECIMAL(3, 2), default=0.80)
    fallback_confidence_threshold = Column(DECIMAL(3, 2), default=0.50)
    human_response_timeout_seconds = Column(Integer, default=180)
    fallback_escalate_timeout_seconds = Column(Integer, default=600)
    fallback_template = Column(Text, default="亲，客服正在为您查询中，请稍等片刻，我们会尽快回复您~")
    busy_template = Column(Text, default="当前咨询较多，已为您排队，预计3分钟内有客服为您服务")
    offline_template = Column(Text, default="当前为非工作时间，您的问题已记录，工作时间将第一时间回复您~")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AutoReplyLog(Base):
    __tablename__ = "auto_reply_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, ForeignKey("conversations.id"), nullable=False)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    mode = Column(String(20), nullable=False, comment="copilot/auto")
    buyer_question = Column(Text, nullable=False)
    ai_reply = Column(Text, nullable=False)
    confidence = Column(DECIMAL(3, 2), nullable=True)
    action_taken = Column(String(30), nullable=False, comment="auto_sent/fallback_sent/transferred/escalated")
    human_override = Column(SmallInteger, default=0, comment="1=人工后续覆盖")
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
