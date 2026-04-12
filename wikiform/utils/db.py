from __future__ import annotations

import re
import sqlite3
from pathlib import Path


DB_RELATIVE = Path("scripts") / "vault-search.db"


def db_path(vault_root: Path) -> Path:
    return vault_root / DB_RELATIVE


def get_connection(vault_root: Path) -> sqlite3.Connection:
    path = db_path(vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id           INTEGER PRIMARY KEY,
            path         TEXT UNIQUE NOT NULL,
            title        TEXT,
            tags         TEXT,
            updated      TEXT,
            content      TEXT,
            mtime        REAL,
            last_indexed TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
            title,
            tags,
            content,
            content=articles,
            content_rowid=id,
            tokenize='porter unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
            INSERT INTO articles_fts(rowid, title, tags, content)
            VALUES (new.id, new.title, new.tags, new.content);
        END;

        CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, title, tags, content)
            VALUES ('delete', old.id, old.title, old.tags, old.content);
        END;

        CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, title, tags, content)
            VALUES ('delete', old.id, old.title, old.tags, old.content);
            INSERT INTO articles_fts(rowid, title, tags, content)
            VALUES (new.id, new.title, new.tags, new.content);
        END;
    """)


def sanitize_fts_query(query: str) -> str:
    """
    Sanitize a user query for FTS5 MATCH.

    FTS5 treats hyphens as NOT operators (column-filter syntax).
    Strategy:
    1. Strip FTS5 special characters: ^ * + ( ) [ ] { } "
    2. Wrap hyphenated tokens in double quotes so FTS5 treats them as
       phrase tokens: multi-head → "multi-head"
    3. Collapse whitespace.

    AND, OR, NOT are preserved — users may use them intentionally.
    """
    sanitized = re.sub(r'[\^*()\[\]{}"+]', " ", query)
    sanitized = re.sub(r"(\b\w+(?:-\w+)+\b)", r'"\1"', sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized
