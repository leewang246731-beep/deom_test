"""记忆压缩引擎 — LLM 提取关键信息 + 过滤噪音 + 合并长期记忆"""
import json
import logging
import re
from datetime import datetime
from typing import Optional

from app.database.session import SessionLocal
from app.models.long_term_memory import LongTermMemory

logger = logging.getLogger(__name__)

# 无关信息关键词模式（寒暄、技术问题等一次性内容）
_NOISE_PATTERNS = [
    r"验证码",
    r"收不到",
    r"怎么登录",
    r"密码忘了",
    r"在吗[?？]?$",
    r"你好[。！]?$",
    r"谢谢",
    r"好的",
    r"嗯+$",
    r"哦+$",
]

MAX_SNIPPETS = 5
MAX_TAGS = 20


def _is_noise(text: str) -> bool:
    """快速判断是否为噪音内容（纯寒暄/一次性技术问题）。"""
    stripped = text.strip()
    if len(stripped) < 3:
        return True
    for pat in _NOISE_PATTERNS:
        if re.search(pat, stripped):
            return True
    return False


def _llm_extract(dialogue_snippet: str) -> dict:
    """调用 LLM 提取结构化关键信息。

    Returns: {"useful": bool, "facts": dict, "tags": list[str], "summary": str}
    """
    from app.services.llm import chat

    prompt = f"""判断以下客服对话是否包含对用户画像或长期需求有价值的信息。

有价值的信息包括：用户透露的个人属性（肤质、年龄、预算、偏好、过敏源）、明确表达的商品需求、消费意愿。
无价值的信息包括：纯寒暄、验证码/登录等技术问题、单纯的情绪宣泄、已解决的一次性问题。

如果有价值，返回 JSON（不要任何其他文字）：
{{"useful":true,"facts":{{"key":"value"}},"tags":["标签1","标签2"],"summary":"一句话摘要"}}

如果无价值，返回：
{{"useful":false}}

对话内容：
{dialogue_snippet[:1500]}"""

    try:
        resp = chat([{"role": "user", "content": prompt}])
        # 清理可能的 markdown 包裹
        cleaned = resp.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        result = json.loads(cleaned)
        if isinstance(result, dict) and "useful" in result:
            return result
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("LLM 记忆提取失败: %s", e)

    return {"useful": False}


def _rule_extract_facts(dialogue_snippet: str) -> dict:
    """基于规则的轻量级事实提取（LLM 不可用时的降级方案）。

    提取明确的键值对模式，如"我是油皮"→ skin_type=油性、"预算200"→ budget=200以内。
    """
    facts = {}
    tags = []

    patterns = [
        (r"(油皮|油性皮肤|混油|大油田)", "skin_type", "油性"),
        (r"(干皮|干性皮肤|混干|沙漠皮)", "skin_type", "干性"),
        (r"(敏感肌|容易过敏|皮肤敏感)", "skin_type", "敏感"),
        (r"预算[约在]?(\d+)", "budget", None),  # None → 用捕获组
        (r"(\d+)[块元]以内", "budget", None),
        (r"(学生党|学生)", "identity", "学生"),
        (r"(宝妈|哺乳期|孕期|孕妇)", "identity", None),
        (r"过敏[原源]?(.{1,8})", "allergies", None),
    ]

    for pat, key, default_val in patterns:
        m = re.search(pat, dialogue_snippet)
        if m:
            val = default_val if default_val else m.group(1)
            facts[key] = val
            if key == "skin_type":
                tags.append(val + "肌肤" if "肌" not in val else val)
            elif key == "budget":
                tags.append(f"预算{val}以内")

    # 提取商品品类需求
    category_keywords = ["面霜", "防晒", "洁面", "精华", "水乳", "面膜", "口红", "粉底",
                         "护肤", "彩妆", "洗面奶", "眼霜", "卸妆", "隔离"]
    for kw in category_keywords:
        if kw in dialogue_snippet:
            tags.append(kw)

    return {"useful": bool(facts or tags), "facts": facts, "tags": list(set(tags)),
            "summary": dialogue_snippet[:80] if (facts or tags) else ""}


# ===== 长期记忆 CRUD =====

def get_long_term_memory(merchant_id: int, user_id: str) -> LongTermMemory:
    """获取或创建长期记忆记录。"""
    db = SessionLocal()
    try:
        mem = db.query(LongTermMemory).filter_by(
            merchant_id=merchant_id, user_id=user_id,
        ).first()
        if not mem:
            mem = LongTermMemory(
                merchant_id=merchant_id,
                user_id=user_id,
                facts={},
                tags=[],
                snippets=[],
                stats={},
                activity_level="new",
            )
            db.add(mem)
            db.flush()
        return mem
    finally:
        db.close()


