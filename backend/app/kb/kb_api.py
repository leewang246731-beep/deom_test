"""知识库 REST API：文档 CRUD、问答（SSE）、统计、同步"""
import asyncio
import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from openai import OpenAI

from app.core.config import settings
from app.core.response import ok, page
from app.core.security import decode_token
from app.database.session import get_db

from app.kb.models import KbDocument, KbChunk, KbConversation, KbMessage
from app.kb.processor import process_document, batch_process
from app.kb.retriever import hybrid_retrieve
from app.kb.optimizer import QueryOptimizer
from app.kb.crag import CragEvaluator
from app.kb.reranker import rerank_by_relevance
from app.kb.postproc import compress_chunks, reorder_chunks
from app.kb.prompt import build_qa_prompt, compute_confidence, build_references
from app.kb.bm25_index import delete_index

router = APIRouter(prefix="/kb", tags=["知识库"])

# Feature flags
FEATURE = {
    "hybrid": True,
    "rerank": True,
    "crag": True,
    "rewrite": True,
    "hyde": False,
    "reorder": True,
    "compress": True,
}

_client: OpenAI | None = None


def _get_llm():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    return _client


def _get_user(auth: str) -> dict:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "未登录"})
    payload = decode_token(auth.split(" ", 1)[1])
    if not payload:
        raise HTTPException(status_code=401, detail={"code": 40101, "msg": "Token 无效"})
    return payload


def _llm_call(prompt: str, label: str = "default") -> str:
    client = _get_llm()
    resp = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=512 if label != "qa" else 1024,
    )
    return resp.choices[0].message.content or ""


def _embed(texts: list[str]) -> list[list[float]]:
    client = _get_llm()
    resp = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in resp.data]


def _embed_single(text: str) -> list[float]:
    return _embed([text])[0]


# ========== 文档管理 ==========

@router.get("/documents")
def list_documents(
    source_type: str = Query(None),
    status: str = Query(None),
    page_no: int = Query(1, alias="page"),
    page_size: int = Query(20),
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    user = _get_user(authorization)
    mid = user.get("merchant_id", 1)
    q = db.query(KbDocument).filter(KbDocument.merchant_id == mid)
    if source_type: q = q.filter(KbDocument.source_type == source_type)
    if status: q = q.filter(KbDocument.status == status)
    total = q.count()
    items = q.order_by(KbDocument.id.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": d.id, "title": d.title, "source_type": d.source_type,
                   "status": d.status, "chunk_count": d.chunk_count,
                   "created_at": d.created_at.isoformat() if d.created_at else None}
                 for d in items], total, page_no, page_size)


@router.post("/documents")
def create_document(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    user = _get_user(authorization)
    mid = user.get("merchant_id", 1)
    doc = KbDocument(
        merchant_id=mid,
        title=body["title"],
        content=body.get("content", ""),
        source_type=body.get("source_type", "manual"),
        source_id=body.get("source_id"),
        status="pending",
    )
    db.add(doc); db.commit(); db.refresh(doc)
    result = process_document(db, doc.id, mid, _embed)
    return ok({"id": doc.id, "status": doc.status, "chunk_count": result.chunk_count})


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    user = _get_user(authorization)
    mid = user.get("merchant_id", 1)
    doc = db.query(KbDocument).filter(KbDocument.id == doc_id, KbDocument.merchant_id == mid).first()
    if not doc:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "文档不存在"})
    db.query(KbChunk).filter(KbChunk.document_id == doc_id).delete()
    db.delete(doc); db.commit()
    return ok(msg="已删除")


# ========== 问答（SSE 流式） ==========

