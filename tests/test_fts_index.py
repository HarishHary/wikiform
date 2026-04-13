from __future__ import annotations

import time
from pathlib import Path

from wikiform.cmd.fts_index import FtsIndexResult, _parse_md, run_fts_index
from wikiform.utils.db import get_connection, init_db


# ─── _parse_md ────────────────────────────────────────────────────────────────

def test_parse_md_with_frontmatter(tmp_path: Path):
    f = tmp_path / "page.md"
    f.write_text("---\ntitle: Hello\ntags: [python, testing]\nupdated: 2024-01-01\n---\nBody.", encoding="utf-8")
    result = _parse_md(f)
    assert result.title == "Hello"
    assert "python" in result.tags
    assert result.updated == "2024-01-01"
    assert result.content.strip() == "Body."


def test_parse_md_no_frontmatter_uses_stem(tmp_path: Path):
    f = tmp_path / "my-note.md"
    f.write_text("Just content here.", encoding="utf-8")
    result = _parse_md(f)
    assert result.title == "my-note"
    assert result.tags == ""


def test_parse_md_tags_joined_csv(tmp_path: Path):
    f = tmp_path / "page.md"
    f.write_text("---\ntags: [a, b, c]\n---\n", encoding="utf-8")
    result = _parse_md(f)
    assert result.tags == "a, b, c"


# ─── run_fts_index ────────────────────────────────────────────────────────────

def test_run_fts_index_indexes_files(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "my-page.md", "---\ntitle: My Page\ntags: [python]\nupdated: 2024-01-01\n---\nContent here.")
    result = run_fts_index(vault, incremental=False)
    assert isinstance(result, FtsIndexResult)
    assert result.indexed >= 1
    assert result.total >= 1


def test_run_fts_index_full_reindex(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "page.md", "---\ntitle: Page\ntags: []\nupdated: 2024-01-01\n---\nContent.")
    run_fts_index(vault, incremental=False)
    result = run_fts_index(vault, incremental=False)
    assert result.indexed >= 1
    assert result.skipped == 0


def test_run_fts_index_incremental_skips_unchanged(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "page.md", "---\ntitle: Page\ntags: []\nupdated: 2024-01-01\n---\nContent.")
    run_fts_index(vault, incremental=False)
    result = run_fts_index(vault, incremental=True)
    assert result.skipped >= 1
    assert result.indexed == 0


def test_run_fts_index_deletes_stale_entries(vault: Path):
    from tests.conftest import write_page
    p = write_page(vault, "temp.md", "---\ntitle: Temp\ntags: []\nupdated: 2024-01-01\n---\n")
    run_fts_index(vault, incremental=False)
    p.unlink()
    result = run_fts_index(vault, incremental=False)
    assert result.deleted >= 1


def test_run_fts_index_result_fields(vault: Path):
    result = run_fts_index(vault, incremental=False)
    assert result.vault_root == str(vault)
    assert result.incremental is False
    assert result.generated_at != ""
