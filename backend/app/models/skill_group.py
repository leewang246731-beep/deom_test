"""技能组 + 成员"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func

from app.database.session import Base


class SkillGroup(Base):
    __tablename__ = "skill_groups"
    __table_args__ = (UniqueConstraint("merchant_id", "name", name="uk_merchant_skill"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    name = Column(String(50), nullable=False)
    description = Column(String(300), nullable=True)
    is_active = Column(SmallInteger, default=1)
    created_at = Column(DateTime, server_default=func.now())


class SkillMember(Base):
    __tablename__ = "skill_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uk_group_user"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("skill_groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("merchant_users.id", ondelete="CASCADE"), nullable=False)
    skill_tags = Column(String(500), nullable=True, comment="逗号分隔，如 精通3C数码,擅长安抚情绪")
