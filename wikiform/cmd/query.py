from __future__ import annotations

import contextlib
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import click
from loguru import logger
from rich.console import Console
from rich.table import Table

from wikiform.utils.cli_helpers import emit_json, resolve_vault_root
from wikiform.utils.db import db_path, get_connection, sanitize_fts_query
from wikiform.utils.embedder import DEFAULT_MODEL, Embedder
from wikiform.utils.vec_db import get_vec_meta, is_legacy_vec_table, load_sqlite_vec, serialize_vector

logger = logger.bind(service="Wikiform - Query")
console = Console()


@dataclass
class SearchResult:
    rank: float
    path: str
    title: str
    tags: str
    updated: str
    snippet: str


_SEARCH_SQL = """
    SELECT
        a.path,
        a.title,
        a.tags,
        a.updated,
        snippet(articles_fts, 2, '<b>', '</b>', '...', 32) AS snippet,
        bm25(articles_fts, 5.0, 2.0, 1.0) AS rank
    FROM articles_fts
    JOIN articles a ON a.id = articles_fts.rowid
    WHERE articles_fts MATCH ?
"""

# Vectors are stored per chunk; collapse to the best-matching chunk per article.
_SEMANTIC_SQL = """
    SELECT
        a.path,
        a.title,
        a.tags,
        a.updated,
        a.content,
        MIN(v.distance) AS distance
    FROM articles_vec v
    JOIN vec_chunks c ON c.chunk_id = v.rowid
    JOIN articles a ON a.id = c.article_id
    WHERE v.embedding MATCH ?
      AND k = ?
"""

_KNN_OVERFETCH = 5
_KNN_MAX_K = 1000


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filter_clauses(tag: str | None, directory: str | None) -> tuple[str, list[str]]:
    """SQL fragment (starting with AND) and params for the --tag / --dir filters on the articles table."""
    sql = ""
    params: list[str] = []
    if tag:
        # tags are stored as "a, b, c": match a whole tag, case-insensitively
        sql += " AND (', ' || LOWER(a.tags) || ', ') LIKE ? ESCAPE '\\'"
        params.append(f"%, {_like_escape(tag.strip().lower())}, %")
    if directory:
        sql += " AND a.path LIKE ? ESCAPE '\\'"
        params.append(f"{_like_escape(directory)}%")
    return sql, params


def _content_snippet(content: str, max_len: int = 200) -> str:
    for line in (content or "").splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-", "*", "|", ">")):
            return line[:max_len]
    return (content or "")[:max_len]


def run_semantic_query(
    vault_root: Path,
    query: str,
    tag: str | None = None,
    directory: str | None = None,
    limit: int = 20,
) -> list[SearchResult]:
    filter_sql, filter_params = _filter_clauses(tag, directory)
    # Several chunks can belong to one article, and filters apply after KNN: over-fetch chunks.
    k = min(limit * _KNN_OVERFETCH, _KNN_MAX_K)

    with contextlib.closing(get_connection(vault_root)) as db:
        load_sqlite_vec(db)
        if is_legacy_vec_table(db):
            raise ValueError("Vector index predates chunking. Run 'wikiform search embed --reset'.")
        # Query with the same model the vectors were built with.
        model = get_vec_meta(db, "model") or DEFAULT_MODEL
        blob = serialize_vector(Embedder(model).embed_query(query))

        sql = _SEMANTIC_SQL + filter_sql + " GROUP BY a.id ORDER BY distance LIMIT ?"
        try:
            rows = db.execute(sql, (blob, k, *filter_params, limit)).fetchall()
        except sqlite3.OperationalError as err:
            raise ValueError(str(err)) from err

    return [
        SearchResult(
            rank=round(row["distance"], 6),
            path=row["path"],
            title=row["title"] or "",
            tags=row["tags"] or "",
            updated=row["updated"] or "",
            snippet=_content_snippet(row["content"]),
        )
        for row in rows
    ]


def run_query(
    vault_root: Path,
    query: str,
    tag: str | None = None,
    directory: str | None = None,
    limit: int = 20,
) -> list[SearchResult]:
    safe_query = sanitize_fts_query(query)
    if not safe_query:
        return []

    filter_sql, filter_params = _filter_clauses(tag, directory)
    sql = _SEARCH_SQL + filter_sql + " ORDER BY rank LIMIT ?"
    params: list[str | int] = [safe_query, *filter_params, limit]

    with contextlib.closing(get_connection(vault_root)) as db:
        try:
            rows = db.execute(sql, params).fetchall()
        except sqlite3.OperationalError as err:
            raise ValueError(str(err)) from err

    return [
        SearchResult(
            rank=round(row["rank"], 4),
            path=row["path"],
            title=row["title"] or "",
            tags=row["tags"] or "",
            updated=row["updated"] or "",
            snippet=row["snippet"] or "",
        )
        for row in rows
    ]


@click.command("query", help="Search indexed wiki pages. Defaults to FTS5 keyword search; use --semantic for vector search (run 'search embed' first).")
@click.argument("query")
@click.option("--tag", default=None, help="Filter by tag (exact tag, case-insensitive)")
@click.option("--dir", "directory", default=None, help="Filter by path prefix")
@click.option("--limit", default=20, show_default=True, type=click.IntRange(1, 100), help="Max results (1-100)")
@click.option("--semantic", is_flag=True, default=False, help="Semantic vector search. Run 'search embed' first to generate embeddings.")
@click.option("--json", "as_json", is_flag=True, help="Print results as JSON to stdout")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON results to file")
@click.pass_context
def query_cmd(ctx: click.Context, query: str, tag: str | None, directory: str | None, limit: int, semantic: bool, as_json: bool, output: Path | None) -> None:
    root = resolve_vault_root(ctx)

    if not db_path(root).exists():
        logger.error("No index found. Run 'wikiform search index' first.")
        raise SystemExit(1)

    if semantic:
        logger.debug("Semantic query: {!r}", query)
        try:
            results = run_semantic_query(root, query, tag=tag, directory=directory, limit=limit)
        except ValueError as err:
            logger.error("Search error: {}", err)
            raise SystemExit(1) from err
    else:
        logger.debug("FTS query: {!r}", query)
        try:
            results = run_query(root, query, tag=tag, directory=directory, limit=limit)
        except ValueError as err:
            logger.error("Search error: {}", err)
            logger.info("Try simplifying your query.")
            raise SystemExit(1) from err

    logger.debug("Found {} result(s)", len(results))

    serialized = [asdict(r) for r in results]

    if output or as_json:
        emit_json(serialized, output, label=f"{len(results)} result(s)")
        return

    if not results:
        logger.info("No results for '{}'", query)
        return

    table = Table(title=f"Search: {query}", show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Title", style="bold")
    table.add_column("Path", style="cyan")
    table.add_column("Tags", style="green")
    table.add_column("Snippet", max_width=60)

    for i, row in enumerate(results, 1):
        snippet = re.sub(r"</?b>", "", row.snippet)
        table.add_row(str(i), row.title, row.path, row.tags, snippet)

    console.print(table)
    logger.info("{} result(s)", len(results))
