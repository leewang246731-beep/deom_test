"""文档处理管道：pending → parsing → vectorizing → done / failed

支持两种输入：
1. 文本内容：doc.content 直接分块
2. 文件上传：通过 DocumentLoaderFactory 解析文件提取文本
"""
from dataclasses import dataclass
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


def _extract_content(doc: KbDocument) -> str:
    """从文档记录中提取待分块的文本内容。

    优先级：file_path（文件上传） > content（手动输入）
    """
    # 文件上传：调用多格式加载器解析
    if doc.file_path:
        try:
            from app.kb.loaders import DocumentLoaderFactory
            result = DocumentLoaderFactory.load(doc.file_path)
            text = result.get("text", "")
            if text.strip():
                return text
        except Exception:
            pass
    # 回退到 content 字段
    return doc.content or ""


def process_document(
    db: Session,
    doc_id: int,
    merchant_id: int,
    embed_fn: Callable[[list[str]], list[list[float]]],
) -> ProcessResult:
    """状态机驱动：pending → parsing → vectorizing → done/failed

    支持文本内容和文件上传两种输入方式。
    """
    doc = db.query(KbDocument).filter(KbDocument.id == doc_id).first()
    if not doc:
        return ProcessResult(ok=False, document_id=doc_id, error="文档不存在")

    try:
        # 1. parsing — 提取文本内容
        doc.status = "parsing"
        db.commit()

        content = _extract_content(doc)
        if not content.strip():
            doc.status = "failed"
            doc.error_msg = "文档内容为空，无法解析"
            db.commit()
            return ProcessResult(ok=False, document_id=doc_id, error="内容为空")

        splitter = TokenTextSplitter()
        chunks = splitter.split(content, doc.title)
        inject_heading_context(chunks, doc.title)

        if not chunks:
            doc.status = "failed"
            doc.error_msg = "无法切分出有效内容"
            db.commit()
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
            db.add(cr)
            db.flush()
            chunk_records.append(cr)

        # 3. vectorizing
        doc.status = "vectorizing"
        db.commit()

        texts = [cr.content for cr in chunk_records]
        embeddings = embed_fn(texts)

        # 写入 ChromaDB
        collection = get_collection(merchant_id)
        ids = [str(cr.id) for cr in chunk_records]
        metas = [
            {"document_id": doc.id, "chunk_index": cr.chunk_index}
            for cr in chunk_records
        ]
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metas)

        for cr in chunk_records:
            cr.embedding_id = str(cr.id)
        db.commit()

        # 4. 重建 BM25 索引
        try:
            all_chunks = (
                db.query(KbChunk)
                .filter(KbChunk.merchant_id == merchant_id)
                .all()
            )
            build_index(
                merchant_id,
                [{"id": c.id, "content": c.content} for c in all_chunks],
            )
        except Exception:
            pass

        doc.status = "done"
        doc.chunk_count = len(chunk_records)
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
    docs = (
        db.query(KbDocument)
        .filter(
            KbDocument.merchant_id == merchant_id,
            KbDocument.status == "pending",
        )
        .all()
    )
    results = []
    for d in docs:
        results.append(process_document(db, d.id, merchant_id, embed_fn))
    return results
