"""vMall 全局配置 (独立 Settings，不与 SaaS 共享)"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "121300"
    DB_NAME: str = "vmall_db"

    JWT_SECRET: str = "vmall-jwt-secret-2026-please-change"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    ACCESS_TOKEN_SECRET: str = "vmall-secret-key-change-in-production"
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    PAYMENT_TIMEOUT_MINUTES: int = 15
    PORT: int = 8020

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8", case_sensitive=True, extra="ignore",
    )


settings = Settings()
