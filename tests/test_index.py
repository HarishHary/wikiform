from __future__ import annotations

from pathlib import Path

from wikiform.cmd.index import Article, IndexWriter, run_index


def make_article(stem: str, title: str, tags: list[str], summary: str = "") -> Article:
    return Article(stem=stem, title=title, tags=tags, updated="2024-01-01", kind="", summary=summary)


# ─── IndexWriter.write_category_index ────────────────────────────────────────

def test_write_category_index_creates_file(tmp_path: Path):
    articles = [make_article("foo", "Foo", ["engineering"])]
    writer = IndexWriter(vault_root=tmp_path, articles=articles, categories=["Engineering"])
    out, n_cats = writer.write_category_index()
    assert out.exists()
    assert n_cats >= 1


def test_write_category_index_contains_article(tmp_path: Path):
    articles = [make_article("foo", "Foo Page", ["engineering"])]
    writer = IndexWriter(vault_root=tmp_path, articles=articles, categories=["Engineering"])
    out, _ = writer.write_category_index()
    content = out.read_text()
    assert "Foo Page" in content
    assert "[[foo|Foo Page]]" in content


def test_write_category_index_uncategorised(tmp_path: Path):
    articles = [make_article("foo", "Foo", ["unknown-tag"])]
    writer = IndexWriter(vault_root=tmp_path, articles=articles, categories=["Engineering"])
    out, _ = writer.write_category_index()
    assert "Uncategorised" in out.read_text()


def test_write_category_index_summary_included(tmp_path: Path):
    articles = [make_article("foo", "Foo", ["engineering"], summary="Short description.")]
    writer = IndexWriter(vault_root=tmp_path, articles=articles, categories=["Engineering"])
    out, _ = writer.write_category_index()
    assert "Short description." in out.read_text()


def test_write_category_index_auto_generated_frontmatter(tmp_path: Path):
    writer = IndexWriter(vault_root=tmp_path, articles=[], categories=[])
    out, _ = writer.write_category_index()
    assert "auto_generated: true" in out.read_text()


# ─── IndexWriter.write_master_index ──────────────────────────────────────────

def test_write_master_index_creates_file(tmp_path: Path):
    articles = [make_article("alpha", "Alpha Page", [])]
    writer = IndexWriter(vault_root=tmp_path, articles=articles, categories=[])
    out = writer.write_master_index()
    assert out.exists()


def test_write_master_index_groups_by_letter(tmp_path: Path):
    articles = [
        make_article("alpha", "Alpha", []),
        make_article("beta", "Beta", []),
    ]
    writer = IndexWriter(vault_root=tmp_path, articles=articles, categories=[])
    content = writer.write_master_index().read_text()
    assert "## A" in content
    assert "## B" in content


def test_write_master_index_non_alpha_under_hash(tmp_path: Path):
    articles = [make_article("42things", "42 Things", [])]
    writer = IndexWriter(vault_root=tmp_path, articles=articles, categories=[])
    content = writer.write_master_index().read_text()
    assert "## #" in content


# ─── IndexWriter.write_tag_index ─────────────────────────────────────────────

def test_write_tag_index_creates_file(tmp_path: Path):
    articles = [make_article("foo", "Foo", ["python"])]
    writer = IndexWriter(vault_root=tmp_path, articles=articles, categories=[])
    out, n_tags = writer.write_tag_index()
    assert out.exists()
    assert n_tags == 1


def test_write_tag_index_groups_by_tag(tmp_path: Path):
    articles = [
        make_article("a", "A", ["python"]),
        make_article("b", "B", ["python", "testing"]),
    ]
    writer = IndexWriter(vault_root=tmp_path, articles=articles, categories=[])
    content, n_tags = writer.write_tag_index()
    text = content.read_text()
    assert "## python" in text
    assert "## testing" in text
    assert n_tags == 2


# ─── run_index integration ────────────────────────────────────────────────────

def test_run_index_creates_all_three_files(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "my-page.md", "---\ntitle: My Page\ntags: [engineering]\nupdated: 2024-01-01\n---\nContent.")
    result = run_index(vault)
    assert Path(result.category_index_path).exists()
    assert Path(result.master_index_path).exists()
    assert Path(result.tag_index_path).exists()


def test_run_index_counts_articles(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "a.md", "---\ntitle: A\ntags: []\nupdated: 2024-01-01\n---\n")
    write_page(vault, "b.md", "---\ntitle: B\ntags: []\nupdated: 2024-01-01\n---\n")
    result = run_index(vault)
    assert result.articles_scanned == 2
