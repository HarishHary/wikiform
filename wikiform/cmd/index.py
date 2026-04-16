from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import click
from loguru import logger

from wikiform.utils.config import read_schema_categories
from wikiform.utils.fs import (
    collect_pages,
    extract_summary,
    load_frontmatter,
    normalize_tags,
)

logger = logger.bind(service="Wikiform - Index")


@dataclass
class Article:
    stem: str
    title: str
    tags: list[str]
    updated: str
    kind: str
    summary: str


@dataclass
class IndexResult:
    vault_root: str
    pages_dir: str
    generated_at: str
    articles_scanned: int
    category_index_path: str
    master_index_path: str
    tag_index_path: str
    categories_indexed: int
    tags_indexed: int


def _today_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _collect_articles(pages_dir: Path) -> list[Article]:
    articles: list[Article] = []
    for md_file in collect_pages(pages_dir):
        attrs, body = load_frontmatter(md_file)
        title = str(attrs.get("title") or md_file.stem).strip() or md_file.stem
        tags = normalize_tags(attrs.get("tags"), source=md_file.name)
        articles.append(Article(
            stem=md_file.stem,
            title=title,
            tags=tags,
            updated=str(attrs.get("updated", "") or ""),
            kind=str(attrs.get("type", "") or ""),
            summary=str(attrs.get("summary", "") or extract_summary(body)).strip(),
        ))
    logger.info("Collected {} articles from {}", len(articles), pages_dir)
    return articles


# ─── IndexWriter ──────────────────────────────────────────────────────────────

@dataclass
class IndexWriter:
    vault_root: Path
    articles: list[Article]
    categories: list[str]

    def write_category_index(self) -> tuple[Path, int]:
        cat_lookup = {c.lower(): c for c in self.categories}
        by_category: dict[str, list[Article]] = defaultdict(list)

        for article in sorted(self.articles, key=lambda x: x.title.lower()):
            assigned = False
            for tag in article.tags:
                if tag.lower() in cat_lookup:
                    by_category[cat_lookup[tag.lower()]].append(article)
                    assigned = True
                    break
            if not assigned:
                by_category["Uncategorised"].append(article)

        ordered = list(self.categories)
        if "Uncategorised" in by_category and "Uncategorised" not in ordered:
            ordered.append("Uncategorised")

        total_categories = sum(1 for c in ordered if c in by_category)

        lines = [
            "---",
            'title: "Wiki Index"',
            f'updated: "{_today_str()}"',
            "auto_generated: true",
            "description: Primary content catalog. Every wiki page listed once, by category. Maintained by wiki-ingest.",
            "---",
            "",
            "# Wiki Index",
            "",
            "> Auto-generated. Do not edit manually - changes will be overwritten by vault index.",
            "",
            f"*{len(self.articles)} pages across {total_categories} categories*",
            "",
        ]

        for category in ordered:
            items = by_category.get(category, [])
            lines.append(f"## {category}")
            if items:
                for article in items:
                    desc = f" - {article.summary}" if article.summary else ""
                    lines.append(f"- [[{article.stem}|{article.title}]]{desc}")
            else:
                lines.append("<!-- no pages in this category yet -->")
            lines.append("")

        out = self.vault_root / "wiki" / "index.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Wrote category index to {}", out)
        return out, total_categories

    def write_master_index(self) -> Path:
        by_letter: dict[str, list[Article]] = defaultdict(list)
        for article in sorted(self.articles, key=lambda x: x.title.lower()):
            title = article.title.strip() or article.stem
            letter = title[0].upper() if title else "#"
            if not letter.isalpha():
                letter = "#"
            by_letter[letter].append(article)

        lines = [
            "---",
            'title: "Master Index"',
            f'updated: "{_today_str()}"',
            "auto_generated: true",
            "description: Every wiki page indexed by title letter, alphabetically. Maintained by vault index.",
            "---",
            "",
            "# Master Index",
            "",
            "> Auto-generated. Do not edit manually - changes will be overwritten by vault index.",
            "",
            f"*{len(self.articles)} pages*",
            "",
        ]

        for letter in sorted(by_letter.keys()):
            lines.append(f"## {letter}")
            for article in by_letter[letter]:
                desc = f" - {article.summary}" if article.summary else ""
                lines.append(f"- [[{article.stem}|{article.title}]]{desc}")
            lines.append("")

        out = self.vault_root / "wiki" / "master-index.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Wrote master index to {}", out)
        return out

    def write_tag_index(self) -> tuple[Path, int]:
        by_tag: dict[str, list[Article]] = defaultdict(list)
        for article in self.articles:
            for tag in article.tags:
                by_tag[tag.lower()].append(article)

        lines = [
            "---",
            'title: "Tag Index"',
            f'updated: "{_today_str()}"',
            "auto_generated: true",
            "description: Every wiki page indexed by tag, alphabetically. Maintained by vault index.",
            "---",
            "",
            "# Tag Index",
            "",
            "> Auto-generated. Do not edit manually - changes will be overwritten by vault index.",
            "",
            f"*{len(by_tag)} tags across {len(self.articles)} pages*",
            "",
        ]

        for tag in sorted(by_tag.keys()):
            items = sorted(by_tag[tag], key=lambda x: x.title.lower())
            lines.append(f"## {tag} ({len(items)})")
            for article in items:
                lines.append(f"- [[{article.stem}|{article.title}]]")
            lines.append("")

        out = self.vault_root / "wiki" / "tag-index.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Wrote tag index to {}", out)
        return out, len(by_tag)


# ─── Public API ───────────────────────────────────────────────────────────────

def run_index(vault_root: Path) -> IndexResult:
    pages_dir = vault_root / "wiki" / "pages"
    categories = read_schema_categories(vault_root)
    articles = _collect_articles(pages_dir)

    writer = IndexWriter(vault_root=vault_root, articles=articles, categories=categories)
    category_index_path, n_categories = writer.write_category_index()
    master_index_path = writer.write_master_index()
    tag_index_path, n_tags = writer.write_tag_index()

    return IndexResult(
        vault_root=str(vault_root),
        pages_dir=str(pages_dir),
        generated_at=datetime.now(UTC).isoformat(),
        articles_scanned=len(articles),
        category_index_path=str(category_index_path),
        master_index_path=str(master_index_path),
        tag_index_path=str(tag_index_path),
        categories_indexed=n_categories,
        tags_indexed=n_tags,
    )


# ─── CLI command ─────────────────────────────────────────────────────────────

@click.command("index", help="Regenerate wiki/index.md, wiki/master-index.md, and wiki/tag-index.md.")
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write JSON report to file instead of stdout")
@click.pass_context
def index_cmd(ctx: click.Context, output: Path | None) -> None:
    vault_root = ctx.obj.get("vault_root")
    if not vault_root:
        logger.error("Vault root path not provided in context")
        raise SystemExit(2)

    root = Path(vault_root).resolve()
    if not root.exists():
        logger.error("Vault root does not exist: {}", root)
        raise SystemExit(2)

    if not (root / "SCHEMA.md").exists():
        logger.warning(
            "SCHEMA.md not found at {}. Category index will have no categories.",
            root / "SCHEMA.md",
        )

    result = run_index(root)
    rendered = json.dumps(asdict(result), indent=2, ensure_ascii=False)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        logger.info("Wrote result to {}", output)
    else:
        click.echo(rendered)
