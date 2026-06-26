"""
AI 引擎接口（PHASE1-PLAN 4.6/4.7 / api.md 3.6）
话术建议 / 催单话术 / 知识库搜索，全部委托步骤6 的 ai_suggest 服务。
步骤6 未接入时返回占位响应，保证接口可联调、前端不被阻塞。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_current_merchant
from app.core.response import ok
from app.database.session import get_db
from app.models.ai_suggestion_log import AISuggestionLog
from app.models.ai_style_config import AIStyleConfig
from app.schemas import AICampaignRequest, AISearchRequest, AISuggestLogRequest, AISuggestRequest, AIStyleCreate, AIStyleUpdate

router = APIRouter(prefix="/ai", tags=["AI 引擎"])


@router.post("/suggest")
async def ai_suggest(
    body: AISuggestRequest,
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    try:
        from app.services.ai_suggest import get_ai_suggestions
        result = await get_ai_suggestions(
            merchant_id=current.merchant_id,
            shop_id=body.shop_id,
            buyer_question=body.buyer_question,
            conversation_history=body.conversation_history,
            product_id=body.product_id,
            db=db,
        )
        return ok(result)
    except Exception as e:
        return ok({
            "suggestions": [{"content": "（AI 话术待步骤6 接入）", "source": "placeholder", "confidence": 0}],
            "note": f"{e}",
        })


@router.post("/campaign/pending-payment")
def ai_campaign(
    body: AICampaignRequest,
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    try:
        from app.services.ai_suggest import generate_payment_reminders
        result = generate_payment_reminders(current.merchant_id, body.shop_id, db)
        if result is None or (isinstance(result, dict) and not result.get("reminders")):
            return ok({"reminders": [], "count": 0, "msg": "当前无待催付订单或 AI 服务暂时不可用"})
        return ok(result)
    except Exception as e:
        return ok({"reminders": [], "count": 0, "msg": f"AI 催付服务调用失败: {str(e)}"})


@router.post("/search")
def ai_search(
    body: AISearchRequest,
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    try:
        from app.services.ai_suggest import knowledge_search
        return ok({"results": knowledge_search(current.merchant_id, body.query, body.top_k)})
    except Exception as e:
        return ok({"results": [], "note": f"AI 搜索待步骤6 接入: {e}"})


@router.post("/suggest/log")
def ai_suggest_log(
    body: AISuggestLogRequest,
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """记录话术采纳结果（agent-design.md 五：采纳反馈闭环）"""
    log = AISuggestionLog(
        conversation_id=body.conversation_id,
        buyer_question=body.buyer_question,
        ai_suggestion=body.ai_suggestion,
        was_adopted=body.was_adopted,
        quality_score=body.quality_score,
        feedback_note=body.feedback_note,
        final_message=body.final_message,
    )
    db.add(log)
    db.commit()
    return ok({"id": log.id}, msg="已记录")


# ===== AI 话术风格（缺口3）=====
@router.get("/styles")
def list_styles(current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    styles = db.query(AIStyleConfig).filter(
        AIStyleConfig.merchant_id == current.merchant_id).order_by(AIStyleConfig.id).all()
    return ok([{
        "id": s.id, "name": s.name, "style_key": s.style_key,
        "tone": s.tone, "greeting": s.greeting, "features": s.features,
        "is_default": s.is_default,
    } for s in styles])


@router.post("/styles")
def create_style(body: AIStyleCreate, current: CurrentUser = Depends(get_current_merchant), db: Session = Depends(get_db)):
    s = AIStyleConfig(
        merchant_id=current.merchant_id,
        name=body.name,
        style_key="custom",
        tone="",
        greeting="",
        features={},
    )
    db.add(s)
    db.commit()
    return ok({"id": s.id}, msg="已创建")


@router.put("/styles/{style_id}")
def update_style(style_id: int, body: AIStyleUpdate, current: CurrentUser = Depends(get_current_merchant),
                 db: Session = Depends(get_db)):
    s = db.query(AIStyleConfig).filter(AIStyleConfig.id == style_id,
                                        AIStyleConfig.merchant_id == current.merchant_id).first()
    if not s:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "风格不存在"})
    for field in ("name", "tone", "greeting", "features"):
        val = getattr(body, field, None)
        if val is not None:
            setattr(s, field, val)
    if body.is_default:
        db.query(AIStyleConfig).filter(
            AIStyleConfig.merchant_id == current.merchant_id, AIStyleConfig.is_default == True
        ).update({"is_default": False})
        s.is_default = True
    db.commit()
    return ok({"id": s.id}, msg="已更新")


@router.delete("/styles/{style_id}")
def delete_style(style_id: int, current: CurrentUser = Depends(get_current_merchant),
                 db: Session = Depends(get_db)):
    s = db.query(AIStyleConfig).filter(AIStyleConfig.id == style_id,
                                        AIStyleConfig.merchant_id == current.merchant_id).first()
    if not s:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "风格不存在"})
    if s.style_key in ("professional", "warm", "expert"):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "预设风格不可删除"})
    db.delete(s)
    db.commit()
    return ok(msg="已删除")


@router.post("/styles/{style_id}/default")
def set_default_style(style_id: int, current: CurrentUser = Depends(get_current_merchant),
                      db: Session = Depends(get_db)):
    db.query(AIStyleConfig).filter(AIStyleConfig.merchant_id == current.merchant_id).update(
        {"is_default": 0}, synchronize_session=False)
    s = db.query(AIStyleConfig).filter(AIStyleConfig.id == style_id,
                                        AIStyleConfig.merchant_id == current.merchant_id).first()
    if not s:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "风格不存在"})
    s.is_default = 1
    db.commit()
    return ok({"id": s.id, "is_default": 1}, msg="已设为默认")
