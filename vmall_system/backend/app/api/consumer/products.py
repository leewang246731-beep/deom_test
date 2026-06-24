"""消费者端 - 商品"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.response import ok, page
from app.database.session import get_db
from app.models.vm_product import VmProduct

router = APIRouter(prefix="/consumer/products", tags=["消费者-商品"])


@router.get("")
def list_products(category: str = Query(None), sort: str = Query("default"),
                  page_no: int = Query(1, alias="page"), page_size: int = Query(20),
                  db: Session = Depends(get_db)):
    q = db.query(VmProduct).filter(VmProduct.status == 1)
    if category:
        q = q.filter(VmProduct.category_path.like(f"%{category}%"))
    if sort == "price_asc":
        q = q.order_by(VmProduct.price_min.asc())
    elif sort == "price_desc":
        q = q.order_by(VmProduct.price_min.desc())
    elif sort == "sales":
        q = q.order_by(VmProduct.total_sales.desc())
    else:
        q = q.order_by(VmProduct.id.desc())
    total = q.count()
    items = q.offset((page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": p.id, "title": p.title, "main_image": p.main_image,
                   "price_min": float(p.price_min), "price_max": float(p.price_max),
                   "category_path": p.category_path, "total_sales": p.total_sales,
                   "total_stock": p.total_stock} for p in items], total, page_no, page_size)


@router.get("/{product_id}")
def product_detail(product_id: int, db: Session = Depends(get_db)):
    p = db.query(VmProduct).get(product_id)
    if not p or p.status != 1:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "商品不存在"})
    return ok({
        "id": p.id, "title": p.title, "main_image": p.main_image,
        "images_json": p.images_json, "price_min": float(p.price_min), "price_max": float(p.price_max),
        "category_path": p.category_path, "description": p.description,
        "skus_json": [{"spec": s["spec"], "price": float(s["price"]), "stock": s["stock"],
                        "sku_code": s["sku_code"]} for s in (p.skus_json or [])],
        "total_stock": p.total_stock, "total_sales": p.total_sales,
    })
