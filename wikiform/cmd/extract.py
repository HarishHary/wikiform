from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

import click
from loguru import logger

from wikiform.utils.extractor import extract_text, fetch_url

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
    ".html": ("articles", "article"),
    ".htm": ("articles", "article"),
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


def _url_slug(url: str) -> str:
    parsed = urlparse(url)
    stem = Path(parsed.path.rstrip("/")).stem or parsed.netloc
    return _slugify(stem) or _slugify(parsed.netloc)


def _build_markdown(title: str, source_type: str, content: str, lang: str | None, source_url: str | None = None) -> str:
    today = date.today().isoformat()
    url_line = f"source_url: {source_url}\n" if source_url else ""
    frontmatter = (
        f"---\n"
        f"title: {title}\n"
        f"source_type: {source_type}\n"
        f"{url_line}"
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


def run_extract_url(url: str, vault_root: Path, overwrite: bool) -> ExtractResult:
    now = datetime.now(UTC).isoformat()

    title, content = fetch_url(url)
    slug = _url_slug(url)

    output_dir = vault_root / "raw" / "articles"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{slug}.md"
    if output_path.exists() and not overwrite:
        logger.error("Output already exists: {}. Use --overwrite to replace.", output_path)
        raise SystemExit(1)

    markdown = _build_markdown(title, "article", content, None, source_url=url)
    output_path.write_text(markdown, encoding="utf-8")
    logger.info("Fetched {} → {}", url, output_path)

    return ExtractResult(
        source=url,
        output=str(output_path),
        source_type="article",
        subdir="articles",
        generated_at=now,
    )


def run_extract(source: Path, vault_root: Path, overwrite: bool) -> ExtractResult:
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


@click.command("extract", help="Extract a source file or URL into a raw markdown file ready for wiki-ingest.")
@click.argument("source")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite if output file already exists.")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON report to file instead of stdout.")
@click.pass_context
def extract_cmd(ctx: click.Context, source: str, overwrite: bool, output: Path | None) -> None:
    vault_root = ctx.obj.get("vault_root")
    if not vault_root:
        logger.error("Vault root path not provided in context")
        raise SystemExit(2)

    root = Path(vault_root).resolve()
    if not root.exists():
        logger.error("Vault root does not exist: {}", root)
        raise SystemExit(2)

    if source.startswith(("http://", "https://")):
        result = run_extract_url(source, root, overwrite=overwrite)
    else:
        source_path = Path(source)
        if not source_path.exists():
            logger.error("File not found: {}", source)
            raise SystemExit(2)
        result = run_extract(source_path.resolve(), root, overwrite=overwrite)

    rendered = json.dumps(asdict(result), indent=2, ensure_ascii=False)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        logger.info("Wrote report to {}", output)
    else:
        click.echo(rendered)
