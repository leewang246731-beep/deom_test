"""AI 话术风格配置（REQUIREMENTS-V2 §3 / database.md §2.7）"""
from sqlalchemy import BigInteger, JSON, Column, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func

from app.database.session import Base


class AIStyleConfig(Base):
    __tablename__ = "ai_style_configs"
    __table_args__ = (UniqueConstraint("merchant_id", "style_key", name="uk_merchant_style"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    name = Column(String(50), nullable=False, comment="风格名称（显示用）")
    style_key = Column(String(30), nullable=False, comment="professional / warm / expert / custom")
    tone = Column(String(20), nullable=True, comment="语气标签")
    greeting = Column(String(200), nullable=True, comment="开场问候语模板")
    features = Column(JSON, nullable=True, comment='{"长度":"简洁","表情":"适量","促单":"温和"}')
    is_default = Column(SmallInteger, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
