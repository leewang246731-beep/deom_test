"""商户列表接口 — 平台端商户选择器数据源"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_platform_user
from app.core.response import ok
from app.database.session import get_db
from app.models.merchant import Merchant

router = APIRouter(prefix="/merchants", tags=["商户管理"])


@router.get("")
def list_merchants(
    current: CurrentUser = Depends(get_platform_user),
    db: Session = Depends(get_db),
):
    """仅平台端可访问。返回所有正常商户供选择器使用。"""
    merchants = (
        db.query(Merchant)
        .filter(Merchant.status == 1)
        .order_by(Merchant.id)
        .all()
    )
    return ok([{"id": m.id, "name": m.name, "status": m.status} for m in merchants])
