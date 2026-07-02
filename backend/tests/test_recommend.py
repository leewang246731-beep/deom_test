"""推荐系统专项测试 — 记忆压缩 / 画像引擎 / 推荐引擎 / Agent工具"""
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database.session import Base, SessionLocal, engine
from app.models.long_term_memory import LongTermMemory


# ===================================================================
# 1. LongTermMemory 模型
# ===================================================================
class TestLongTermMemoryModel(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine, checkfirst=True)

    def test_tablename(self):
        self.assertEqual(LongTermMemory.__tablename__, "long_term_memories")

    def test_columns(self):
        cols = {c.name for c in LongTermMemory.__table__.columns}
        required = {"id", "merchant_id", "user_id", "facts", "tags",
                     "snippets", "stats", "activity_level",
                     "last_conversation_at", "created_at", "updated_at"}
        self.assertTrue(required.issubset(cols), f"Missing: {required - cols}")

    def test_crud(self):
        db = SessionLocal()
        try:
            mem = LongTermMemory(
                merchant_id=88, user_id="test_user_001",
                facts={"skin_type": "油性", "budget": "150"},
                tags=["护肤", "防晒", "控油"],
                snippets=[{"text": "用户询问控油面霜", "time": "2026-07-01T10:00:00"}],
                stats={"order_count": 5, "avg_order_amount": 120},
                activity_level="active",
            )
            db.add(mem)
            db.commit()
            mid = mem.id
            self.assertIsNotNone(mid)

            m2 = db.query(LongTermMemory).filter_by(id=mid).first()
            self.assertEqual(m2.facts["skin_type"], "油性")
            self.assertEqual(len(m2.tags), 3)
            self.assertEqual(m2.activity_level, "active")

            db.delete(m2)
            db.commit()
        finally:
            db.rollback()
            db.close()

    def test_unique_constraint(self):
        """merchant_id + user_id 唯一约束"""
        db = SessionLocal()
        try:
            m1 = LongTermMemory(merchant_id=87, user_id="uniq_user",
                                facts={}, tags=[], snippets=[], stats={})
            db.add(m1)
            db.commit()

            m2 = LongTermMemory(merchant_id=87, user_id="uniq_user",
                                facts={}, tags=[], snippets=[], stats={})
            db.add(m2)
            with self.assertRaises(Exception):
                db.commit()
            db.rollback()

            # cleanup
            db.delete(m1)
            db.commit()
        finally:
            db.rollback()
            db.close()


# ===================================================================
# 2. 记忆压缩引擎
# ===================================================================
class TestMemoryCompressor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine, checkfirst=True)
        cls.merchant_id = 86
        cls.user_id = "compress_test_user"

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(LongTermMemory).filter_by(merchant_id=cls.merchant_id).delete()
            db.commit()
        finally:
            db.close()

    def setUp(self):
        # 每个测试前清理
        db = SessionLocal()
        try:
            db.query(LongTermMemory).filter_by(
                merchant_id=self.merchant_id, user_id=self.user_id).delete()
            db.commit()
        finally:
            db.close()

    def test_noise_filtered(self):
        """纯寒暄被过滤"""
        from app.services.memory_compressor import compress_conversation
        result = compress_conversation(self.merchant_id, self.user_id,
                                       "你好，在吗？", use_llm=False)
        self.assertFalse(result["compressed"])
        self.assertEqual(result["reason"], "noise_filtered")

    def test_noise_short_text(self):
        """过短文被过滤"""
        from app.services.memory_compressor import compress_conversation
        result = compress_conversation(self.merchant_id, self.user_id,
                                       "嗯", use_llm=False)
        self.assertFalse(result["compressed"])

    def test_rule_extract_skin_type(self):
        """规则提取肤质"""
        from app.services.memory_compressor import compress_conversation
        result = compress_conversation(
            self.merchant_id, self.user_id,
            "我是油皮，想找个清爽的面霜，预算150以内，不要太贵的",
            use_llm=False,
        )
        self.assertTrue(result["compressed"])
        self.assertIn("skin_type", result.get("facts_added", []))
        self.assertIn("budget", result.get("facts_added", []))

        # 验证长期记忆已更新
        from app.services.memory_compressor import get_long_term_memory
        mem = get_long_term_memory(self.merchant_id, self.user_id)
        self.assertEqual(mem.facts.get("skin_type"), "油性")
        self.assertIn("油性肌肤", mem.tags)

    def test_rule_extract_tags(self):
        """规则提取品类标签"""
        from app.services.memory_compressor import compress_conversation
        result = compress_conversation(
            self.merchant_id, self.user_id,
            "推荐一款保湿面霜和防晒吧，我是干皮敏感肌",
            use_llm=False,
        )
        self.assertTrue(result["compressed"])
        tags = result.get("tags_added", [])
        self.assertTrue(any("面霜" in t or "防晒" in t for t in tags))

    def test_snippets_capped_at_5(self):
        """snippets 上限 5 条"""
        from app.services.memory_compressor import compress_conversation, get_long_term_memory

        for i in range(7):
            compress_conversation(
                self.merchant_id, self.user_id,
                f"我想买第{i}种护肤品，我是{'油' if i % 2 == 0 else '干'}皮",
                use_llm=False,
            )

        mem = get_long_term_memory(self.merchant_id, self.user_id)
        self.assertLessEqual(len(mem.snippets or []), 5)

    def test_tags_capped_at_20(self):
        """tags 上限 20"""
        from app.services.memory_compressor import compress_conversation, get_long_term_memory

        for i in range(25):
            compress_conversation(
                self.merchant_id, self.user_id,
                f"我想买品类_{i} 我是油皮肤质预算{i}00",
                use_llm=False,
            )

        mem = get_long_term_memory(self.merchant_id, self.user_id)
        self.assertLessEqual(len(mem.tags or []), 20)

    def test_facts_overwrite(self):
        """新 facts 覆盖旧值"""
        from app.services.memory_compressor import compress_conversation, get_long_term_memory

        compress_conversation(self.merchant_id, self.user_id,
                              "我是油皮，预算100以内", use_llm=False)
        mem1 = get_long_term_memory(self.merchant_id, self.user_id)
        self.assertEqual(mem1.facts.get("skin_type"), "油性")

        compress_conversation(self.merchant_id, self.user_id,
                              "其实我是干皮，之前说错了，预算200", use_llm=False)
        mem2 = get_long_term_memory(self.merchant_id, self.user_id)
        self.assertEqual(mem2.facts.get("skin_type"), "干性")


