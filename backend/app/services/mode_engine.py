"""
客服工作台模式引擎 (SERVICE-MODE-PLAN §4/§7)
判断模式 → 执行对应逻辑 → 记录日志
"""
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.service_mode import AutoReplyLog, ServiceModeConfig


def get_mode_config(db: Session, merchant_id: int) -> ServiceModeConfig:
    """获取商户模式配置，不存在则创建默认。"""
    cfg = db.query(ServiceModeConfig).filter(ServiceModeConfig.merchant_id == merchant_id).first()
    if not cfg:
        cfg = ServiceModeConfig(merchant_id=merchant_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def get_effective_mode(db: Session, merchant_id: int, conv: Conversation = None) -> str:
    """获取会话的有效模式：会话级覆盖 > 时段自动切换 > 全局默认。"""
    if conv and conv.current_mode:
        return conv.current_mode
    cfg = get_mode_config(db, merchant_id)
    # 时段检查
    if cfg.auto_mode_hours and _in_auto_hours(cfg.auto_mode_hours):
        return "auto"
    return cfg.default_mode or "copilot"


def calc_confidence(fused: list, llm_response: str, buyer_question: str) -> float:
    """计算 AI 回复的置信度（0-1）。"""
    score = 0.50
    if fused:
        top_rrf = fused[0].get("rrf", 0)
        if top_rrf > 0.015:
            score += 0.15
        if top_rrf > 0.025:
            score += 0.10
    if 20 < len(llm_response) < 300:
        score += 0.05
    specifics = ["¥", "元", "码", "天", "小时", "快递", "已", "可以", "有货", "发"]
    if any(s in llm_response for s in specifics):
        score += 0.10
    simple_q = ["有货", "多少钱", "几天到", "什么快递", "支持", "尺码", "颜色", "发货"]
    if any(p in buyer_question for p in simple_q):
        score += 0.10
    return round(min(score, 0.99), 2)


def should_auto_send(confidence: float, cfg: ServiceModeConfig) -> str:
    """判断自动模式下的操作：auto_send / fallback / transfer。"""
    auto_threshold = float(cfg.auto_confidence_threshold or 0.80)
    fallback_threshold = float(cfg.fallback_confidence_threshold or 0.50)
    if confidence >= auto_threshold:
        return "auto_send"
    elif confidence >= fallback_threshold:
        return "fallback"
    else:
        return "transfer"


def set_pending_timeout(db: Session, conv: Conversation, cfg: ServiceModeConfig):
    """设置人工响应超时时间点。"""
    timeout_secs = cfg.human_response_timeout_seconds or 180
    conv.pending_timeout_at = datetime.now() + timedelta(seconds=timeout_secs)
    db.commit()


def clear_pending_timeout(db: Session, conv: Conversation):
    """人工已响应，清除超时。"""
    conv.pending_timeout_at = None
    conv.last_human_at = datetime.now()
    db.commit()


def log_auto_reply(db: Session, conv_id: int, merchant_id: int, mode: str,
                   buyer_question: str, ai_reply: str, confidence: float,
                   action: str, response_ms: int = 0):
    """记录自动回复日志。"""
    db.add(AutoReplyLog(
        conversation_id=conv_id, merchant_id=merchant_id, mode=mode,
        buyer_question=buyer_question, ai_reply=ai_reply,
        confidence=confidence, action_taken=action, response_time_ms=response_ms,
    ))
    db.commit()


def increment_auto_count(db: Session, conv: Conversation):
    """自动回复计数+1。"""
    conv.auto_reply_count = (conv.auto_reply_count or 0) + 1
    db.commit()


def switch_mode(db: Session, conv: Conversation, new_mode: str, reason: str = ""):
    """切换会话模式。"""
    conv.current_mode = new_mode
    if new_mode == "manual":
        conv.pending_timeout_at = None
    db.commit()
    return {"conversation_id": conv.id, "mode": new_mode, "reason": reason}


ROLE_PROMPTS = {
    "pre_sale": "你是售前客服。重点：突出商品卖点和优势，适当推荐搭配，制造紧迫感促成下单，回答价格/优惠/规格问题。",
    "in_sale": "你是售中客服。重点：提供准确物流信息，安抚等待焦虑，处理地址修改/加急请求，引用具体快递状态。",
    "after_sale": "你是售后客服。重点：表达歉意和理解，提供明确解决方案（退/换/补），说明流程和时效，适当提供补偿方案，态度温和不过度承诺。",
}


def get_role_prompt(skill_tags: str = "") -> str:
    """根据技能标签返回角色 Prompt。"""
    tags = (skill_tags or "").lower()
    if any(k in tags for k in ["售前", "咨询", "推荐", "pre"]):
        return ROLE_PROMPTS["pre_sale"]
    elif any(k in tags for k in ["售中", "物流", "发货", "in_sale"]):
        return ROLE_PROMPTS["in_sale"]
    elif any(k in tags for k in ["售后", "退", "投诉", "after"]):
        return ROLE_PROMPTS["after_sale"]
    return ""


def _in_auto_hours(hours_str: str) -> bool:
    """判断当前时间是否在自动模式时段内。如 '22:00-08:00'。"""
    try:
        parts = hours_str.split("-")
        if len(parts) != 2:
            return False
        start_h, start_m = map(int, parts[0].strip().split(":"))
        end_h, end_m = map(int, parts[1].strip().split(":"))
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        if start_minutes > end_minutes:  # 跨午夜
            return current_minutes >= start_minutes or current_minutes < end_minutes
        else:
            return start_minutes <= current_minutes < end_minutes
    except Exception:
        return False
