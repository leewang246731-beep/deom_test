"""
商品库接口（PHASE1-PLAN 4.3 / api.md 3.3 + REQUIREMENTS-V2 缺口1）
筛选/详情走 DB；语义搜索 /search 走向量服务；/sync 独立同步商品。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, require_roles
from app.core.platform_connector import get_platform_connector
from app.core.response import ok, page
from app.database.session import get_db
from app.models.external_product import ExternalProduct
from app.models.platform_shop import PlatformShop

router = APIRouter(prefix="/products", tags=["商品库"])


def _merchant_shop_ids(db: Session, merchant_id: int) -> list:
    return [r[0] for r in db.query(PlatformShop.id).filter(
        PlatformShop.merchant_id == merchant_id).all()]


def _product_dict(p: ExternalProduct) -> dict:
    return {
        "id": p.id, "shop_id": p.shop_id, "title": p.title,
        "price": float(p.price), "stock": p.stock,
        "description": p.description, "category_path": p.category_path,
        "images_json": p.images_json, "embedding_status": p.embedding_status,
        "status": p.status,
    }


@router.get("")
def list_products(
    shop_id: int = Query(None), category: str = Query(None),
    keyword: str = Query(None), price_min: float = Query(None), price_max: float = Query(None),
    page_no: int = Query(1, alias="page"), page_size: int = Query(20),
    current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db),
):
    shop_ids = _merchant_shop_ids(db, current.merchant_id)
    if not shop_ids:
        return page([], 0, page_no, page_size)
    q = db.query(ExternalProduct).filter(ExternalProduct.shop_id.in_(shop_ids))
    if shop_id:
        q = q.filter(ExternalProduct.shop_id == shop_id)
    if category:
        q = q.filter(ExternalProduct.category_path.like(f"%{category}%"))
    if keyword:
        q = q.filter(ExternalProduct.title.like(f"%{keyword}%"))
    if price_min is not None:
        q = q.filter(ExternalProduct.price >= price_min)
    if price_max is not None:
        q = q.filter(ExternalProduct.price <= price_max)
    total = q.count()
    items = q.order_by(ExternalProduct.id).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([_product_dict(p) for p in items], total, page_no, page_size)


@router.get("/search")
def search_products(
    q: str = Query(..., description="自然语言查询"),
    shop_id: int = Query(None),
    current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db),
):
    """语义搜索：向量检索 + 可选店铺过滤（缺口5）。"""
    shop_ids = _merchant_shop_ids(db, current.merchant_id)
    if shop_id and shop_id in shop_ids:
        shop_ids = [shop_id]
    shop_map = {s.id: s.shop_name for s in db.query(PlatformShop).filter(
        PlatformShop.id.in_(shop_ids)).all()} if shop_ids else {}
    results = []
    try:
        from app.services.ai_suggest import semantic_search_products
        results = semantic_search_products(current.merchant_id, q, shop_ids, top_k=10)
    except Exception:
        items = db.query(ExternalProduct).filter(
            ExternalProduct.shop_id.in_(shop_ids),
            ExternalProduct.title.like(f"%{q}%"),
        ).limit(10).all() if shop_ids else []
        results = [{"id": p.id, "title": p.title, "score": None, "shop_id": p.shop_id} for p in items]
    for r in results:
        r["shop_name"] = shop_map.get(r.get("shop_id"), "")
    return ok({"query": q, "results": results})


@router.get("/{product_id}")
def product_detail(product_id: int, current: CurrentUser = Depends(get_current_merchant),
                   db: Session = Depends(get_db)):
    shop_ids = _merchant_shop_ids(db, current.merchant_id)
    p = db.query(ExternalProduct).filter(
        ExternalProduct.id == product_id,
        ExternalProduct.shop_id.in_(shop_ids) if shop_ids else False,
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "商品不存在"})
    return ok(_product_dict(p))


@router.post("/sync/{shop_id}")
async def sync_products(
    shop_id: int,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    """单独同步该店铺商品（缺口1：支持 UPDATE 已存在的商品）。"""
    shop = db.query(PlatformShop).filter(
        PlatformShop.id == shop_id, PlatformShop.merchant_id == current.merchant_id).first()
    if not shop:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "店铺不存在"})
    connector = get_platform_connector(shop_id, db)
    products = await connector.fetch_products(shop_id)
    new_p = upd_p = 0
    for p in products:
        exist = db.query(ExternalProduct).filter(
            ExternalProduct.shop_id == shop_id,
            ExternalProduct.platform_product_id == p["platform_product_id"],
        ).first()
        if exist:
            exist.title = p["title"]
            exist.price = p["price"]
            exist.stock = p["stock"]
            exist.description = p["description"]
            exist.status = p["status"]
            exist.last_sync_at = p["last_sync_at"]
            upd_p += 1
        else:
            db.add(ExternalProduct(
                shop_id=shop_id, platform_product_id=p["platform_product_id"],
                title=p["title"], price=p["price"], stock=p["stock"],
                description=p["description"], images_json=p["images_json"],
                category_path=p["category_path"], status=p["status"],
                last_sync_at=p["last_sync_at"], embedding_status="pending",
            ))
            new_p += 1
    db.commit()
    return ok({"shop_id": shop_id, "new_products": new_p, "updated_products": upd_p,
               "total_products": new_p + upd_p}, msg="商品同步完成")
