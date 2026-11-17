from __future__ import annotations

import contextlib
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import click
from loguru import logger

from wikiform.utils.chunking import chunk_text
from wikiform.utils.cli_helpers import emit_json, resolve_vault_root
from wikiform.utils.db import get_connection
from wikiform.utils.embedder import DEFAULT_MODEL, Embedder
from wikiform.utils.vec_db import (
    delete_article_vectors,
    drop_vec_table,
    get_vec_meta,
    init_vec_table,
    is_legacy_vec_table,
    load_sqlite_vec,
    replace_article_vectors,
    set_vec_meta,
)

logger = logger.bind(service="Wikiform - Embed")


@dataclass
class EmbedResult:
    vault_root: str
    model: str
    generated_at: str
    embedded: int
    skipped: int
    deleted: int
    total: int


_BATCH_SIZE = 32


def _article_text(row: sqlite3.Row) -> str:
    return f"{row['title'] or ''}. {row['tags'] or ''}. {row['content'] or ''}"


def _article_chunks(row: sqlite3.Row) -> list[str]:
    """Split an article into embeddable chunks; each chunk carries the title (and tags on the first) for context."""
    title = row["title"] or ""
    tags = row["tags"] or ""
    chunks = chunk_text(row["content"] or "")
    return [f"{title}. {tags}. {c}" if i == 0 else f"{title}. {c}" for i, c in enumerate(chunks)]


def run_embed(vault_root: Path, model: str, incremental: bool, reset: bool) -> EmbedResult:
    now = datetime.now(UTC).isoformat()
    embedder = Embedder(model)
    dim = embedder.dimension
    embedded = 0
    skipped = 0
    deleted = 0

    with contextlib.closing(get_connection(vault_root)) as db:
        load_sqlite_vec(db)
        if reset:
            drop_vec_table(db)
        elif is_legacy_vec_table(db):
            logger.warning("Vector table predates chunking/model tracking - rebuilding it")
            drop_vec_table(db)

        stored_model = get_vec_meta(db, "model")
        stored_dim = get_vec_meta(db, "dim")
        if stored_model is not None and (stored_model != model or stored_dim != str(dim)):
            raise ValueError(f"Vectors were built with model '{stored_model}' ({stored_dim} dims); requested '{model}' ({dim} dims). Re-run with --reset.")

        init_vec_table(db, dim)
        set_vec_meta(db, "model", model)
        set_vec_meta(db, "dim", str(dim))

        try:
            articles = db.execute("SELECT id, path, title, tags, content FROM articles").fetchall()
        except sqlite3.OperationalError as err:
            raise ValueError("No article index found. Run 'wikiform search index' first.") from err
        total = len(articles)

        stored_hashes = {r["article_id"]: r["content_hash"] for r in db.execute("SELECT article_id, content_hash FROM vec_articles").fetchall()}

        pending: list[tuple[sqlite3.Row, str, list[str]]] = []
        for row in articles:
            content_hash = hashlib.sha256(_article_text(row).encode("utf-8")).hexdigest()
            if incremental and stored_hashes.get(row["id"]) == content_hash:
                skipped += 1
                continue
            pending.append((row, content_hash, _article_chunks(row)))

        # Embed in batches across articles, then write each article's vectors.
        flat = [chunk for _, _, chunks in pending for chunk in chunks]
        vectors: list[list[float]] = []
        for start in range(0, len(flat), _BATCH_SIZE):
            vectors.extend(embedder.embed_many(flat[start : start + _BATCH_SIZE], batch_size=_BATCH_SIZE))

        offset = 0
        for row, content_hash, chunks in pending:
            replace_article_vectors(db, row["id"], content_hash, vectors[offset : offset + len(chunks)])
            offset += len(chunks)
            logger.debug("Embedded: {} ({} chunk(s))", row["path"], len(chunks))
            embedded += 1

        article_ids = {row["id"] for row in articles}
        for stale_id in set(stored_hashes) - article_ids:
            delete_article_vectors(db, stale_id)
            logger.debug("Removed stale vectors for article id={}", stale_id)
            deleted += 1

        db.commit()

    return EmbedResult(
        vault_root=str(vault_root),
        model=model,
        generated_at=now,
        embedded=embedded,
        skipped=skipped,
        deleted=deleted,
        total=total,
    )


@click.command("embed", help="Generate vector embeddings for all indexed articles. Run 'search index' first.")
@click.option("--model", default=DEFAULT_MODEL, show_default=True, help="Sentence-transformers model name.")
@click.option("--incremental", is_flag=True, default=False, help="Skip articles whose text is unchanged since they were last embedded.")
@click.option("--reset", is_flag=True, default=False, help="Drop and recreate the vector table before embedding. Required when changing models.")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON report to file instead of stdout.")
@click.pass_context
def embed_cmd(ctx: click.Context, model: str, incremental: bool, reset: bool, output: Path | None) -> None:
    root = resolve_vault_root(ctx)

    try:
        result = run_embed(root, model=model, incremental=incremental, reset=reset)
    except ValueError as err:
        logger.error("{}", err)
        raise SystemExit(1) from err
    logger.info("Embedded: {}  Skipped: {}  Deleted: {}  Total: {}", result.embedded, result.skipped, result.deleted, result.total)

    emit_json(result, output)
