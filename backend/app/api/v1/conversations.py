"""
客服工作台接口（PHASE1-PLAN 4.5 / api.md 3.5）
会话列表/详情/分配/关闭走 DB；WebSocket /ws/service 实时推送。
"""
import asyncio
import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_user, get_effective_merchant_id
from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import SessionLocal, get_db
from app.models.conversation import Conversation
from app.models.platform_shop import PlatformShop
from app.schemas import ConversationMessageSend

router = APIRouter(tags=["客服工作台"])
ws_router = APIRouter(tags=["客服工作台-WS"])  # 无 /api/v1 前缀，挂根路径

# ===== WebSocket 连接池 (广播 new_conversation / new_message) =====
_ws_clients: dict[int, set] = {}  # merchant_id → {WebSocket, ...}


def _register_ws(merchant_id: int, ws: WebSocket):
    _ws_clients.setdefault(merchant_id, set()).add(ws)


def _unregister_ws(merchant_id: int, ws: WebSocket):
    clients = _ws_clients.get(merchant_id)
    if clients:
        clients.discard(ws)
        if not clients:
            del _ws_clients[merchant_id]


async def broadcast_service_event(merchant_id: int, event_type: str, data: dict | None = None):
    """向指定商户的所有 WebSocket 客户端广播事件（非关键路径，异常静默）。"""
    clients = _ws_clients.get(merchant_id, set())
    dead = []
    for ws in clients:
        try:
            await ws.send_json({"type": event_type, "data": data or {}})
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


def _merchant_shop_ids(db: Session, merchant_id: int | None) -> list:
    q = db.query(PlatformShop.id)
    if merchant_id is not None:
        q = q.filter(PlatformShop.merchant_id == merchant_id)
    return [r[0] for r in q.all()]


def _conv_brief(c: Conversation) -> dict:
    msgs = c.messages_json or []
    preview = msgs[-1]["content"] if msgs else ""
    return {
        "id": c.id, "shop_id": c.shop_id, "buyer_nick": c.buyer_nick,
        "product_id": c.product_id,
        "status": c.handled_status, "handled_status": c.handled_status,
        "assigned_to": c.assigned_to, "preview": preview,
        "current_mode": c.current_mode,
        "auto_reply_count": c.auto_reply_count or 0,
        "last_message_at": c.last_message_at.isoformat() if c.last_message_at else None,
    }


