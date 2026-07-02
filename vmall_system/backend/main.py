"""
vMall 虚拟电商平台 — FastAPI 入口 :8020
独立运行，与 SaaS 项目零耦合。
含：超时订单取消 + 物流自动推进模拟器
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.session import Base, engine
import app.models  # noqa: F401


async def timeout_scanner():
    """每 60 秒扫描超时未付订单并取消。"""
    while True:
        await asyncio.sleep(60)
        try:
            from app.database.session import SessionLocal
            from app.services.order_state import cancel_timeout_orders
            db = SessionLocal()
            n = cancel_timeout_orders(db, settings.PAYMENT_TIMEOUT_MINUTES)
            if n: print(f"[vMall] 取消超时订单: {n} 笔")
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine, checkfirst=True)
    timeout_task = asyncio.create_task(timeout_scanner())
    logistics_task = asyncio.create_task(
        __import__("app.tasks.logistics_simulator", fromlist=["run_simulator"]).run_simulator(
            int(getattr(settings, "LOGISTICS_INTERVAL_SECONDS", "30"))
        )
    )
    yield
    timeout_task.cancel()
    logistics_task.cancel()


app = FastAPI(title="vMall 虚拟电商平台", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                    allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"code": 200, "msg": "vMall running"}


# ---- 路由注册 ----
from app.api.consumer.auth import router as consumer_auth
from app.api.consumer.products import router as consumer_products
from app.api.consumer.orders import router as consumer_orders
from app.api.consumer.conversations import router as consumer_convs
from app.api.consumer.after_sales import router as consumer_as
from app.api.consumer.profile import router as consumer_profile
from app.api.consumer.payment_link import router as consumer_paylink

from app.api.admin.auth import router as admin_auth
from app.api.admin.orders import router as admin_orders
from app.api.admin.after_sales import router as admin_as
from app.api.admin.conversations import router as admin_convs
from app.api.admin.settings import router as admin_settings
from app.api.admin.logistics import router as admin_logistics
from app.api.admin.wallet import router as admin_wallet

from app.api.merchant.auth import router as merchant_auth
from app.api.merchant.dashboard import router as merchant_dashboard
from app.api.merchant.products import router as merchant_products
from app.api.merchant.orders import router as merchant_orders
from app.api.merchant.conversations import router as merchant_convs
from app.api.merchant.settings import router as merchant_settings
from app.api.merchant.binding import router as merchant_binding

from app.api.openapi.router import router as openapi_router
from app.api.openapi.logistics import router as openapi_logistics

v1_routers = [consumer_auth, consumer_products, consumer_orders, consumer_convs, consumer_as, consumer_profile, consumer_paylink,
              admin_auth, admin_orders, admin_as, admin_convs, admin_settings, admin_logistics, admin_wallet,
              merchant_auth, merchant_dashboard, merchant_products, merchant_orders, merchant_convs,
              merchant_settings, merchant_binding]
for r in v1_routers:
    app.include_router(r, prefix="/api/v1")
app.include_router(openapi_router)
app.include_router(openapi_logistics)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)
