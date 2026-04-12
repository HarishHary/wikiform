from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import click
from loguru import logger
from rich.console import Console
from rich.table import Table

from wikiform.utils.db import db_path, get_connection, sanitize_fts_query

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

    sql = _SEARCH_SQL
    params: list[str | int] = [safe_query]

    if tag:
        sql += " AND a.tags LIKE ?"
        params.append(f"%{tag}%")
    if directory:
        sql += " AND a.path LIKE ?"
        params.append(f"{directory}%")

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    db = get_connection(vault_root)
    try:
        rows = db.execute(sql, params).fetchall()
    except sqlite3.OperationalError as exc:
        raise ValueError(str(exc)) from exc
    finally:
        db.close()

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


@click.command("query")
@click.argument("query")
@click.option("--tag", default=None, help="Filter by tag (substring match)")
@click.option("--dir", "directory", default=None, help="Filter by path prefix")
@click.option("--limit", default=20, show_default=True, help="Max results")
@click.option("--json", "as_json", is_flag=True, help="Print results as JSON to stdout")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON results to file")
@click.pass_context
def query_cmd(ctx: click.Context, query: str, tag: str | None, directory: str | None, limit: int, as_json: bool, output: Path | None) -> None:
    vault_root = ctx.obj.get("vault_root")
    if not vault_root:
        logger.error("Vault root path not provided in context")
        raise SystemExit(2)

    root = Path(vault_root).resolve()
    if not root.exists():
        logger.error("Vault root does not exist: {}", root)
        raise SystemExit(2)

    if not db_path(root).exists():
        logger.error("No index found. Run 'wikiform search index' first.")
        raise SystemExit(1)

    logger.debug("FTS query: {!r}", query)

    try:
        results = run_query(root, query, tag=tag, directory=directory, limit=limit)
    except ValueError as exc:
        logger.error("Search error: {}", exc)
        logger.info("Try simplifying your query.")
        raise SystemExit(1)

    logger.debug("Found {} result(s)", len(results))

    serialized = [asdict(r) for r in results]

    if output:
        rendered = json.dumps(serialized, indent=2, ensure_ascii=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        logger.info("Wrote {} result(s) to {}", len(results), output)
        return

    if as_json:
        click.echo(json.dumps(serialized, indent=2, ensure_ascii=False))
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
