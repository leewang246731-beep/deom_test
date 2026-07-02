"""vMall Webhook 异步分发（带失败日志）"""
import httpx
from sqlalchemy.orm import Session

from app.models.vm_merchant import VmMerchant
from app.models.vm_platform_setting import VmPlatformSetting
from app.models.vm_webhook_log import VmWebhookLog


def _get_webhook_url(db: Session, merchant_id: int = None) -> str:
    """按商户获取 webhook URL，未绑定时回退全局。"""
    if merchant_id:
        m = db.query(VmMerchant).filter(VmMerchant.id == merchant_id).first()
        if m and m.saas_bound and m.saas_url:
            return f"{m.saas_url}/api/v1/webhooks/vmall"
    s = db.query(VmPlatformSetting).first()
    return (s.saas_webhook_url or "") if s else ""


async def dispatch(db_factory, event_type: str, payload: dict):
    """异步推送 Webhook。db_factory 是 SessionLocal。"""
    db = db_factory()
    try:
        url = _get_webhook_url(db, payload.get("_merchant_id"))
        if not url:
            _log(db, event_type, payload, url, "skipped", None, "无 Webhook 地址")
            return
        # 计算签名
        import hmac, hashlib
        from app.core.config import settings
        secret = getattr(settings, "WEBHOOK_SECRET", "vmall-webhook-secret-2026")
        body_str = __import__("json").dumps({"event": event_type, "data": payload}, ensure_ascii=False, default=str)
        signature = hmac.new(secret.encode(), body_str.encode(), hashlib.sha256).hexdigest()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"event": event_type, "data": payload, "timestamp": __import__("datetime").datetime.now().isoformat()},
                headers={"X-Webhook-Source": "vmall", "X-Event-Type": event_type, "X-Webhook-Signature": signature},
                timeout=10,
            )
            if resp.status_code < 400:
                _log(db, event_type, payload, url, "success", resp.status_code, resp.text[:500])
            else:
                _log(db, event_type, payload, url, "failed", resp.status_code, resp.text[:500])
    except Exception as e:
        _log(db, event_type, payload, "", "failed", None, str(e)[:500])
    finally:
        db.close()


def _log(db: Session, event_type: str, payload: dict, url: str, status: str, code, body):
    db.add(VmWebhookLog(
        event_type=event_type, payload=payload, target_url=url,
        status=status, response_code=code, response_body=body,
        error_message=body if status == "failed" else None,
    ))
    db.commit()


def _enrich(db: Session, payload: dict) -> dict:
    """为 payload 补充 shop_name / saas_shop_id，供 SaaS 端精确路由到对应店铺。"""
    mid = payload.get("_merchant_id") or payload.get("merchant_id")
    if mid and (not payload.get("shop_name") or not payload.get("saas_shop_id")):
        m = db.query(VmMerchant).filter(VmMerchant.id == mid).first()
        if m:
            payload = dict(payload)
            payload.setdefault("shop_name", m.shop_name)
            if not payload.get("saas_shop_id"):
                payload["saas_shop_id"] = m.saas_shop_id
    return payload


def dispatch_sync(db: Session, event_type: str, payload: dict):
    """同步推送 + 记日志（用于 sync 端点，避免 async dispatch 未 await 被丢弃）。"""
    payload = _enrich(db, payload)
    url = _get_webhook_url(db, payload.get("_merchant_id") or payload.get("merchant_id"))
    if not url:
        _log(db, event_type, payload, url, "skipped", None, "无 Webhook 地址")
        return False
    try:
        import json as _json
        import urllib.request
        import urllib.error
        import hmac, hashlib
        from datetime import datetime
        from app.core.config import settings
        body = _json.dumps({"event": event_type, "data": payload,
                            "timestamp": datetime.now().isoformat()}).encode("utf-8")
        secret = getattr(settings, "WEBHOOK_SECRET", "vmall-webhook-secret-2026")
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "Content-Type": "application/json",
            "X-Webhook-Source": "vmall", "X-Event-Type": event_type,
            "X-Webhook-Signature": signature})
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            _log(db, event_type, payload, url, "success", resp.status, "")
            return True
        except urllib.error.HTTPError as he:
            _log(db, event_type, payload, url, "failed", he.code, he.read().decode("utf-8", "ignore")[:500])
            return False
    except Exception as e:
        _log(db, event_type, payload, url, "failed", None, str(e)[:500])
        return False
