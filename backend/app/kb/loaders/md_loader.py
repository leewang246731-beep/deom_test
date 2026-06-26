"""Markdown + TXT Loader."""
from app.kb.loaders.base_loader import BaseDocumentLoader, LoadedDocument


class MarkdownLoader(BaseDocumentLoader):
    @staticmethod
    def supported_extensions() -> list[str]:
        return [".md", ".markdown", ".txt", ".text", ".rst"]

    def load(self, file_path: str) -> LoadedDocument:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        # Extract headings as metadata markers
        import re
        headings = re.findall(r'^#{1,3}\s+(.+)$', text, re.MULTILINE)

        return LoadedDocument(
            text=text,
            metadata={
                "source": file_path,
                "format": "markdown",
                "headings": headings[:20],
            },
        )
