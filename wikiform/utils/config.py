from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

logger = logger.bind(service="Wikiform - Config")
# Required frontmatter fields when SCHEMA.md has no parseable block.
DEFAULT_REQUIRED_FIELDS: frozenset[str] = frozenset({"title", "tags", "updated"})

# Fields that are always optional regardless of schema.
OPTIONAL_FIELDS: frozenset[str] = frozenset({"sources", "type"})


def _parse_categories(text: str) -> list[str]:
    match = re.search(r"## Index Categories\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not match:
        logger.debug("No '## Index Categories' section found in SCHEMA.md")
        return []
    categories = []
    for line in match.group(1).splitlines():
        name = re.sub(r"^[-*]\s+", "", line.strip()).strip()  # drop one bullet marker, keep dashes inside names
        if name:
            categories.append(name)
    logger.debug("Read {} categories from SCHEMA.md: {}", len(categories), categories)
    return categories


def _parse_required_fields(text: str) -> frozenset[str]:
    match = re.search(r"## (?:Wiki )?Page Frontmatter.*?```ya?ml(.*?)```", text, re.DOTALL)
    if not match:
        logger.debug("No Page Frontmatter block found in SCHEMA.md, using defaults")
        return DEFAULT_REQUIRED_FIELDS

    # Only top-level keys (column 0): indented lines belong to nested values, not required fields.
    fields = set(re.findall(r"^([A-Za-z_][\w-]*)\s*:", match.group(1), re.MULTILINE))

    if not fields:
        logger.debug("No fields parsed from SCHEMA.md frontmatter block, using defaults")
        return DEFAULT_REQUIRED_FIELDS

    fields -= OPTIONAL_FIELDS
    logger.debug("Required fields from SCHEMA.md: {}", fields)
    return frozenset(fields)


def _read_schema_text(vault_root: Path) -> str | None:
    schema_path = vault_root / "SCHEMA.md"
    if not schema_path.exists():
        logger.debug("SCHEMA.md not found at {}", schema_path)
        return None
    return schema_path.read_text(encoding="utf-8").replace("\r\n", "\n")


def read_schema_categories(vault_root: Path) -> list[str]:
    """Read index categories from SCHEMA.md ## Index Categories section."""
    text = _read_schema_text(vault_root)
    return _parse_categories(text) if text is not None else []


def read_schema_required_fields(vault_root: Path) -> frozenset[str]:
    """Read required frontmatter fields from SCHEMA.md, falling back to defaults."""
    text = _read_schema_text(vault_root)
    if text is None:
        logger.debug("Using default required fields: {}", DEFAULT_REQUIRED_FIELDS)
        return DEFAULT_REQUIRED_FIELDS
    return _parse_required_fields(text)
