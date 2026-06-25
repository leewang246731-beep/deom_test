"""
FastAPI 应用入口
- 注册 CORS + lifespan (超时检测器)
- create_all(checkfirst=True)
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.database.session import Base, engine
import app.models  # noqa: F401


async def _timeout_checker():
    """每 10 秒扫描待人工响应的会话，触发兜底话术或升级工单。"""
    from datetime import datetime
    while True:
        await asyncio.sleep(10)
        try:
            from app.database.session import SessionLocal
            from app.models.conversation import Conversation
            from app.models.service_mode import ServiceModeConfig
            db = SessionLocal()
            # 找超时会话
            expired = db.query(Conversation).filter(
                Conversation.pending_timeout_at != None,
                Conversation.pending_timeout_at < datetime.now(),
                Conversation.handled_status == "pending",
            ).all()
            for conv in expired:
                cfg = db.query(ServiceModeConfig).filter(
                    ServiceModeConfig.merchant_id == 1).first()
                fallback = cfg.fallback_template if cfg else "亲，客服正在为您查询中，请稍等~"
                # 追加兜底话术到 messages_json
                msgs = conv.messages_json or []
                msgs.append({"role": "service", "content": f"[AI兜底] {fallback}",
                             "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "auto": True})
                conv.messages_json = msgs
                conv.pending_timeout_at = None
                conv.auto_reply_count = (conv.auto_reply_count or 0) + 1
                # 日志
                from app.services.mode_engine import log_auto_reply
                log_auto_reply(db, conv.id, 1, "copilot", "超时兜底", fallback, 0.0, "fallback_sent")
            db.commit()
            db.close()
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine, checkfirst=True)
    task = asyncio.create_task(_timeout_checker())
    from app.services.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    task.cancel()
    stop_scheduler()


app = FastAPI(
    title="多平台智能托管 SaaS 平台",
    description="后端 API (FastAPI + SQLAlchemy + MySQL 8.0)",
    version="2.0.0",
    lifespan=lifespan,
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
from app.api.v1 import ai, audit, auth, categories, conversations, dashboard, orders, products, recommendations, shops, skill_groups, sla, tickets, users, webhook_logs, webhooks, service_mode, openapi

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
app.include_router(service_mode.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(audit.router, prefix=settings.API_PREFIX)
app.include_router(webhook_logs.router, prefix=settings.API_PREFIX)
app.include_router(openapi.router, prefix=settings.API_PREFIX)

# 知识库
from app.kb.kb_api import router as kb_router
app.include_router(kb_router, prefix=settings.API_PREFIX)
# 会话 REST 带 /api/v1 前缀；WebSocket /ws/service 挂根路径（不带前缀）
app.include_router(conversations.router, prefix=settings.API_PREFIX)
app.include_router(conversations.ws_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8010)
