"""TokenTextSplitter：句子感知切分 + 标题上下文注入"""
import re

DEFAULT_CHUNK_SIZE = 384
DEFAULT_OVERLAP = 48


def estimate_tokens(text: str) -> int:
    """中文按字符数  1.3 ≈ token 数"""
    return int(len(text) / 1.3)


class TokenTextSplitter:
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str, heading: str = "") -> list[dict]:
        if not text:
            return []

        # 句子切分: 中文句号/问号/叹号/换行
        sentences = re.split(r'(?<=[。！？\n])\s*', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        buffer = ""
        idx = 0
        for sent in sentences:
            candidate = (buffer + " " + sent).strip() if buffer else sent
            if estimate_tokens(candidate) > self.chunk_size and buffer:
                content = buffer.strip()
                if heading:
                    content = f"[{heading}] {content}"
                chunks.append({"content": content, "token_count": estimate_tokens(content), "heading_context": heading})
                buffer = sent
                idx += 1
            else:
                buffer = candidate

        if buffer.strip():
            content = buffer.strip()
            if heading:
                content = f"[{heading}] {content}"
            chunks.append({"content": content, "token_count": estimate_tokens(content), "heading_context": heading})

        return chunks


def inject_heading_context(chunks: list[dict], heading: str) -> list[dict]:
    """为已切分的 chunks 批量注入标题上下文"""
    for c in chunks:
        if heading and heading not in (c.get("heading_context") or ""):
            c["heading_context"] = heading
            if not c["content"].startswith(f"[{heading}]"):
                c["content"] = f"[{heading}] {c['content']}"
    return chunks
