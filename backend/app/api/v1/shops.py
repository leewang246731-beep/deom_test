"""
店铺管理接口（PHASE1-PLAN 4.2 / api.md 3.2）
所有查询按 merchant_id 过滤。手动 /sync 替代二期 Celery 定时同步。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, require_roles
from app.core.platform_connector import get_platform_connector
from app.core.response import ok
from app.database.session import get_db
from app.models.conversation import Conversation
from app.models.external_order import ExternalOrder
from app.models.external_product import ExternalProduct
from app.models.platform_shop import PlatformShop
from app.schemas import ShopCreate

router = APIRouter(prefix="/shops", tags=["店铺管理"])


def _get_owned_shop(db: Session, shop_id: int, merchant_id: int) -> PlatformShop:
    shop = db.query(PlatformShop).filter(
        PlatformShop.id == shop_id, PlatformShop.merchant_id == merchant_id
    ).first()
    if not shop:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "店铺不存在"})
    return shop


@router.get("")
def list_shops(current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    shops = db.query(PlatformShop).filter(
        PlatformShop.merchant_id == current.merchant_id
    ).order_by(PlatformShop.id).all()
    result = []
    for s in shops:
        product_cnt = db.query(ExternalProduct).filter(ExternalProduct.shop_id == s.id).count()
        order_cnt = db.query(ExternalOrder).filter(ExternalOrder.shop_id == s.id).count()
        result.append({
            "id": s.id,
            "platform_type": s.platform_type,
            "shop_name": s.shop_name,
            "shop_url": s.shop_url,
            "sync_status": s.sync_status,
            "last_sync_at": s.last_sync_at.isoformat() if s.last_sync_at else None,
            "is_active": s.is_active,
            "product_count": product_cnt,
            "order_count": order_cnt,
        })
    return ok(result)


@router.post("")
def bind_shop(
    body: ShopCreate,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    shop = PlatformShop(
        merchant_id=current.merchant_id,
        platform_type=body.platform_type,
        shop_name=body.shop_name,
        shop_url=body.shop_url,
        sync_status="idle",
        is_active=1,
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)
    return ok({"id": shop.id, "shop_name": shop.shop_name})


@router.delete("/{shop_id}")
def unbind_shop(
    shop_id: int,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    shop = _get_owned_shop(db, shop_id, current.merchant_id)
    # 级联删除该店铺商品/订单/会话
    db.query(Conversation).filter(Conversation.shop_id == shop_id).delete(synchronize_session=False)
    db.query(ExternalOrder).filter(ExternalOrder.shop_id == shop_id).delete(synchronize_session=False)
    db.query(ExternalProduct).filter(ExternalProduct.shop_id == shop_id).delete(synchronize_session=False)
    db.delete(shop)
    db.commit()
    return ok(msg="已解绑")


@router.get("/{shop_id}/status")
def shop_status(shop_id: int, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    shop = _get_owned_shop(db, shop_id, current.merchant_id)
    return ok({
        "id": shop.id,
        "sync_status": shop.sync_status,
        "last_sync_at": shop.last_sync_at.isoformat() if shop.last_sync_at else None,
    })


@router.post("/{shop_id}/sync")
async def sync_shop(
    shop_id: int,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    """
    手动触发同步（替代二期 Celery）：拉取商品+订单 upsert 入库。
    新商品 embedding_status=pending，向量化由步骤6 的 AI Pipeline 回填。
    """
    shop = _get_owned_shop(db, shop_id, current.merchant_id)
    shop.sync_status = "syncing"
    db.commit()
    try:
        connector = get_platform_connector(shop_id, db)
        products = await connector.fetch_products(shop_id)
        new_p = 0
        for p in products:
            exists = db.query(ExternalProduct).filter(
                ExternalProduct.shop_id == shop_id,
                ExternalProduct.platform_product_id == p["platform_product_id"],
            ).first()
            if exists:
                continue
            db.add(ExternalProduct(
                shop_id=shop_id,
                platform_product_id=p["platform_product_id"],
                title=p["title"], price=p["price"], stock=p["stock"],
                description=p["description"], images_json=p["images_json"],
                category_path=p["category_path"], status=p["status"],
                last_sync_at=p["last_sync_at"],
            ))
            new_p += 1

        orders = await connector.fetch_orders(shop_id, datetime.now() - timedelta(days=7))
        new_o = 0
        for o in orders:
            exists = db.query(ExternalOrder).filter(
                ExternalOrder.shop_id == shop_id,
                ExternalOrder.platform_order_id == o["platform_order_id"],
            ).first()
            if exists:
                continue
            db.add(ExternalOrder(
                shop_id=shop_id,
                platform_order_id=o["platform_order_id"], buyer_openid=o["buyer_openid"],
                buyer_nick=o["buyer_nick"], total_amount=o["total_amount"],
                discount_amount=o["discount_amount"], pay_amount=o["pay_amount"],
                status=o["status"], sku_details_json=o["sku_details_json"],
                receiver_name=o["receiver_name"], receiver_phone=o["receiver_phone"],
                receiver_address=o["receiver_address"], pay_time=o["pay_time"],
                ship_time=o["ship_time"], created_at=o["created_at"],
            ))
            new_o += 1

        shop.sync_status = "idle"
        shop.last_sync_at = datetime.now()
        db.commit()
        return ok({"new_products": new_p, "new_orders": new_o}, msg="同步完成")
    except Exception as e:
        shop.sync_status = "error"
        db.commit()
        raise HTTPException(status_code=500, detail={"code": 50001, "msg": f"同步失败: {e}"})
