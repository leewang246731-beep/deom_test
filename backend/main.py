"""
FastAPI 应用入口
- 注册 CORS
- create_all(checkfirst=True)：表不存在才建
- 健康检查
- 业务 router 随接口批次逐步注册（步骤4 打开）
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.database.session import Base, engine
import app.models  # noqa: F401  注册全部 ORM 模型到 Base.metadata

Base.metadata.create_all(bind=engine, checkfirst=True)

app = FastAPI(
    title="多平台智能托管 SaaS 平台",
    description="后端 API (FastAPI + SQLAlchemy + MySQL 8.0)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.API_PREFIX}/health", tags=["系统"])
def health_check():
    return {"code": 200, "msg": "ok", "data": {"service": "running"}}


@app.get(f"{settings.API_PREFIX}/health/db", tags=["系统"])
def health_check_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"code": 200, "msg": "ok", "data": {"database": "connected"}}
    except Exception as e:
        return {"code": 500, "msg": f"数据库连接失败: {e}", "data": None}


# ===== 业务路由注册区（步骤4）=====
from app.api.v1 import ai, auth, categories, conversations, dashboard, orders, products, recommendations, shops, skill_groups, sla, tickets, webhooks

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(shops.router, prefix=settings.API_PREFIX)
app.include_router(products.router, prefix=settings.API_PREFIX)
app.include_router(orders.router, prefix=settings.API_PREFIX)
app.include_router(ai.router, prefix=settings.API_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_PREFIX)
app.include_router(categories.router, prefix=settings.API_PREFIX)
app.include_router(recommendations.router, prefix=settings.API_PREFIX)
app.include_router(tickets.router, prefix=settings.API_PREFIX)
app.include_router(skill_groups.router, prefix=settings.API_PREFIX)
app.include_router(sla.router, prefix=settings.API_PREFIX)
app.include_router(webhooks.router, prefix=settings.API_PREFIX)
# 会话 REST 带 /api/v1 前缀；WebSocket /ws/service 挂根路径（不带前缀）
app.include_router(conversations.router, prefix=settings.API_PREFIX)
app.include_router(conversations.ws_router)
app.include_router(conversations.ws_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8010)
