from __future__ import annotations

from pathlib import Path

import pytest

from wikiform.utils.fs import (
    extract_summary,
    extract_wikilinks,
    load_frontmatter,
    normalize_rel,
    normalize_tags,
    collect_pages,
    collect_vault_files,
    should_skip,
)


# ─── normalize_tags ───────────────────────────────────────────────────────────

def test_normalize_tags_list():
    assert normalize_tags(["foo", "bar"]) == ["foo", "bar"]


def test_normalize_tags_list_strips_whitespace():
    assert normalize_tags(["  foo  ", " bar"]) == ["foo", "bar"]


def test_normalize_tags_string_csv():
    assert normalize_tags("foo, bar, baz") == ["foo", "bar", "baz"]


def test_normalize_tags_none_returns_empty():
    assert normalize_tags(None) == []


def test_normalize_tags_empty_strings_silently_skipped():
    assert normalize_tags(["foo", "", "  ", "bar"]) == ["foo", "bar"]


def test_normalize_tags_non_string_warns(caplog):
    import logging
    result = normalize_tags([1, "valid"], source="test.md")
    assert result == ["valid"]


def test_normalize_tags_unexpected_type_warns():
    result = normalize_tags(42)
    assert result == []


# ─── extract_wikilinks ────────────────────────────────────────────────────────

def test_extract_wikilinks_basic():
    assert extract_wikilinks("See [[foo]] for details.") == ["foo"]


def test_extract_wikilinks_alias():
    assert extract_wikilinks("See [[foo|Foo Page]].") == ["foo"]


def test_extract_wikilinks_heading_anchor():
    assert extract_wikilinks("See [[foo#section]].") == ["foo"]


def test_extract_wikilinks_heading_and_alias():
    assert extract_wikilinks("[[foo#section|Label]]") == ["foo"]


def test_extract_wikilinks_multiple():
    links = extract_wikilinks("[[alpha]] and [[beta|Beta]]")
    assert links == ["alpha", "beta"]


def test_extract_wikilinks_empty():
    assert extract_wikilinks("No links here.") == []


def test_extract_wikilinks_ignores_images():
    assert extract_wikilinks("![[image.png]]") == []


# ─── extract_summary ─────────────────────────────────────────────────────────

def test_extract_summary_returns_first_prose():
    body = "# Heading\n\nThis is prose."
    assert extract_summary(body) == "This is prose."


def test_extract_summary_skips_headings_and_separators():
    body = "# H1\n---\n> quote\nActual prose."
    assert extract_summary(body) == "Actual prose."


def test_extract_summary_respects_max_len():
    body = "A" * 200
    assert len(extract_summary(body)) == 120


def test_extract_summary_empty_body():
    assert extract_summary("") == ""


def test_extract_summary_only_markup():
    assert extract_summary("# Heading\n---\n> quote") == ""


# ─── normalize_rel ────────────────────────────────────────────────────────────

def test_normalize_rel_produces_forward_slashes(tmp_path: Path):
    f = tmp_path / "sub" / "file.md"
    f.parent.mkdir()
    f.touch()
    result = normalize_rel(f, tmp_path)
    assert "\\" not in result
    assert result == "sub/file.md"


# ─── load_frontmatter ─────────────────────────────────────────────────────────

def test_load_frontmatter_valid(tmp_path: Path):
    f = tmp_path / "page.md"
    f.write_text("---\ntitle: Hello\ntags: [a, b]\n---\nBody text.", encoding="utf-8")
    meta, body = load_frontmatter(f)
    assert meta["title"] == "Hello"
    assert meta["tags"] == ["a", "b"]
    assert body.strip() == "Body text."


def test_load_frontmatter_no_frontmatter(tmp_path: Path):
    f = tmp_path / "page.md"
    f.write_text("Just plain text.", encoding="utf-8")
    meta, body = load_frontmatter(f)
    assert meta == {}
    assert "plain text" in body


def test_load_frontmatter_missing_file(tmp_path: Path):
    f = tmp_path / "missing.md"
    meta, body = load_frontmatter(f)
    assert meta == {}
    assert body == ""


# ─── should_skip ──────────────────────────────────────────────────────────────

def test_should_skip_returns_true_for_skip_dirs(tmp_path: Path):
    f = tmp_path / ".git" / "config"
    assert should_skip(f, tmp_path) is True


def test_should_skip_returns_false_for_normal_path(tmp_path: Path):
    f = tmp_path / "wiki" / "pages" / "foo.md"
    assert should_skip(f, tmp_path) is False


# ─── collect_pages ────────────────────────────────────────────────────────────

def test_collect_pages_returns_md_files(tmp_path: Path):
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "alpha.md").write_text("", encoding="utf-8")
    (pages / "beta.md").write_text("", encoding="utf-8")
    (pages / "README.md").write_text("", encoding="utf-8")
    result = collect_pages(pages)
    names = [f.name for f in result]
    assert "alpha.md" in names
    assert "beta.md" in names
    assert "README.md" not in names


def test_collect_pages_missing_dir(tmp_path: Path):
    assert collect_pages(tmp_path / "nonexistent") == []


# ─── collect_vault_files ──────────────────────────────────────────────────────

def test_collect_vault_files_covers_pages_raw_wiki(tmp_path: Path):
    (tmp_path / "wiki" / "pages").mkdir(parents=True)
    (tmp_path / "raw").mkdir()
    (tmp_path / "wiki" / "pages" / "page.md").write_text("", encoding="utf-8")
    (tmp_path / "raw" / "source.md").write_text("", encoding="utf-8")
    (tmp_path / "wiki" / "index.md").write_text("", encoding="utf-8")

    result = collect_vault_files(tmp_path)
    names = [f.name for f in result]
    assert "page.md" in names
    assert "source.md" in names
    assert "index.md" in names


def test_collect_vault_files_no_duplicates(tmp_path: Path):
    (tmp_path / "wiki" / "pages").mkdir(parents=True)
    (tmp_path / "wiki" / "pages" / "page.md").write_text("", encoding="utf-8")

    result = collect_vault_files(tmp_path)
    paths = [str(f) for f in result]
    assert len(paths) == len(set(paths))