@router.get("/conversations")
def list_conversations(
    shop_id: int = Query(None),
    handled_status: str = Query(None),
    page_no: int = Query(1, alias="page", ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current: CurrentUser = Depends(get_current_user),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    shop_ids = _merchant_shop_ids(db, mid)
    if not shop_ids and mid is not None:
        return page([], 0, page_no, page_size)
    q = db.query(Conversation).filter(Conversation.shop_id.in_(shop_ids))
    if shop_id:
        q = q.filter(Conversation.shop_id == shop_id)
    if handled_status:
        q = q.filter(Conversation.handled_status == handled_status)
    total = q.count()
    items = q.order_by(Conversation.last_message_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([_conv_brief(c) for c in items], total, page_no, page_size)


@router.get("/conversations/export")
def export_conversations(
    shop_id: int = Query(None), handled_status: str = Query(None),
    current: CurrentUser = Depends(get_current_user),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    shop_ids = _merchant_shop_ids(db, mid)
    q = db.query(Conversation).filter(Conversation.shop_id.in_(shop_ids)) if shop_ids else db.query(Conversation).filter(False)
    if shop_id: q = q.filter(Conversation.shop_id == shop_id)
    if handled_status: q = q.filter(Conversation.handled_status == handled_status)
    rows = q.order_by(Conversation.last_message_at.desc()).all()
    out = io.StringIO()
    out.write('﻿')
    w = csv.writer(out)
    w.writerow(["ID", "买家", "商品ID", "状态", "处理人", "模式", "自动回复数", "最近消息时间"])
    for c in rows:
        w.writerow([c.id, c.buyer_nick, c.product_id or "", c.handled_status, c.assigned_to or "",
                     c.current_mode or "", c.auto_reply_count or 0,
                     c.last_message_at.isoformat() if c.last_message_at else ""])
    out.seek(0)
    return StreamingResponse(iter([out.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=conversations.csv"})


@router.get("/conversations/{conv_id}")
def conversation_detail(conv_id: int, current: CurrentUser = Depends(get_current_user), mid: int = Depends(get_effective_merchant_id), db: Session = Depends(get_db)):
    shop_ids = _merchant_shop_ids(db, mid)
    c = db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.shop_id.in_(shop_ids) if shop_ids else True,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    return ok({
        "id": c.id, "shop_id": c.shop_id, "buyer_nick": c.buyer_nick,
        "product_id": c.product_id, "messages_json": c.messages_json,
        "ai_suggest_reply": c.ai_suggest_reply,
        "status": c.handled_status, "handled_status": c.handled_status,
        "current_mode": c.current_mode, "auto_reply_count": c.auto_reply_count,
        "assigned_to": c.assigned_to,
    })


@router.post("/conversations/{conv_id}/assign")
def assign_conversation(conv_id: int, current: CurrentUser = Depends(get_current_user), mid: int = Depends(get_effective_merchant_id), db: Session = Depends(get_db)):
    shop_ids = _merchant_shop_ids(db, mid)
    c = db.query(Conversation).filter(
        Conversation.id == conv_id, Conversation.shop_id.in_(shop_ids) if shop_ids else False
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    c.assigned_to = current.user_id
    db.commit()
    return ok({"id": c.id, "assigned_to": c.assigned_to})


@router.post("/conversations/{conv_id}/messages")
def send_conversation_message(conv_id: int, body: ConversationMessageSend, current: CurrentUser = Depends(get_current_user), mid: int = Depends(get_effective_merchant_id), db: Session = Depends(get_db)):
    """客服发送消息 → 追加到 SaaS Conversation + 同步回 vMall（双向桥接：去程）"""
    shop_ids = _merchant_shop_ids(db, mid)
    c = db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.shop_id.in_(shop_ids) if shop_ids else False,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    content = body.content
    now = datetime.now()
    msgs = list(c.messages_json or [])
    msgs.append({"role": "service", "content": content, "time": now.strftime("%Y-%m-%d %H:%M:%S")})
    c.messages_json = msgs
    c.last_message_at = now
    c.handled_status = "replied"
    c.last_human_at = now
    db.commit()

    vmall_conv_id = c.platform_conversation_id or ""
    if vmall_conv_id.startswith("vmall_"):
        vmall_conv_id = vmall_conv_id[len("vmall_"):]
    if vmall_conv_id and vmall_conv_id.isdigit():
        vmall_url = None
        try:
            shop = db.query(PlatformShop).filter(PlatformShop.id == c.shop_id).first()
            vmall_url = shop.shop_url if shop and shop.shop_url else None
        except Exception:
            pass
        if not vmall_url:
            vmall_url = "http://127.0.0.1:8020"
        target = f"{vmall_url}/api/v1/consumer/conversations/{vmall_conv_id}/messages/internal"
        try:
            import requests as _r
            _r.post(
                target,
                json={"api_key": "vmall-internal-demo-key", "content": content, "msg_type": "text"},
                timeout=5,
            )
        except Exception:
            pass
    return ok({"id": c.id, "messages_json": [{"role": m["role"], "content": m["content"], "time": m.get("time", "")} for m in msgs]})


@router.post("/conversations/{conv_id}/close")
def close_conversation(conv_id: int, current: CurrentUser = Depends(get_current_user), mid: int = Depends(get_effective_merchant_id), db: Session = Depends(get_db)):
    shop_ids = _merchant_shop_ids(db, mid)
    c = db.query(Conversation).filter(
        Conversation.id == conv_id, Conversation.shop_id.in_(shop_ids) if shop_ids else False
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    c.handled_status = "closed"
    db.commit()
    return ok({"id": c.id, "handled_status": c.handled_status})


@ws_router.websocket("/ws/service")
async def ws_service(websocket: WebSocket, token: str = Query(...)):
    """
    客服工作台实时通道。
    - 鉴权：query token → JWT 校验
    - 客户端发 {"type":"ai_suggest","conversation_id":..,"question":..} → 返回 AI 建议
    - 服务端可推送 new_conversation / new_message（一期演示：心跳 + 按需响应）
    """
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4401)
        return
    merchant_id = payload.get("merchant_id")
    await websocket.accept()
    _register_ws(merchant_id, websocket)
    await websocket.send_json({"type": "connected", "merchant_id": merchant_id})
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await websocket.send_json({"type": "error", "msg": "非法 JSON"})
                continue

            if msg.get("type") == "ai_suggest":
                suggestions = await _ws_ai_suggest(merchant_id, msg)
                await websocket.send_json({
                    "type": "ai_suggest",
                    "conversation_id": msg.get("conversation_id"),
                    "suggestions": suggestions,
                })
            elif msg.get("type") == "set_mode":
                from app.services.mode_engine import switch_mode
                db2 = SessionLocal()
                conv = db2.query(Conversation).get(msg.get("conversation_id"))
                if conv:
                    switch_mode(db2, conv, msg.get("mode", "copilot"))
                    await websocket.send_json({"type": "mode_changed", "conversation_id": conv.id, "mode": conv.current_mode})
                db2.close()
            elif msg.get("type") == "takeover":
                from app.services.mode_engine import switch_mode, clear_pending_timeout
                db2 = SessionLocal()
                conv = db2.query(Conversation).get(msg.get("conversation_id"))
                if conv:
                    switch_mode(db2, conv, "copilot", "WS接管")
                    clear_pending_timeout(db2, conv)
                    await websocket.send_json({"type": "mode_changed", "conversation_id": conv.id, "mode": "copilot", "reason": "takeover"})
                db2.close()
            elif msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "ack", "received": msg.get("type")})
    except WebSocketDisconnect:
        pass
    finally:
        _unregister_ws(merchant_id, websocket)


async def _ws_ai_suggest(merchant_id: int, msg: dict) -> list:
    """委托步骤6 AI Pipeline；未就绪时返回占位建议。"""
    try:
        from app.services.ai_suggest import get_ai_suggestions
        db = SessionLocal()
        try:
            result = await get_ai_suggestions(
                merchant_id=merchant_id,
                shop_id=msg.get("shop_id"),
                buyer_question=msg.get("question", ""),
                conversation_history=msg.get("history"),
                product_id=msg.get("product_id"),
                db=db,
            )
            return result.get("suggestions", [])
        finally:
            db.close()
    except Exception:
        await asyncio.sleep(0)
        return [{"content": "（AI 话术生成失败，请手动回复）", "source": "placeholder", "confidence": 0}]
