"""用户管理接口（平台跨租户查看 + 商户租户隔离）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_user, get_current_merchant, require_roles
from app.core.response import ok, page
from app.core.security import hash_password
from app.database.session import get_db
from app.models.merchant_user import MerchantUser
from app.schemas import UserCreate, UserUpdate

router = APIRouter(prefix="/users", tags=["用户管理"])


def _user_dict(u: MerchantUser) -> dict:
    return {
        "id": u.id, "username": u.username, "display_name": u.display_name,
        "role": u.role, "status": u.status,
        "merchant_id": u.merchant_id,
        "last_login_at": str(u.last_login_at) if u.last_login_at else None,
        "created_at": str(u.created_at) if u.created_at else None,
    }


@router.get("")
def list_users(
    page_no: int = Query(1, alias="page"),
    page_size: int = Query(20),
    role: str = Query(None),
    merchant_id: int = Query(None),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(MerchantUser)
    # 平台视角看全部商户用户，商户视角只看自己
    if current.token_type == "access":
        q = q.filter(MerchantUser.merchant_id == current.merchant_id)
    elif merchant_id:
        q = q.filter(MerchantUser.merchant_id == merchant_id)
    if role:
        q = q.filter(MerchantUser.role == role)
    total = q.count()
    items = q.order_by(MerchantUser.id).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([_user_dict(u) for u in items], total, page_no, page_size)


@router.post("")
def create_user(
    body: UserCreate,
    current: CurrentUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    exist = db.query(MerchantUser).filter(
        MerchantUser.merchant_id == current.merchant_id,
        MerchantUser.username == body.username,
    ).first()
    if exist:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "用户名已存在"})
    if body.role not in ("admin", "manager", "service"):
        raise HTTPException(status_code=400, detail={"code": 40002, "msg": "角色无效"})
    u = MerchantUser(
        merchant_id=current.merchant_id,
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.username,
        role=body.role,
        status=1,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return ok(_user_dict(u), msg="用户已创建")


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UserUpdate,
    current: CurrentUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    u = db.query(MerchantUser).filter(
        MerchantUser.id == user_id,
        MerchantUser.merchant_id == current.merchant_id,
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "用户不存在"})
    if body.display_name is not None:
        u.display_name = body.display_name
    if body.role is not None and body.role in ("admin", "manager", "service"):
        u.role = body.role
    if body.status is not None:
        u.status = body.status
    if body.password:
        u.password_hash = hash_password(body.password)
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
