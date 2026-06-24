"""
数据库连接 (engine / SessionLocal / Base / get_db)
连接池写法沿用通用配置，连接串由 app.core.config.settings 提供。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """请求级数据库会话依赖：取一个会话，结束后归还连接池。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
