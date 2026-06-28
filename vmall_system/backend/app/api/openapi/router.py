"""OpenAPI — SaaS 对接接口（REQUIREMENTS §3.6）"""
from datetime import datetime

from fastapi import Header,APIRouter, Depends, HTTPException, Query
from jose import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.response import ok, page
from app.database.session import get_db, SessionLocal
from app.models.vm_after_sale import VmAfterSale
from app.models.vm_conversation import VmConversation
from app.models.vm_logistics import VmLogistics
from app.models.vm_message import VmMessage
from app.models.vm_order import VmOrder
from app.models.vm_order_item import VmOrderItem
from app.models.vm_platform_setting import VmPlatformSetting
from app.models.vm_product import VmProduct
from app.services.webhook import dispatch, dispatch_sync

router = APIRouter(prefix="/openapi", tags=["OpenAPI"])


def _verify_token(authorization: str, db: Session) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "缺少 Token"})
    token = authorization.split(" ", 1)[1]
    s = db.query(VmPlatformSetting).first()
    secret = s.access_token_secret if s else settings.ACCESS_TOKEN_SECRET
    try:
        return jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "Token 无效"})


@router.post("/auth")
def openapi_auth(body: dict, db: Session = Depends(get_db)):
    """SaaS 获取 AccessToken。"""
    merchant_id = body.get("merchant_id")
    shop_id = body.get("shop_id")
    s = db.query(VmPlatformSetting).first()
    secret = s.access_token_secret if s else settings.ACCESS_TOKEN_SECRET
    token = jwt.encode(
        {"merchant_id": merchant_id, "shop_id": shop_id, "type": "openapi",
         "exp": datetime.utcnow().timestamp() + 86400 * 7},
        secret, algorithm=settings.JWT_ALGORITHM,
    )
    return ok({"access_token": token, "expires_in": 86400 * 7, "shop_id": shop_id})


@router.get("/products")
def list_products(page_no: int = Query(1, alias="page"), page_size: int = Query(100),
                  last_sync_time: str = Query(None), authorization: str = Header(None),
                  db: Session = Depends(get_db)):
    _verify_token(authorization, db)
    q = db.query(VmProduct).filter(VmProduct.status == 1)
    if last_sync_time:
        q = q.filter(VmProduct.updated_at >= last_sync_time)
    total = q.count()
    items = q.offset((page_no - 1) * page_size).limit(page_size).all()
    result = []
    for p in items:
        result.append({
            "id": p.id, "title": p.title, "main_image": p.main_image,
            "price_min": float(p.price_min), "price_max": float(p.price_max),
            "category_path": p.category_path, "description": p.description,
            "skus_json": [{"spec": s["spec"], "price": float(s["price"]), "stock": s["stock"],
                            "sku_code": s["sku_code"]} for s in (p.skus_json or [])],
            "total_stock": p.total_stock, "status": p.status,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        })
    return ok({"items": result, "total": total, "page": page_no, "page_size": page_size,
               "has_more": (page_no * page_size) < total})


