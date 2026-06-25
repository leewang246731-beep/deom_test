"""运营后台 - 客服消息"""
from datetime import datetime

from fastapi import Header,APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_conversation import VmConversation
from app.models.vm_message import VmMessage

router = APIRouter(prefix="/admin/conversations", tags=["运营-客服"])


def _get_admin(auth: str) -> dict:
    return decode_token(auth.split(" ", 1)[1])


@router.get("")
def list_convs(status: str = Query(None), page_no: int = Query(1, alias="page"),
               page_size: int = Query(20), authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    q = db.query(VmConversation)
    if status: q = q.filter(VmConversation.status == status)
    total = q.count()
    items = q.order_by(VmConversation.last_message_at.desc()).offset(
        (page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": c.id, "buyer_id": c.buyer_id, "status": c.status,
                   "order_id": c.order_id, "product_id": c.product_id,
                   "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
                   "buyer_ip_region": c.buyer_ip_region,
                   "buyer_last_online": c.buyer_last_online.isoformat() if c.buyer_last_online else None}
                  for c in items], total, page_no, page_size)


@router.post("/{conv_id}/messages")
def reply(conv_id: int, body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    payload = _get_admin(authorization)
    c = db.query(VmConversation).get(conv_id)
    if not c:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    msg = VmMessage(conversation_id=conv_id, sender_role="admin",
                    msg_type=body.get("msg_type", "text"),
                    content_json=body.get("content", {"text": body.get("text", "")}))
    db.add(msg)
    c.last_message_at = datetime.now()
    c.admin_id = int(payload["sub"])
    db.commit()
    return ok({"id": msg.id})


@router.get("/{conv_id}/messages")
def get_messages(conv_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_admin(authorization)
    msgs = db.query(VmMessage).filter(VmMessage.conversation_id == conv_id).order_by(
        VmMessage.created_at).all()
    return ok([{"id": m.id, "sender_role": m.sender_role, "msg_type": m.msg_type,
                "content_json": m.content_json,
                "created_at": m.created_at.isoformat() if m.created_at else None} for m in msgs])
