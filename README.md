# Wikiform

LLM-backed wiki

## Installation

```bash
poetry install
```

For the web search UI:

```bash
poetry install --with serve
```

## Commands

```bash
# Regenerate all three index files
wikiform index --vault-root PATH

# Audit the vault for structural issues
wikiform lint --vault-root PATH
wikiform lint --vault-root PATH --check broken_link
wikiform lint --vault-root PATH --output report.json

# Build or update the FTS5 search index
wikiform search index --vault-root PATH
wikiform search index --vault-root PATH --incremental

# Search the vault
wikiform search query "multi-head attention" --vault-root PATH
wikiform search query "transformer" --vault-root PATH --tag Concepts --limit 10
wikiform search query "transformer" --vault-root PATH --json

# Start the web UI
wikiform search serve --vault-root PATH --port 8787
```
