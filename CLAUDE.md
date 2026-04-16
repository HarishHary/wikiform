# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Setup

```bash
poetry install                   # core deps only
poetry install --with serve      # include FastAPI/uvicorn for the web UI
poetry install --only dev        # dev tools only (lint, test, etc.)
```

## Common Commands

```bash
# Tests
pytest tests -v -l -p no:warnings --disable-warnings
# or
make tests

# Linting
flake8 --config .flake8 wikiform/    # style/error checks
bandit -r wikiform/ -c pyproject.toml  # security checks
black wikiform/ --config pyproject.toml --diff --color  # formatting diff

make lint    # runs flake8
make bandit  # runs bandit
make black   # runs black diff

# Build
make build   # poetry build → dist/
make install # build + pip install wheel
```

## Architecture

Wikiform is a Python CLI (`wikiform/cli.py`) for managing Obsidian-style markdown vaults. The entry point is `wikiform.cli:cli`. It uses a **two-level Click group**: the parent `cli` collects the global `--vault-root PATH` option and stores it in `ctx.obj["vault_root"]`; all subcommands retrieve it from there.

### Commands (`wikiform/cmd/`)

| Command        | File               | Purpose                                                                                         |
| -------------- | ------------------ | ----------------------------------------------------------------------------------------------- |
| `index`        | `cmd/index.py`     | Regenerates `wiki/index.md`, `wiki/master-index.md`, `wiki/tag-index.md` from `wiki/pages/*.md` |
| `lint`         | `cmd/lint.py`      | Runs structural checks on the vault (broken links, frontmatter, orphans, naming, etc.)          |
| `search index` | `cmd/fts_index.py` | Builds/updates the FTS5 SQLite search index                                                     |
| `search query` | `cmd/query.py`     | Searches via FTS5, renders results with Rich                                                    |
| `search serve` | `cmd/serve.py`     | FastAPI + uvicorn web UI at port 8787                                                           |

### Vault Directory Layout Expected

```
{vault_root}/
  SCHEMA.md             ← defines categories and required frontmatter fields
  wiki/
    pages/              ← flat *.md article files (kebab-case slugs)
    index.md            ← auto-generated (category index)
    master-index.md     ← auto-generated (alphabetical)
    tag-index.md        ← auto-generated (by tag)
  raw/                  ← ingestion sources (recursive *.md)
  _meta/
    vault-search.db      ← FTS5 SQLite database
    _wiki_state.json     ← ingest extraction state (file content hashes; gitignored)
    _wiki_llm_cache.json ← LLM response cache, keyed by content-hash:model (gitignored)
```

### Utilities (`wikiform/utils/`)

- **`fs.py`** - file collection (`collect_pages`, `collect_vault_files`, `collect_md_files`), frontmatter parsing (`load_frontmatter`), tag normalization, wikilink extraction (`extract_wikilinks`). `collect_pages` is flat (pages only); `collect_vault_files` covers pages + raw + wiki top-level for linting; `collect_md_files` is vault-wide for search indexing.
- **`config.py`** - reads `SCHEMA.md` via regex to extract `## Index Categories` (ordered list) and `## Wiki Page Frontmatter` yaml block (required fields). Falls back to `DEFAULT_REQUIRED_FIELDS = {title, tags, updated}` if absent.
- **`db.py`** - SQLite helpers; `init_db` creates the `articles` table and `articles_fts` virtual FTS5 table (porter + unicode61 tokenizer, content-table mode synced via triggers). BM25 weights: title 5.0, tags 2.0, content 1.0. `sanitize_fts_query` quotes hyphenated tokens to prevent FTS5 parsing them as NOT operators.

### Lint Checks

Eight named checks run in `cmd/lint.py`: `broken_link`, `frontmatter`, `orphan`, `tag_consistency`, `stale_raw`, `naming`, `empty`, `missing_cross_ref`. Run a single check with `--check <name>`. Auto-generated files (index.md, tag-index.md, master-index.md) are exempt from frontmatter and orphan checks via `AUTO_GENERATED_WIKI_FILES`. Page files must use kebab-case slugs (`naming` check).

### Key Conventions

- All outputs (index files, lint reports, search results) are JSON unless displayed via Rich tables.
- Frontmatter `auto_generated: true` exempts a file from lint checks.
- Tags must be YAML lists in frontmatter; `normalize_tags` handles both list and comma-string forms with warnings.
- `SKIP_DIRS = {.obsidian, .git, .trash, node_modules, outputs}` are never traversed.
