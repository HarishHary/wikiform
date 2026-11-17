from __future__ import annotations

import json
from pathlib import Path

import frontmatter
import pytest
from click.testing import CliRunner

from wikiform.cli import cli
from wikiform.cmd.extract import _build_markdown, _fence, _file_slug, _url_slug, run_extract


def test_frontmatter_survives_yaml_special_characters_in_title():
    md = _build_markdown('Attention: Is All You Need #1 "quoted"', "paper", "body", None, source_url="https://x.org/a?b=c#d")
    meta = frontmatter.loads(md).metadata
    assert meta["title"] == 'Attention: Is All You Need #1 "quoted"'
    assert meta["source_url"] == "https://x.org/a?b=c#d"
    assert meta["status"] == "raw"
    assert meta["ingested_to"] == []


def test_frontmatter_field_order_is_stable():
    md = _build_markdown("T", "paper", "body", None)
    keys = list(frontmatter.loads(md).metadata)
    assert keys == ["title", "source_type", "status", "slug", "ingested_date", "ingested_to", "added"]


def test_file_slug_ascii():
    assert _file_slug("My Report v2") == "my-report-v2"


def test_file_slug_non_ascii_falls_back_to_hash():
    slug = _file_slug("日本語")
    assert slug.startswith("file-") and len(slug) > len("file-")
    assert _file_slug("日本語") == slug
    assert _file_slug("中文") != slug


def test_url_slug():
    assert _url_slug("https://example.com/blog/My-Post.html") == "my-post"
    assert _url_slug("https://example.com/") == "example-com"


def test_fence_grows_past_backticks_in_content():
    out = _fence("a ```x``` b", "python")
    assert out.startswith("````python\n") and out.endswith("````\n")


def test_run_extract_non_ascii_filename_does_not_create_hidden_md(vault: Path, tmp_path: Path):
    src = tmp_path / "日本語.txt"
    src.write_text("konnichiwa", encoding="utf-8")
    result = run_extract(src, vault, overwrite=False)
    out = Path(result.output)
    assert out.name != ".md" and out.exists()


def test_run_extract_refuses_overwrite_without_flag(vault: Path, tmp_path: Path):
    src = tmp_path / "notes.txt"
    src.write_text("one", encoding="utf-8")
    run_extract(src, vault, overwrite=False)
    with pytest.raises(SystemExit) as exc:
        run_extract(src, vault, overwrite=False)
    assert exc.value.code == 1
    run_extract(src, vault, overwrite=True)


def test_run_extract_code_file_wrapped_in_fence(vault: Path, tmp_path: Path):
    src = tmp_path / "snippet.py"
    src.write_text("print('```')\n", encoding="utf-8")
    result = run_extract(src, vault, overwrite=False)
    text = Path(result.output).read_text(encoding="utf-8")
    assert "````python" in text


def test_extract_cmd_reports_failure_with_exit_1(vault: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    def boom(path: Path) -> str:
        raise RuntimeError("converter exploded")

    monkeypatch.setattr("wikiform.cmd.extract.extract_text", boom)
    src = tmp_path / "doc.txt"
    src.write_text("x", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--vault-root", str(vault), "extract", str(src)])
    assert result.exit_code == 1


def test_extract_cmd_json_output(vault: Path, tmp_path: Path):
    src = tmp_path / "doc.txt"
    src.write_text("hello", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--vault-root", str(vault), "extract", str(src)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["subdir"] == "papers"


# ─── preserving the original ──────────────────────────────────────────────────

def test_frontmatter_records_source_file_between_source_type_and_status():
    md = _build_markdown("T", "paper", "body", None, source_file="raw/papers/t.pdf")
    meta = frontmatter.loads(md).metadata
    assert meta["source_file"] == "raw/papers/t.pdf"
    assert list(meta)[:3] == ["title", "source_type", "source_file"]


def test_run_extract_copies_original_next_to_markdown(vault: Path, tmp_path: Path):
    src = tmp_path / "My Notes.txt"
    src.write_text("hello", encoding="utf-8")
    result = run_extract(src, vault, overwrite=False)
    copy = vault / "raw" / "papers" / "my-notes.txt"
    assert copy.read_text(encoding="utf-8") == "hello"
    assert result.source_file == "raw/papers/my-notes.txt"
    assert frontmatter.load(result.output).metadata["source_file"] == "raw/papers/my-notes.txt"
    assert src.exists()  # the user's file is left alone


def test_run_extract_does_not_copy_markdown_sources(vault: Path, tmp_path: Path):
    src = tmp_path / "note.md"
    src.write_text("# hi", encoding="utf-8")
    result = run_extract(src, vault, overwrite=False)
    assert result.source_file is None
    assert "source_file" not in frontmatter.load(result.output).metadata
    assert [p.name for p in (vault / "raw" / "papers").iterdir()] == ["note.md"]


def test_run_extract_binary_original_is_preserved_byte_for_byte(vault: Path, tmp_path: Path):
    src = tmp_path / "pic.png"
    payload = bytes(range(256)) * 4
    src.write_bytes(payload)
    result = run_extract(src, vault, overwrite=False)
    assert (vault / result.source_file).read_bytes() == payload
    assert result.subdir == "images"


def test_run_extract_source_already_in_vault_is_not_copied_onto_itself(vault: Path):
    src = vault / "raw" / "papers" / "inplace.txt"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("data", encoding="utf-8")
    result = run_extract(src, vault, overwrite=False)
    assert src.read_text(encoding="utf-8") == "data"
    assert result.source_file == "raw/papers/inplace.txt"


def test_run_extract_refuses_to_clobber_existing_original_without_overwrite(vault: Path, tmp_path: Path):
    existing = vault / "raw" / "papers" / "report.pdf"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"older original")
    src = tmp_path / "report.pdf"
    src.write_bytes(b"newer original")
    with pytest.raises(SystemExit):
        run_extract(src, vault, overwrite=False)
    assert existing.read_bytes() == b"older original"
    assert not (vault / "raw" / "papers" / "report.md").exists()  # nothing half-written


def test_run_extract_overwrite_replaces_markdown_and_original(vault: Path, tmp_path: Path):
    src = tmp_path / "doc.txt"
    src.write_text("v1", encoding="utf-8")
    run_extract(src, vault, overwrite=False)
    src.write_text("v2", encoding="utf-8")
    run_extract(src, vault, overwrite=True)
    assert (vault / "raw" / "papers" / "doc.txt").read_text(encoding="utf-8") == "v2"


def test_extract_cmd_json_includes_source_file(vault: Path, tmp_path: Path):
    src = tmp_path / "doc.txt"
    src.write_text("hello", encoding="utf-8")
    result = CliRunner().invoke(cli, ["--vault-root", str(vault), "extract", str(src)])
    assert json.loads(result.stdout)["source_file"] == "raw/papers/doc.txt"


def test_extracted_raw_file_passes_lint_cleanly(vault: Path, tmp_path: Path):
    from wikiform.cmd.lint import run_lint

    src = tmp_path / "doc.txt"
    src.write_text("hello", encoding="utf-8")
    run_extract(src, vault, overwrite=False)
    report = run_lint(vault, vault / "wiki" / "pages", "frontmatter")
    assert report.issues == []
