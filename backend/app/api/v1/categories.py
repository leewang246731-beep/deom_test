"""
分类管理接口（REQUIREMENTS-V2 §6）
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_user, get_effective_merchant_id, require_roles
from app.core.response import ok
from app.database.session import get_db
from app.models.category import Category

router = APIRouter(prefix="/categories", tags=["分类管理"])


class CategoryCreate(BaseModel):
    name: str
    parent_id: int = None


class CategoryUpdate(BaseModel):
    name: str = None
    parent_id: int = None
    sort_order: int = None


def _build_tree(cats: list[Category], parent_id: int = None) -> list[dict]:
    return [{
        "id": c.id, "name": c.name, "parent_id": c.parent_id,
        "level": c.level, "sort_order": c.sort_order,
        "children": _build_tree(cats, c.id),
    } for c in cats if c.parent_id == parent_id]


@router.get("")
def list_categories(current: CurrentUser = Depends(get_current_user),
                    mid: int = Depends(get_effective_merchant_id),
                    db: Session = Depends(get_db)):
    cats = db.query(Category).filter(
        Category.merchant_id == mid
    ).order_by(Category.level, Category.sort_order).all()
    return ok(_build_tree(cats))


@router.post("")
def create_category(body: CategoryCreate,
                    current: CurrentUser = Depends(require_roles("admin", "manager")),
                    mid: int = Depends(get_effective_merchant_id),
                    db: Session = Depends(get_db)):
    level = 1
    if body.parent_id:
        parent = db.query(Category).filter(Category.id == body.parent_id,
                                            Category.merchant_id == mid).first()
        if not parent:
            raise HTTPException(status_code=404, detail={"code": 40401, "msg": "父分类不存在"})
        level = parent.level + 1
    max_order = db.query(Category.sort_order).filter(
        Category.merchant_id == mid).order_by(Category.sort_order.desc()).first()
    sort_order = (max_order[0] + 1) if max_order else 0
    cat = Category(merchant_id=mid, name=body.name,
                   parent_id=body.parent_id, level=level, sort_order=sort_order)
    db.add(cat)
    db.commit()
    return ok({"id": cat.id}, msg="已创建")


@router.put("/{cat_id}")
def update_category(cat_id: int, body: CategoryUpdate,
                    current: CurrentUser = Depends(require_roles("admin", "manager")),
                    mid: int = Depends(get_effective_merchant_id),
                    db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == cat_id,
                                     Category.merchant_id == mid).first()
    if not cat:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "分类不存在"})
    if body.name is not None:
        cat.name = body.name
    if body.sort_order is not None:
        cat.sort_order = body.sort_order
    db.commit()
    return ok({"id": cat.id}, msg="已更新")


@router.delete("/{cat_id}")
def delete_category(cat_id: int,
                    current: CurrentUser = Depends(require_roles("admin", "manager")),
                    mid: int = Depends(get_effective_merchant_id),
                    db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == cat_id,
                                     Category.merchant_id == mid).first()
    if not cat:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "分类不存在"})
    children = db.query(Category).filter(Category.parent_id == cat_id).count()
    if children:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "该分类下有子分类，无法删除"})
    db.delete(cat)
    db.commit()
    return ok(msg="已删除")
