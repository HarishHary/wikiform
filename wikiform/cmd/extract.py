from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlparse

import click
import frontmatter
from loguru import logger

from wikiform.utils.cli_helpers import emit_json, resolve_vault_root
from wikiform.utils.extractor import extract_text, fetch_url
from wikiform.utils.fs import normalize_rel

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
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".sql": "sql",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".sh": "bash",
    ".bat": "batch",
    ".ps1": "powershell",
    ".xml": "xml",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
}


def _slugify(stem: str) -> str:
    slug = stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _file_slug(stem: str) -> str:
    """Slug for a local file stem; falls back to a short hash when nothing ASCII survives (e.g. '日本語')."""
    return _slugify(stem) or f"file-{hashlib.sha1(stem.encode('utf-8')).hexdigest()[:8]}"  # nosec B324


def _url_slug(url: str) -> str:
    parsed = urlparse(url)
    stem = Path(parsed.path.rstrip("/")).stem or parsed.netloc
    return _slugify(stem) or _slugify(parsed.netloc) or _file_slug(url)


def _fence(content: str, lang: str) -> str:
    """Wrap content in a code fence longer than any backtick run inside it."""
    longest = max((len(m) for m in re.findall(r"`+", content)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{lang}\n{content}\n{fence}\n"


def _build_markdown(title: str, source_type: str, content: str, lang: str | None, source_url: str | None = None, source_file: str | None = None) -> str:
    meta: dict[str, object] = {"title": title, "source_type": source_type}
    if source_url:
        meta["source_url"] = source_url
    if source_file:
        meta["source_file"] = source_file  # vault-relative path of the preserved original
    meta.update({"status": "raw", "slug": "", "ingested_date": "", "ingested_to": [], "added": date.today()})

    # Serialised by PyYAML so titles/URLs containing ':', '#', quotes etc. stay valid YAML.
    frontmatter_block = frontmatter.dumps(frontmatter.Post("", **meta), sort_keys=False).strip()

    if lang:
        body = _fence(content, lang)
    else:
        body = content if content.endswith("\n") else content + "\n"
    return f"{frontmatter_block}\n\n{body}"


@dataclass
class ExtractResult:
    source: str
    output: str
    source_type: str
    subdir: str
    generated_at: str
    source_file: str | None = None  # vault-relative path of the preserved original (None for URLs and .md sources)


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

    slug = _file_slug(source.stem)
    output_path = output_dir / f"{slug}.md"

    # Keep the original next to its markdown (same slug, original extension). A .md source needs no copy:
    # the extracted file already contains its full text and would collide with the copy's name.
    original_path = output_dir / f"{slug}{ext}" if ext and ext != ".md" else None

    for target in (output_path, original_path):
        if target is not None and target.exists() and not overwrite and target.resolve() != source.resolve():
            logger.error("Output already exists: {}. Use --overwrite to replace.", target)
            raise SystemExit(1)

    content = extract_text(source)
    lang = _LANG.get(ext) if source_type == "code" else None

    copied = False
    if original_path is not None and original_path.resolve() != source.resolve():  # source may already live at the destination
        shutil.copy2(source, original_path)
        copied = True
    source_file = normalize_rel(original_path, vault_root) if original_path is not None else None

    try:
        output_path.write_text(_build_markdown(source.stem, source_type, content, lang, source_file=source_file), encoding="utf-8")
    except OSError:
        if copied and original_path is not None:
            original_path.unlink(missing_ok=True)  # don't leave an orphaned copy without its markdown
        raise
    logger.info("Extracted {} → {}", source.name, output_path)

    return ExtractResult(
        source=str(source),
        output=str(output_path),
        source_type=source_type,
        subdir=subdir,
        generated_at=now,
        source_file=source_file,
    )


@click.command("extract", help="Extract a source file or URL into a raw markdown file ready for wiki-ingest.")
@click.argument("source")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite if output file already exists.")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON report to file instead of stdout.")
@click.pass_context
def extract_cmd(ctx: click.Context, source: str, overwrite: bool, output: Path | None) -> None:
    root = resolve_vault_root(ctx)

    try:
        if source.startswith(("http://", "https://")):
            result = run_extract_url(source, root, overwrite=overwrite)
        else:
            source_path = Path(source)
            if not source_path.exists():
                logger.error("File not found: {}", source)
                raise SystemExit(2)
            result = run_extract(source_path.resolve(), root, overwrite=overwrite)
    except SystemExit:
        raise
    except Exception as err:  # extractors/requests raise many library-specific types
        logger.error("Extraction failed for {}: {}", source, err)
        raise SystemExit(1) from err

    emit_json(result, output, label="report")
