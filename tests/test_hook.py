from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from tests.conftest import write_page, write_raw
from wikiform.cli import cli
from wikiform.cmd.hook import DIRTY_FLAG
from wikiform.utils.db import db_path

GOOD_PAGE = "---\ntitle: Good\ntags: [Research]\nupdated: 2024-01-01\n---\nBody text.\n"
RAW_WITH_FM = "---\ntitle: Src\nstatus: raw\nslug: ''\n---\n\nImmutable body.\n"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_VAULT_ROOT", raising=False)


def run_hook(event: str, payload: dict | str | None, *, cwd: Path | None = None) -> Result:
    if isinstance(payload, dict):
        payload = {"cwd": str(cwd or Path.cwd()), **payload}
        payload = json.dumps(payload)
    return CliRunner().invoke(cli, ["hook", event], input=payload or "")


def tool(name: str, path: Path, **tool_input) -> dict:
    return {"tool_name": name, "tool_input": {"file_path": str(path), **tool_input}}


# ─── guard ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["index.md", "tag-index.md", "master-index.md"])
def test_guard_blocks_edits_to_existing_generated_indexes(vault: Path, name: str):
    f = vault / "wiki" / name
    f.write_text("---\nauto_generated: true\n---\n", encoding="utf-8")
    for t in ("Write", "Edit"):
        result = run_hook("guard", tool(t, f, content="x", old_string="a", new_string="b"), cwd=vault)
        assert result.exit_code == 2
        assert "auto-generated" in result.stderr and "index" in result.stderr


def test_guard_allows_creating_generated_indexes(vault: Path):
    """wiki-init has to be able to create them the first time."""
    result = run_hook("guard", tool("Write", vault / "wiki" / "index.md", content="x"), cwd=vault)
    assert result.exit_code == 0 and result.stderr == ""


def test_guard_blocks_rewriting_raw_body(vault: Path):
    f = write_raw(vault, "papers/src.md", RAW_WITH_FM)
    result = run_hook("guard", tool("Write", f, content="---\ntitle: Src\n---\n\nChanged body.\n"), cwd=vault)
    assert result.exit_code == 2 and "immutable" in result.stderr


def test_guard_allows_write_that_only_changes_raw_frontmatter(vault: Path):
    f = write_raw(vault, "papers/src.md", RAW_WITH_FM)
    new = "---\ntitle: Src\nstatus: ingested\nslug: src\n---\n\nImmutable body.\n"
    assert run_hook("guard", tool("Write", f, content=new), cwd=vault).exit_code == 0


def test_guard_allows_edit_inside_raw_frontmatter(vault: Path):
    f = write_raw(vault, "papers/src.md", RAW_WITH_FM)
    result = run_hook("guard", tool("Edit", f, old_string="status: raw", new_string="status: ingested"), cwd=vault)
    assert result.exit_code == 0


def test_guard_blocks_edit_touching_raw_body(vault: Path):
    f = write_raw(vault, "papers/src.md", RAW_WITH_FM)
    result = run_hook("guard", tool("Edit", f, old_string="Immutable body.", new_string="New."), cwd=vault)
    assert result.exit_code == 2


def test_guard_blocks_edit_spanning_frontmatter_into_body(vault: Path):
    f = write_raw(vault, "papers/src.md", RAW_WITH_FM)
    result = run_hook("guard", tool("Edit", f, old_string="slug: ''\n---\n\nImmutable", new_string="x"), cwd=vault)
    assert result.exit_code == 2


def test_guard_checks_every_edit_in_multiedit(vault: Path):
    f = write_raw(vault, "papers/src.md", RAW_WITH_FM)
    edits = [{"old_string": "status: raw", "new_string": "status: ingested"}, {"old_string": "Immutable body.", "new_string": "x"}]
    assert run_hook("guard", tool("MultiEdit", f, edits=edits), cwd=vault).exit_code == 2
    assert run_hook("guard", tool("MultiEdit", f, edits=edits[:1]), cwd=vault).exit_code == 0


def test_guard_allows_adding_frontmatter_to_raw_file_without_any(vault: Path):
    f = write_raw(vault, "papers/pasted.md", "Just pasted text.\n")
    result = run_hook("guard", tool("Edit", f, old_string="Just pasted", new_string="---\ntitle: P\n---\nJust pasted"), cwd=vault)
    assert result.exit_code == 0
    assert run_hook("guard", tool("Edit", f, old_string="pasted text", new_string="other"), cwd=vault).exit_code == 2


