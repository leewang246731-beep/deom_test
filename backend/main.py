"""
FastAPI 应用入口
- 注册 CORS + lifespan (超时检测器) + 请求追踪
- create_all(checkfirst=True)
"""
import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

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
            from app.models.platform_shop import PlatformShop
            from app.models.service_mode import ServiceModeConfig
            db = SessionLocal()
            # 找超时会话
            expired = db.query(Conversation).filter(
                Conversation.pending_timeout_at != None,
                Conversation.pending_timeout_at < datetime.now(),
                Conversation.handled_status == "pending",
            ).all()
            for conv in expired:
                # 通过 shop → merchant 查找对应商户的服务模式配置
                merchant_id = None
                shop = db.query(PlatformShop).filter(PlatformShop.id == conv.shop_id).first()
                if shop:
                    merchant_id = shop.merchant_id
                cfg = db.query(ServiceModeConfig).filter(
                    ServiceModeConfig.merchant_id == merchant_id).first() if merchant_id else None
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
                log_auto_reply(db, conv.id, merchant_id or 1, "copilot", "超时兜底", fallback, 0.0, "fallback_sent")
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
    version="2.2.0",
    lifespan=lifespan,
)

# CORS — 开发用 * ，生产通过 .env 限制
cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求追踪中间件 — 注入 X-Request-ID
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = rid
        start = time.time()
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time"] = f"{(time.time() - start)*1000:.0f}ms"
        return response

app.add_middleware(RequestIDMiddleware)


@app.get(f"{settings.API_PREFIX}/health", tags=["系统"])
def health_check():
    """聚合健康检查：DB + Redis + ChromaDB + LLM 连通性。"""
    status = {"service": "running", "db": "unknown", "redis": "unknown", "chromadb": "unknown", "llm": "unknown"}
    # DB
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        status["db"] = "connected"
    except Exception as e:
        status["db"] = f"error: {e}"
    # Redis
    try:
        from app.core.redis_client import get_redis
        r = get_redis()
        if r.ping():
            status["redis"] = "connected"
    except Exception as e:
        status["redis"] = f"error: {e}"
    # ChromaDB
    try:
        from app.services.chroma_client import _get_client
        _get_client().heartbeat()
        status["chromadb"] = "connected"
    except Exception as e:
        status["chromadb"] = f"error: {e}"
    # LLM (DashScope OpenAI 兼容模式)
    try:
        from app.services.llm import chat
        test_resp = chat([{"role": "user", "content": "ping"}])
        status["llm"] = "connected" if test_resp else "empty_response"
    except Exception as e:
        status["llm"] = f"error: {e}"

    critical = ["db", "redis", "chromadb"]
    healthy = all(status.get(k) == "connected" for k in critical)
    return {"code": 200 if healthy else 503, "msg": "healthy" if healthy else "degraded", "data": status}


@app.get(f"{settings.API_PREFIX}/health/db", tags=["系统"])
def health_check_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"code": 200, "msg": "ok", "data": {"database": "connected"}}
    except Exception as e:
        return {"code": 500, "msg": f"数据库连接失败: {e}", "data": None}


# ===== 业务路由注册区（步骤4）=====
from app.api.v1 import ai, audit, auth, categories, conversations, coupons, dashboard, merchants, orders, products, recommendations, shops, skill_groups, sla, tickets, users, webhook_logs, webhooks, service_mode, openapi

app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(shops.router, prefix=settings.API_PREFIX)
app.include_router(merchants.router, prefix=settings.API_PREFIX)
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
app.include_router(coupons.router, prefix=settings.API_PREFIX)

# 知识库
from app.kb.kb_api import router as kb_router
app.include_router(kb_router, prefix=settings.API_PREFIX)
# 会话 REST 带 /api/v1 前缀；WebSocket /ws/service 挂根路径（不带前缀）
app.include_router(conversations.router, prefix=settings.API_PREFIX)
app.include_router(conversations.ws_router)


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", "8012"))
    uvicorn.run(app, host="0.0.0.0", port=port)
