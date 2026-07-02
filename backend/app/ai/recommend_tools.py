"""商品推荐 Agent 工具 — 闭包绑定 merchant_id

四个工具（user_id 为运行时参数，与现有 get_buyer_profile 模式一致）:
  - recommend:             基于画像推荐商品
  - update_user_fact:      更新用户画像事实
  - compress_conversation: 记忆压缩
  - get_profile_summary:   读取画像摘要
"""
import logging

from langchain_core.tools import tool as langchain_tool

from app.services.profile_engine import UserProfileEngine
from app.services.recommend_engine import ProductRecommendEngine

logger = logging.getLogger(__name__)


def build_recommend_tool(merchant_id: int):
    """基于多维画像的个性化推荐工具"""

    @langchain_tool
    def recommend(user_id: str, need_tags: str = "", top_k: int = 3) -> str:
        """基于用户画像和需求标签推荐商品。

        参数：
        - user_id: 买家 OpenID（从对话上下文获取，通常是 buyer_openid）
        - need_tags: 当前需求关键词，逗号分隔（如"保湿面霜,清爽,不油腻"），无具体需求时传空字符串
        - top_k: 返回商品数量，默认3

        返回：推荐商品列表，含名称、价格和个性化推荐理由。
        """
        profile_engine = UserProfileEngine(merchant_id)
        recommend_engine = ProductRecommendEngine(merchant_id)

        tags_list = [t.strip() for t in need_tags.split(",") if t.strip()] if need_tags else []

        profile = profile_engine.get_full_profile(user_id)
        products = recommend_engine.recommend(profile, tags_list, top_k)

        if not products:
            return "暂未找到合适的推荐商品，建议您描述具体需求，我帮您精准匹配。"

        lines = [f"为您找到 {len(products)} 款推荐商品："]
        for i, item in enumerate(products, 1):
            p = item["product"]
            reason = item.get("reason", "推荐")
            stock_hint = f" (仅剩{p['stock']}件)" if p.get("stock", 0) < 20 else ""
            lines.append(
                f"{i}. {p['title']}  ¥{p['price']:.0f}{stock_hint} — {reason}"
            )

        # 附加画像洞察
        tags = profile.get("tags", [])
        if tags:
            lines.append(f"\n💡 基于您的偏好: {', '.join(tags[:5])}")

        return "\n".join(lines)

    return recommend


def build_update_fact_tool(merchant_id: int):
    """更新用户画像事实工具"""

    @langchain_tool
    def update_user_fact(user_id: str, key: str, value: str) -> str:
        """更新用户画像偏好事实，让下次推荐更精准。

        使用时机：用户主动透露个人信息时（如"我是油皮"→ key=skin_type value=油性、
        "预算200以内"→ key=budget value=200、"我对花粉过敏"→ key=allergies value=花粉）。

        参数：
        - user_id: 买家 OpenID
        - key: 事实键名，常用: skin_type / budget / allergies / identity
        - value: 事实值

        返回：更新确认。
        """
        engine = UserProfileEngine(merchant_id)
        engine.update_fact(user_id, key, value)
        return f"已记录: {key}={value}，后续推荐会更贴合您的需求。"

    return update_user_fact


def build_compress_memory_tool(merchant_id: int):
    """记忆压缩工具"""
    from app.services.memory_compressor import compress_conversation as _compress

    @langchain_tool
    def compress_conversation_tool(user_id: str, dialogue_snippet: str) -> str:
        """压缩会话关键信息到长期记忆。会话结束或话题切换时使用。

        参数：
        - user_id: 买家 OpenID
        - dialogue_snippet: 需要压缩的对话片段（合并最近几轮的文本）

        返回：压缩结果摘要。
        """
        result = _compress(merchant_id, user_id, dialogue_snippet)
        if result.get("compressed"):
            facts = result.get("facts_added", [])
            tags = result.get("tags_added", [])
            parts = []
            if facts:
                parts.append(f"提取偏好: {', '.join(facts)}")
            if tags:
                parts.append(f"更新标签: {', '.join(tags)}")
            return "记忆已更新。" + " ".join(parts) if parts else "记忆已更新。"
        reason = result.get("reason", "")
        if reason == "noise_filtered":
            return "当前对话无需压缩（寒暄/技术问题类内容已过滤）。"
        return "当前对话无新增有用信息，画像未变化。"

    return compress_conversation_tool


def build_profile_summary_tool(merchant_id: int):
    """读取用户画像摘要工具"""

    @langchain_tool
    def get_profile_summary(user_id: str) -> str:
        """获取用户画像摘要：属性、消费习惯、兴趣标签、近期意图。

        使用时机：需要了解用户偏好或消费能力来做出决策时。

        参数：
        - user_id: 买家 OpenID

        返回：多维度画像文本摘要。
        """
        engine = UserProfileEngine(merchant_id)
        return engine.get_profile_summary(user_id)

    return get_profile_summary
