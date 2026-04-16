from __future__ import annotations

import contextlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import click
from loguru import logger

from wikiform.utils.db import get_connection, init_db
from wikiform.utils.fs import collect_md_files, load_frontmatter, normalize_rel, normalize_tags

logger = logger.bind(service="Wikiform - FTS Index")


@dataclass
class ParsedMd:
    title: str
    tags: str
    updated: str
    content: str


@dataclass
class FtsIndexResult:
    vault_root: str
    incremental: bool
    generated_at: str
    indexed: int
    skipped: int
    deleted: int
    total: int


def _parse_md(filepath: Path) -> ParsedMd:
    attrs, content = load_frontmatter(filepath)
    if not attrs and content.strip():
        logger.warning("No frontmatter parsed for {}, indexing raw text", filepath.name)

    tags = normalize_tags(attrs.get("tags"), source=filepath.name)
    return ParsedMd(
        title=str(attrs.get("title") or filepath.stem).strip() or filepath.stem,
        tags=", ".join(tags),
        updated=str(attrs.get("updated", "") or ""),
        content=content,
    )


def run_fts_index(vault_root: Path, incremental: bool) -> FtsIndexResult:
    now = datetime.now(UTC).isoformat()
    indexed = 0
    skipped = 0
    deleted = 0
    current_files: set[str] = set()

    with contextlib.closing(get_connection(vault_root)) as db:
        init_db(db)

        for md_file in collect_md_files(vault_root):
            rel_path = normalize_rel(md_file, vault_root)
            current_files.add(rel_path)

            try:
                mtime = md_file.stat().st_mtime
            except OSError:
                logger.warning("Could not stat {}, skipping", rel_path)
                continue

            if incremental:
                row = db.execute(
                    "SELECT mtime FROM articles WHERE path = ?", (rel_path,)
                ).fetchone()
                if row and row["mtime"] >= mtime:
                    skipped += 1
                    continue

            parsed = _parse_md(md_file)
            db.execute(
                """INSERT INTO articles (path, title, tags, updated, content, mtime, last_indexed)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(path) DO UPDATE SET
                       title        = excluded.title,
                       tags         = excluded.tags,
                       updated      = excluded.updated,
                       content      = excluded.content,
                       mtime        = excluded.mtime,
                       last_indexed = excluded.last_indexed""",
                (rel_path, parsed.title, parsed.tags, parsed.updated,
                 parsed.content, mtime, now),
            )
            logger.debug("Indexed: {}", rel_path)
            indexed += 1

        all_paths = {r["path"] for r in db.execute("SELECT path FROM articles").fetchall()}
        for path in all_paths - current_files:
            db.execute("DELETE FROM articles WHERE path = ?", (path,))
            logger.debug("Removed stale entry: {}", path)
            deleted += 1

        db.commit()

    return FtsIndexResult(
        vault_root=str(vault_root),
        incremental=incremental,
        generated_at=now,
        indexed=indexed,
        skipped=skipped,
        deleted=deleted,
        total=len(current_files),
    )


@click.command("fts-index", help="Build or update the FTS5 search index. By default, all markdown files will be re-indexed. Use --incremental to only index new or modified files since the last run.")
@click.option("--incremental", is_flag=True, help="Only index new or modified files")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON report to file instead of stdout")
@click.pass_context
def fts_index_cmd(ctx: click.Context, incremental: bool, output: Path | None) -> None:
    vault_root = ctx.obj.get("vault_root")
    if not vault_root:
        logger.error("Vault root path not provided in context")
        raise SystemExit(2)

    root = Path(vault_root).resolve()
    if not root.exists():
        logger.error("Vault root does not exist: {}", root)
        raise SystemExit(2)

    result = run_fts_index(root, incremental)
    logger.info(
        "Indexed: {}  Skipped: {}  Removed: {}  Total: {}",
        result.indexed, result.skipped, result.deleted, result.total,
    )

    rendered = json.dumps(asdict(result), indent=2, ensure_ascii=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        logger.info("Wrote result to {}", output)
    else:
        click.echo(rendered)
