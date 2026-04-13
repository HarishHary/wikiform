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
    (tmp_path / "scripts").mkdir()
    (tmp_path / "SCHEMA.md").write_text(SCHEMA_MD, encoding="utf-8")
    return tmp_path
