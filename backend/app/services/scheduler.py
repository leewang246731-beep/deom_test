"""APScheduler 定时同步调度器 — 每30分钟自动同步已绑定店铺。"""
import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
_sync_log: list[dict] = []  # 最近 50 条同步记录


async def _sync_all_shops():
    from app.database.session import SessionLocal
    from app.models.platform_shop import PlatformShop
    from app.core.platform_connector import get_platform_connector
    from app.models.external_product import ExternalProduct
    from app.models.external_order import ExternalOrder

    db = SessionLocal()
    try:
        shops = db.query(PlatformShop).filter(PlatformShop.is_active == 1).all()
        results = []
        for shop in shops:
            try:
                connector = get_platform_connector(shop.id, db)
                products = await connector.fetch_products(shop.id)
                new_p = upd_p = 0
                for p in products:
                    exist = db.query(ExternalProduct).filter(
                        ExternalProduct.shop_id == shop.id,
                        ExternalProduct.platform_product_id == p["platform_product_id"],
                    ).first()
                    if exist:
                        exist.title = p["title"]
                        exist.price = p["price"]
                        exist.stock = p["stock"]
                        exist.status = p["status"]
                        exist.last_sync_at = p["last_sync_at"]
                        upd_p += 1
                    else:
                        db.add(ExternalProduct(
                            shop_id=shop.id, platform_product_id=p["platform_product_id"],
                            title=p["title"], price=p["price"], stock=p["stock"],
                            description=p["description"], images_json=p["images_json"],
                            category_path=p["category_path"], status=p["status"],
                            last_sync_at=p["last_sync_at"], embedding_status="pending",
                        ))
                        new_p += 1
                shop.sync_status = "idle"
                shop.last_sync_at = datetime.now()
                db.commit()
                results.append({"shop_id": shop.id, "shop_name": shop.shop_name,
                                "new": new_p, "updated": upd_p, "status": "ok"})
            except Exception as e:
                shop.sync_status = "error"
                db.commit()
                results.append({"shop_id": shop.id, "shop_name": shop.shop_name,
                                "error": str(e)[:120], "status": "error"})

        entry = {"time": datetime.now().isoformat(), "results": results}
        _sync_log.insert(0, entry)
        if len(_sync_log) > 50:
            _sync_log.pop()
    finally:
        db.close()


async def trigger_sync_all():
    """手动触发全部店铺同步（供 API 调用）。"""
    await _sync_all_shops()


def _run_sync():
    asyncio.create_task(_sync_all_shops())


def start_scheduler():
    scheduler.add_job(
        _run_sync, "interval", minutes=30, id="sync_all",
        next_run_time=None,
    )
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown(wait=False)


def get_sync_log() -> list[dict]:
    return _sync_log
