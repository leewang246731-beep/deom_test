"""
Quality Monitor — Track retrieval adoption + user feedback.

Writes quality metrics to DB for dashboard display and continuous improvement.
"""
import json
from datetime import datetime
from app.database.session import SessionLocal


def log_qa_trace(
    merchant_id: int,
    user_id: int | None,
    question: str,
    answer: str,
    chunks: list[dict],
    confidence: float,
    latency_ms: int,
    trace: list[dict],
    mode: str = "auto",
):
    """Log Q&A trace to database for analytics."""
    try:
        from app.kb.models import KbConversation, KbMessage
        db = SessionLocal()
        try:
            # Find or create conversation (simplified: always create new message)
            # In production, this would link to an active conversation
            refs = []
            for i, c in enumerate(chunks[:5]):
                refs.append({
                    "index": i + 1,
                    "content_snippet": c.get("content", "")[:120],
                    "score": c.get("rerank_score") or c.get("fusion_score") or c.get("score", 0),
                })

            # Log as a feedback-ready record
            msg = KbMessage(
                conversation_id=0,  # standalone QA
                role="assistant",
                content=answer,
                references_json=json.dumps(refs, ensure_ascii=False),
                confidence=confidence,
                latency_ms=latency_ms,
                created_at=datetime.now(),
            )
            db.add(msg)
            db.commit()
        finally:
            db.close()
    except Exception:
        pass  # Non-critical


def record_feedback(message_id: int, rating: int, comment: str = ""):
    """Record user feedback on Q&A quality."""
    try:
        from app.kb.models import KbMessage
        db = SessionLocal()
        try:
            msg = db.query(KbMessage).get(message_id)
            if msg:
                msg.confidence = max(0, min(1, rating / 5.0))  # Normalize to 0-1
                if comment:
                    # Append feedback to references
                    refs = json.loads(msg.references_json or "[]")
                    refs.append({"feedback": comment, "rating": rating})
                    msg.references_json = json.dumps(refs, ensure_ascii=False)
                db.commit()
        finally:
            db.close()
    except Exception:
        pass


def get_quality_stats(merchant_id: int) -> dict:
    """Get quality statistics for dashboard."""
    try:
        from app.kb.models import KbMessage, KbDocument, KbChunk
        db = SessionLocal()
        try:
            total_qa = db.query(KbMessage).filter(KbMessage.role == "assistant").count()
            avg_conf = db.query(KbMessage.confidence).filter(
                KbMessage.role == "assistant", KbMessage.confidence > 0
            ).all()
            avg_confidence = round(sum(c[0] for c in avg_conf) / len(avg_conf), 2) if avg_conf else 0

            return {
                "total_qa": total_qa,
                "avg_confidence": avg_confidence,
                "timestamp": datetime.now().isoformat(),
            }
        finally:
            db.close()
    except Exception:
        return {"total_qa": 0, "avg_confidence": 0, "error": "stats_unavailable"}
