from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date
from pathlib import Path

import click
from loguru import logger

from wikiform.utils.extractor import extract_text

logger = logger.bind(service="Wikiform - Extract")

# Maps extension → (raw/ subdir, source_type)
_ROUTING: dict[str, tuple[str, str]] = {
    ".pdf": ("papers", "paper"),
    ".md": ("papers", "paper"),
    ".txt": ("papers", "paper"),
    ".docx": ("papers", "paper"),
    ".dotx": ("papers", "paper"),
    ".pptx": ("papers", "paper"),
    ".csv": ("datasets", "dataset"),
    ".json": ("datasets", "dataset"),
    ".yaml": ("datasets", "dataset"),
    ".yml": ("datasets", "dataset"),
    ".toml": ("datasets", "dataset"),
    ".xlsx": ("datasets", "dataset"),
    ".xltx": ("datasets", "dataset"),
    ".py": ("code", "code"),
    ".js": ("code", "code"),
    ".ts": ("code", "code"),
    ".sql": ("code", "code"),
    ".go": ("code", "code"),
    ".rs": ("code", "code"),
    ".rb": ("code", "code"),
    ".java": ("code", "code"),
    ".c": ("code", "code"),
    ".cpp": ("code", "code"),
    ".h": ("code", "code"),
    ".sh": ("code", "code"),
    ".bat": ("code", "code"),
    ".ps1": ("code", "code"),
    ".xml": ("code", "code"),
    ".html": ("code", "code"),
    ".png": ("images", "image"),
    ".jpg": ("images", "image"),
    ".jpeg": ("images", "image"),
    ".svg": ("images", "image"),
}

# Language tag for fenced code blocks
_LANG: dict[str, str] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".sql": "sql", ".go": "go", ".rs": "rust",
    ".rb": "ruby", ".java": "java", ".sh": "bash",
    ".bat": "batch", ".ps1": "powershell", ".xml": "xml",
    ".html": "html", ".c": "c", ".cpp": "cpp",
    ".h": "c",
}


def _slugify(stem: str) -> str:
    slug = stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _build_markdown(title: str, source_type: str, content: str, lang: str | None) -> str:
    today = date.today().isoformat()
    frontmatter = (
        f"---\n"
        f"title: {title}\n"
        f"source_type: {source_type}\n"
        f"status: raw\n"
        f"slug: \"\"\n"
        f"ingested_date: \"\"\n"
        f"ingested_to: []\n"
        f"added: {today}\n"
        f"---\n"
    )
    if lang:
        body = f"```{lang}\n{content}\n```\n"
    else:
        body = content if content.endswith("\n") else content + "\n"
    return frontmatter + "\n" + body


@dataclass
class ExtractResult:
    source: str
    output: str
    source_type: str
    subdir: str
    generated_at: str


def run_extract(source: Path, vault_root: Path, overwrite: bool) -> ExtractResult:
    from datetime import datetime
    now = datetime.now(UTC).isoformat()

    ext = source.suffix.lower()
    subdir, source_type = _ROUTING.get(ext, ("misc", "other"))

    output_dir = vault_root / "raw" / subdir
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify(source.stem)
    output_path = output_dir / f"{slug}.md"

    if output_path.exists() and not overwrite:
        logger.error("Output already exists: {}. Use --overwrite to replace.", output_path)
        raise SystemExit(1)

    content = extract_text(source)
    lang = _LANG.get(ext) if source_type == "code" else None
    markdown = _build_markdown(source.stem, source_type, content, lang)

    output_path.write_text(markdown, encoding="utf-8")
    logger.info("Extracted {} → {}", source.name, output_path)

    return ExtractResult(
        source=str(source),
        output=str(output_path),
        source_type=source_type,
        subdir=subdir,
        generated_at=now,
    )


@click.command("extract", help="Extract a source file into a raw markdown file ready for wiki-ingest.")
@click.argument("source", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite if output file already exists.")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON report to file instead of stdout.")
@click.pass_context
def extract_cmd(ctx: click.Context, source: Path, overwrite: bool, output: Path | None) -> None:
    vault_root = ctx.obj.get("vault_root")
    if not vault_root:
        logger.error("Vault root path not provided in context")
        raise SystemExit(2)

    root = Path(vault_root).resolve()
    if not root.exists():
        logger.error("Vault root does not exist: {}", root)
        raise SystemExit(2)

    result = run_extract(source.resolve(), root, overwrite=overwrite)

    rendered = json.dumps(asdict(result), indent=2, ensure_ascii=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        logger.info("Wrote report to {}", output)
    else:
        click.echo(rendered)
