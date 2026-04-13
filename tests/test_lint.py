from __future__ import annotations

import time
from pathlib import Path

import pytest

from wikiform.cmd.lint import (
    AUTO_GENERATED_WIKI_FILES,
    FileInfo,
    Issue,
    Linter,
    _compute_health,
    _resolve_link,
    run_lint,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_file(
    path: str,
    meta: dict | None = None,
    content: str = "Some prose content.",
    size: int = 100,
    mtime: float = time.time(),
) -> FileInfo:
    stem = Path(path).stem
    return FileInfo(
        path=path,
        abs_path=f"/vault/{path}",
        stem=stem,
        meta=meta if meta is not None else {"title": stem, "tags": [], "updated": "2024-01-01"},
        content=content,
        size=size,
        mtime=mtime,
    )


def make_linter(files: dict[str, FileInfo], pages_dir_rel: str = "wiki/pages") -> Linter:
    return Linter(
        files=files,
        required_fields=frozenset({"title", "tags", "updated"}),
        pages_dir_rel=pages_dir_rel,
    )


# ─── _resolve_link ────────────────────────────────────────────────────────────

def test_resolve_link_by_stem():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md")}
    linter = make_linter(files)
    assert linter._stem_map.get("foo") == ["wiki/pages/foo.md"]
    result = _resolve_link("foo", files, linter._stem_map)
    assert result == ["wiki/pages/foo.md"]


def test_resolve_link_with_md_extension():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md")}
    linter = make_linter(files)
    result = _resolve_link("foo.md", files, linter._stem_map)
    assert result == ["wiki/pages/foo.md"]


def test_resolve_link_missing():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md")}
    linter = make_linter(files)
    result = _resolve_link("nonexistent", files, linter._stem_map)
    assert result == []


def test_resolve_link_subdirectory_prefix():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md")}
    linter = make_linter(files)
    result = _resolve_link("pages/foo", files, linter._stem_map)
    assert "wiki/pages/foo.md" in result


# ─── check_broken_links ───────────────────────────────────────────────────────

def test_check_broken_links_no_issues():
    files = {
        "wiki/pages/foo.md": make_file("wiki/pages/foo.md", content="See [[bar]]."),
        "wiki/pages/bar.md": make_file("wiki/pages/bar.md"),
    }
    issues = make_linter(files).check_broken_links()
    assert issues == []


def test_check_broken_links_detects_broken():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md", content="[[missing]]")}
    issues = make_linter(files).check_broken_links()
    assert len(issues) == 1
    assert issues[0].type == "error"
    assert "missing" in issues[0].message


def test_check_broken_links_skips_auto_generated():
    files = {
        "wiki/index.md": make_file("wiki/index.md", content="[[gone]]"),
    }
    issues = make_linter(files).check_broken_links()
    assert issues == []


def test_check_broken_links_skips_auto_generated_meta():
    files = {
        "wiki/pages/gen.md": make_file("wiki/pages/gen.md", meta={"auto_generated": True}, content="[[gone]]"),
    }
    issues = make_linter(files).check_broken_links()
    assert issues == []


# ─── check_frontmatter ────────────────────────────────────────────────────────

def test_check_frontmatter_valid():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md")}
    issues = make_linter(files).check_frontmatter()
    assert issues == []


def test_check_frontmatter_missing():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md", meta={})}
    issues = make_linter(files).check_frontmatter()
    assert any(i.type == "error" and i.check == "frontmatter" for i in issues)


def test_check_frontmatter_missing_required_field():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md", meta={"title": "Foo"})}
    issues = make_linter(files).check_frontmatter()
    assert any(i.type == "warning" and "tags" in i.message for i in issues)


def test_check_frontmatter_tags_not_list():
    files = {"wiki/pages/foo.md": make_file(
        "wiki/pages/foo.md",
        meta={"title": "Foo", "tags": "not-a-list", "updated": "2024-01-01"},
    )}
    issues = make_linter(files).check_frontmatter()
    assert any("tags" in i.message and "list" in i.message for i in issues)


def test_check_frontmatter_skips_auto_generated():
    files = {"wiki/index.md": make_file("wiki/index.md", meta={})}
    issues = make_linter(files).check_frontmatter()
    assert issues == []


# ─── check_orphans ────────────────────────────────────────────────────────────

def test_check_orphans_linked_file_not_orphan():
    files = {
        "wiki/pages/hub.md": make_file("wiki/pages/hub.md", content="See [[leaf]]."),
        "wiki/pages/leaf.md": make_file("wiki/pages/leaf.md"),
    }
    issues = make_linter(files).check_orphans()
    orphan_paths = [i.file for i in issues if i.check == "orphan"]
    assert "wiki/pages/leaf.md" not in orphan_paths


def test_check_orphans_unlinked_file_is_orphan():
    files = {"wiki/pages/lone.md": make_file("wiki/pages/lone.md")}
    issues = make_linter(files).check_orphans()
    assert any(i.file == "wiki/pages/lone.md" for i in issues)


def test_check_orphans_auto_generated_links_dont_count():
    files = {
        "wiki/index.md": make_file("wiki/index.md", content="[[lone]]"),
        "wiki/pages/lone.md": make_file("wiki/pages/lone.md"),
    }
    issues = make_linter(files).check_orphans()
    assert any(i.file == "wiki/pages/lone.md" for i in issues)


def test_check_orphans_skips_templates():
    files = {"templates/note.md": make_file("templates/note.md")}
    issues = make_linter(files).check_orphans()
    assert issues == []


# ─── check_tag_consistency ────────────────────────────────────────────────────

def test_check_tag_consistency_single_use_tag():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md", meta={
        "title": "Foo", "tags": ["rare-tag"], "updated": "2024-01-01",
    })}
    issues = make_linter(files).check_tag_consistency()
    assert any("rare-tag" in i.message for i in issues)


