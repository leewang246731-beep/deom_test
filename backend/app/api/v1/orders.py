"""
订单中心接口（PHASE1-PLAN 4.4 / api.md 3.4）
列表/筛选/详情走 DB；售后用 Redis 分布式锁防并发；催单委托步骤6 AI Pipeline。
"""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant, get_current_user, require_roles
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
    page_no: int = Query(1, alias="page"),
    page_size: int = Query(20),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    shop_ids = _merchant_shop_ids(db, current.merchant_id)
    if not shop_ids and current.merchant_id is not None:
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
def pending_payment(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    shop_ids = _merchant_shop_ids(db, current.merchant_id)
    items = db.query(ExternalOrder).filter(
        ExternalOrder.shop_id.in_(shop_ids) if shop_ids else True,
        ExternalOrder.status == "pending",
    ).all()
    return ok([_order_dict(o) for o in items])


@router.post("/pending-payment/remind")
def remind_pending(
    body: AICampaignRequest,
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """批量催单：支持分页（缺口4），limit 不超过 .env CAMPAIGN_MAX_PER_REQUEST。"""
    try:
        from app.services.ai_suggest import generate_payment_reminders
        limit = min(body.limit or 20, 50)
        result = generate_payment_reminders(current.merchant_id, body.shop_id, db, limit=limit, offset=body.offset or 0)
        return ok(result)
    except Exception as e:
        return ok({"reminders": [], "count": 0, "total_pending": 0, "has_more": False, "note": f"AI 催单待步骤6 接入: {e}"})


@router.get("/export")
def export_orders(
    shop_id: int = Query(None), status: str = Query(None),
    current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db),
):
    shop_ids = _merchant_shop_ids(db, current.merchant_id)
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
def order_detail(order_id: int, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    shop_ids = _merchant_shop_ids(db, current.merchant_id)
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
    db: Session = Depends(get_db),
):
    """售后：Redis 分布式锁防并发，Mock 模式直接标记 refunded。"""
    shop_ids = _merchant_shop_ids(db, current.merchant_id)
    o = db.query(ExternalOrder).filter(
        ExternalOrder.id == order_id,
        ExternalOrder.shop_id.in_(shop_ids) if shop_ids else False,
    ).first()
    if not o:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})

    r = get_redis()
    lock_key = mkey(current.merchant_id, "lock", f"refund_{order_id}")
    if not r.set(lock_key, "1", nx=True, ex=30):
        raise HTTPException(status_code=409, detail={"code": 40901, "msg": "售后处理中，请勿重复提交"})
    try:
        if o.status in ("refunded", "refunding"):
            raise HTTPException(status_code=409, detail={"code": 40901, "msg": "订单已在售后流程"})
        o.status = "refunded"
        db.commit()

        # C5 跨系统联动：vMall 订单同步通知 vMall 售后审批
        vmall_result = None
        try:
            shop = db.query(PlatformShop).filter(PlatformShop.id == o.shop_id).first()
            if shop and shop.platform_type == "vmall" and shop.access_token:
                from app.core.platform_connector.vmall import V3Connector
                connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
                # 尝试查找对应的售后单并审批
                sale_id = o.platform_order_id  # vMall 订单号可关联售后
                vmall_result = connector.approve_after_sale(sale_id, "approve", "SaaS平台审核通过")
        except Exception:
            pass  # vMall 通知非关键路径

        return ok({"id": o.id, "status": o.status, "vmall_notified": vmall_result is not None}, msg="售后成功")
    finally:
        r.delete(lock_key)
