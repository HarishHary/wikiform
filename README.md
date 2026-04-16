# Wikiform

LLM-backed wiki management CLI. Extract sources, index, lint, and search an Obsidian-style markdown vault.

## Installation

```bash
poetry install
```

For the web search UI:

```bash
poetry install --with serve
```

> **PDF extraction** uses `opendataloader-pdf` and requires a Java runtime. If Java is not installed, extraction falls back to `markitdown` automatically.

## Commands

```bash
# Extract a source file into raw/ ready for wiki-ingest
wikiform extract path/to/file.pdf --vault-root PATH
wikiform extract path/to/report.docx --vault-root PATH
wikiform extract path/to/data.xlsx --vault-root PATH --overwrite

# Regenerate all three index files
wikiform index --vault-root PATH

# Audit the vault for structural issues
wikiform lint --vault-root PATH
wikiform lint --vault-root PATH --check broken_link
wikiform lint --vault-root PATH --output report.json

# Build or update the FTS5 search index
wikiform search index --vault-root PATH
wikiform search index --vault-root PATH --incremental

# Generate vector embeddings for semantic search
wikiform search embed --vault-root PATH
wikiform search embed --vault-root PATH --reset   # drop and recreate (required when switching models)
wikiform search embed --vault-root PATH --incremental  # skip already-embedded articles

# Search the vault
wikiform search query "multi-head attention" --vault-root PATH
wikiform search query "transformer" --vault-root PATH --tag Concepts --limit 10
wikiform search query "transformer" --vault-root PATH --json
wikiform search query "anomaly detection techniques" --vault-root PATH --semantic  # vector search

# Start the web UI
wikiform search serve --vault-root PATH --port 8787
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
wikiform search index --vault-root PATH
wikiform search embed --vault-root PATH

# Query with semantic search
wikiform search query "detection engineering workflow" --vault-root PATH --semantic
```

> **Note:** sqlite-vec requires Python compiled with `--enable-loadable-sqlite-extensions`. If you see `AttributeError: 'sqlite3.Connection' object has no attribute 'enable_load_extension'`, rebuild your Python:
> ```bash
> PYTHON_CONFIGURE_OPTS="--enable-loadable-sqlite-extensions" pyenv install 3.14.0 --force
> ```
