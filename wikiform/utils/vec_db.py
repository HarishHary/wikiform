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
    db.execute("DROP TABLE IF EXISTS articles_vec")
    db.commit()


def init_vec_table(db: sqlite3.Connection, dims: int = EMBEDDING_DIM) -> None:
    db.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS articles_vec USING vec0(
            embedding float[{dims}]
        )
    """)
    db.commit()


def serialize_vector(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def upsert_vec(db: sqlite3.Connection, rowid: int, vector: list[float]) -> None:
    blob = serialize_vector(vector)
    db.execute("DELETE FROM articles_vec WHERE rowid = ?", (rowid,))
    db.execute("INSERT INTO articles_vec(rowid, embedding) VALUES (?, ?)", (rowid, blob))
