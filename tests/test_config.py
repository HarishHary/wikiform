from __future__ import annotations

from pathlib import Path

from wikiform.utils.config import (
    DEFAULT_REQUIRED_FIELDS,
    SchemaConfig,
    _parse_categories,
    _parse_required_fields,
    load_schema,
    read_schema_categories,
    read_schema_required_fields,
)


SCHEMA_TEXT = """\
## Index Categories
- Engineering
- Research
- Design

## Wiki Page Frontmatter
```yaml
title: ""
tags: []
updated: ""
summary: ""
```
"""


# ─── _parse_categories ────────────────────────────────────────────────────────

def test_parse_categories_extracts_list():
    result = _parse_categories(SCHEMA_TEXT)
    assert result == ["Engineering", "Research", "Design"]


def test_parse_categories_missing_section():
    result = _parse_categories("No categories here.")
    assert result == []


def test_parse_categories_ignores_empty_lines():
    text = "## Index Categories\n- Alpha\n\n- Beta\n\n## Other\n"
    assert _parse_categories(text) == ["Alpha", "Beta"]


# ─── _parse_required_fields ───────────────────────────────────────────────────

def test_parse_required_fields_extracts_fields():
    result = _parse_required_fields(SCHEMA_TEXT)
    assert "title" in result
    assert "tags" in result
    assert "updated" in result


def test_parse_required_fields_excludes_optional():
    result = _parse_required_fields(SCHEMA_TEXT)
    assert "sources" not in result
    assert "type" not in result


def test_parse_required_fields_missing_block():
    result = _parse_required_fields("No frontmatter block here.")
    assert result == DEFAULT_REQUIRED_FIELDS


def test_parse_required_fields_empty_block():
    text = "## Wiki Page Frontmatter\n```yaml\n```\n"
    result = _parse_required_fields(text)
    assert result == DEFAULT_REQUIRED_FIELDS


# ─── load_schema ──────────────────────────────────────────────────────────────

def test_load_schema_returns_schema_config(tmp_path: Path):
    (tmp_path / "SCHEMA.md").write_text(SCHEMA_TEXT, encoding="utf-8")
    result = load_schema(tmp_path)
    assert isinstance(result, SchemaConfig)
    assert "Engineering" in result.categories
    assert "title" in result.required_fields


def test_load_schema_missing_file_returns_defaults(tmp_path: Path):
    result = load_schema(tmp_path)
    assert result.categories == []
    assert result.required_fields == DEFAULT_REQUIRED_FIELDS


# ─── read_schema_categories / read_schema_required_fields ─────────────────────

def test_read_schema_categories(tmp_path: Path):
    (tmp_path / "SCHEMA.md").write_text(SCHEMA_TEXT, encoding="utf-8")
    assert read_schema_categories(tmp_path) == ["Engineering", "Research", "Design"]


def test_read_schema_categories_missing_file(tmp_path: Path):
    assert read_schema_categories(tmp_path) == []


def test_read_schema_required_fields(tmp_path: Path):
    (tmp_path / "SCHEMA.md").write_text(SCHEMA_TEXT, encoding="utf-8")
    fields = read_schema_required_fields(tmp_path)
    assert "title" in fields
    assert "updated" in fields


def test_read_schema_required_fields_missing_file(tmp_path: Path):
    assert read_schema_required_fields(tmp_path) == DEFAULT_REQUIRED_FIELDS