# ===================================================================
# 3. 画像引擎
# ===================================================================
class TestProfileEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine, checkfirst=True)
        cls.merchant_id = 85
        cls.user_id = "profile_test_user"

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(LongTermMemory).filter_by(merchant_id=cls.merchant_id).delete()
            db.commit()
        finally:
            db.close()

    def setUp(self):
        db = SessionLocal()
        try:
            db.query(LongTermMemory).filter_by(
                merchant_id=self.merchant_id, user_id=self.user_id).delete()
            db.commit()
        finally:
            db.close()

    def test_get_full_profile_empty(self):
        """空画像返回默认结构"""
        from app.services.profile_engine import UserProfileEngine
        engine = UserProfileEngine(self.merchant_id)
        profile = engine.get_full_profile(self.user_id)
        self.assertIn("basic", profile)
        self.assertIn("tags", profile)
        self.assertIn("facts", profile)
        self.assertIn("consumption", profile)
        self.assertIn("intents", profile)
        self.assertIn("activity_level", profile)
        self.assertEqual(profile["activity_level"], "new")

    def test_update_fact_and_retrieve(self):
        """更新 fact 后画像可读到"""
        from app.services.profile_engine import UserProfileEngine
        engine = UserProfileEngine(self.merchant_id)
        engine.update_fact(self.user_id, "skin_type", "敏感")
        engine.update_fact(self.user_id, "budget", "200以内")

        profile = engine.get_full_profile(self.user_id)
        self.assertEqual(profile["facts"]["skin_type"], "敏感")
        self.assertEqual(profile["facts"]["budget"], "200以内")

    def test_profile_summary(self):
        """画像摘要生成"""
        from app.services.profile_engine import UserProfileEngine
        engine = UserProfileEngine(self.merchant_id)
        engine.update_fact(self.user_id, "skin_type", "油性")
        engine.update_fact(self.user_id, "budget", "150")

        summary = engine.get_profile_summary(self.user_id)
        self.assertIn("油性", summary)
        self.assertIn("150", summary)

    def test_profile_summary_empty(self):
        """无数据用户返回默认摘要"""
        from app.services.profile_engine import UserProfileEngine
        engine = UserProfileEngine(self.merchant_id)
        summary = engine.get_profile_summary("brand_new_user")
        # 新用户无画像数据时显示活跃度为"新用户"
        self.assertIn("新用户", summary)


# ===================================================================
# 4. 推荐引擎
# ===================================================================
class TestRecommendEngine(unittest.TestCase):

    def test_empty_candidates(self):
        """空候选返回空列表"""
        from app.services.recommend_engine import ProductRecommendEngine
        engine = ProductRecommendEngine(merchant_id=99999)
        profile = {"tags": [], "facts": {}, "consumption": {}, "intents": [], "activity_level": "new"}
        result = engine.recommend(profile)
        self.assertEqual(len(result), 0)

    def test_generate_reason(self):
        """推荐理由生成"""
        from app.services.recommend_engine import generate_reason

        profile = {
            "tags": ["护肤", "控油"],
            "facts": {"skin_type": "油性"},
            "consumption": {
                "top_categories": ["护肤"],
                "avg_order_amount": 120,
            },
        }
        product = {"title": "清爽控油面霜", "price": 99}

        reason = generate_reason(profile, product, 0.8)
        self.assertTrue(len(reason) > 0)
        # 至少匹配到一条理由
        self.assertTrue(
            "您常买的品类" in reason or
            "适合油性肌肤" in reason or
            "价格合适" in reason or
            "符合您的偏好" in reason or
            "热销推荐" in reason,
            f"Unexpected reason: {reason}"
        )

    def test_generate_reason_fallback(self):
        """无匹配时的兜底理由"""
        from app.services.recommend_engine import generate_reason
        profile = {"tags": [], "facts": {}, "consumption": {}}
        product = {"title": "未知商品XYZ", "price": 9999}
        reason = generate_reason(profile, product, 0.1)
        self.assertEqual(reason, "热销推荐")


