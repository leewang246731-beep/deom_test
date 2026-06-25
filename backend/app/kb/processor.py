"""文档处理管道：pending → parsing → vectorizing → done / failed"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.kb.models import KbDocument, KbChunk
from app.kb.splitter import TokenTextSplitter, inject_heading_context
from app.kb.chroma_client import get_collection
from app.kb.bm25_index import build_index


@dataclass
class ProcessResult:
    ok: bool
    document_id: int
    chunk_count: int = 0
    error: str | None = None


def process_document(
    db: Session,
    doc_id: int,
    merchant_id: int,
    embed_fn: Callable[[list[str]], list[list[float]]],
) -> ProcessResult:
    """状态机驱动：pending → parsing → vectorizing → done/failed"""
    doc = db.query(KbDocument).filter(KbDocument.id == doc_id).first()
    if not doc:
        return ProcessResult(ok=False, document_id=doc_id, error="文档不存在")

    try:
        # 1. parsing
        doc.status = "parsing"; db.commit()

        splitter = TokenTextSplitter()
        chunks = splitter.split(doc.content or "", doc.title)
        inject_heading_context(chunks, doc.title)

        if not chunks:
            doc.status = "failed"; doc.error_msg = "无法切分出有效内容"; db.commit()
            return ProcessResult(ok=False, document_id=doc_id, error="无法切分")

        # 2. 写入 chunk 记录
        chunk_records = []
        for i, c in enumerate(chunks):
            cr = KbChunk(
                document_id=doc.id,
                merchant_id=merchant_id,
                chunk_index=i,
                content=c["content"],
                heading_context=c.get("heading_context", ""),
                token_count=c.get("token_count", 0),
            )
            db.add(cr); db.flush()
            chunk_records.append(cr)

        # 3. vectorizing
        doc.status = "vectorizing"; db.commit()

        texts = [cr.content for cr in chunk_records]
        embeddings = embed_fn(texts)

        # 写入 ChromaDB
        collection = get_collection(merchant_id)
        ids = [str(cr.id) for cr in chunk_records]
        metas = [{"document_id": doc.id, "chunk_index": cr.chunk_index} for cr in chunk_records]
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)

        for cr in chunk_records:
            cr.embedding_id = str(cr.id)
        db.commit()

        # 4. 重建 BM25 索引
        try:
            all_chunks = db.query(KbChunk).filter(KbChunk.merchant_id == merchant_id).all()
            build_index(merchant_id, [{"id": c.id, "content": c.content} for c in all_chunks])
        except Exception:
            pass

        doc.status = "done"; doc.chunk_count = len(chunk_records)
        doc.error_msg = None
        db.commit()

        return ProcessResult(ok=True, document_id=doc_id, chunk_count=len(chunk_records))

    except Exception as e:
        doc.status = "failed"
        doc.error_msg = str(e)[:500]
        db.commit()
        return ProcessResult(ok=False, document_id=doc_id, error=str(e))


def batch_process(
    db: Session,
    merchant_id: int,
    embed_fn: Callable[[list[str]], list[list[float]]],
) -> list[ProcessResult]:
    """处理该租户下所有 pending 的文档"""
    docs = db.query(KbDocument).filter(
        KbDocument.merchant_id == merchant_id,
        KbDocument.status == "pending",
    ).all()
    results = []
    for d in docs:
        results.append(process_document(db, d.id, merchant_id, embed_fn))
    return results
