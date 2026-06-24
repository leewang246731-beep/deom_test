"""消费者端 - 会话"""
from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db, SessionLocal
from app.models.vm_conversation import VmConversation
from app.models.vm_message import VmMessage
from app.services.webhook import dispatch

router = APIRouter(prefix="/consumer/conversations", tags=["消费者-会话"])


def _get_buyer(auth: str) -> int:
    payload = decode_token(auth.split(" ", 1)[1])
    return int(payload["sub"])


@router.post("")
def create_conv(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    buyer_id = _get_buyer(authorization)
    c = VmConversation(buyer_id=buyer_id, product_id=body.get("product_id"),
                        order_id=body.get("order_id"),
                        buyer_ip_region=body.get("ip_region", "江苏·南京"),
                        buyer_last_online=datetime.now())
    db.add(c); db.commit()
    return ok({"id": c.id})


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
    dispatch(SessionLocal, "NEW_MESSAGE", {"conversation_id": conv_id, "sender_role": "buyer",
                                            "content": body.get("content", {}),
                                            "msg_type": body.get("msg_type", "text")})
    return ok({"id": msg.id})


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
