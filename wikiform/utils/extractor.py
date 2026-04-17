from __future__ import annotations

import contextlib
import io
import subprocess
from html.parser import HTMLParser
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable

import opendataloader_pdf
import requests
import trafilatura
from loguru import logger
from markitdown import MarkItDown

logger = logger.bind(service="Wikiform - Extractor")

_REGISTRY: dict[str, Extractor] = {}
_md = MarkItDown()
_C = TypeVar("_C")


class HTMLTextStripper(HTMLParser):
    """Stdlib HTML parser that skips non-content blocks and collects plain text."""
    _SKIP_TAGS: frozenset[str] = frozenset({
        "script", "style", "head", "noscript", "svg", "math",
        "canvas", "template", "iframe",
    })

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self._parts)


@runtime_checkable
class Extractor(Protocol):
    def extract(self, path: Path) -> str:
        """Extract text content from the given file path."""
        ...


def handles(*extensions: str) -> Callable[[type[_C]], type[_C]]:
    """Class decorator that registers an extractor for the given file extensions."""
    def decorator(cls: type[_C]) -> type[_C]:
        instance = cls()  # type: ignore[call-arg]
        for ext in extensions:
            _REGISTRY[ext.lower()] = instance  # type: ignore[arg-type]
        return cls
    return decorator


@handles(".pdf")
class PDFExtractor:
    def __init__(self) -> None:
        self._java_available: bool | None = None

    def _check_java(self) -> bool:
        if self._java_available is None:
            try:
                subprocess.run(["java", "-version"], capture_output=True, timeout=5, check=True)
                self._java_available = True
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                self._java_available = False
                logger.warning("Java not found — PDF extraction will use markitdown fallback")
        return self._java_available

    def extract(self, path: Path) -> str:
        if self._check_java():
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


@handles(".html", ".htm")
class HTMLExtractor:
    def extract(self, path: Path) -> str:
        html = path.read_text(encoding="utf-8", errors="replace")
        result = trafilatura.extract(html, output_format="markdown", include_tables=True, include_comments=False)
        return result or _md.convert(str(path)).text_content


@handles(
    ".docx", ".dotx", ".xlsx", ".xltx", ".pptx",
    ".txt", ".md", ".py", ".sql", ".js", ".ts", ".csv",
    ".json", ".yaml", ".yml", ".toml", ".xml",
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


def fetch_url(url: str) -> tuple[str, str]:
    """Fetch a URL and extract its main content.

    Returns (title, markdown_content). Title falls back to the URL if not found.
    """
    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    html = response.text
    metadata = trafilatura.extract_metadata(html)
    title = (metadata.title if metadata and metadata.title else None) or url

    content = trafilatura.extract(html, output_format="markdown", include_images=True, include_tables=True, include_comments=False, favor_recall=True)

    if not content:
        content = trafilatura.extract(html, output_format="markdown", include_images=True, include_tables=True, include_comments=False, favor_precision=True)

    if not content:
        logger.warning("trafilatura returned empty content, falling back to html stripper for {}", url)
        stripper = HTMLTextStripper()
        stripper.feed(html)
        content = stripper.get_text()

    if not content:
        logger.warning("html stripper returned empty content, falling back to markitdown for {}", url)
        content = _md.convert(url).text_content

    return title, content or ""
