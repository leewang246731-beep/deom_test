"""
全局配置 (Settings)
从 backend/.env 读取环境变量，集中管理数据库、JWT、Redis、ChromaDB、AI 等配置。
"""
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ===== 数据库 (MySQL 8.0+) =====
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "121300"
    DB_NAME: str = "demo_test"

    # ===== JWT =====
    JWT_SECRET: str = "demo-ecom-secret-2026-please-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ===== Redis =====
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # ===== ChromaDB (嵌入式 PersistentClient) =====
    CHROMA_PERSIST_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "chroma"
    )

    # ===== 平台模式 =====
    PLATFORM_MODE: str = "mock"  # mock / real

    # ===== AI / DashScope (OpenAI 兼容模式) =====
    DASHSCOPE_API_KEY: str = ""
    LLM_API_BASE: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    EMBEDDING_MODEL: str = "text-embedding-v4"
    LLM_MODEL: str = "qwen-plus"  # qwen-plus 比 qwen-max 配额更宽松，性价比更高
    RAG_TOP_K: int = 20
    AI_SUGGEST_COUNT: int = 3
    LLM_MAX_RETRIES: int = 2  # LLM 调用失败重试次数
    LLM_TIMEOUT: int = 30     # LLM 调用超时(秒)
    # DeepSeek 兜底（主 LLM 失败时切换；OpenAI 兼容端点）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ===== 项目通用 =====
    API_PREFIX: str = "/api/v1"
    PAGE_SIZE: int = 20
    BCRYPT_ROUNDS: int = 12

    # ===== CORS (生产部署时限制为前端域名) =====
    CORS_ORIGINS: str = "*"  # 逗号分隔，如 "http://localhost:8093,https://admin.example.com"

    # ===== 文件上传 =====
    UPLOAD_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "uploads"
    )
    UPLOAD_MAX_MB: int = 50  # 单文件最大上传大小(MB)
    ALLOWED_UPLOAD_EXTENSIONS: str = ".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.md,.markdown,.txt,.text,.rst,.csv"

    # ===== 登录限流 =====
    LOGIN_RATE_LIMIT: int = 10  # 每分钟每IP最大尝试次数
    LOGIN_RATE_WINDOW: int = 60  # 限流窗口（秒）

    @property
    def DATABASE_URL(self) -> str:
        """SQLAlchemy 连接串：mysql+pymysql://用户:密码@主机:端口/库名"""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    # .env 路径相对 backend 根目录 (app/core/config.py 上溯三级)
    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
        ),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
