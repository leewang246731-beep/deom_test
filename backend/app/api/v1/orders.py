"""
订单中心接口（PHASE1-PLAN 4.4 / api.md 3.4）
列表/筛选/详情走 DB；售后用 Redis 分布式锁防并发；催单委托步骤6 AI Pipeline。
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_user, get_effective_merchant_id, require_roles
from app.core.config import settings
from app.core.redis_client import get_redis, mkey
from app.core.response import ok, page
from app.database.session import get_db
from app.models.external_order import ExternalOrder
from app.models.platform_shop import PlatformShop
from app.schemas import AICampaignRequest

router = APIRouter(prefix="/orders", tags=["订单中心"])


def _merchant_shop_ids(db: Session, merchant_id: int | None) -> list:
    q = db.query(PlatformShop.id)
    if merchant_id is not None:
        q = q.filter(PlatformShop.merchant_id == merchant_id)
    return [r[0] for r in q.all()]


def _order_dict(o: ExternalOrder) -> dict:
    return {
        "id": o.id, "shop_id": o.shop_id, "platform_order_id": o.platform_order_id,
        "buyer_nick": o.buyer_nick, "total_amount": float(o.total_amount),
        "pay_amount": float(o.pay_amount), "status": o.status,
        "sku_details_json": o.sku_details_json,
        "receiver_name": o.receiver_name, "receiver_phone": o.receiver_phone,
        "receiver_address": o.receiver_address,
        "pay_time": o.pay_time.isoformat() if o.pay_time else None,
        "ship_time": o.ship_time.isoformat() if o.ship_time else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


@router.get("")
def list_orders(
    shop_id: int = Query(None),
    status: str = Query(None),
    page_no: int = Query(1, alias="page", ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current: CurrentUser = Depends(get_current_user),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    shop_ids = _merchant_shop_ids(db, mid)
    if not shop_ids and mid is not None:
        return page([], 0, page_no, page_size)
    q = db.query(ExternalOrder).filter(ExternalOrder.shop_id.in_(shop_ids))
    if shop_id:
        q = q.filter(ExternalOrder.shop_id == shop_id)
    if status:
        q = q.filter(ExternalOrder.status == status)
    total = q.count()
    items = q.order_by(ExternalOrder.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([_order_dict(o) for o in items], total, page_no, page_size)


@router.get("/pending-payment")
def pending_payment(
    current: CurrentUser = Depends(get_current_user),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db)):
    shop_ids = _merchant_shop_ids(db, mid)
    items = db.query(ExternalOrder).filter(
        ExternalOrder.shop_id.in_(shop_ids) if shop_ids else True,
        ExternalOrder.status == "pending",
    ).all()
    return ok([_order_dict(o) for o in items])


@router.post("/pending-payment/remind")
def remind_pending(
    body: AICampaignRequest,
    current: CurrentUser = Depends(get_current_user),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    """批量催单：AI 生成话术 → 冷却检查 → 落库 → real+vmall 外发。"""
    from app.services.ai_suggest import generate_payment_reminders
    from app.core.platform_connector.vmall import V3Connector
    from app.core.platform_connector.runner import run_connector
    from app.models.order_reminder import OrderReminder
    from datetime import datetime

    r = get_redis()
    limit = min(body.limit or 20, 50)
    reminders_data = generate_payment_reminders(mid, body.shop_id, db, limit=limit, offset=body.offset or 0)
    reminders = reminders_data.get("reminders", [])

    sent_count = 0
    skipped_count = 0
    enriched = []

    for rem in reminders:
        order_id = rem.get("order_id")
        buyer_openid = rem.get("buyer_openid", "")
        content = rem.get("script", "")

        # 冷却检查
        cooldown_key = mkey(mid, "remind", str(order_id))
        if r.exists(cooldown_key):
            skipped_count += 1
            rem["skipped"] = True
            enriched.append(rem)
            continue

        # 落库发送记录
        db.add(OrderReminder(
            merchant_id=mid, shop_id=body.shop_id, order_id=order_id,
            buyer_openid=str(buyer_openid), content=content, channel="vmall",
            sent_at=datetime.now(),
        ))

        # real 模式 + vmall → 外发通知
        if settings.PLATFORM_MODE == "real":
            shop = db.query(PlatformShop).filter(PlatformShop.id == body.shop_id).first()
            if shop and shop.platform_type == "vmall" and shop.access_token:
                connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
                ok, _, err = run_connector(
                    connector.send_notification(int(buyer_openid) if buyer_openid else 0, order_id, content)
                )
                if not ok:
                    rem["send_error"] = err
            else:
                rem["send_error"] = "not vmall or no token"
        else:
            rem["channel"] = "local"

        # 设冷却
        r.set(cooldown_key, "1", ex=settings.REMINDER_COOLDOWN_SECONDS)
        sent_count += 1
        rem["skipped"] = False
        enriched.append(rem)

    db.commit()

    return ok({
        "reminders": enriched,
        "sent_count": sent_count,
        "skipped_count": skipped_count,
        "total_pending": reminders_data.get("total_pending", 0),
        "has_more": len(reminders) >= limit,
    })


@router.get("/export")
def export_orders(
    shop_id: int = Query(None), status: str = Query(None),
    current: CurrentUser = Depends(get_current_user),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    shop_ids = _merchant_shop_ids(db, mid)
    q = db.query(ExternalOrder).filter(ExternalOrder.shop_id.in_(shop_ids)) if shop_ids else db.query(ExternalOrder)
    if shop_id: q = q.filter(ExternalOrder.shop_id == shop_id)
    if status: q = q.filter(ExternalOrder.status == status)
    rows = q.order_by(ExternalOrder.created_at.desc()).all()
    out = io.StringIO()
    out.write('﻿')
    w = csv.writer(out)
    w.writerow(["ID", "平台订单号", "买家", "金额", "实付", "状态", "收货人", "电话", "地址", "下单时间"])
    for o in rows:
        w.writerow([o.id, o.platform_order_id, o.buyer_nick, float(o.total_amount), float(o.pay_amount),
                     o.status, o.receiver_name or "", o.receiver_phone or "", o.receiver_address or "",
                     o.created_at.isoformat() if o.created_at else ""])
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=orders.csv"})


@router.get("/{order_id}")
def order_detail(
    order_id: int,
    current: CurrentUser = Depends(get_current_user),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db)):
    shop_ids = _merchant_shop_ids(db, mid)
    o = db.query(ExternalOrder).filter(
        ExternalOrder.id == order_id,
        ExternalOrder.shop_id.in_(shop_ids) if shop_ids else True,
    ).first()
    if not o:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    return ok(_order_dict(o))


@router.post("/{order_id}/refund")
def refund_order(
    order_id: int,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    """售后：Redis 锁防并发；real+vmall 联动审批售后；mock/非vmall 本地标记。"""
    shop_ids = _merchant_shop_ids(db, mid)
    o = db.query(ExternalOrder).filter(
        ExternalOrder.id == order_id,
        ExternalOrder.shop_id.in_(shop_ids) if shop_ids else False,
    ).first()
    if not o:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})

    r = get_redis()
    lock_key = mkey(mid, "lock", f"refund_{order_id}")
    if not r.set(lock_key, "1", nx=True, ex=30):
        raise HTTPException(status_code=409, detail={"code": 40901, "msg": "售后处理中，请勿重复提交"})
    try:
        if o.status in ("refunded", "refunding"):
            raise HTTPException(status_code=409, detail={"code": 40901, "msg": "订单已在售后流程"})
        if o.status not in ("paid", "refunding"):
            raise HTTPException(status_code=400, detail={"code": 40001, "msg": "当前订单状态不允许售后"})

        before_status = o.status
        vmall_notified = False

        # real 模式 + vmall 店铺 + 有 after_sale_id → 联动 vmall 审批
        shop = db.query(PlatformShop).filter(PlatformShop.id == o.shop_id).first()
        if (settings.PLATFORM_MODE == "real" and shop and shop.platform_type == "vmall"
                and shop.access_token and o.after_sale_id):
            from app.core.platform_connector.vmall import V3Connector
            from app.core.platform_connector.runner import run_connector
            connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
            success, data, err = run_connector(
                connector.approve_after_sale(o.after_sale_id, "approve", "SaaS平台审核通过")
            )
            if success:
                o.status = "refunded"
                o.after_sale_status = "approved"
                vmall_notified = True
            else:
                # vmall 联动失败：订单保持 refunding，记录审计后返回错误
                _write_audit(db, mid, current.user_id, current.username, "order",
                             order_id, before_status, "refunding",
                             f"vmall_approve_failed: {err}")
                db.commit()  # 持久化审计日志（订单状态未变）
                raise HTTPException(
                    status_code=502,
                    detail={"code": 50201, "msg": f"vMall 售后审批失败，已挂起: {err}"},
                )
        else:
            o.status = "refunded"

        _write_audit(db, mid, current.user_id, current.username, "order",
                     order_id, before_status, o.status,
                     f"vmall_notified={vmall_notified}")
        db.commit()

        return ok({"id": o.id, "status": o.status, "vmall_notified": vmall_notified}, msg="售后成功")
    finally:
        r.delete(lock_key)


def _write_audit(db, merchant_id, user_id, username, target_type, target_id, before_val, after_val, extra):
    from app.models.audit_log import AuditLog
    import json
    db.add(AuditLog(
        merchant_id=merchant_id, user_id=user_id, username=username,
        action="status_change", target_type=target_type, target_id=target_id,
        detail_json=json.dumps({"before": before_val, "after": after_val, "extra": extra}, ensure_ascii=False),
        ip="",
    ))