def save_long_term_memory(memory: LongTermMemory):
    """持久化长期记忆（merge 模式，兼容跨 session 对象）。"""
    db = SessionLocal()
    try:
        merged = db.merge(memory)
        db.commit()
    finally:
        db.close()


# ===== 压缩入口 =====

def compress_conversation(merchant_id: int, user_id: str, dialogue_snippet: str,
                          use_llm: bool = True) -> dict:
    """记忆压缩主流程。

    1. 噪音过滤 → 2. LLM/规则提取 → 3. 合并长期记忆 → 4. 持久化

    Returns: 压缩结果摘要 dict
    """
    # 1. 噪音快速过滤
    if _is_noise(dialogue_snippet):
        return {"compressed": False, "reason": "noise_filtered"}

    # 2. 关键信息提取
    if use_llm:
        extracted = _llm_extract(dialogue_snippet)
    else:
        extracted = _rule_extract_facts(dialogue_snippet)

    if not extracted.get("useful"):
        return {"compressed": False, "reason": "no_useful_info"}

    # 3. 合并长期记忆
    mem = get_long_term_memory(merchant_id, user_id)

    # 合并 facts
    current_facts = dict(mem.facts or {})
    for k, v in extracted.get("facts", {}).items():
        current_facts[k] = v  # 新值覆盖旧值
    mem.facts = current_facts

    # 合并 tags（去重，上限 MAX_TAGS）
    current_tags = set(mem.tags or [])
    current_tags.update(extracted.get("tags", []))
    mem.tags = list(current_tags)[:MAX_TAGS]

    # 追加 snippet（上限 MAX_SNIPPETS，FIFO）
    snippets = list(mem.snippets or [])
    summary = extracted.get("summary", dialogue_snippet[:80])
    snippets.append({"text": summary, "time": datetime.now().isoformat()})
    if len(snippets) > MAX_SNIPPETS:
        snippets = snippets[-MAX_SNIPPETS:]
    mem.snippets = snippets

    # 更新活跃度
    mem.last_conversation_at = datetime.now()
    order_count = (mem.stats or {}).get("order_count", 0)
    if order_count == 0:
        mem.activity_level = "new"
    elif order_count >= 5:
        mem.activity_level = "active"
    else:
        mem.activity_level = "active"

    # 4. 持久化
    save_long_term_memory(mem)

    logger.info("记忆压缩完成 merchant=%s user=%s facts=%d tags=%d snippets=%d",
                merchant_id, user_id, len(current_facts), len(mem.tags), len(snippets))

    return {
        "compressed": True,
        "facts_added": list(extracted.get("facts", {}).keys()),
        "tags_added": extracted.get("tags", []),
        "snippet_count": len(snippets),
    }


def build_stats_from_orders(merchant_id: int, user_id: str):
    """从订单数据更新长期记忆中的 stats 字段。"""
    from app.database.session import SessionLocal
    from app.models.external_order import ExternalOrder
    from app.models.platform_shop import PlatformShop

    db = SessionLocal()
    try:
        sids = [r[0] for r in db.query(PlatformShop.id).filter(
            PlatformShop.merchant_id == merchant_id).all()]
        if not sids:
            return

        orders = db.query(ExternalOrder).filter(
            ExternalOrder.shop_id.in_(sids),
            ExternalOrder.buyer_openid == user_id,
            ExternalOrder.status != "pending",
        ).all()

        if not orders:
            return

        total_spent = sum(float(o.pay_amount or 0) for o in orders)
        categories = set()
        for o in orders:
            for sku in (o.sku_details_json or []):
                title = sku.get("title", "") if isinstance(sku, dict) else ""
                if title:
                    categories.add(title[:20])

        mem = get_long_term_memory(merchant_id, user_id)
        mem.stats = {
            "order_count": len(orders),
            "total_spent": round(total_spent, 2),
            "avg_order_amount": round(total_spent / len(orders), 2),
            "top_categories": list(categories)[:5],
            "last_order_at": str(orders[0].created_at) if orders else None,
            "updated_at": datetime.now().isoformat(),
        }

        # 更新活跃度
        last_order = orders[0]
        days_since = (datetime.now() - last_order.created_at).days if last_order.created_at else 999
        if days_since > 90:
            mem.activity_level = "lost"
        elif days_since > 30:
            mem.activity_level = "dormant"
        elif len(orders) >= 5:
            mem.activity_level = "active"
        else:
            mem.activity_level = "new"

        save_long_term_memory(mem)
    finally:
        db.close()