def test_guard_allows_sidecar_meta_yaml(vault: Path):
    f = vault / "raw" / "images" / "pic.png.meta.yaml"
    f.parent.mkdir(parents=True)
    f.write_text("title: x\n", encoding="utf-8")
    assert run_hook("guard", tool("Write", f, content="title: y\n"), cwd=vault).exit_code == 0


def test_guard_ignores_wiki_pages_and_other_tools(vault: Path, tmp_path: Path):
    page = write_page(vault, "p.md", GOOD_PAGE)
    assert run_hook("guard", tool("Write", page, content="x"), cwd=vault).exit_code == 0
    assert run_hook("guard", {"tool_name": "Bash", "tool_input": {"command": "ls"}}, cwd=vault).exit_code == 0


def test_guard_ignores_files_outside_any_vault(tmp_path: Path):
    outside = tmp_path / "elsewhere" / "raw" / "x.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("x", encoding="utf-8")
    result = run_hook("guard", tool("Write", outside, content="y"), cwd=tmp_path)
    assert result.exit_code == 0 and result.stderr == ""


def test_guard_resolves_relative_paths_against_cwd(vault: Path):
    f = vault / "wiki" / "index.md"
    f.write_text("x", encoding="utf-8")
    payload = {"tool_name": "Write", "tool_input": {"file_path": "wiki/index.md", "content": "y"}}
    assert run_hook("guard", payload, cwd=vault).exit_code == 2


