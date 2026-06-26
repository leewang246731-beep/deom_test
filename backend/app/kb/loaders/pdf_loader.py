"""PDF Loader — using pypdf (lightweight, no LlamaIndex dependency)."""
from app.kb.loaders.base_loader import BaseDocumentLoader, LoadedDocument


class PDFLoader(BaseDocumentLoader):
    @staticmethod
    def supported_extensions() -> list[str]:
        return [".pdf"]

    def load(self, file_path: str) -> LoadedDocument:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("pypdf not installed. Run: pip install pypdf")

        reader = PdfReader(file_path)
        pages = []
        full_text = []

        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"page_num": i + 1, "text": text.strip()})
                full_text.append(text.strip())

        metadata = {
            "total_pages": len(reader.pages),
            "source": file_path,
            "format": "pdf",
        }
        if reader.metadata:
            metadata["title"] = reader.metadata.get("title", "")
            metadata["author"] = reader.metadata.get("author", "")

        return LoadedDocument(
            text="\n\n".join(full_text),
            metadata=metadata,
            pages=pages,
        )