# ===================================================================
# 5. Agent 工具
# ===================================================================
class TestRecommendAgentTools(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine, checkfirst=True)
        cls.merchant_id = 84
        cls.user_id = "agent_rec_test"

    @classmethod
    def tearDownClass(cls):
        db = SessionLocal()
        try:
            db.query(LongTermMemory).filter_by(merchant_id=cls.merchant_id).delete()
            db.commit()
        finally:
            db.close()

    def test_update_user_fact_tool(self):
        from app.ai.recommend_tools import build_update_fact_tool
        tool = build_update_fact_tool(self.merchant_id)
        result = tool.invoke({
            "user_id": self.user_id,
            "key": "skin_type",
            "value": "干性",
        })
        self.assertIn("已记录", result)
        self.assertIn("skin_type=干性", result)

    def test_profile_summary_tool(self):
        from app.ai.recommend_tools import build_profile_summary_tool
        # 先建点数据
        from app.services.profile_engine import UserProfileEngine
        engine = UserProfileEngine(self.merchant_id)
        engine.update_fact(self.user_id, "skin_type", "敏感")

        tool = build_profile_summary_tool(self.merchant_id)
        result = tool.invoke({"user_id": self.user_id})
        self.assertIn("敏感", result)

    def test_recommend_tool_empty(self):
        """推荐工具 — 无候选商品时"""
        from app.ai.recommend_tools import build_recommend_tool
        tool = build_recommend_tool(merchant_id=99999)
        result = tool.invoke({
            "user_id": "any_user",
            "need_tags": "test",
        })
        self.assertIn("暂未找到", result)

    def test_compress_tool_noise(self):
        """压缩工具 — 噪音过滤"""
        from app.ai.recommend_tools import build_compress_memory_tool
        tool = build_compress_memory_tool(self.merchant_id)
        result = tool.invoke({
            "user_id": self.user_id,
            "dialogue_snippet": "在吗",
        })
        self.assertIn("无需压缩", result)

    def test_compress_tool_useful(self):
        """压缩工具 — 有用信息"""
        from app.ai.recommend_tools import build_compress_memory_tool
        tool = build_compress_memory_tool(self.merchant_id)
        result = tool.invoke({
            "user_id": self.user_id,
            "dialogue_snippet": "我是油皮，想找控油面霜，预算150以内，对花粉过敏",
        })
        self.assertIn("记忆已更新", result)


# ===================================================================
# 6. Tool Registry 集成
# ===================================================================
class TestRegistryRecommendTools(unittest.TestCase):

    def test_recommend_tools_registered(self):
        from app.ai.tool_registry import init_registry
        registry = init_registry(merchant_id=1)
        names = registry.list_names()

        for name in ("recommend", "update_user_fact", "compress_conversation_tool", "get_profile_summary"):
            self.assertIn(name, names, f"{name} not in registry")

    def test_recommend_tool_tags(self):
        from app.ai.tool_registry import init_registry
        registry = init_registry(merchant_id=1)

        profile_tools = registry.get_by_tags(["profile"])
        self.assertGreaterEqual(len(profile_tools), 4)
        names = {t.name for t in profile_tools}
        self.assertTrue({"recommend", "update_user_fact", "compress_conversation_tool", "get_profile_summary"}.issubset(names))


# ===================================================================
# 7. Agent Prompt 集成
# ===================================================================
class TestAgentPromptRecommend(unittest.TestCase):

    def test_prompt_contains_recommend_tools(self):
        import inspect
        from app.ai import agent as agent_module
        source = inspect.getsource(agent_module.create_service_agent)
        self.assertIn("recommend", source)
        self.assertIn("get_profile_summary", source)
        self.assertIn("update_user_fact", source)
        self.assertIn("compress_conversation_tool", source)

    def test_prompt_contains_recommend_rules(self):
        import inspect
        from app.ai import agent as agent_module
        source = inspect.getsource(agent_module.create_service_agent)
        self.assertIn("商品推荐规则", source)
        self.assertIn("高度个性化", source)
        self.assertIn("need_tags", source)


if __name__ == "__main__":
    unittest.main()
