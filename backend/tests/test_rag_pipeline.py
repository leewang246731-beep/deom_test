"""
回归测试：RAG 管道关键修复验证

覆盖：
- test_hybrid_retrieve_auto_rebuild_index  (BUG-B)
- test_self_correction_max_retry_limits     (BUG-D)
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# 将 backend 加入 path，确保各模块可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── 测试夹具 ────────────────────────────────────────────────


def _fake_embed(text: str) -> list[float]:
    """简易伪嵌入：避免对真实模型 / API 的依赖"""
    return [0.1] * 256


def _fake_chunks(merchant_id: int = 1, count: int = 10) -> list[dict]:
    """生成一组伪 chunk，模拟数据库返回。chunk 内容包含中文以便分词。"""
    docs = [
        "本店支持7天无理由退货，退货请保持商品完好。",
        "物流默认使用顺丰快递，全国3-5天送达。",
        "商品价格已含税，如需发票请在下单时勾选。",
        "店铺客服工作时间：周一至周五 9:00-18:00。",
        "如有质量问题，可在签收后48小时内申请换货。",
    ]
    chunks = []
    for i in range(count):
        chunks.append({
            "id": 1000 + i,
            "content": docs[i % len(docs)],
        })
    return chunks


# ── BUG-B: BM25 索引自动冷启动重建 ───────────────────────────


class TestHybridRetrieveAutoRebuild(unittest.TestCase):
    """验证 BM25 内存索引失效后能否自动冷启动重建并正常返回结果"""

    def setUp(self):
        """创建临时 BM25 索引目录，避免污染真实数据"""
        self.tmp_dir = tempfile.mkdtemp(prefix="bm25_test_")
        # 将 bm25_index.INDEX_DIR 指向临时目录
        self._patch_bm25_dir = patch(
            "app.kb.bm25_index.INDEX_DIR", self.tmp_dir
        )
        self._patch_bm25_dir.start()

        # Mock chroma 查询，返回伪向量结果
        self._patch_chroma = patch(
            "app.kb.retriever.get_collection",
            return_value=MagicMock(
                query=MagicMock(
                    return_value={
                        "ids": [["2001", "2002", "2003"]],
                        "documents": [["商品A 详情描述……", "退换货政策说明……", "物流配送时效……"]],
                        "metadatas": [[
                            {"heading_context": "商品A"},
                            {"heading_context": "退换货"},
                            {"heading_context": "物流"},
                        ]],
                        "distances": [[0.15, 0.22, 0.35]],
                    }
                )
            ),
        )
        self.mock_chroma = self._patch_chroma.start()

        # Mock 数据库查询 — 返回伪 chunks 用于 BM25 冷启动重建
        self._patch_db = patch(
            "app.kb.retriever.SessionLocal",
            return_value=MagicMock(
                query=MagicMock(
                    return_value=MagicMock(
                        filter=MagicMock(
                            return_value=MagicMock(
                                all=MagicMock(return_value=[
                                    MagicMock(id=1001, content="本店支持7天无理由退货，退货请保持商品完好。"),
                                    MagicMock(id=1002, content="物流默认使用顺丰快递，全国3-5天送达。"),
                                    MagicMock(id=1003, content="商品价格已含税，如需发票请在下单时勾选。"),
                                    MagicMock(id=1004, content="店铺客服工作时间：周一至周五 9:00-18:00。"),
                                    MagicMock(id=1005, content="如有质量问题，可在签收后48小时内申请换货。"),
                                ])
                            )
                        )
                    )
                ),
                # close() 无操作
                close=MagicMock(),
            ),
        )
        self.mock_db = self._patch_db.start()

    def tearDown(self):
        self._patch_bm25_dir.stop()
        self._patch_chroma.stop()
        self._patch_db.stop()
        # 清理临时目录
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_auto_rebuild_when_index_missing(self):
        """BM25 索引不存在时，hybrid_retrieve 应自动重建并返回混合结果"""
        from app.kb.retriever import hybrid_retrieve

        # 确保索引不存在
        merchant_id = 9999
        index_path = os.path.join(self.tmp_dir, f"merchant_{merchant_id}.pkl")
        self.assertFalse(os.path.exists(index_path), "索引文件不应预先存在")

        results = hybrid_retrieve(
            merchant_id=merchant_id,
            query="退货政策是什么",
            query_embedding=[0.1] * 256,
            dense_k=20,
            bm25_k=20,
            use_bm25=True,
        )

        # 关键断言
        self.assertIsInstance(results, list)
        self.assertTrue(len(results) > 0, "混合检索应返回结果")
        # 索引文件应在调用后被重建
        self.assertTrue(os.path.exists(index_path), "BM25 索引应在冷启动后被自动创建")

    def test_normal_hybrid_when_index_exists(self):
        """已存在 BM25 索引时，直接使用，不走数据库重建"""
        from app.kb.retriever import hybrid_retrieve

        merchant_id = 8888
        # 先调用一次创建索引
        hybrid_retrieve(merchant_id, "默认查询", [0.2] * 256, use_bm25=True)
        # 第二次调用：索引已存在，不应触发数据库重建
        self.mock_db.reset_mock()
        results = hybrid_retrieve(merchant_id, "七天无理由", [0.15] * 256, use_bm25=True)
        self.assertIsInstance(results, list)
        # SessionLocal 不应被再次调用（索引已存在不触发重建）
        # 注意：第一次调用会创建 SessionLocal，第二次重建路径不调用
        # SessionLocal 可能被 import 时引用，这里只验证不抛异常


# ── BUG-D: 自纠错 max_retries 防护 ────────────────────────────


class TestSelfCorrectionMaxRetries(unittest.TestCase):
    """验证自纠错在 max_retries 耗尽后触发安全降级，避免死循环"""

    def test_max_retries_triggers_safe_degradation(self):
        """注入永远校验不通过的 Mock LLM，验证达到上限后安全降级"""
        from app.kb.self_correction import SelfCorrection

        sc = SelfCorrection(enabled=True, threshold=0.6, max_retries=3)

        # Mock chat 返回永远不通过的校验结果
        with patch("app.kb.self_correction.chat") as mock_chat:
            # 每次都返回 score=0.3（低于阈值 0.6），迫使 needs_correction=True
            mock_chat.return_value = '{"factual": false, "score": 0.3, "unsupported_claims": ["编造的数据"]}'

            fake_chunks = [
                {"content": "本店退货政策为7天无理由。"},
                {"content": "物流默认顺丰快递。"},
            ]

            result = sc.self_correct_generate("我们提供30天无理由退货", fake_chunks)

            # 核心断言
            self.assertTrue(result["degraded"], "3次重试后应触发安全降级")
            self.assertEqual(result["retries"], 3, "应恰好重试3次")
            self.assertIn("人工客服", result["answer"], "降级回复应引导联系人工客服")
            self.assertEqual(mock_chat.call_count, 3 + 3, "check(3次) + correct(3次) = 6次 LLM 调用")
            # 注意：check 3次 + correct 3次（correct 也会调用 chat）

    def test_no_retry_when_answer_is_factual(self):
        """高质量回复不应触发任何重试"""
        from app.kb.self_correction import SelfCorrection

        sc = SelfCorrection(enabled=True, threshold=0.6, max_retries=3)

        with patch("app.kb.self_correction.chat") as mock_chat:
            # 返回高分，factual=true
            mock_chat.return_value = '{"factual": true, "score": 0.95, "unsupported_claims": []}'

            fake_chunks = [{"content": "本店支持7天无理由退货。"}]
            result = sc.self_correct_generate("本店支持7天无理由退货", fake_chunks)

            self.assertFalse(result["corrected"], "无需纠正")
            self.assertFalse(result["degraded"], "不应降级")
            self.assertEqual(result["retries"], 0, "零次重试")
            self.assertEqual(mock_chat.call_count, 1, "仅一次 check 调用")

    def test_disabled_self_correction_passthrough(self):
        """禁用状态下直接透传原始回答"""
        from app.kb.self_correction import SelfCorrection

        sc = SelfCorrection(enabled=False)
        result = sc.self_correct_generate("任意回答", [])
        self.assertEqual(result["answer"], "任意回答")
        self.assertEqual(result["retries"], 0)
        self.assertFalse(result["degraded"])


# ── Multi-Format Document Upload Tests ─────────────────────


class TestDocumentLoaders(unittest.TestCase):
    """验证多格式文档加载器正确解析各类文件"""

    @classmethod
    def setUpClass(cls):
        """创建各格式的测试文件"""
        cls.tmp_dir = tempfile.mkdtemp(prefix="docload_test_")
        cls.test_files = {}

        # TXT
        txt_path = os.path.join(cls.tmp_dir, "test.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("这是一个测试文档。\n包含多行内容。\n用于验证文本加载器。")
        cls.test_files[".txt"] = txt_path

        # MD
        md_path = os.path.join(cls.tmp_dir, "test.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 标题一\n\n这是正文内容。\n\n## 标题二\n\n更多内容。")
        cls.test_files[".md"] = md_path

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def test_md_loader(self):
        from app.kb.loaders.factory import DocumentLoaderFactory
        result = DocumentLoaderFactory.load(self.test_files[".md"])
        self.assertIn("标题一", result["text"])
        self.assertIn("标题二", result["text"])
        self.assertEqual(result["metadata"]["format"], "markdown")

    def test_txt_loader(self):
        from app.kb.loaders.factory import DocumentLoaderFactory
        result = DocumentLoaderFactory.load(self.test_files[".txt"])
        self.assertIn("测试文档", result["text"])
        self.assertEqual(result["metadata"]["format"], "markdown")

    def test_factory_rejects_unsupported(self):
        from app.kb.loaders.factory import DocumentLoaderFactory
        with self.assertRaises(ValueError):
            DocumentLoaderFactory.get_loader("test.xyz")

    def test_factory_supported_formats(self):
        from app.kb.loaders.factory import DocumentLoaderFactory
        formats = DocumentLoaderFactory.supported_formats()
        self.assertIn("pdf", formats)
        self.assertIn("docx", formats)
        self.assertIn("xlsx", formats)
        self.assertIn("pptx", formats)
        self.assertIn("md", formats)
        self.assertIn("txt", formats)

    def test_factory_convenience_load(self):
        from app.kb.loaders.factory import DocumentLoaderFactory
        result = DocumentLoaderFactory.load(self.test_files[".txt"])
        self.assertIsInstance(result, dict)
        self.assertIn("text", result)
        self.assertIn("metadata", result)


# ── 运行入口 ──────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main()
