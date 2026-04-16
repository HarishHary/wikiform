from __future__ import annotations

import contextlib
import io
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

import opendataloader_pdf
from loguru import logger
from markitdown import MarkItDown

logger = logger.bind(service="Wikiform - Extractor")

_REGISTRY: dict[str, Extractor] = {}
_md = MarkItDown()


@runtime_checkable
class Extractor(Protocol):
    def extract(self, path: Path) -> str:
        """Extract text content from the given file path."""
        ...


def handles(*extensions: str):
    """Class decorator that registers an extractor for the given file extensions."""
    def decorator(cls: type) -> type:
        instance = cls()
        for ext in extensions:
            _REGISTRY[ext.lower()] = instance
        return cls
    return decorator


@handles(".pdf")
class PDFExtractor:
    def __init__(self) -> None:
        try:
            subprocess.run(["java", "-version"], capture_output=True, timeout=5, check=True)
            self._java_available = True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            self._java_available = False
            logger.warning("Java not found — PDF extraction will use markitdown fallback")

    def extract(self, path: Path) -> str:
        if self._java_available:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                opendataloader_pdf.convert(
                    input_path=str(path),
                    format="markdown",
                    to_stdout=True,
                    quiet=True,
                )
            return buf.getvalue()
        return _md.convert(str(path)).text_content


@handles(
    ".docx", ".dotx", ".xlsx", ".xltx", ".pptx",
    ".txt", ".md", ".py", ".sql", ".js", ".ts", ".csv",
    ".json", ".yaml", ".yml", ".toml", ".html", ".xml",
    ".bat", ".ps1", ".sh", ".go", ".rs", ".rb", ".java",
    ".c", ".cpp", ".h", ".epub", ".zip",
)
class MarkItDownExtractor:
    def extract(self, path: Path) -> str:
        return _md.convert(str(path)).text_content


class BinaryExtractor:
    def extract(self, path: Path) -> str:
        size = path.stat().st_size
        return f"[Binary file: {path.name}, size: {size:,} bytes — no text extracted]"


def extract_text(path: Path) -> str:
    """Dispatch to the registered extractor for this file extension."""
    extractor = _REGISTRY.get(path.suffix.lower(), BinaryExtractor())
    return extractor.extract(path)
