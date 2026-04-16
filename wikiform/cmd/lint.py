from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

import click
from loguru import logger

from wikiform.utils.config import read_schema_required_fields
from wikiform.utils.fs import (
    collect_vault_files,
    extract_wikilinks,
    load_frontmatter,
    normalize_rel,
)

logger = logger.bind(service="Wikiform - Lint")


@dataclass
class FileInfo:
    path: str
    abs_path: str
    stem: str
    meta: dict[str, Any]
    content: str
    size: int
    mtime: float


# Wiki-level files that are auto-generated and exempt from orphan/frontmatter checks.
AUTO_GENERATED_WIKI_FILES: frozenset[str] = frozenset({
    "wiki/index.md",
    "wiki/tag-index.md",
    "wiki/master-index.md",
    "wiki/log.md",
    "wiki/overview.md",
})


IssueCheck = Literal[
    "broken_link", "frontmatter", "orphan", "tag_consistency",
    "stale_raw", "naming", "empty", "missing_cross_ref",
]


@dataclass
class Issue:
    type: Literal["error", "warning", "info"]
    check: IssueCheck
    file: str | None  # None for vault-level issues not tied to a specific file
    message: str


HealthStatus = Literal["GOOD", "FAIR", "NEEDS_ATTENTION"]


@dataclass
class ReportSummary:
    files_scanned: int
    errors: int
    warnings: int
    infos: int
    generated_at: str
    overall_health: HealthStatus


@dataclass
class Report:
    vault_root: str
    pages_dir: str
    checks_run: list[IssueCheck]
    summary: ReportSummary
    issues: list[Issue] = field(default_factory=list)


# ─── File collection ──────────────────────────────────────────────────────────

def _collect_files(vault_root: Path) -> dict[str, FileInfo]:
    files: dict[str, FileInfo] = {}

    for md_file in collect_vault_files(vault_root):
        rel_str = normalize_rel(md_file, vault_root)
        attrs, content = load_frontmatter(md_file)

        try:
            stat = md_file.stat()
            size = stat.st_size
            mtime = stat.st_mtime
        except OSError as err:
            logger.warning("Failed to stat {}: {}", rel_str, err)
            size = 0
            mtime = 0.0

        files[rel_str] = FileInfo(
            path=rel_str,
            abs_path=str(md_file),
            stem=md_file.stem,
            meta=attrs,
            content=content,
            size=size,
            mtime=mtime,
        )

    logger.info("Collected {} markdown files", len(files))
    return files


def _build_stem_map(files: dict[str, FileInfo]) -> dict[str, list[str]]:
    stem_map: dict[str, list[str]] = defaultdict(list)
    for path, info in files.items():
        stem_map[info.stem.lower()].append(path)
    return stem_map


def _resolve_link(
    link: str,
    files: dict[str, FileInfo],
    stem_map: dict[str, list[str]],
) -> list[str]:
    target = link.strip()
    target_no_ext = target.removesuffix(".md")
    target_no_ext_lower = target_no_ext.lower()

    matches: list[str] = list(stem_map.get(target_no_ext_lower, []))

    # Only scan all paths when the target includes a directory prefix (e.g. [[subdir/foo]]).
    # Pure stem targets are already fully resolved by the stem map above.
    if "/" in target_no_ext_lower:
        target_lower = target.lower()
        for path in files:
            path_no_ext = path.removesuffix(".md").lower()
            if path.lower() == target_lower or path_no_ext == target_no_ext_lower:
                matches.append(path)
            elif path_no_ext.endswith("/" + target_no_ext_lower):
                matches.append(path)

    return sorted(set(matches))


_KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_TAG_NORMALISE_RE = re.compile(r"[-_\s]+")
_STALE_RAW_DAYS: int = 7
_SECONDS_PER_DAY: int = 86400
_HEALTH_FAIR_WARNING_THRESHOLD: int = 5


# ─── Linter ───────────────────────────────────────────────────────────────────

