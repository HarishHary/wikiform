from __future__ import annotations

import contextlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import click
from loguru import logger

from wikiform.utils.db import get_connection
from wikiform.utils.embedder import DEFAULT_MODEL, Embedder
from wikiform.utils.vec_db import drop_vec_table, init_vec_table, load_sqlite_vec, upsert_vec

logger = logger.bind(service="Wikiform - Embed")


@dataclass
class EmbedResult:
    vault_root: str
    model: str
    generated_at: str
    embedded: int
    skipped: int
    total: int


def run_embed(vault_root: Path, model: str, incremental: bool, reset: bool) -> EmbedResult:
    now = datetime.now(timezone.utc).isoformat()
    embedder = Embedder(model)
    embedded = 0
    skipped = 0

    with contextlib.closing(get_connection(vault_root)) as db:
        load_sqlite_vec(db)
        if reset:
            drop_vec_table(db)
        init_vec_table(db)

        articles = db.execute("SELECT id, title, tags, content FROM articles").fetchall()
        total = len(articles)

        if incremental:
            already_embedded = {r[0] for r in db.execute("SELECT rowid FROM articles_vec").fetchall()}
        else:
            already_embedded = set()

        for row in articles:
            if incremental and row["id"] in already_embedded:
                skipped += 1
                continue

            text = f"{row['title'] or ''}. {row['tags'] or ''}. {row['content'] or ''}"
            vector = embedder.embed(text)
            upsert_vec(db, row["id"], vector)
            logger.debug("Embedded article id={}", row["id"])
            embedded += 1

        db.commit()

    return EmbedResult(
        vault_root=str(vault_root),
        model=model,
        generated_at=now,
        embedded=embedded,
        skipped=skipped,
        total=total,
    )


@click.command("embed", help="Generate vector embeddings for all indexed articles. Run 'search index' first.")
@click.option("--model", default=DEFAULT_MODEL, show_default=True, help="Sentence-transformers model name.")
@click.option("--incremental", is_flag=True, default=False, help="Skip articles already embedded.")
@click.option("--reset", is_flag=True, default=False, help="Drop and recreate the vector table before embedding. Required when changing models.")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON report to file instead of stdout.")
@click.pass_context
def embed_cmd(ctx: click.Context, model: str, incremental: bool, reset: bool, output: Path | None) -> None:
    vault_root = ctx.obj.get("vault_root")
    if not vault_root:
        logger.error("Vault root path not provided in context")
        raise SystemExit(2)

    root = Path(vault_root).resolve()
    if not root.exists():
        logger.error("Vault root does not exist: {}", root)
        raise SystemExit(2)

    result = run_embed(root, model=model, incremental=incremental, reset=reset)
    logger.info("Embedded: {}  Skipped: {}  Total: {}", result.embedded, result.skipped, result.total)

    rendered = json.dumps(asdict(result), indent=2, ensure_ascii=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        logger.info("Wrote result to {}", output)
    else:
        click.echo(rendered)
