from __future__ import annotations

import sqlite3
import struct

import sqlite_vec

EMBEDDING_DIM = 768


def load_sqlite_vec(db: sqlite3.Connection) -> None:
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)


def drop_vec_table(db: sqlite3.Connection) -> None:
    """Drop the vector table and all bookkeeping tables tied to it."""
    db.execute("DROP TABLE IF EXISTS articles_vec")
    db.execute("DROP TABLE IF EXISTS vec_chunks")
    db.execute("DROP TABLE IF EXISTS vec_articles")
    db.execute("DROP TABLE IF EXISTS vec_meta")
    db.commit()


def init_vec_table(db: sqlite3.Connection, dims: int = EMBEDDING_DIM) -> None:
    """Create the vector table plus bookkeeping.

    - articles_vec: one vector per *chunk* (rowid == vec_chunks.chunk_id)
    - vec_chunks:   chunk_id -> article_id
    - vec_articles: article_id -> hash of the text that was embedded (staleness detection)
    - vec_meta:     model name and dimension the table was built with
    """
    db.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS articles_vec USING vec0(
            embedding float[{int(dims)}]
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS vec_chunks (
            chunk_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER NOT NULL
        )
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_vec_chunks_article ON vec_chunks(article_id)")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS vec_articles (
            article_id   INTEGER PRIMARY KEY,
            content_hash TEXT NOT NULL
        )
        """
    )
    db.execute("CREATE TABLE IF NOT EXISTS vec_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.commit()


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (name,)).fetchone() is not None


def is_legacy_vec_table(db: sqlite3.Connection) -> bool:
    """True when articles_vec exists but was built before chunk/meta tracking (rowid == article id)."""
    return _table_exists(db, "articles_vec") and not _table_exists(db, "vec_meta")


def get_vec_meta(db: sqlite3.Connection, key: str) -> str | None:
    if not _table_exists(db, "vec_meta"):
        return None
    row = db.execute("SELECT value FROM vec_meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_vec_meta(db: sqlite3.Connection, key: str, value: str) -> None:
    db.execute("INSERT INTO vec_meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def serialize_vector(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def delete_article_vectors(db: sqlite3.Connection, article_id: int) -> None:
    """Remove every chunk vector and the hash record for one article."""
    chunk_ids = [r[0] for r in db.execute("SELECT chunk_id FROM vec_chunks WHERE article_id = ?", (article_id,)).fetchall()]
    for chunk_id in chunk_ids:
        db.execute("DELETE FROM articles_vec WHERE rowid = ?", (chunk_id,))
    db.execute("DELETE FROM vec_chunks WHERE article_id = ?", (article_id,))
    db.execute("DELETE FROM vec_articles WHERE article_id = ?", (article_id,))


def replace_article_vectors(db: sqlite3.Connection, article_id: int, content_hash: str, vectors: list[list[float]]) -> None:
    """Replace all chunk vectors for an article. Does not commit (callers own the transaction)."""
    delete_article_vectors(db, article_id)
    for vector in vectors:
        cursor = db.execute("INSERT INTO vec_chunks(article_id) VALUES (?)", (article_id,))
        db.execute("INSERT INTO articles_vec(rowid, embedding) VALUES (?, ?)", (cursor.lastrowid, serialize_vector(vector)))
    db.execute("INSERT INTO vec_articles(article_id, content_hash) VALUES (?, ?)", (article_id, content_hash))
