"""Claude Code hook handlers (``wikiform hook <event>``).

Hooks run on every tool call while the plugin is enabled, so every handler must be fast and must do
nothing (exit 0, no output) when the file or session is not inside a wikiform vault. Handlers never
raise: an unexpected error fails open (exit 0) rather than blocking the user's session.

Protocol (Claude Code): the event payload arrives as JSON on stdin; exit code 2 blocks (PreToolUse) or
feeds stderr back to the model (PostToolUse); SessionStart stdout is added to the model's context.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click
from loguru import logger

from wikiform.utils.db import db_path
from wikiform.utils.fs import SKIP_DIRS, SKIP_FILES, collect_pages, load_frontmatter, normalize_rel
from wikiform.utils.vault import find_vault_root, resolve_vault

CONFIG_ENV_VAR = "CLAUDE_PLUGIN_OPTION_VAULT_ROOT"
DEBUG_ENV_VAR = "WIKIFORM_HOOK_DEBUG"
DIRTY_FLAG = Path("_meta") / ".dirty"

_FILE_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})
_GENERATED_INDEXES = frozenset({"wiki/index.md", "wiki/tag-index.md", "wiki/master-index.md"})
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(?:\n|\Z)", re.DOTALL)
_LOG_HEADING_RE = re.compile(r"^##\s*\[[^\]]*\]\s*([\w-]+)\s*\|", re.MULTILINE)
_FILE_WALK_UP = 8  # raw/ can nest several levels below the vault root


@dataclass
class HookResult:
    code: int = 0
    message: str = ""  # stderr (what the model/user sees on exit 2)
    stdout: str = ""  # SessionStart context


# ─── helpers ──────────────────────────────────────────────────────────────────


def _configured_root(ctx_root: str | None) -> str | None:
    return os.environ.get(CONFIG_ENV_VAR) or ctx_root or None


def _target_file(payload: dict[str, Any]) -> Path | None:
    """Absolute path of the file a Write/Edit/MultiEdit call targets, or None for other tools."""
    if payload.get("tool_name") not in _FILE_TOOLS:
        return None
    raw = (payload.get("tool_input") or {}).get("file_path")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(payload.get("cwd") or ".") / path
    return path.resolve()


def _vault_for_file(path: Path, configured: str | None) -> tuple[Path, str] | None:
    """(vault_root, vault-relative posix path) for a file inside a vault, else None."""
    root = resolve_vault(configured, None)
    if root is None or not path.is_relative_to(root):
        root = find_vault_root(path, max_up=_FILE_WALK_UP)
    if root is None or not path.is_relative_to(root):
        return None
    return root, normalize_rel(path, root)


def _split_frontmatter(text: str) -> tuple[int, str]:
    """(end offset of the frontmatter block, body). Offset is 0 when there is no frontmatter."""
    match = _FRONTMATTER_RE.match(text)
    end = match.end() if match else 0
    return end, text[end:]


def _hook_cmd(root: Path, sub: str) -> str:
    return f'wikiform --vault-root "{root}" {sub}'


# ─── guard (PreToolUse) ───────────────────────────────────────────────────────


def _raw_edit_allowed(text: str, old: str, new: str) -> bool:
    """Raw files: only the YAML frontmatter may change; the body is immutable."""
    if not old:
        return True
    fm_end, _ = _split_frontmatter(text)
    pos = text.find(old)
    if pos == -1:
        return True  # the Edit tool will reject it on its own
    while pos != -1:
        if fm_end:
            if pos + len(old) > fm_end:
                return False
        elif not (pos == 0 and new.lstrip().startswith("---")):  # no frontmatter yet: only prepending one is allowed
            return False
        pos = text.find(old, pos + 1)
    return True


def handle_guard(payload: dict[str, Any], configured: str | None) -> HookResult:
    path = _target_file(payload)
    if path is None or not path.exists():
        return HookResult()  # creating a file is always fine
    located = _vault_for_file(path, configured)
    if located is None:
        return HookResult()
    root, rel = located

    if rel in _GENERATED_INDEXES:
        return HookResult(
            2,
            f"BLOCKED: {rel} is auto-generated and is overwritten on every index run. Do not edit it by hand. "
            f"Edit the page(s) instead and run: {_hook_cmd(root, 'index')} (it also runs automatically at the end of the turn).",
        )

    if rel.startswith("raw/") and not rel.endswith(".meta.yaml"):
        tool_input = payload.get("tool_input") or {}
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return HookResult()
        message = (
            f"BLOCKED: {rel} is a raw source and its body is immutable. Only its YAML frontmatter may change - "
            "use the Edit tool on the frontmatter block (or rewrite the file with an identical body)."
        )
        tool = payload.get("tool_name")
        if tool == "Write":
            if _split_frontmatter(tool_input.get("content") or "")[1] != _split_frontmatter(text)[1]:
                return HookResult(2, message)
        else:
            edits = tool_input.get("edits") if tool == "MultiEdit" else [tool_input]
            for edit in edits or []:
                if not _raw_edit_allowed(text, edit.get("old_string") or "", edit.get("new_string") or ""):
                    return HookResult(2, message)
    return HookResult()


# ─── post-write (PostToolUse) ─────────────────────────────────────────────────


def handle_post_write(payload: dict[str, Any], configured: str | None) -> HookResult:
    from wikiform.cmd.lint import lint_file

    path = _target_file(payload)
    if path is None or not path.exists():
        return HookResult()
    located = _vault_for_file(path, configured)
    if located is None:
        return HookResult()
    root, rel = located
    # wiki/pages is flat: wiki/pages/<slug>.md
    if not (rel.startswith("wiki/pages/") and rel.count("/") == 2 and rel.endswith(".md")) or path.name in SKIP_FILES:
        return HookResult()

    flag = root / DIRTY_FLAG
    flag.parent.mkdir(parents=True, exist_ok=True)
    flag.touch()

    problems = [i for i in lint_file(root, path) if i.type in ("error", "warning")]
    if not problems:
        return HookResult()
    lines = "\n".join(f"- {i.message}" for i in problems)
    return HookResult(2, f"{rel} has problems that `wikiform lint` would report. Fix them now:\n{lines}")


# ─── finalize (Stop) ──────────────────────────────────────────────────────────


def handle_finalize(payload: dict[str, Any], configured: str | None) -> HookResult:
    from wikiform.cmd.fts_index import run_fts_index
    from wikiform.cmd.index import run_index

    root = resolve_vault(configured, Path(payload.get("cwd") or "."))
    if root is None or not (root / DIRTY_FLAG).exists():
        return HookResult()
    run_index(root)
    run_fts_index(root, incremental=True)
    (root / DIRTY_FLAG).unlink(missing_ok=True)
    return HookResult(message="wikiform: regenerated wiki indexes and refreshed the search index")


# ─── session-start ────────────────────────────────────────────────────────────


def _ingests_since_lint(log: Path) -> int | None:
    if not log.is_file():
        return None
    count = 0
    for operation in _LOG_HEADING_RE.findall(log.read_text(encoding="utf-8", errors="replace")):  # newest first
        if operation == "lint":
            break
        if operation == "ingest":
            count += 1
    return count


def _pending_raw(root: Path) -> int:
    raw = root / "raw"
    if not raw.is_dir():
        return 0
    pending = 0
    for f in raw.rglob("*.md"):
        rel_parts = f.relative_to(root).parts
        if any(p in SKIP_DIRS for p in rel_parts) or f.name in SKIP_FILES:
            continue
        if load_frontmatter(f)[0].get("status") == "raw":
            pending += 1
    return pending


def _search_index_state(root: Path, pages: list[Path]) -> str:
    db = db_path(root)
    if not db.exists():
        return "not built"
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            indexed, newest_indexed = con.execute("SELECT COUNT(*), COALESCE(MAX(mtime), 0) FROM articles").fetchone()
        finally:
            con.close()
        newest_page = max((p.stat().st_mtime for p in pages), default=0.0)
    except (sqlite3.Error, OSError):
        return "unreadable"
    return "up to date" if indexed == len(pages) and newest_page <= newest_indexed else "stale"


def handle_session_start(payload: dict[str, Any], configured: str | None) -> HookResult:
    root = resolve_vault(configured, Path(payload.get("cwd") or "."))
    if root is None:
        return HookResult()
    pages = collect_pages(root / "wiki" / "pages")
    parts = [f"{len(pages)} pages", f"{_pending_raw(root)} raw sources awaiting ingest"]
    since_lint = _ingests_since_lint(root / "wiki" / "log.md")
    if since_lint is not None:
        parts.append(f"{since_lint} ingests since last lint")
    state = _search_index_state(root, pages)
    lines = [f"Wikiform vault: {root}", "- " + " | ".join(parts), f"- search index: {state}"]
    if state in ("stale", "not built"):
        lines.append(f"  (refresh with: {_hook_cmd(root, 'search index --incremental')})")
    return HookResult(stdout="\n".join(lines))


# ─── CLI ──────────────────────────────────────────────────────────────────────

_HANDLERS: dict[str, Callable[[dict[str, Any], str | None], HookResult]] = {
    "guard": handle_guard,
    "post-write": handle_post_write,
    "finalize": handle_finalize,
    "session-start": handle_session_start,
}


def _read_payload() -> dict[str, Any]:
    stream = click.get_text_stream("stdin")
    if stream.isatty():
        return {}
    try:
        data = json.loads(stream.read() or "{}")
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


@click.command("hook", help="Claude Code hook handler (reads the event JSON on stdin). Used by the wikiform plugin; not meant for manual use.")
@click.argument("event", type=click.Choice(sorted(_HANDLERS)))
@click.pass_context
def hook_cmd(ctx: click.Context, event: str) -> None:
    logger.remove()  # hooks must keep stdout/stderr clean: only HookResult output is emitted
    configured = _configured_root((ctx.obj or {}).get("vault_root"))
    try:
        result = _HANDLERS[event](_read_payload(), configured)
    except Exception:  # fail open: a broken hook must never block the session
        if os.environ.get(DEBUG_ENV_VAR):
            click.echo(traceback.format_exc(), err=True)
        return
    if result.stdout:
        click.echo(result.stdout)
    if result.message:
        click.echo(result.message, err=True)
    if result.code:
        raise SystemExit(result.code)
