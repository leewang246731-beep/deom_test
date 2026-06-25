"""商户 - 客服会话"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db
from app.models.vm_conversation import VmConversation
from app.models.vm_message import VmMessage

router = APIRouter(prefix="/merchant/conversations", tags=["商户-会话"])


def _get_merchant(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload or payload.get("type") != "merchant":
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "需商户登录"})
    return payload


def _msg_content(m):
    """content_json may be dict or text; normalise to string."""
    cj = m.content_json
    if isinstance(cj, dict):
        return cj.get("text", str(cj))
    return str(cj) if cj else ""


@router.get("")
def list_convs(status: str = Query(None), authorization: str = Header(None), db: Session = Depends(get_db)):
    merchant = _get_merchant(authorization)
    mid = int(merchant["sub"])
    q = db.query(VmConversation).filter(VmConversation.merchant_id == mid)
    if status: q = q.filter(VmConversation.status == status)
    convs = q.order_by(VmConversation.created_at.desc()).all()
    return ok([{"id": c.id, "user_name": f"买家-{c.buyer_id}", "status": c.status,
                "last_message": None, "updated_at": c.created_at.isoformat() if c.created_at else None}
               for c in convs])


@router.get("/{conv_id}/messages")
def get_messages(conv_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_merchant(authorization)
    msgs = db.query(VmMessage).filter(VmMessage.conversation_id == conv_id).order_by(VmMessage.created_at.asc()).all()
    return ok([{"id": m.id, "sender": m.sender_role, "content": _msg_content(m),
                "created_at": m.created_at.isoformat() if m.created_at else None} for m in msgs])


@router.post("/{conv_id}/messages")
def send_msg(conv_id: int, body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_merchant(authorization)
    m = VmMessage(conversation_id=conv_id, sender_role=body.get("sender", "merchant"),
                  content_json={"text": body["content"]})
    db.add(m); db.commit()
    return ok({"id": m.id}, msg="发送成功")
