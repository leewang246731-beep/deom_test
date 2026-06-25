"""商户 - SaaS 绑定管理"""
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_merchant import VmMerchant
from app.models.vm_platform_setting import VmPlatformSetting

router = APIRouter(prefix="/merchant/binding", tags=["商户-绑定"])

SAAS_OPENAPI_KEY = "vmall-openapi-secret-2026"


def _get_merchant(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "merchant":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需商户登录"})
    return payload


@router.get("/status")
def binding_status(authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    u = db.query(VmMerchant).get(int(merchant["sub"]))
    return ok({
        "bound": u.saas_bound,
        "saas_url": u.saas_url,
        "saas_shop_id": u.saas_shop_id,
        "saas_shop_name": u.shop_name,
        "saas_bind_time": u.saas_bind_time.isoformat() if u.saas_bind_time else None,
        "bind_status": "active" if u.saas_bound else "idle",
    })


@router.post("/confirm")
def confirm_binding(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    """vMall 商户输入 bind_token 确认绑定 → 调用 SaaS /openapi/confirm-bind。"""
    merchant = _get_merchant(authorization)
    u = db.query(VmMerchant).get(int(merchant["sub"]))
    if u.saas_bound:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "已绑定，请先解绑"})

    bind_token = body.get("bind_token", "").strip()
    saas_url = body.get("saas_url", "").strip().rstrip("/")
    if not bind_token or not saas_url:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "请提供 bind_token 和 saas_url"})

    # 调用 SaaS OpenAPI 确认绑定
    try:
        import requests as _r
        resp = _r.post(
            f"{saas_url}/api/v1/openapi/confirm-bind",
            json={"bind_token": bind_token, "vmall_url": f"http://127.0.0.1:8020"},
            headers={"X-API-Key": SAAS_OPENAPI_KEY},
            timeout=10,
        )
        if resp.status_code >= 400:
            detail = resp.json().get("detail", {})
            raise HTTPException(status_code=400, detail={"code": 40002, "msg": detail.get("msg", "绑定验证失败")})
        data = resp.json().get("data", {})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": 50001, "msg": f"连接 SaaS 失败: {e}"})

    saas_shop_id = data.get("saas_shop_id")
    u.saas_bound = True
    u.saas_shop_id = saas_shop_id
    u.saas_url = saas_url
    u.saas_bind_time = datetime.now()
    db.commit()

    # 更新全局 webhook URL（如果尚未设置）
    setting = db.query(VmPlatformSetting).first()
    if setting and not setting.saas_webhook_url:
        setting.saas_webhook_url = f"{saas_url}/api/v1/webhooks/vmall"
        db.commit()

    return ok({
        "shop_id": saas_shop_id,
        "bound": True,
        "shop_name": u.shop_name,
    }, msg="绑定成功")


@router.delete("")
def unbind(authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    u = db.query(VmMerchant).get(int(merchant["sub"]))
    if not u.saas_bound:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "尚未绑定"})

    saas_shop_id = u.saas_shop_id
    saas_url = u.saas_url

    # 通知 SaaS 重置绑定状态
    if saas_url and saas_shop_id:
        try:
            import requests as _r
            _r.post(
                f"{saas_url}/api/v1/openapi/unbind-shop",
                json={"shop_id": saas_shop_id},
                headers={"X-API-Key": SAAS_OPENAPI_KEY},
                timeout=5,
            )
        except Exception:
            pass  # 尽力通知

    u.saas_bound = False
    u.saas_shop_id = None
    u.saas_url = None
    u.saas_bind_time = None
    db.commit()
    return ok(msg="解绑成功")
