"""知识库数据模型：文档、切片、会话、消息"""
from sqlalchemy import BigInteger, Column, DateTime, Float, Integer, SmallInteger, String, Text, JSON, func
from app.database.session import Base


class KbDocument(Base):
    __tablename__ = "kb_documents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(Integer, nullable=False, index=True, comment="租户ID")
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=True, comment="原始全文")
    source_type = Column(String(30), default="manual", comment="product/shop_info/conversation/manual/upload")
    source_id = Column(BigInteger, nullable=True, comment="来源实体ID")
    status = Column(String(20), default="pending", comment="pending/parsing/vectorizing/done/failed")
    chunk_count = Column(Integer, default=0)
    error_msg = Column(String(500), nullable=True)
    file_path = Column(String(500), nullable=True, comment="上传文件存储路径")
    file_type = Column(String(20), nullable=True, comment="文件类型: pdf/docx/xlsx/pptx/md/txt")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    document_id = Column(BigInteger, nullable=False, index=True)
    merchant_id = Column(Integer, nullable=False, index=True)
    chunk_index = Column(Integer, default=0)
    content = Column(Text, nullable=False)
    heading_context = Column(String(300), nullable=True)
    token_count = Column(Integer, default=0)
    embedding_id = Column(String(100), nullable=True, comment="ChromaDB embedding ID")
    created_at = Column(DateTime, server_default=func.now())


class KbConversation(Base):
    __tablename__ = "kb_conversations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    title = Column(String(200), default="新对话")
    retrieval_mode = Column(String(20), default="auto", comment="fast/auto/comprehensive")
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class KbMessage(Base):
    __tablename__ = "kb_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(BigInteger, nullable=False, index=True)
    role = Column(String(10), nullable=False, comment="user/assistant")
    content = Column(Text, nullable=False)
    references_json = Column(JSON, nullable=True, comment="引用来源列表")
    confidence = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