def test_guard_uses_configured_vault_root(vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_VAULT_ROOT", str(vault))
    f = vault / "wiki" / "index.md"
    f.write_text("x", encoding="utf-8")
    assert run_hook("guard", tool("Write", f, content="y"), cwd=tmp_path).exit_code == 2


@pytest.mark.parametrize("payload", ["", "not json", "[]", "{}", None])
def test_hooks_fail_open_on_bad_input(payload):
    for event in ("guard", "post-write", "finalize", "session-start"):
        result = run_hook(event, payload)
        assert result.exit_code == 0, event


# ─── post-write ───────────────────────────────────────────────────────────────

def test_post_write_valid_page_marks_vault_dirty(vault: Path):
    page = write_page(vault, "good-page.md", GOOD_PAGE)
    result = run_hook("post-write", tool("Write", page, content=GOOD_PAGE), cwd=vault)
    assert result.exit_code == 0 and result.stderr == ""
    assert (vault / DIRTY_FLAG).exists()


def test_post_write_reports_missing_frontmatter_fields(vault: Path):
    page = write_page(vault, "thin-page.md", "---\ntitle: Thin\n---\nBody\n")
    result = run_hook("post-write", tool("Write", page, content=""), cwd=vault)
    assert result.exit_code == 2
    assert "tags" in result.stderr and "updated" in result.stderr


def test_post_write_enforces_first_tag_is_an_index_category(vault: Path):
    page = write_page(vault, "wrong-tag.md", "---\ntitle: T\ntags: [entity, Research]\nupdated: 2024-01-01\n---\nBody\n")
    result = run_hook("post-write", tool("Write", page, content=""), cwd=vault)
    assert result.exit_code == 2
    assert "First tag 'entity' is not an Index Category" in result.stderr and "Research" in result.stderr
    page = write_page(vault, "no-tags.md", "---\ntitle: T\ntags: []\nupdated: 2024-01-01\n---\nBody\n")
    assert "No tags" in run_hook("post-write", tool("Write", page, content=""), cwd=vault).stderr


def test_post_write_first_tag_match_is_case_insensitive(vault: Path):
    page = write_page(vault, "ci-page.md", "---\ntitle: T\ntags: [research]\nupdated: 2024-01-01\n---\nBody\n")
    assert run_hook("post-write", tool("Write", page, content=""), cwd=vault).exit_code == 0


def test_post_write_reports_non_kebab_filename(vault: Path):
    page = write_page(vault, "Bad_Name.md", GOOD_PAGE)
    result = run_hook("post-write", tool("Write", page, content=""), cwd=vault)
    assert result.exit_code == 2 and "kebab" in result.stderr


def test_post_write_reports_missing_frontmatter(vault: Path):
    page = write_page(vault, "no-fm.md", "Just text\n")
    assert run_hook("post-write", tool("Write", page, content=""), cwd=vault).exit_code == 2


def test_post_write_ignores_raw_and_generated_files(vault: Path):
    raw = write_raw(vault, "papers/src.md", RAW_WITH_FM)
    idx = vault / "wiki" / "index.md"
    idx.write_text("x", encoding="utf-8")
    for f in (raw, idx):
        result = run_hook("post-write", tool("Write", f, content=""), cwd=vault)
        assert result.exit_code == 0
    assert not (vault / DIRTY_FLAG).exists()


def test_post_write_ignores_non_vault_files(tmp_path: Path):
    f = tmp_path / "wiki" / "pages" / "x.md"
    f.parent.mkdir(parents=True)
    f.write_text("no frontmatter", encoding="utf-8")
    assert run_hook("post-write", tool("Write", f, content=""), cwd=tmp_path).exit_code == 0


# ─── finalize ─────────────────────────────────────────────────────────────────

def test_finalize_reindexes_and_clears_flag(vault: Path):
    write_page(vault, "good-page.md", GOOD_PAGE)
    (vault / "_meta").mkdir(exist_ok=True)
    (vault / DIRTY_FLAG).touch()
    result = run_hook("finalize", {}, cwd=vault)
    assert result.exit_code == 0
    assert "good-page" in (vault / "wiki" / "index.md").read_text(encoding="utf-8")
    assert "good-page" in (vault / "wiki" / "master-index.md").read_text(encoding="utf-8")
    assert db_path(vault).exists()
    assert not (vault / DIRTY_FLAG).exists()


def test_finalize_is_a_no_op_when_not_dirty(vault: Path):
    write_page(vault, "good-page.md", GOOD_PAGE)
    result = run_hook("finalize", {}, cwd=vault)
    assert result.exit_code == 0 and result.stderr == ""
    assert not (vault / "wiki" / "index.md").exists()
    assert not db_path(vault).exists()


def test_finalize_keeps_flag_when_reindex_fails(vault: Path, monkeypatch: pytest.MonkeyPatch):
    (vault / "_meta").mkdir(exist_ok=True)
    (vault / DIRTY_FLAG).touch()

    def boom(root):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr("wikiform.cmd.index.run_index", boom)
    assert run_hook("finalize", {}, cwd=vault).exit_code == 0
    assert (vault / DIRTY_FLAG).exists()  # retried at the next Stop


def test_finalize_outside_a_vault_does_nothing(tmp_path: Path):
    result = run_hook("finalize", {}, cwd=tmp_path)
    assert result.exit_code == 0 and result.stdout == ""


# ─── session-start ────────────────────────────────────────────────────────────

def test_session_start_silent_outside_vault(tmp_path: Path):
    result = run_hook("session-start", {}, cwd=tmp_path)
    assert result.exit_code == 0 and result.stdout == ""


def test_session_start_reports_vault_status(vault: Path):
    write_page(vault, "a-page.md", GOOD_PAGE)
    write_raw(vault, "papers/pending.md", RAW_WITH_FM)
    write_raw(vault, "papers/done.md", "---\ntitle: D\nstatus: ingested\n---\nx\n")
    (vault / "wiki" / "log.md").write_text("# Log\n\n## [2024-02-02] ingest | b\n\n## [2024-02-01] ingest | a\n\n## [2024-01-31] lint | x\n\n## [2024-01-30] ingest | old\n", encoding="utf-8")
    out = run_hook("session-start", {}, cwd=vault).stdout
    assert "1 pages" in out
    assert "1 raw sources awaiting ingest" in out
    assert "2 ingests since last lint" in out
    assert "search index: not built" in out and "search index --incremental" in out


def test_session_start_detects_stale_and_fresh_search_index(vault: Path):
    from wikiform.cmd.fts_index import run_fts_index

    page = write_page(vault, "a-page.md", GOOD_PAGE)
    run_fts_index(vault, incremental=False)
    assert "search index: up to date" in run_hook("session-start", {}, cwd=vault).stdout
    time.sleep(0.01)
    os.utime(page, None)
    assert "search index: stale" in run_hook("session-start", {}, cwd=vault).stdout
    write_page(vault, "second-page.md", GOOD_PAGE)
    assert "search index: stale" in run_hook("session-start", {}, cwd=vault).stdout


def test_session_start_finds_vault_from_subdirectory(vault: Path):
    assert "Wikiform vault" in run_hook("session-start", {}, cwd=vault / "wiki" / "pages").stdout


# ─── plugin wiring ────────────────────────────────────────────────────────────

def test_hooks_json_only_references_existing_handlers():
    import re

    from wikiform.cmd.hook import _HANDLERS

    config = json.loads((Path(__file__).parent.parent / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    used = set()
    for entries in config["hooks"].values():
        for entry in entries:
            for h in entry["hooks"]:
                assert h["type"] == "command"
                used.update(re.findall(r"wikiform hook ([\w-]+)", h["command"]))
    assert used == set(_HANDLERS)
    assert set(config["hooks"]) == {"SessionStart", "PreToolUse", "PostToolUse", "Stop"}
