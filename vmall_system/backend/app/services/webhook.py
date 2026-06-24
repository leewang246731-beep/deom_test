"""vMall Webhook 异步分发（带失败日志）"""
import httpx
from sqlalchemy.orm import Session

from app.models.vm_platform_setting import VmPlatformSetting
from app.models.vm_webhook_log import VmWebhookLog


def _get_webhook_url(db: Session) -> str:
    s = db.query(VmPlatformSetting).first()
    return (s.saas_webhook_url or "") if s else ""


async def dispatch(db_factory, event_type: str, payload: dict):
    """异步推送 Webhook。db_factory 是 SessionLocal。"""
    db = db_factory()
    try:
        url = _get_webhook_url(db)
        if not url:
            _log(db, event_type, payload, url, "skipped", None, "无 Webhook 地址")
            return
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"event": event_type, "data": payload, "timestamp": __import__("datetime").datetime.now().isoformat()},
                headers={"X-Webhook-Source": "vmall", "X-Event-Type": event_type},
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


def dispatch_sync(db: Session, event_type: str, payload: dict):
    """同步推送 + 记日志（用于需要即时确认的场景）。"""
    url = _get_webhook_url(db)
    if not url:
        _log(db, event_type, payload, url, "skipped", None, "无 Webhook 地址")
        return False
    try:
        import requests
        r = requests.post(
            url,
            json={"event": event_type, "data": payload, "timestamp": __import__("datetime").datetime.now().isoformat()},
            headers={"X-Webhook-Source": "vmall", "X-Event-Type": event_type},
            timeout=10,
        )
        if r.status_code < 400:
            _log(db, event_type, payload, url, "success", r.status_code, "")
            return True
        else:
            _log(db, event_type, payload, url, "failed", r.status_code, r.text[:500])
            return False
    except Exception as e:
        _log(db, event_type, payload, url, "failed", None, str(e)[:500])
        return False
