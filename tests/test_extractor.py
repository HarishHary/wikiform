from __future__ import annotations

from pathlib import Path

import pytest

from wikiform.utils import extractor
from wikiform.utils.extractor import BinaryExtractor, extract_text, fetch_url


def test_fetch_url_rejects_non_http_scheme():
    with pytest.raises(ValueError, match="scheme"):
        fetch_url("file:///etc/passwd")


def test_unknown_extension_falls_back_to_binary_metadata(tmp_path: Path):
    f = tmp_path / "blob.xyz"
    f.write_bytes(b"\x00\x01\x02")
    assert "Binary file: blob.xyz" in extract_text(f)
    assert "3 bytes" in BinaryExtractor().extract(f)


def test_importing_extractor_does_not_load_heavy_dependencies():
    import subprocess
    import sys

    code = "import sys, wikiform.utils.extractor; heavy = {'markitdown', 'trafilatura', 'opendataloader_pdf'}; sys.exit(1 if heavy & set(sys.modules) else 0)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def test_markitdown_is_built_once(monkeypatch: pytest.MonkeyPatch):
    calls: list[int] = []

    class Fake:
        def __init__(self) -> None:
            calls.append(1)

    monkeypatch.setitem(__import__("sys").modules, "markitdown", type("M", (), {"MarkItDown": Fake}))
    extractor._markitdown.cache_clear()
    extractor._markitdown()
    extractor._markitdown()
    extractor._markitdown.cache_clear()
    assert len(calls) == 1
