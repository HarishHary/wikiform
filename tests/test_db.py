from __future__ import annotations

import sqlite3
from pathlib import Path

from wikiform.utils.db import (
    db_path,
    get_connection,
    init_db,
    sanitize_fts_query,
)


# ─── db_path ──────────────────────────────────────────────────────────────────

def test_db_path_location(tmp_path: Path):
    result = db_path(tmp_path)
    assert result == tmp_path / "_meta" / "vault-search.db"


# ─── get_connection ───────────────────────────────────────────────────────────

def test_get_connection_creates_parent_dir(tmp_path: Path):
    db = get_connection(tmp_path)
    db.close()
    assert (tmp_path / "_meta").is_dir()


def test_get_connection_returns_row_factory(tmp_path: Path):
    db = get_connection(tmp_path)
    assert db.row_factory is sqlite3.Row
    db.close()


# ─── init_db ──────────────────────────────────────────────────────────────────

def test_init_db_creates_articles_table(tmp_path: Path):
    db = get_connection(tmp_path)
    init_db(db)
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='articles'"
    ).fetchone()
    assert row is not None
    db.close()


def test_init_db_creates_fts_table(tmp_path: Path):
    db = get_connection(tmp_path)
    init_db(db)
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='articles_fts'"
    ).fetchone()
    assert row is not None
    db.close()


def test_init_db_idempotent(tmp_path: Path):
    db = get_connection(tmp_path)
    init_db(db)
    init_db(db)  # second call must not raise
    db.close()


# ─── sanitize_fts_query ───────────────────────────────────────────────────────

def test_sanitize_fts_query_hyphenated_token():
    result = sanitize_fts_query("machine-learning")
    assert result == '"machine-learning"'


def test_sanitize_fts_query_multiple_hyphenated():
    result = sanitize_fts_query("deep-learning neural-net")
    assert '"deep-learning"' in result
    assert '"neural-net"' in result


def test_sanitize_fts_query_strips_special_chars():
    result = sanitize_fts_query("hello (world)")
    assert "(" not in result
    assert ")" not in result


def test_sanitize_fts_query_plain_word():
    assert sanitize_fts_query("python") == "python"


def test_sanitize_fts_query_empty():
    assert sanitize_fts_query("") == ""


def test_sanitize_fts_query_only_special_chars():
    assert sanitize_fts_query("()[]{}") == ""


def test_sanitize_fts_query_preserves_and_or():
    result = sanitize_fts_query("foo AND bar")
    assert "AND" in result
    assert "foo" in result
    assert "bar" in result
