"""Document Loader Factory — returns the correct loader by file extension."""
import os
from app.kb.loaders.base_loader import BaseDocumentLoader


# Map extension → loader class (lazy import to avoid import errors)
_LOADER_REGISTRY = {
    ".pdf": "app.kb.loaders.pdf_loader.PDFLoader",
    ".docx": "app.kb.loaders.docx_loader.DocxLoader",
    ".doc": "app.kb.loaders.docx_loader.DocxLoader",
    ".xlsx": "app.kb.loaders.xlsx_loader.XlsxLoader",
    ".xls": "app.kb.loaders.xlsx_loader.XlsxLoader",
    ".pptx": "app.kb.loaders.pptx_loader.PptxLoader",
    ".ppt": "app.kb.loaders.pptx_loader.PptxLoader",
    ".md": "app.kb.loaders.md_loader.MarkdownLoader",
    ".markdown": "app.kb.loaders.md_loader.MarkdownLoader",
    ".txt": "app.kb.loaders.md_loader.MarkdownLoader",
    ".text": "app.kb.loaders.md_loader.MarkdownLoader",
    ".rst": "app.kb.loaders.md_loader.MarkdownLoader",
}


class DocumentLoaderFactory:
    """根据文件扩展名返回对应的 Loader 实例。"""

    @staticmethod
    def get_loader(file_path: str) -> BaseDocumentLoader:
        ext = os.path.splitext(file_path)[1].lower()
        loader_path = _LOADER_REGISTRY.get(ext)

        if not loader_path:
            supported = ", ".join(sorted(set(_LOADER_REGISTRY.values())))
            raise ValueError(f"Unsupported file type '{ext}'. Supported: {supported}")

        # Lazy import
        module_path, class_name = loader_path.rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        loader_class = getattr(module, class_name)
        return loader_class()

    @staticmethod
    def supported_formats() -> list[str]:
        return sorted(set(ext.lstrip(".") for ext in _LOADER_REGISTRY))

    @staticmethod
    def load(file_path: str) -> dict:
        """便捷方法：加载文件并返回 dict {text, metadata}。"""
        loader = DocumentLoaderFactory.get_loader(file_path)
        doc = loader.load(file_path)
        return {
            "text": doc.text,
            "metadata": doc.metadata,
            "pages": doc.pages if hasattr(doc, 'pages') else [],
        }
