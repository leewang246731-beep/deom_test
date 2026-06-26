"""Abstract base class for document loaders."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LoadedDocument:
    """Parsed document with metadata."""
    text: str
    metadata: dict = field(default_factory=dict)
    pages: list[dict] = field(default_factory=list)  # [{page_num, text}]


class BaseDocumentLoader(ABC):
    """所有文档加载器的抽象基类。"""

    @abstractmethod
    def load(self, file_path: str) -> LoadedDocument:
        """解析文件，返回 LoadedDocument。"""
        ...

    @staticmethod
    def supported_extensions() -> list[str]:
        """返回支持的扩展名列表。"""
        return []
