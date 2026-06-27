"""CRAG (Corrective RAG)：评估 → 判决 → 校正动作（含 Web 搜索降级）"""
import json
import logging
import re
from typing import Callable
from urllib.request import Request, urlopen
from urllib.error import URLError

logger = logging.getLogger(__name__)

# ── 内容清洗工具 ────────────────────────────────────────────

def strip_html(text: str) -> str:
    """移除 HTML 标签，保留纯文本"""
    clean = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', text, flags=re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<[^>]+>', '', clean)
    clean = re.sub(r'\s+', ' ', clean)
    return clean.strip()


def token_truncate(text: str, max_tokens: int = 800) -> str:
    """按字符数粗略截断（中文约 1 字 = 1 token，英文约 4 字符 = 1 token）"""
    # 保守估计：取 2 倍 max_tokens 字符数，确保不超过 token 限制
    max_chars = max_tokens * 2
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


# ── Web 搜索降级 ────────────────────────────────────────────

def web_search_fallback(query: str, top_k: int = 3) -> list[dict]:
    """Web 搜索降级：当知识库无相关内容时，尝试从公开网络抓取摘要。

    对抓取内容执行 strip_html + token_truncate(max=800) 清洗，
    防止 HTML 标签污染 Prompt 或原始页面过长导致上下文溢出。
    """
    results = []
    try:
        # 使用 DuckDuckGo 非 JS 端点（GET 请求，无需 API Key）
        encoded = query.replace(" ", "+")
        search_url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = Request(search_url, headers={"User-Agent": "CragEvaluator/1.0"})
        with urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # 简易解析：提取 class="result__snippet" 的内容
        snippet_pattern = re.compile(
            r'class="result__snippet"[^>]*>(.*?)</a>', re.DOTALL
        )
        snippets = snippet_pattern.findall(html)
        for i, snip in enumerate(snippets[:top_k]):
            cleaned = token_truncate(strip_html(snip), max_tokens=800)
            if len(cleaned) > 20:
                results.append({
                    "chunk_id": -(i + 1),  # 负 ID 区分来源
                    "content": cleaned,
                    "meta": {"source": "web_search", "query": query},
                    "dense_score": 0.0,
                    "fusion_score": 0.0,
                })
        if results:
            logger.info("Web search fallback returned %d snippets for query: %s", len(results), query[:80])
    except URLError as e:
        logger.warning("Web search fallback failed: %s", e)
    except Exception:
        logger.exception("Web search fallback unexpected error")

    return results


# ── CRAG 评估器 ─────────────────────────────────────────────

class CragEvaluator:
    def __init__(self, llm_fn: Callable[[str, str], str] | None = None):
        self.llm = llm_fn

    def evaluate(self, query: str, top_chunks: list[dict]) -> dict:
        """对 Top-5 chunks 做 LLM 相关性评估，返回 CRAG 判决"""
        if not top_chunks:
            return {"verdict": "no_context", "relevant": [], "irrelevant": []}

        if not self.llm:
            return {"verdict": "all_relevant", "relevant": [c["chunk_id"] for c in top_chunks], "irrelevant": []}

        ctx = "\n\n".join(f"[{i+1}] {c['content'][:300]}" for i, c in enumerate(top_chunks[:5]))
        prompt = (
            f"评估以下检索到的文档片段与问题的相关性。\n"
            f"问题: {query}\n\n"
            f"片段:\n{ctx}\n\n"
            f"对每个片段，标记为 relevant 或 irrelevant。输出 JSON 数组: [{{\"id\": 数字, \"verdict\": \"relevant|irrelevant\"}}]"
        )
        try:
            resp = self.llm(prompt, "crag").strip()
            verdicts = _parse_verdicts(resp, top_chunks)
        except Exception:
            verdicts = [{"id": i+1, "verdict": "relevant"} for i in range(len(top_chunks[:5]))]

        relevant = [top_chunks[v["id"]-1]["chunk_id"] for v in verdicts if v["verdict"] == "relevant" and v["id"]-1 < len(top_chunks)]
        irrelevant = [top_chunks[v["id"]-1]["chunk_id"] for v in verdicts if v["verdict"] == "irrelevant" and v["id"]-1 < len(top_chunks)]

        if not relevant:
            return {"verdict": "no_relevant", "relevant": [], "irrelevant": irrelevant}

        return {"verdict": "partial", "relevant": relevant, "irrelevant": irrelevant}

    def evaluate_with_fallback(self, query: str, top_chunks: list[dict], web_search: bool = False) -> dict:
        """评估 + Web 降级：当知识库无相关内容时自动触发 Web 搜索。

        Web 搜索结果经过 strip_html + token_truncate(max=800) 清洗，
        避免 HTML 标签污染或上下文溢出。
        """
        result = self.evaluate(query, top_chunks)

        if result["verdict"] in ("no_context", "no_relevant") and web_search:
            logger.info("CRAG verdict=%s, triggering web search fallback", result["verdict"])
            web_chunks = web_search_fallback(query)
            if web_chunks:
                result["verdict"] = "partial"
                result["relevant"] = [c["chunk_id"] for c in web_chunks]
                result["web_fallback"] = True
                result["web_chunks"] = web_chunks
            else:
                result["web_fallback"] = False

        return result


def _parse_verdicts(resp: str, top_chunks: list[dict]) -> list[dict]:
    """从 LLM 响应中解析判决 JSON"""
    match = re.search(r'\[[\s\S]*\]', resp)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return [{"id": i+1, "verdict": "relevant"} for i in range(len(top_chunks[:5]))]