@router.post("/ask")
async def kb_ask(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    """知识库问答 SSE 流式输出"""
    user = _get_user(authorization)
    mid = body.get("merchant_id") or user.get("merchant_id") or 1
    query = body["question"]
    conv_id = body.get("conversation_id")
    mode = body.get("mode", "auto")

    optimizer = QueryOptimizer(_llm_call)
    evaluator = CragEvaluator(_llm_call)

    async def stream():
        t_start = time.time()
        try:
            # Step 1: 重写
            rewritten = optimizer.rewrite(query) if FEATURE["rewrite"] else query
            # Step 2: embed
            q_emb = _embed_single(rewritten)
            # Step 3: hybrid retrieve
            chunks = hybrid_retrieve(mid, rewritten, q_emb, use_bm25=FEATURE["hybrid"])
            # Step 4: CRAG
            if FEATURE["crag"] and chunks:
                crag = evaluator.evaluate(rewritten, chunks[:5])
                if crag["verdict"] == "no_context":
                    yield f"data: {json.dumps({'type': 'warning', 'msg': '知识库中没有相关信息'})}\n\n"
                    return
                elif crag["verdict"] == "partial":
                    relevant_ids = set(crag["relevant"])
                    chunks = [c for c in chunks if c["chunk_id"] in relevant_ids]
            # Step 5: rerank
            if FEATURE["rerank"] and chunks:
                chunks = rerank_by_relevance(chunks, q_emb, _embed)
            # Step 6: postproc
            if FEATURE["compress"]:
                chunks = compress_chunks(chunks)
            if FEATURE["reorder"]:
                chunks = reorder_chunks(chunks)
            # Step 7: prompt + LLM
            prompt = build_qa_prompt(query, chunks)
            yield f"data: {json.dumps({'type': 'context', 'sources': build_references(chunks), 'retrieved': len(chunks)})}\n\n"

            client = _get_llm()
            stream_resp = client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
                stream=True,
            )
            full = ""
            for chunk in stream_resp:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    full += delta
                    yield f"data: {json.dumps({'type': 'token', 'content': delta})}\n\n"
                    await asyncio.sleep(0)

            latency = int((time.time() - t_start) * 1000)
            confidence = compute_confidence(chunks, full)
            # Save conversation
            if conv_id:
                try:
                    db_msg = KbMessage(conversation_id=conv_id, role="user", content=query)
                    db.add(db_msg)
                    msg_ass = KbMessage(
                        conversation_id=conv_id, role="assistant", content=full,
                        references_json=build_references(chunks), confidence=confidence, latency_ms=latency,
                    )
                    db.add(msg_ass)
                    db.commit()
                except Exception:
                    pass
            refs = build_references(chunks)
            yield f"data: {json.dumps({'type': 'done', 'confidence': confidence, 'latency_ms': latency, 'references': refs})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'msg': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ========== 会话管理 ==========

@router.get("/conversations")
def list_conversations(
    page_no: int = Query(1, alias="page"),
    page_size: int = Query(20),
    authorization: str = Header(None),
    db: Session = Depends(get_db),
):
    user = _get_user(authorization)
    mid = user.get("merchant_id", 1)
    q = db.query(KbConversation).filter(KbConversation.merchant_id == mid)
    total = q.count()
    items = q.order_by(KbConversation.updated_at.desc()).offset((page_no - 1) * page_size).limit(page_size).all()
    return page([{"id": c.id, "title": c.title, "message_count": c.message_count,
                   "created_at": c.created_at.isoformat() if c.created_at else None,
                   "updated_at": c.updated_at.isoformat() if c.updated_at else None}
                 for c in items], total, page_no, page_size)


@router.post("/conversations")
def create_conversation(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    user = _get_user(authorization)
    mid = user.get("merchant_id", 1)
    conv = KbConversation(
        merchant_id=mid, user_id=user.get("sub", 0),
        title=body.get("title", "新对话"),
        retrieval_mode=body.get("mode", "auto"),
    )
    db.add(conv); db.commit(); db.refresh(conv)
    return ok({"id": conv.id, "title": conv.title})


@router.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    _get_user(authorization)
    msgs = db.query(KbMessage).filter(KbMessage.conversation_id == conv_id).order_by(KbMessage.id.asc()).all()
    return ok([{"id": m.id, "role": m.role, "content": m.content[:500],
                "references": m.references_json, "confidence": m.confidence,
                "created_at": m.created_at.isoformat() if m.created_at else None}
               for m in msgs])


# ========== 统计 + 同步 ==========

@router.get("/stats")
def kb_stats(authorization: str = Header(None), db: Session = Depends(get_db)):
    user = _get_user(authorization)
    mid = user.get("merchant_id", 1)
    docs = db.query(KbDocument).filter(KbDocument.merchant_id == mid).count()
    chunks = db.query(KbChunk).filter(KbChunk.merchant_id == mid).count()
    convs = db.query(KbConversation).filter(KbConversation.merchant_id == mid).count()
    return ok({"document_count": docs, "chunk_count": chunks, "conversation_count": convs})


@router.post("/sync")
def sync_shop_knowledge(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    """
    同步店铺知识：在商户绑定 SaaS 后调用。
    从外部商品表提取数据，生成知识文档并向量化。
    """
    user = _get_user(authorization)
    mid = body.get("merchant_id") or user.get("merchant_id") or 1
    from app.models.external_product import ExternalProduct

    products = db.query(ExternalProduct).filter(ExternalProduct.shop_id.in_(
        db.query(ExternalProduct.shop_id).filter(ExternalProduct.shop_id.isnot(None))
    )).all()
    if not products:
        return ok({"synced": 0, "message": "无需同步"})

    created = 0
    for p in products[:100]:
        existing = db.query(KbDocument).filter(
            KbDocument.merchant_id == mid, KbDocument.source_type == "product",
            KbDocument.source_id == p.id,
        ).first()
        if existing:
            continue
        content = f"商品名称: {p.title}\n价格: {p.price}\n库存: {p.stock}\n分类: {p.category_path or ''}\n描述: {p.description or ''}"
        doc = KbDocument(merchant_id=mid, title=p.title, content=content,
                         source_type="product", source_id=p.id, status="pending")
        db.add(doc)
        created += 1

    db.commit()

    if created:
        batch_process(db, mid, _embed)

    return ok({"synced": created, "message": f"已同步 {created} 个商品知识"})
