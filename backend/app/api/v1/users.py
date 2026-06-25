"""用户管理接口"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, require_roles
from app.core.response import ok, page
from app.core.security import hash_password
from app.database.session import get_db
from app.models.merchant_user import MerchantUser

router = APIRouter(prefix="/users", tags=["用户管理"])


def _user_dict(u: MerchantUser) -> dict:
    return {
        "id": u.id, "username": u.username, "display_name": u.display_name,
        "role": u.role, "status": u.status, "last_login_at": str(u.last_login_at) if u.last_login_at else None,
        "created_at": str(u.created_at) if u.created_at else None,
    }


@router.get("")
def list_users(
    page_no: int = Query(1, alias="page"),
    page_size: int = Query(20),
    role: str = Query(None),
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    db: Session = Depends(get_db),
):
    q = db.query(MerchantUser).filter(MerchantUser.merchant_id == current.merchant_id)
    if role:
        q = q.filter(MerchantUser.role == role)
    total = q.count()
    items = q.order_by(MerchantUser.id).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([_user_dict(u) for u in items], total, page_no, page_size)


@router.post("")
def create_user(
    body: dict,
    current: CurrentUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    exist = db.query(MerchantUser).filter(
        MerchantUser.merchant_id == current.merchant_id,
        MerchantUser.username == body["username"],
    ).first()
    if exist:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "用户名已存在"})
    if body.get("role") not in ("admin", "manager", "service"):
        raise HTTPException(status_code=400, detail={"code": 40002, "msg": "角色无效"})
    u = MerchantUser(
        merchant_id=current.merchant_id,
        username=body["username"],
        password_hash=hash_password(body.get("password", "123456")),
        display_name=body.get("display_name", body["username"]),
        role=body["role"],
        status=body.get("status", 1),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return ok(_user_dict(u), msg="用户已创建")


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: dict,
    current: CurrentUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    u = db.query(MerchantUser).filter(
        MerchantUser.id == user_id,
        MerchantUser.merchant_id == current.merchant_id,
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "用户不存在"})
    if "display_name" in body:
        u.display_name = body["display_name"]
    if "role" in body and body["role"] in ("admin", "manager", "service"):
        u.role = body["role"]
    if "status" in body:
        u.status = body["status"]
    if "password" in body and body["password"]:
        u.password_hash = hash_password(body["password"])
    db.commit()
    db.refresh(u)
    return ok(_user_dict(u), msg="用户已更新")


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    current: CurrentUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    u = db.query(MerchantUser).filter(
        MerchantUser.id == user_id,
        MerchantUser.merchant_id == current.merchant_id,
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "用户不存在"})
    if u.id == current.user_id:
        raise HTTPException(status_code=400, detail={"code": 40003, "msg": "不能删除自己"})
    db.delete(u)
    db.commit()
    return ok(None, msg="用户已删除")
