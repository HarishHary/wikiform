from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


logger = logger.bind(service="Wikiform - Config")
# Required frontmatter fields when SCHEMA.md has no parseable block.
DEFAULT_REQUIRED_FIELDS: frozenset[str] = frozenset({"title", "tags", "updated"})

# Fields that are always optional regardless of schema.
OPTIONAL_FIELDS: frozenset[str] = frozenset({"sources", "type"})


@dataclass
class SchemaConfig:
    categories: list[str]
    required_fields: frozenset[str]


def _parse_categories(text: str) -> list[str]:
    match = re.search(r"## Index Categories\n(.*?)(?=\n## |\Z)", text, re.DOTALL)
    if not match:
        logger.debug("No '## Index Categories' section found in SCHEMA.md")
        return []
    categories = [
        line.strip().lstrip("-").strip()
        for line in match.group(1).splitlines()
        if line.strip().lstrip("-").strip()
    ]
    logger.debug("Read {} categories from SCHEMA.md: {}", len(categories), categories)
    return categories


def _parse_required_fields(text: str) -> frozenset[str]:
    match = re.search(
        r"## (?:Wiki )?Page Frontmatter.*?```ya?ml(.*?)```", text, re.DOTALL
    )
    if not match:
        logger.debug("No Page Frontmatter block found in SCHEMA.md, using defaults")
        return DEFAULT_REQUIRED_FIELDS

    fields: set[str] = set()
    for line in match.group(1).splitlines():
        m = re.match(r"\s*([a-z_]+)\s*:", line)
        if m:
            fields.add(m.group(1))

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
    return schema_path.read_text(encoding="utf-8")


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


def load_schema(vault_root: Path) -> SchemaConfig:
    """Load all schema configuration in one file read."""
    text = _read_schema_text(vault_root)
    if text is None:
        return SchemaConfig(categories=[], required_fields=DEFAULT_REQUIRED_FIELDS)
    return SchemaConfig(
        categories=_parse_categories(text),
        required_fields=_parse_required_fields(text),
    )