@dataclass
class Linter:
    files: dict[str, FileInfo]
    required_fields: frozenset[str]
    pages_dir_rel: str
    _stem_map: dict[str, list[str]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._stem_map = _build_stem_map(self.files)

    # ── individual checks ────────────────────────────────────────────────────

    def check_broken_links(self) -> list[Issue]:
        issues: list[Issue] = []
        for path, info in self.files.items():
            if path in AUTO_GENERATED_WIKI_FILES or info.meta.get("auto_generated"):
                continue
            for link in extract_wikilinks(info.content):
                if not _resolve_link(link, self.files, self._stem_map):
                    issues.append(Issue(
                        type="error", check="broken_link", file=path,
                        message=f"Broken wikilink [[{link}]] - no matching file found",
                    ))
        return issues

    def check_frontmatter(self) -> list[Issue]:
        issues: list[Issue] = []
        for path, info in self.files.items():
            meta = info.meta
            if path in AUTO_GENERATED_WIKI_FILES or meta.get("auto_generated"):
                continue
            if not meta:
                issues.append(Issue(
                    type="error", check="frontmatter", file=path,
                    message="No YAML frontmatter found",
                ))
                continue
            missing = sorted(f for f in self.required_fields if f not in meta)
            if missing:
                issues.append(Issue(
                    type="warning", check="frontmatter", file=path,
                    message=f"Missing required fields: {', '.join(missing)}",
                ))
            tags = meta.get("tags")
            if tags is not None and not isinstance(tags, list):
                issues.append(Issue(
                    type="warning", check="frontmatter", file=path,
                    message=f"'tags' must be a YAML list, got {type(tags).__name__}",
                ))
        return issues

    def check_orphans(self) -> list[Issue]:
        incoming: dict[str, int] = defaultdict(int)
        for path, info in self.files.items():
            if path in AUTO_GENERATED_WIKI_FILES or info.meta.get("auto_generated"):
                continue
            for link in extract_wikilinks(info.content):
                for target in _resolve_link(link, self.files, self._stem_map):
                    incoming[target] += 1

        issues: list[Issue] = []
        for path, info in self.files.items():
            if path in AUTO_GENERATED_WIKI_FILES:
                continue
            if info.meta.get("auto_generated"):
                continue
            if "templates/" in path:
                continue
            if path.startswith("raw/") and info.meta.get("status") != "ingested":
                continue
            if incoming[path] == 0:
                issues.append(Issue(
                    type="info", check="orphan", file=path,
                    message="No incoming wikilinks from any other file",
                ))
        return issues

    def check_tag_consistency(self) -> list[Issue]:
        tag_counts: Counter[str] = Counter()
        for path, info in self.files.items():
            if path in AUTO_GENERATED_WIKI_FILES or info.meta.get("auto_generated"):
                continue
            tags = info.meta.get("tags", [])
            if isinstance(tags, list):
                for t in tags:
                    normalised_tag = str(t).strip().lower()
                    if normalised_tag:
                        tag_counts[normalised_tag] += 1

        issues: list[Issue] = []
        seen: dict[str, str] = {}
        for tag in sorted(tag_counts.keys()):
            if tag_counts[tag] == 1:
                issues.append(Issue(
                    type="info", check="tag_consistency", file=None,
                    message=f"Tag '{tag}' used only once - possible typo?",
                ))
            normalised = _TAG_NORMALISE_RE.sub("", tag)
            if normalised in seen and seen[normalised] != tag:
                issues.append(Issue(
                    type="info", check="tag_consistency", file=None,
                    message=f"Similar tags: '{seen[normalised]}' and '{tag}' - consider merging",
                ))
            seen[normalised] = tag
        return issues

    def check_stale_raw(self) -> list[Issue]:
        cutoff = datetime.now(UTC).timestamp() - _STALE_RAW_DAYS * _SECONDS_PER_DAY
        issues: list[Issue] = []
        for path, info in self.files.items():
            if not path.startswith("raw/"):
                continue
            if info.mtime == 0.0:
                continue
            if info.meta.get("status") == "raw" and info.mtime < cutoff:
                issues.append(Issue(
                    type="info", check="stale_raw", file=path,
                    message=f"Raw source older than {_STALE_RAW_DAYS} days with status 'raw' - not yet ingested",
                ))
        return issues

    def check_naming(self) -> list[Issue]:
        pages_prefix = self.pages_dir_rel + "/"
        issues: list[Issue] = []
        for path, info in self.files.items():
            if not path.startswith(pages_prefix):
                continue
            if info.meta.get("auto_generated"):
                continue
            if not _KEBAB_RE.match(info.stem):
                issues.append(Issue(
                    type="warning", check="naming", file=path,
                    message=f"Filename '{info.stem}' violates kebab-case slug convention",
                ))
        return issues

    def check_empty(self) -> list[Issue]:
        issues: list[Issue] = []
        for path, info in self.files.items():
            if path in AUTO_GENERATED_WIKI_FILES or info.meta.get("auto_generated"):
                continue
            if info.size == 0:
                issues.append(Issue(
                    type="warning", check="empty", file=path,
                    message="File is empty (0 bytes)",
                ))
            elif not info.content.strip() and info.meta:
                issues.append(Issue(
                    type="info", check="empty", file=path,
                    message="File has frontmatter but no body content",
                ))
        return issues

    def check_cross_refs(self) -> list[Issue]:
        tag_files: dict[str, set[str]] = defaultdict(set)
        for path, info in self.files.items():
            if path in AUTO_GENERATED_WIKI_FILES or info.meta.get("auto_generated"):
                continue
            tags = info.meta.get("tags", [])
            if isinstance(tags, list):
                for t in tags:
                    tag_files[str(t).strip().lower()].add(path)

        issues: list[Issue] = []
        for path, info in self.files.items():
            if path in AUTO_GENERATED_WIKI_FILES or info.meta.get("auto_generated"):
                continue
            if path.startswith("raw/"):
                continue
            linked: set[str] = set()
            for link in extract_wikilinks(info.content):
                linked.update(_resolve_link(link, self.files, self._stem_map))

            tags = info.meta.get("tags", [])
            if not isinstance(tags, list):
                continue

            related: set[str] = set()
            for t in tags:
                related.update(tag_files.get(str(t).strip().lower(), set()))
            related.discard(path)

            unlinked = related - linked
            if 0 < len(unlinked) <= 5:
                for target in sorted(unlinked):
                    issues.append(Issue(
                        type="info", check="missing_cross_ref", file=path,
                        message=f"Consider linking to [[{self.files[target].stem}]] (shared tags)",
                    ))
        return issues

    # ── dispatch ─────────────────────────────────────────────────────────────

    def _all_checks(self) -> dict[IssueCheck, Callable[[], list[Issue]]]:
        return {
            "broken_link": self.check_broken_links,
            "frontmatter": self.check_frontmatter,
            "orphan": self.check_orphans,
            "tag_consistency": self.check_tag_consistency,
            "stale_raw": self.check_stale_raw,
            "naming": self.check_naming,
            "empty": self.check_empty,
            "missing_cross_ref": self.check_cross_refs,
        }

    def run(self, check_name: str | None = None) -> tuple[list[Issue], list[IssueCheck]]:
        checks = self._all_checks()
        selected: dict[IssueCheck, Callable[[], list[Issue]]] = {}
        if check_name:
            if check_name not in checks:
                raise ValueError(
                    f"Unknown check '{check_name}'. Valid: {', '.join(sorted(checks))}"
                )
            validated: IssueCheck = cast(IssueCheck, check_name)
            selected = {validated: checks[validated]}
        else:
            selected = checks

        issues: list[Issue] = []
        for name, fn in selected.items():
            logger.debug("Running check: {}", name)
            issues.extend(fn())

        return issues, list(selected.keys())


# ─── Health / report ─────────────────────────────────────────────────────────

def _compute_health(errors: int, warnings: int) -> HealthStatus:
    if errors == 0 and warnings <= _HEALTH_FAIR_WARNING_THRESHOLD:
        return "GOOD"
    if errors == 0:
        return "FAIR"
    return "NEEDS_ATTENTION"


def run_lint(
    vault_root: Path,
    pages_dir: Path,
    check_name: str | None = None,
) -> Report:
    required_fields = read_schema_required_fields(vault_root)
    files = _collect_files(vault_root)
    pages_dir_rel = normalize_rel(pages_dir, vault_root)

    linter = Linter(files=files, required_fields=required_fields, pages_dir_rel=pages_dir_rel)
    issues, checks_run = linter.run(check_name)

    errors = sum(1 for i in issues if i.type == "error")
    warnings = sum(1 for i in issues if i.type == "warning")
    infos = sum(1 for i in issues if i.type == "info")

    summary = ReportSummary(
        files_scanned=len(files),
        errors=errors,
        warnings=warnings,
        infos=infos,
        generated_at=datetime.now(UTC).isoformat(),
        overall_health=_compute_health(errors, warnings),
    )

    report = Report(
        vault_root=str(vault_root),
        pages_dir=str(pages_dir),
        checks_run=checks_run,
        summary=summary,
        issues=issues,
    )

    logger.info(
        "Finished: {} files, {} errors, {} warnings, {} infos - {}",
        summary.files_scanned, errors, warnings, infos, summary.overall_health,
    )
    return report


# ─── CLI command ─────────────────────────────────────────────────────────────

@click.command("lint")
@click.option("--pages-dir", default=None, help="Pages directory (default: <vault-root>/wiki/pages)")
@click.option("-c", "--check", "check_name", default=None, help="Run only one named check")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON report to file instead of stdout")
@click.pass_context
def lint_cmd(ctx: click.Context, pages_dir: str | None, check_name: str | None, output: Path | None) -> None:
    vault_root = ctx.obj.get("vault_root")
    if not vault_root:
        logger.error("Vault root path not provided in context")
        raise SystemExit(2)

    root = Path(vault_root).resolve()
    if not root.exists():
        logger.error("Vault root does not exist: {}", root)
        raise SystemExit(2)

    actual_pages_dir = Path(pages_dir).resolve() if pages_dir else root / "wiki" / "pages"

    if not actual_pages_dir.exists():
        logger.warning("Pages directory does not exist: {}", actual_pages_dir)

    try:
        report = run_lint(root, actual_pages_dir, check_name)
    except ValueError as err:
        logger.error(str(err))
        raise SystemExit(2) from err

    rendered = json.dumps(asdict(report), indent=2, ensure_ascii=False)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        logger.info("Wrote report to {}", output)
    else:
        click.echo(rendered)

    raise SystemExit(1 if report.summary.errors > 0 else 0)
