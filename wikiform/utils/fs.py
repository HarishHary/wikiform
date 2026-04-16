from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import frontmatter
from loguru import logger

logger = logger.bind(service="Wikiform - FS")

SKIP_DIRS: frozenset[str] = frozenset({
    ".obsidian",
    ".git",
    ".trash",
    "node_modules",
    "outputs",
})

SKIP_FILES: frozenset[str] = frozenset({
    "README.md",
    "LICENSE.md",
    "SCHEMA.md",
})

# Prefixes that indicate a line is structural markup, not prose.
SUMMARY_SKIP_PREFIXES: tuple[str, ...] = (
    "#", "---", ">", "|", "[[", "-", "*", "!",
)


def should_skip(path: Path, vault_root: Path) -> bool:
    """Return True if any component of the path is in SKIP_DIRS."""
    return any(p in SKIP_DIRS for p in path.relative_to(vault_root).parts)


def normalize_rel(path: Path, root: Path) -> str:
    """Return a root-relative path string with forward slashes."""
    return str(path.relative_to(root)).replace("\\", "/")


def normalize_tags(value: object, source: str = "") -> list[str]:
    """
    Normalise a frontmatter tags value to a flat list of strings.
    Logs a warning and returns [] for unexpected types.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [t.strip() for t in value.split(",") if t.strip()]
    if isinstance(value, list):
        result = []
        for t in value:
            if isinstance(t, str):
                if t.strip():
                    result.append(t.strip())
            else:
                logger.warning(
                    "Non-string tag {} in {}, skipping", repr(t), source or "unknown"
                )
        return result
    logger.warning(
        "Unexpected tags type {} in {}: {}, skipping",
        type(value).__name__,
        source or "unknown",
        repr(value),
    )
    return []


def extract_summary(body: str, max_len: int = 120) -> str:
    """
    Return the first line of body text that looks like prose.
    Skips headings, separators, blockquotes, tables, list items,
    wikilinks, and image embeds.
    """
    for line in body.splitlines():
        line = line.strip()
        if line and not any(line.startswith(p) for p in SUMMARY_SKIP_PREFIXES):
            return line[:max_len]
    return ""


def load_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """
    Load a markdown file and return (metadata_dict, body_text).
    Returns ({}, raw_text) on parse failure.
    """
    try:
        parsed = frontmatter.load(str(path))
        return dict(parsed.metadata or {}), parsed.content or ""
    except Exception as exc:
        logger.warning("Failed to parse frontmatter for {}: {}", path.name, exc)
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except Exception as read_exc:
            logger.error("Failed to read {}: {}", path.name, read_exc)
            body = ""
        return {}, body


def collect_pages(pages_dir: Path) -> list[Path]:
    """
    Return all .md files in wiki/pages/ - flat only, no subdirectories.
    Skips reserved filenames.
    """
    if not pages_dir.exists():
        logger.warning("Pages directory does not exist: {}", pages_dir)
        return []
    return sorted(
        f for f in pages_dir.glob("*.md") if f.name not in SKIP_FILES
    )


def collect_vault_files(vault_root: Path) -> list[Path]:
    """
    Return all .md files across the vault suitable for linting:
      - wiki/pages/*.md  (flat)
      - raw/**/*.md      (recursive)
      - wiki/*.md        (top-level only, not wiki/pages/ again)
    """
    results: list[Path] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            results.append(path)

    pages_dir = vault_root / "wiki" / "pages"
    if pages_dir.exists():
        for f in sorted(pages_dir.glob("*.md")):
            if f.name not in SKIP_FILES:
                _add(f)

    raw_dir = vault_root / "raw"
    if raw_dir.exists():
        for f in sorted(raw_dir.rglob("*.md")):
            rel = f.relative_to(vault_root)
            if not any(p in SKIP_DIRS for p in rel.parts) and f.name not in SKIP_FILES:
                _add(f)

    wiki_dir = vault_root / "wiki"
    if wiki_dir.exists():
        for f in sorted(wiki_dir.glob("*.md")):
            if f.name not in SKIP_FILES:
                _add(f)

    return results


def collect_md_files(vault_root: Path) -> list[Path]:
    """
    Return all .md files in the vault for search indexing.
    Uses rglob but skips SKIP_DIRS and SKIP_FILES.
    """
    results: list[Path] = []
    for f in sorted(vault_root.rglob("*.md")):
        if not should_skip(f, vault_root) and f.name not in SKIP_FILES:
            results.append(f)
    return results


def extract_wikilinks(content: str) -> list[str]:
    """Extract [[target]] and [[target|alias]] wikilink targets, skipping ![[embed]] syntax."""
    return re.findall(
        r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]", content
    )
