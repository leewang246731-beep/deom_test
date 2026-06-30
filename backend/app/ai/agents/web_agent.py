"""WebSearchAgent — 联网搜索专家（知识库无结果时的补充信息源）"""
from app.ai.agents.base_agent import BaseExpertAgent
from app.ai.tool_registry import ToolRegistry
from langchain_core.tools import tool


class WebSearchAgent(BaseExpertAgent):
    name = "web"
    description = "联网搜索公开信息，补充知识库之外的答案"

    def _build_tools(self) -> list:
        mid = self.merchant_id
        registry = ToolRegistry.get()

        # 从 registry 获取共享的 web_search 工具
        ws = registry.get_tool("web_search")
        tools = [ws] if ws else []

        @tool
        def fetch_page_content(url: str) -> str:
            """抓取指定网页的文本内容。url 为完整网址。返回页面摘要（最多500字）。"""
            import re
            import urllib.request
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    html = resp.read().decode("utf-8", errors="replace")
                # 去除 script/style 标签
                html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
                # 提取可见文本
                text = re.sub(r'<[^>]+>', ' ', html)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:500] if text else "页面无文本内容"
            except Exception as e:
                return f"抓取失败: {e}"

        tools.append(fetch_page_content)
        return tools

    def _build_prompt(self) -> str:
        return f"""你是联网搜索专家。当商品知识库、订单系统等内部数据源无法回答买家问题时，
你可以通过 web_search 搜索公开网页获取补充信息，或通过 fetch_page_content 深入抓取具体网页。

{self.role_prompt}

规则：
- 优先尝试内部工具（如 search_product_kb），无结果时再用联网搜索
- 引用搜索结果时说明来源
- 搜索结果不代表官方信息，语气要谨慎（"根据公开信息…"）
- 回复简洁（<300字）"""
