from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.conftest import FakeEmbedder, write_page
from wikiform.cmd.embed import run_embed
from wikiform.cmd.fts_index import run_fts_index
from wikiform.cmd.query import run_query, run_semantic_query
from wikiform.utils.db import get_connection
from wikiform.utils.vec_db import load_sqlite_vec

pytestmark = pytest.mark.usefixtures("fake_embedder")


@pytest.fixture(autouse=True)
def _require_loadable_sqlite_extensions():
    if not hasattr(sqlite3.connect(":memory:"), "enable_load_extension"):
        pytest.skip("sqlite3 built without loadable extension support")


def _page(vault: Path, name: str, title: str, tags: str, body: str) -> None:
    write_page(vault, name, f"---\ntitle: {title}\ntags: [{tags}]\nupdated: 2024-01-01\n---\n{body}\n")


def _index_and_embed(vault: Path, **kw) -> object:
    run_fts_index(vault, incremental=False)
    return run_embed(vault, model="fake-model", incremental=kw.get("incremental", False), reset=kw.get("reset", False))


def _vec_count(vault: Path) -> int:
    db = get_connection(vault)
    try:
        load_sqlite_vec(db)
        return db.execute("SELECT COUNT(*) FROM articles_vec").fetchone()[0]
    finally:
        db.close()


# ─── embed ────────────────────────────────────────────────────────────────────

def test_embed_creates_one_vector_per_chunk(vault: Path):
    _page(vault, "short.md", "Short", "a", "tiny body")
    _page(vault, "long.md", "Long", "a", "\n\n".join("paragraph " + "word " * 100 for _ in range(10)))
    result = _index_and_embed(vault)
    assert result.embedded == 2
    assert _vec_count(vault) > 2  # the long page produced several chunks


def test_incremental_embed_skips_unchanged(vault: Path):
    _page(vault, "p.md", "P", "a", "same text")
    _index_and_embed(vault)
    result = run_embed(vault, model="fake-model", incremental=True, reset=False)
    assert (result.embedded, result.skipped) == (0, 1)


def test_incremental_embed_refreshes_changed_article(vault: Path):
    """Regression: edited pages used to keep their stale vector under --incremental."""
    _page(vault, "p.md", "P", "a", "apples oranges")
    _index_and_embed(vault)
    query = "completely different words here"
    distance_before = run_semantic_query(vault, query, limit=1)[0].rank
    _page(vault, "p.md", "P", "a", query)
    run_fts_index(vault, incremental=False)
    result = run_embed(vault, model="fake-model", incremental=True, reset=False)
    assert (result.embedded, result.skipped) == (1, 0)
    assert run_semantic_query(vault, query, limit=1)[0].rank < distance_before


def test_incremental_embed_does_not_reuse_vector_for_recycled_article_id(vault: Path):
    """Regression: SQLite may reuse a deleted article's id for a new article."""
    _page(vault, "old.md", "Old", "a", "old content alpha")
    _index_and_embed(vault)
    (vault / "wiki" / "pages" / "old.md").unlink()
    _page(vault, "new.md", "New", "a", "brand new content beta")
    run_fts_index(vault, incremental=False)
    result = run_embed(vault, model="fake-model", incremental=True, reset=False)
    assert result.embedded == 1 and result.skipped == 0 and result.deleted == 1


def test_embed_removes_vectors_of_deleted_articles(vault: Path):
    _page(vault, "a.md", "A", "x", "one")
    _page(vault, "b.md", "B", "x", "two")
    _index_and_embed(vault)
    before = _vec_count(vault)
    (vault / "wiki" / "pages" / "b.md").unlink()
    run_fts_index(vault, incremental=False)
    result = run_embed(vault, model="fake-model", incremental=True, reset=False)
    assert result.deleted == 1
    assert _vec_count(vault) < before


def test_embed_model_change_without_reset_is_rejected(vault: Path):
    _page(vault, "p.md", "P", "a", "text")
    _index_and_embed(vault)
    with pytest.raises(ValueError, match="--reset"):
        run_embed(vault, model="other-model", incremental=False, reset=False)
    run_embed(vault, model="other-model", incremental=False, reset=True)


def test_embed_without_index_raises_helpful_error(vault: Path):
    with pytest.raises(ValueError, match="search index"):
        run_embed(vault, model="fake-model", incremental=False, reset=False)


def test_legacy_vector_table_is_rebuilt(vault: Path):
    _page(vault, "p.md", "P", "a", "text")
    run_fts_index(vault, incremental=False)
    db = get_connection(vault)
    load_sqlite_vec(db)
    db.execute("CREATE VIRTUAL TABLE articles_vec USING vec0(embedding float[768])")
    db.commit()
    db.close()
    result = run_embed(vault, model="fake-model", incremental=False, reset=False)
    assert result.embedded == 1


# ─── semantic query ───────────────────────────────────────────────────────────

def test_semantic_query_returns_one_result_per_article(vault: Path):
    _page(vault, "long.md", "Long", "a", "\n\n".join("paragraph " + "word " * 100 for _ in range(10)))
    _page(vault, "other.md", "Other", "a", "something else entirely")
    _index_and_embed(vault)
    paths = [r.path for r in run_semantic_query(vault, "paragraph word", limit=10)]
    assert len(paths) == len(set(paths)) == 2


def test_semantic_query_applies_tag_and_dir_filters(vault: Path):
    _page(vault, "ml.md", "ML", "machine-learning", "neural networks")
    _page(vault, "web.md", "Web", "html", "neural networks")
    _index_and_embed(vault)
    only_ml = run_semantic_query(vault, "neural networks", tag="machine-learning", limit=10)
    assert [r.title for r in only_ml] == ["ML"]
    assert run_semantic_query(vault, "neural networks", directory="nowhere/", limit=10) == []


def test_semantic_query_uses_model_stored_at_embed_time(vault: Path, monkeypatch: pytest.MonkeyPatch):
    seen: list[str] = []

    class Spy(FakeEmbedder):
        def __init__(self, model_name: str = "fake-model") -> None:
            seen.append(model_name)
            super().__init__(model_name)

    monkeypatch.setattr("wikiform.cmd.embed.Embedder", Spy)
    monkeypatch.setattr("wikiform.cmd.query.Embedder", Spy)
    _page(vault, "p.md", "P", "a", "text")
    run_fts_index(vault, incremental=False)
    run_embed(vault, model="custom/model-x", incremental=False, reset=False)
    run_semantic_query(vault, "text")
    assert seen == ["custom/model-x", "custom/model-x"]


def test_semantic_query_on_legacy_table_asks_for_reset(vault: Path):
    _page(vault, "p.md", "P", "a", "text")
    run_fts_index(vault, incremental=False)
    db = get_connection(vault)
    load_sqlite_vec(db)
    db.execute("CREATE VIRTUAL TABLE articles_vec USING vec0(embedding float[768])")
    db.commit()
    db.close()
    with pytest.raises(ValueError, match="--reset"):
        run_semantic_query(vault, "text")


# ─── FTS tag filter ───────────────────────────────────────────────────────────

def test_fts_tag_filter_matches_whole_tag_only(vault: Path):
    """Regression: --tag ml used to match 'html' via LIKE %ml%."""
    _page(vault, "ml.md", "ML", "ml", "common word")
    _page(vault, "web.md", "Web", "html, css", "common word")
    run_fts_index(vault, incremental=False)
    assert [r.title for r in run_query(vault, "common", tag="ml")] == ["ML"]
    assert [r.title for r in run_query(vault, "common", tag="HTML")] == ["Web"]
