"""消费者端 - 会话"""
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db, SessionLocal
from app.models.vm_buyer import VmBuyer
from app.models.vm_conversation import VmConversation
from app.models.vm_merchant import VmMerchant
from app.models.vm_message import VmMessage
from app.models.vm_product import VmProduct
from app.services.webhook import dispatch, dispatch_sync

router = APIRouter(prefix="/consumer/conversations", tags=["消费者-会话"])
INTERNAL_KEY = "vmall-internal-demo-key"


def _get_buyer(auth: str) -> int:
    payload = decode_token(auth.split(" ", 1)[1])
    return int(payload["sub"])


def _merchant_info(db: Session, conv_id: int) -> dict:
    """返回会话对应的 {merchant_id, saas_shop_id, saas_url}。"""
    c = db.query(VmConversation).filter(VmConversation.id == conv_id).first()
    if not c or not c.merchant_id:
        return {}
    m = db.query(VmMerchant).filter(VmMerchant.id == c.merchant_id).first()
    if not m or not m.saas_bound:
        return {"merchant_id": c.merchant_id}
    return {"merchant_id": c.merchant_id, "saas_shop_id": m.saas_shop_id, "saas_url": m.saas_url}


@router.post("")
def create_conv(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    # 根据 product_id 推断 merchant_id
    merchant_id = 1
    pid = body.get("product_id")
    if pid:
        p = db.query(VmProduct).filter(VmProduct.id == pid).first()
        if p:
            merchant_id = p.merchant_id

    # 同 buyer + 同 product 的未关闭会话复用，避免重复创建
    if pid:
        existing = db.query(VmConversation).filter(
            VmConversation.buyer_id == buyer_id,
            VmConversation.product_id == pid,
            VmConversation.merchant_id == merchant_id,
            VmConversation.status == "open",
        ).order_by(VmConversation.last_message_at.desc()).first()
        if existing:
            existing.buyer_last_online = datetime.now()
            db.commit()
            return ok({"id": existing.id, "reused": True})

    # 同 buyer + 同 order 的会话也复用
    oid = body.get("order_id")
    if oid:
        existing = db.query(VmConversation).filter(
            VmConversation.buyer_id == buyer_id,
            VmConversation.order_id == oid,
            VmConversation.status == "open",
        ).order_by(VmConversation.last_message_at.desc()).first()
        if existing:
            existing.buyer_last_online = datetime.now()
            db.commit()
            return ok({"id": existing.id, "reused": True})

    c = VmConversation(buyer_id=buyer_id, merchant_id=merchant_id,
                        product_id=pid, order_id=body.get("order_id"),
                        buyer_ip_region=body.get("ip_region", "江苏·南京"),
                        buyer_last_online=datetime.now())
    db.add(c); db.commit()
    return ok({"id": c.id})


@router.post("/{conv_id}/messages/internal")
def receive_saas_reply(conv_id: int, body: dict, db: Session = Depends(get_db)):
    """SaaS 客服回复 → vMall VmMessage（内部服务调用，双向桥接：回程）"""
    if body.get("api_key") != INTERNAL_KEY:
        raise HTTPException(status_code=403, detail={"code": 40300, "msg": "无权访问"})
    c = db.query(VmConversation).filter(VmConversation.id == conv_id).first()
    if not c:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    content_json = {"text": body.get("content", "")}
    if body.get("card"):
        content_json["card"] = body["card"]
    msg = VmMessage(conversation_id=conv_id, sender_role="admin",
                    msg_type=body.get("msg_type", "text"),
                    content_json=content_json)
    db.add(msg)
    c.last_message_at = datetime.now()
    db.commit()
    return ok({"id": msg.id})


@router.post("/{conv_id}/messages")
def send_message(conv_id: int, body: dict, authorization: str = Header(None),
                 db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    c = db.query(VmConversation).filter(VmConversation.id == conv_id,
                                         VmConversation.buyer_id == buyer_id).first()
    if not c: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    msg = VmMessage(conversation_id=conv_id, sender_role="buyer",
                    msg_type=body.get("msg_type", "text"),
                    content_json=body.get("content", {"text": body.get("text", "")}))
    db.add(msg); c.last_message_at = datetime.now(); c.buyer_last_online = datetime.now(); db.commit()

    buyer = db.query(VmBuyer).filter(VmBuyer.id == buyer_id).first()
    mi = _merchant_info(db, conv_id)
    _content = body.get("content", {"text": body.get("text", "")})
    dispatch_sync(db, "NEW_MESSAGE", {
        "conversation_id": conv_id, "sender_role": "buyer",
        "content": _content,
        "card": _content.get("card") if isinstance(_content, dict) else None,
        "msg_type": body.get("msg_type", "text"),
        "buyer_nick": buyer.nickname if buyer else f"买家{buyer_id}",
        "buyer_id": buyer_id,
        "product_id": c.product_id,
        "merchant_id": c.merchant_id,
        "saas_shop_id": mi.get("saas_shop_id"),
        "_merchant_id": c.merchant_id,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    })
    return ok({"id": msg.id})


@router.get("/{conv_id}")
def get_conversation(conv_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    """获取会话详情（含商品信息，用于聊天窗口展示商品卡片）。"""
    buyer_id = _get_buyer(authorization)
    c = db.query(VmConversation).filter(
        VmConversation.id == conv_id, VmConversation.buyer_id == buyer_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    product_info = None
    if c.product_id:
        p = db.query(VmProduct).filter(VmProduct.id == c.product_id).first()
        if p:
            product_info = {
                "id": p.id, "title": p.title, "price": float(p.price_min),
                "image": p.main_image, "stock": p.total_stock,
            }
    return ok({
        "id": c.id, "merchant_id": c.merchant_id,
        "product_id": c.product_id, "product": product_info,
        "order_id": c.order_id, "status": c.status,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    })


@router.get("/{conv_id}/messages")
def get_messages(conv_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    c = db.query(VmConversation).filter(VmConversation.id == conv_id,
                                         VmConversation.buyer_id == buyer_id).first()
    if not c: raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    msgs = db.query(VmMessage).filter(VmMessage.conversation_id == conv_id).order_by(VmMessage.created_at).all()
    return ok([{"id": m.id, "sender_role": m.sender_role, "msg_type": m.msg_type,
                "content_json": m.content_json,
                "created_at": m.created_at.isoformat() if m.created_at else None} for m in msgs])