def test_check_tag_consistency_similar_tags():
    files = {
        "wiki/pages/a.md": make_file("wiki/pages/a.md", meta={
            "title": "A", "tags": ["machine-learning"], "updated": "2024-01-01",
        }),
        "wiki/pages/b.md": make_file("wiki/pages/b.md", meta={
            "title": "B", "tags": ["machine_learning"], "updated": "2024-01-01",
        }),
    }
    issues = make_linter(files).check_tag_consistency()
    assert any("similar" in i.message.lower() for i in issues)


def test_check_tag_consistency_skips_auto_generated():
    files = {
        "wiki/index.md": make_file("wiki/index.md", meta={
            "title": "Index", "tags": ["only-here"], "updated": "2024-01-01",
        }),
    }
    issues = make_linter(files).check_tag_consistency()
    assert not any("only-here" in i.message for i in issues)


# ─── check_stale_raw ─────────────────────────────────────────────────────────

def test_check_stale_raw_old_file():
    old_mtime = time.time() - 8 * 86400  # 8 days ago
    files = {"raw/source.md": make_file(
        "raw/source.md",
        meta={"status": "raw"},
        mtime=old_mtime,
    )}
    issues = make_linter(files).check_stale_raw()
    assert any(i.check == "stale_raw" for i in issues)


def test_check_stale_raw_recent_file():
    files = {"raw/source.md": make_file(
        "raw/source.md",
        meta={"status": "raw"},
        mtime=time.time(),
    )}
    issues = make_linter(files).check_stale_raw()
    assert issues == []


def test_check_stale_raw_skips_zero_mtime():
    files = {"raw/source.md": make_file(
        "raw/source.md",
        meta={"status": "raw"},
        mtime=0.0,
    )}
    issues = make_linter(files).check_stale_raw()
    assert issues == []


def test_check_stale_raw_only_raw_status():
    old_mtime = time.time() - 8 * 86400
    files = {"raw/source.md": make_file(
        "raw/source.md",
        meta={"status": "processed"},
        mtime=old_mtime,
    )}
    issues = make_linter(files).check_stale_raw()
    assert issues == []


# ─── check_naming ─────────────────────────────────────────────────────────────

def test_check_naming_valid_kebab():
    files = {"wiki/pages/my-page.md": make_file("wiki/pages/my-page.md")}
    issues = make_linter(files).check_naming()
    assert issues == []


def test_check_naming_invalid_uppercase():
    files = {"wiki/pages/MyPage.md": make_file("wiki/pages/MyPage.md")}
    issues = make_linter(files).check_naming()
    assert any(i.check == "naming" for i in issues)


def test_check_naming_invalid_spaces():
    files = {"wiki/pages/my page.md": make_file("wiki/pages/my page.md")}
    issues = make_linter(files).check_naming()
    assert any(i.check == "naming" for i in issues)


def test_check_naming_skips_non_pages():
    files = {"raw/My_Source.md": make_file("raw/My_Source.md")}
    issues = make_linter(files).check_naming()
    assert issues == []


# ─── check_empty ──────────────────────────────────────────────────────────────

def test_check_empty_zero_bytes():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md", size=0, content="")}
    issues = make_linter(files).check_empty()
    assert any(i.type == "warning" and i.check == "empty" for i in issues)


def test_check_empty_frontmatter_no_body():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md", content="  ", size=50)}
    issues = make_linter(files).check_empty()
    assert any(i.type == "info" and i.check == "empty" for i in issues)


def test_check_empty_skips_auto_generated():
    files = {"wiki/index.md": make_file("wiki/index.md", content="", size=0)}
    issues = make_linter(files).check_empty()
    assert issues == []


# ─── _compute_health ──────────────────────────────────────────────────────────

def test_compute_health_good():
    assert _compute_health(0, 0) == "GOOD"


def test_compute_health_good_few_warnings():
    assert _compute_health(0, 5) == "GOOD"


def test_compute_health_fair():
    assert _compute_health(0, 6) == "FAIR"


def test_compute_health_needs_attention():
    assert _compute_health(1, 0) == "NEEDS_ATTENTION"


# ─── Linter.run ───────────────────────────────────────────────────────────────

def test_run_single_check():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md", meta={})}
    linter = make_linter(files)
    issues, checks_run = linter.run("frontmatter")
    assert checks_run == ["frontmatter"]
    assert all(i.check == "frontmatter" for i in issues)


def test_run_all_checks():
    files = {"wiki/pages/foo.md": make_file("wiki/pages/foo.md")}
    linter = make_linter(files)
    _, checks_run = linter.run()
    assert len(checks_run) == 8


def test_run_unknown_check_raises():
    linter = make_linter({})
    with pytest.raises(ValueError, match="Unknown check"):
        linter.run("nonexistent")


# ─── run_lint integration ─────────────────────────────────────────────────────

def test_run_lint_returns_report(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "my-page.md", "---\ntitle: My Page\ntags: [engineering]\nupdated: 2024-01-01\n---\nContent.")
    report = run_lint(vault, vault / "wiki" / "pages")
    assert report.summary.files_scanned >= 1
    assert report.summary.overall_health in ("GOOD", "FAIR", "NEEDS_ATTENTION")


def test_run_lint_detects_broken_link(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "broken.md", "---\ntitle: Broken\ntags: []\nupdated: 2024-01-01\n---\n[[nonexistent]]")
    report = run_lint(vault, vault / "wiki" / "pages")
    assert any(i.check == "broken_link" for i in report.issues)
    assert report.summary.errors >= 1
