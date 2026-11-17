from __future__ import annotations

from pathlib import Path

import pytest


SCHEMA_MD = """\
## Index Categories
- Engineering
- Research
- Uncategorised

## Wiki Page Frontmatter
```yaml
title: ""
tags: []
updated: ""
```
"""


def write_page(vault: Path, name: str, content: str) -> Path:
    """Write a markdown file into wiki/pages/."""
    p = vault / "wiki" / "pages" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def write_raw(vault: Path, name: str, content: str) -> Path:
    """Write a markdown file into raw/."""
    p = vault / "raw" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Minimal vault with SCHEMA.md and required directories."""
    (tmp_path / "wiki" / "pages").mkdir(parents=True)
    (tmp_path / "raw").mkdir()
    (tmp_path / "_meta").mkdir()
    (tmp_path / "SCHEMA.md").write_text(SCHEMA_MD, encoding="utf-8")
    return tmp_path


class FakeEmbedder:
    """Deterministic bag-of-words embedder (8 dims) so vector tests need no model download."""

    DIM = 8

    def __init__(self, model_name: str = "fake-model") -> None:
        self.model_name = model_name

    @property
    def dimension(self) -> int:
        return self.DIM

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.DIM
        for word in text.lower().split():
            vec[sum(map(ord, word.strip(".,"))) % self.DIM] += 1.0
        return vec

    def embed_many(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        return self.embed(query)


@pytest.fixture
def fake_embedder(monkeypatch: pytest.MonkeyPatch) -> type[FakeEmbedder]:
    monkeypatch.setattr("wikiform.cmd.embed.Embedder", FakeEmbedder)
    monkeypatch.setattr("wikiform.cmd.query.Embedder", FakeEmbedder)
    return FakeEmbedder
