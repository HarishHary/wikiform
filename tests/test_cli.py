from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from wikiform.cli import cli


# ─── Helpers ──────────────────────────────────────────────────────────────────

def invoke(vault: Path, *args: str) -> "click.testing.Result":
    """Run the CLI with --vault-root set to *vault*, stdout and stderr separated."""
    runner = CliRunner()
    return runner.invoke(cli, ["--vault-root", str(vault), *args], catch_exceptions=False)


# ─── Top-level CLI ────────────────────────────────────────────────────────────

def test_cli_no_subcommand_prints_help(vault: Path):
    result = invoke(vault)
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_cli_version_flag():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "version" in result.output.lower()


def test_cli_missing_vault_root_errors():
    runner = CliRunner()
    result = runner.invoke(cli, ["index"])
    assert result.exit_code != 0


# ─── index command ────────────────────────────────────────────────────────────

def test_index_command_creates_output_files(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "alpha.md", "---\ntitle: Alpha\ntags: [engineering]\nupdated: 2024-01-01\n---\nContent.")
    result = invoke(vault, "index")
    assert result.exit_code == 0
    assert (vault / "wiki" / "index.md").exists()
    assert (vault / "wiki" / "master-index.md").exists()
    assert (vault / "wiki" / "tag-index.md").exists()


def test_index_command_outputs_json(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "beta.md", "---\ntitle: Beta\ntags: []\nupdated: 2024-01-01\n---\n")
    result = invoke(vault, "index")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "articles_scanned" in data
    assert data["articles_scanned"] >= 1


def test_index_command_counts_articles(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "p1.md", "---\ntitle: P1\ntags: []\nupdated: 2024-01-01\n---\n")
    write_page(vault, "p2.md", "---\ntitle: P2\ntags: []\nupdated: 2024-01-01\n---\n")
    result = invoke(vault, "index")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["articles_scanned"] == 2


# ─── lint command ─────────────────────────────────────────────────────────────

def test_lint_command_exits_zero_clean_vault(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "clean-page.md", "---\ntitle: Clean\ntags: [engineering]\nupdated: 2024-01-01\n---\nBody.")
    result = invoke(vault, "lint")
    assert result.exit_code == 0


def test_lint_command_outputs_json(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "my-page.md", "---\ntitle: My Page\ntags: []\nupdated: 2024-01-01\n---\nBody.")
    result = invoke(vault, "lint")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "summary" in data
    assert "issues" in data


def test_lint_command_single_check(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "my-page.md", "---\ntitle: My Page\ntags: []\nupdated: 2024-01-01\n---\nBody.")
    result = invoke(vault, "lint", "--check", "frontmatter")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["checks_run"] == ["frontmatter"]


def test_lint_command_detects_broken_link(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "broken.md", "---\ntitle: Broken\ntags: []\nupdated: 2024-01-01\n---\n[[no-such-page]]")
    result = invoke(vault, "lint")
    # exit code 1 because broken links are errors
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert any(i["check"] == "broken_link" for i in data["issues"])


def test_lint_command_unknown_check_errors(vault: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--vault-root", str(vault), "lint", "--check", "nonexistent"],
    )
    assert result.exit_code != 0


# ─── search index sub-command ─────────────────────────────────────────────────

def test_search_index_full_reindex(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "indexed.md", "---\ntitle: Indexed\ntags: [python]\nupdated: 2024-01-01\n---\nSearchable content.")
    result = invoke(vault, "search", "index")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["indexed"] >= 1
    assert data["incremental"] is False


def test_search_index_incremental_flag(vault: Path):
    from tests.conftest import write_page
    write_page(vault, "note.md", "---\ntitle: Note\ntags: []\nupdated: 2024-01-01\n---\nContent.")
    invoke(vault, "search", "index")  # full pass first
    result = invoke(vault, "search", "index", "--incremental")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["incremental"] is True
    assert data["skipped"] >= 1


def test_search_index_outputs_json_fields(vault: Path):
    result = invoke(vault, "search", "index")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    for key in ("vault_root", "incremental", "generated_at", "indexed", "skipped", "deleted", "total"):
        assert key in data, f"Missing key: {key}"
