"""SaaS OpenAPI — vMall 绑定 + 注册。共享密钥 API Key + JWT 双模式鉴权。"""
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, require_roles
from app.core.config import settings
from app.core.response import ok
from app.database.session import get_db
from app.models.merchant import Merchant
from app.models.platform_shop import PlatformShop
from app.schemas import GenerateBindTokenRequest, ConfirmBindRequest, UnbindShopRequest, RegisterShopRequest

router = APIRouter(prefix="/openapi", tags=["OpenAPI"])

_OPENAPI_KEY = getattr(settings, "OPENAPI_KEY", "vmall-openapi-secret-2026")


def _verify_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != _OPENAPI_KEY:
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "无效的 API Key"})
    return True


def _fetch_vmall_token(vmall_url: str, merchant_id: int, shop_id: int) -> str:
    """从 vMall 获取 OpenAPI access_token，失败返回空字符串。"""
    try:
        import httpx
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"{vmall_url}/openapi/auth",
                json={"merchant_id": merchant_id, "shop_id": shop_id},
            )
            if resp.status_code == 200:
                data = resp.json()
                # vMall 返回 {code, data: {access_token, expires_in, shop_id}, msg}
                inner = data.get("data", data)
                return inner.get("access_token", "")
    except Exception:
        pass
    return ""


@router.post("/generate-bind-token")
def generate_bind_token(body: GenerateBindTokenRequest, current: CurrentUser = Depends(require_roles("admin", "manager")),
                        db: Session = Depends(get_db)):
    """SaaS 管理端：为指定 vmall 店铺生成绑定 token。"""
    shop = db.query(PlatformShop).filter(
        PlatformShop.id == body.shop_id, PlatformShop.merchant_id == current.merchant_id
    ).first()
    if not shop:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "店铺不存在"})
    if shop.platform_type != "vmall":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "仅 vmall 类型店铺需生成绑定 token"})
    token = secrets.token_urlsafe(24)
    shop.bind_token = token
    shop.bind_status = "pending"
    db.commit()
    return ok({
        "bind_token": token,
        "saas_url": f"http://127.0.0.1:8010",
        "shop_id": shop.id,
        "shop_name": shop.shop_name,
    }, msg="绑定 token 已生成")


@router.post("/regenerate-bind-token")
def regenerate_bind_token(body: GenerateBindTokenRequest, current: CurrentUser = Depends(require_roles("admin", "manager")),
                          db: Session = Depends(get_db)):
    """重新生成绑定 token。"""
    shop = db.query(PlatformShop).filter(
        PlatformShop.id == body.shop_id, PlatformShop.merchant_id == current.merchant_id
    ).first()
    if not shop:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "店铺不存在"})
    if shop.bind_status == "active":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "已绑定的店铺无法重新生成 token"})
    token = secrets.token_urlsafe(24)
    shop.bind_token = token
    shop.bind_status = "pending"
    db.commit()
    return ok({"bind_token": token}, msg="绑定 token 已重新生成")


@router.post("/confirm-bind")
def confirm_bind(body: ConfirmBindRequest, _: bool = Depends(_verify_key), db: Session = Depends(get_db)):
    """vMall 端调用：用 token 确认绑定。幂等：同一 token 重复调用返回已有数据。"""
    shop = db.query(PlatformShop).filter(PlatformShop.bind_token == body.bind_token).first()
    if not shop:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "无效的绑定 token"})

    if shop.bind_status == "active":
        # 已绑定但可能缺少 access_token，尝试补充
        if not shop.access_token and body.vmall_url:
            token = _fetch_vmall_token(body.vmall_url, shop.merchant_id, shop.id)
            if token:
                shop.access_token = token
                shop.shop_url = body.vmall_url or shop.shop_url
                db.commit()
        return ok({
            "saas_merchant_id": shop.merchant_id,
            "saas_shop_id": shop.id,
            "shop_name": shop.shop_name,
            "registered_at": datetime.now().isoformat(),
            "has_access_token": bool(shop.access_token),
        })

    shop.bind_status = "active"
    shop.shop_url = body.vmall_url or ""
    # 自动获取 vMall OpenAPI access_token，供后续同步使用
    if body.vmall_url:
        token = _fetch_vmall_token(body.vmall_url, shop.merchant_id, shop.id)
        if token:
            shop.access_token = token
    db.commit()

    return ok({
        "saas_merchant_id": shop.merchant_id,
        "saas_shop_id": shop.id,
        "shop_name": shop.shop_name,
        "registered_at": datetime.now().isoformat(),
        "has_access_token": bool(shop.access_token),
    })


@router.post("/unbind-shop")
def unbind_shop(body: UnbindShopRequest, _: bool = Depends(_verify_key), db: Session = Depends(get_db)):
    """vMall 解绑通知 → 重置 SaaS 侧 bind_status。"""
    shop = db.query(PlatformShop).filter(PlatformShop.id == body.shop_id).first()
    if shop and shop.bind_status == "active":
        shop.bind_status = "idle"
        shop.bind_token = None
        db.commit()
    return ok(msg="ok")


@router.post("/register-shop")
def register_shop(body: RegisterShopRequest, _: bool = Depends(_verify_key), db: Session = Depends(get_db)):
    """vMall 商户绑定注册（兼容旧版调用）。创建 SaaS Merchant + PlatformShop，返回 saas_shop_id。"""
    merchant = Merchant(name=body.shop_name, contact=body.contact_phone or "", status=1)
    db.add(merchant)
    db.flush()

    shop = PlatformShop(
        merchant_id=merchant.id,
        platform_type="vmall",
        shop_name=body.shop_name,
        shop_url=body.saas_url or "",
        sync_status="idle",
        is_active=1,
    )
    db.add(shop)
    db.commit()
    db.refresh(shop)

    return ok({
        "saas_merchant_id": merchant.id,
        "saas_shop_id": shop.id,
        "shop_name": body.shop_name,
        "registered_at": datetime.now().isoformat(),
    })
