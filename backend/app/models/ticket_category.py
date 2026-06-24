"""工单分类（多级树，复用 categories 表结构模式）"""
from sqlalchemy import BigInteger, Column, ForeignKey, Integer, SmallInteger, String

from app.database.session import Base


class TicketCategory(Base):
    __tablename__ = "ticket_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, ForeignKey("merchants.id"), nullable=False)
    name = Column(String(50), nullable=False)
    parent_id = Column(Integer, ForeignKey("ticket_categories.id"), nullable=True)
    level = Column(SmallInteger, default=1)
    sort_order = Column(Integer, default=0)