@router.get("/orders")
def list_orders(status: str = Query(None), start_time: str = Query(None),
                end_time: str = Query(None), page_no: int = Query(1, alias="page"),
                page_size: int = Query(100), authorization: str = Header(None),
                db: Session = Depends(get_db)):
    _verify_token(authorization, db)
    q = db.query(VmOrder)
    if status: q = q.filter(VmOrder.status == status)
    if start_time: q = q.filter(VmOrder.created_at >= start_time)
    if end_time: q = q.filter(VmOrder.created_at <= end_time)
    total = q.count()
    orders = q.order_by(VmOrder.updated_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    result = []
    for o in orders:
        items = db.query(VmOrderItem).filter(VmOrderItem.order_id == o.id).all()
        result.append(_order_for_saas(o, items))
    return ok({"items": result, "total": total, "page": page_no, "page_size": page_size,
               "has_more": (page_no * page_size) < total})


def _order_for_saas(o: VmOrder, items: list) -> dict:
    sku_details = []
    for i in items:
        p = None  # optional: db lookup product title
        sku_details.append({"title": "", "sku_code": i.sku_code, "sku_spec": i.sku_spec,
                             "unit_price": float(i.unit_price), "quantity": i.quantity,
                             "product_id": i.product_id})
    return {
        "id": o.id, "order_no": o.order_no, "buyer_id": o.buyer_id, "buyer_nick": "",
        "total_amount": float(o.total_amount), "discount_amount": float(o.discount_amount or 0),
        "pay_amount": float(o.pay_amount), "status": o.status, "after_sale_status": o.after_sale_status,
        "receiver_name": o.receiver_name, "receiver_phone": o.receiver_phone,
        "receiver_address": o.receiver_address,
        "pay_time": o.pay_time.isoformat() if o.pay_time else None,
        "ship_time": o.ship_time.isoformat() if o.ship_time else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "sku_details": sku_details,
    }


@router.post("/orders/{order_id}/deliver")
def deliver(order_id: int, body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    _verify_token(authorization, db)
    o = db.query(VmOrder).get(order_id)
    if not o:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    if o.status != "paid":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "只能对待发货订单操作"})
    o.status = "shipped"
    o.ship_time = datetime.now()
    log = VmLogistics(order_id=order_id, company=body.get("company", "快递"),
                       tracking_no=body.get("tracking_no", ""), status="picked_up",
                       events_json=[{"time": datetime.now().isoformat(), "status": "已揽收"}])
    db.add(log)
    db.commit()
    dispatch_sync(db, "ORDER_SHIPPED", {"merchant_id": o.merchant_id, "_merchant_id": o.merchant_id, 
        "order_id": o.id, "order_no": o.order_no, "status": "shipped",
        "logistics": {"company": body.get("company", ""), "tracking_no": body.get("tracking_no", "")},
    })
    return ok({"status": "shipped", "logistics": {"id": log.id, "company": log.company,
                "tracking_no": log.tracking_no}})


@router.post("/after-sales/{sale_id}/approve")
def approve_sale(sale_id: int, body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    _verify_token(authorization, db)
    a = db.query(VmAfterSale).get(sale_id)
    if not a:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "售后单不存在"})
    action = body.get("action", "approve")
    if action == "approve":
        a.status = "approved"
        a.reviewed_at = datetime.now()
        a.review_remark = body.get("remark", "")
    elif action == "reject":
        a.status = "rejected"
        a.reviewed_at = datetime.now()
        a.review_remark = body.get("remark", "")
        order = db.query(VmOrder).get(a.order_id)
        if order: order.after_sale_status = None
    db.commit()
    return ok({"id": a.id, "status": a.status})


@router.get("/conversations")
def list_convs(page_no: int = Query(1, alias="page"), page_size: int = Query(100),
               status: str = Query(None), authorization: str = Header(None),
               db: Session = Depends(get_db)):
    _verify_token(authorization, db)
    q = db.query(VmConversation)
    if status: q = q.filter(VmConversation.status == status)
    total = q.count()
    items = q.offset((page_no - 1) * page_size).limit(page_size).all()
    result = []
    for c in items:
        msgs = db.query(VmMessage).filter(VmMessage.conversation_id == c.id).order_by(
            VmMessage.created_at.desc()).limit(20).all()
        messages_json = [{"role": m.sender_role, "content": m.content_json.get("text", ""),
                           "time": m.created_at.isoformat() if m.created_at else None} for m in reversed(msgs)]
        result.append({
            "id": c.id, "buyer_id": c.buyer_id, "buyer_nick": f"买家#{c.buyer_id}",
            "product_id": c.product_id, "order_id": c.order_id, "status": c.status,
            "messages_json": messages_json,
            "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
        })
    return ok({"items": result, "total": total, "page": page_no, "page_size": page_size,
               "has_more": (page_no * page_size) < total})


@router.post("/messages")
def send_message(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    _verify_token(authorization, db)
    conv_id = body.get("conversation_id")
    c = db.query(VmConversation).get(conv_id)
    if not c:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    msg = VmMessage(conversation_id=conv_id, sender_role="admin",
                    msg_type=body.get("msg_type", "text"),
                    content_json=body.get("content", {"text": body.get("text", "")}))
    db.add(msg)
    c.last_message_at = datetime.now()
    db.commit()
    return ok({"id": msg.id})
