"""
Smart Chunker — tiktoken-based token-precise chunking.

Replaces the old char-based TokenTextSplitter (len/1.3 heuristic)
with tiktoken cl100k_base encoding for exact token control.
Adapted from D:/project_test/backend/rag/splitter.py (no LlamaIndex dependency).
"""
import re
from typing import Optional

try:
    import tiktoken
    _TOKENIZER = tiktoken.encoding_for_model("gpt-3.5-turbo")
except ImportError:
    _TOKENIZER = None


# Sentence boundary separators (Chinese + English)
_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; "]


class SmartChunker:
    """tiktoken-based smart chunker with heading injection."""

    def __init__(self, chunk_size: int = 384, chunk_overlap: int = 48):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _count_tokens(self, text: str) -> int:
        if _TOKENIZER:
            return len(_TOKENIZER.encode(text))
        # Fallback: rough estimate for Chinese
        return int(len(text) / 1.3)

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences at natural boundaries."""
        pattern = "(" + "|".join(re.escape(s) for s in _SEPARATORS) + ")"
        parts = re.split(pattern, text)
        sentences = []
        buf = ""
        for part in parts:
            buf += part
            if any(part.endswith(s) for s in ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; "]):
                if buf.strip():
                    sentences.append(buf.strip())
                buf = ""
        if buf.strip():
            sentences.append(buf.strip())
        return sentences or [text]

    def chunk(self, text: str, document_title: str = "") -> list[dict]:
        """
        Chunk text into token-sized pieces.

        Returns: [{"content": str, "chunk_index": int, "token_count": int, "heading_context": str}, ...]
        """
        sentences = self._split_sentences(text)
        chunks = []
        current_chunk = []
        current_tokens = 0
        heading_prefix = f"[{document_title}]\n" if document_title else ""

        for sent in sentences:
            sent_tokens = self._count_tokens(sent)

            if current_tokens + sent_tokens > self.chunk_size and current_chunk:
                # Flush current chunk
                content = heading_prefix + "".join(current_chunk)
                chunks.append({
                    "content": content,
                    "chunk_index": len(chunks),
                    "token_count": self._count_tokens(content),
                    "heading_context": document_title or "",
                })
                # Keep overlap: last sentence becomes start of next chunk
                overlap_start = max(0, len(current_chunk) - 1)
                current_chunk = current_chunk[overlap_start:]
                current_tokens = self._count_tokens("".join(current_chunk))

            current_chunk.append(sent)
            current_tokens += sent_tokens

        # Flush remaining
        if current_chunk:
            content = heading_prefix + "".join(current_chunk)
            chunks.append({
                "content": content,
                "chunk_index": len(chunks),
                "token_count": self._count_tokens(content),
                "heading_context": document_title or "",
            })

        return chunks

    def chunk_with_metadata(self, text: str, document_title: str = "",
                            source_file: str = "", format: str = "") -> list[dict]:
        """Chunk with extra metadata for ChromaDB storage."""
        chunks = self.chunk(text, document_title)
        for c in chunks:
            c["source_file"] = source_file
            c["format"] = format
            c["title"] = document_title
        return chunks
