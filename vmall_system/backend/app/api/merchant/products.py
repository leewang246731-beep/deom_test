"""商户 - 商品管理"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_product import VmProduct

router = APIRouter(prefix="/merchant/products", tags=["商户-商品"])


def _get_merchant(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "merchant":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需商户登录"})
    return payload


def _to_dict(p):
    return {"id": p.id, "name": p.title, "price": float(p.price_min), "price_max": float(p.price_max),
            "stock": p.total_stock, "status": p.status, "image_url": p.main_image,
            "category_id": None, "category_path": p.category_path,
            "description": p.description or "",
            "created_at": p.created_at.isoformat() if p.created_at else None}


@router.get("")
def list_products(page_no: int = Query(1, alias="page"), page_size: int = Query(20),
                  authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    mid = int(merchant["sub"])
    q = db.query(VmProduct).filter(VmProduct.merchant_id == mid)
    total = q.count()
    items = q.order_by(VmProduct.id.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([_to_dict(p) for p in items], total, page_no, page_size)


@router.get("/{product_id}")
def get_product(product_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    p = db.query(VmProduct).filter(VmProduct.id == product_id, VmProduct.merchant_id == int(merchant["sub"])).first()
    if not p: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "商品不存在"})
    return ok(_to_dict(p))


@router.post("")
def create_product(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    p = VmProduct(
        merchant_id=int(merchant["sub"]),
        title=body["name"],
        price_min=body.get("price", 0),
        price_max=body.get("price", 0),
        category_path=body.get("category_path", ""),
        description=body.get("description", ""),
        main_image=body.get("image_url", ""),
        total_stock=body.get("stock", 0),
        skus_json=body.get("skus", []),
        status=body.get("status", 1),
    )
    db.add(p); db.commit(); db.refresh(p)
    return ok({"id": p.id}, msg="添加成功")


@router.put("/{product_id}")
def update_product(product_id: int, body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    p = db.query(VmProduct).filter(VmProduct.id == product_id, VmProduct.merchant_id == int(merchant["sub"])).first()
    if not p: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "商品不存在"})
    if "name" in body: p.title = body["name"]
    if "price" in body:
        p.price_min = body["price"]
        p.price_max = body["price"]
    if "image_url" in body: p.main_image = body["image_url"]
    if "stock" in body: p.total_stock = body["stock"]
    if "category_path" in body: p.category_path = body["category_path"]
    if "description" in body: p.description = body["description"]
    if "status" in body: p.status = body["status"]
    db.commit()
    return ok({"id": p.id}, msg="更新成功")


@router.delete("/{product_id}")
def delete_product(product_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    p = db.query(VmProduct).filter(VmProduct.id == product_id, VmProduct.merchant_id == int(merchant["sub"])).first()
    if not p: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "商品不存在"})
    db.delete(p); db.commit()
    return ok(msg="删除成功")
