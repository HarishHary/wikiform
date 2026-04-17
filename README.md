# Wikiform

LLM-backed wiki management CLI. Extract sources, index, lint, and search an Obsidian-style markdown vault.

## Installation

```bash
poetry install                 # all core deps (includes search, embeddings, extraction)
poetry install --only dev      # dev tools only (lint, test, etc.)
```

> **PDF extraction** uses `opendataloader-pdf` and requires a Java runtime. If Java is not installed, extraction falls back to `markitdown` automatically.

> **Semantic search** (sqlite-vec) requires Python compiled with `--enable-loadable-sqlite-extensions`. See the [Semantic Search](#semantic-search) section for setup.

## Commands

`--vault-root` is a global option and must come before the subcommand.

```bash
# Extract a source file or URL into raw/ ready for wiki-ingest
wikiform --vault-root PATH extract path/to/file.pdf
wikiform --vault-root PATH extract path/to/report.docx
wikiform --vault-root PATH extract path/to/data.xlsx --overwrite
wikiform --vault-root PATH extract https://example.com/article

# Regenerate all three index files
wikiform --vault-root PATH index

# Audit the vault for structural issues
wikiform --vault-root PATH lint
wikiform --vault-root PATH lint --check broken_link
wikiform --vault-root PATH lint --output report.json

# Build or update the FTS5 search index
wikiform --vault-root PATH search index
wikiform --vault-root PATH search index --incremental       # skip unchanged files

# Generate vector embeddings for semantic search
wikiform --vault-root PATH search embed
wikiform --vault-root PATH search embed --incremental       # skip already-embedded articles
wikiform --vault-root PATH search embed --reset             # drop and recreate (required when switching models)

# Search the vault
wikiform --vault-root PATH search query "multi-head attention"
wikiform --vault-root PATH search query "transformer" --tag Concepts --limit 10
wikiform --vault-root PATH search query "transformer" --json
wikiform --vault-root PATH search query "anomaly detection techniques" --semantic  # vector search
```

## Vault Layout

```
{vault_root}/
  SCHEMA.md             ← categories and required frontmatter fields
  wiki/
    pages/              ← wiki articles (kebab-case slugs)
    index.md            ← auto-generated
    master-index.md     ← auto-generated
    tag-index.md        ← auto-generated
  raw/
    papers/             ← documents (.pdf .md .txt .docx .pptx)
    datasets/           ← data files (.csv .json .yaml .xlsx)
    code/               ← source files (.py .js .ts .sql etc.)
    images/             ← images (.png .jpg .svg)
    misc/               ← binary or unrecognised types
  _meta/
    vault-search.db     ← FTS5 + vector search index (sqlite-vec)
```

## Supported File Types for `extract`

| Type | Extensions |
|------|------------|
| Plain text / code | `.txt .md .py .sql .js .ts .csv .json .yaml .html .xml .sh` and more |
| Word | `.docx .dotx` |
| Excel | `.xlsx .xltx` |
| PDF | `.pdf` (Java required for opendataloader-pdf; falls back to markitdown) |
| PowerPoint | `.pptx` |
| Binary | Size metadata only, no text extraction |

## Semantic Search

Wikiform supports local vector search alongside FTS5 keyword search, powered by [sqlite-vec](https://github.com/asg017/sqlite-vec) and [sentence-transformers](https://www.sbert.net/).

**Default model:** `BAAI/bge-base-en-v1.5` (768-dim, 512-token limit)

```bash
# One-time setup: build the FTS index, then generate embeddings
wikiform --vault-root PATH search index
wikiform --vault-root PATH search embed

# Query with semantic search
wikiform --vault-root PATH search query "detection engineering workflow" --semantic
```

> **Note:** sqlite-vec requires Python compiled with `--enable-loadable-sqlite-extensions`. If you see `AttributeError: 'sqlite3.Connection' object has no attribute 'enable_load_extension'`, rebuild your Python:
> ```bash
> PYTHON_CONFIGURE_OPTS="--enable-loadable-sqlite-extensions" pyenv install 3.14.0 --force
> ```
