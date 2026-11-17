# Shared Wiki Context

## Binary check

Before any operation, verify wikiform is installed:

```bash
command -v wikiform
```

If missing, stop and tell the user:

> `wikiform` is not installed. Run `pipx install wikiform` then try again.

## Vault root resolution

Resolve the vault root in this order:

1. The configured vault root given by the router (`user_config.vault_root`), if non-empty and the directory exists
2. Search for `SCHEMA.md` starting from the current directory, then each parent up to 3 levels
3. Stop at the first match
   If no `SCHEMA.md` is found, stop and tell the user:

> No vault found. Run `/wikiform:wikiform init` to create one.

Call the result `<WIKI_ROOT>` (absolute path, no trailing slash).

## Running the wikiform CLI

`--vault-root` is a **global** option and must come **before** the subcommand. Placing it after the subcommand is an error.

```bash
wikiform --vault-root "<WIKI_ROOT>" <command> [options]
```

Commands used by the modes:

| Command                                         | Purpose                                                                                                   |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `extract <path-or-URL> [--overwrite]`           | Convert a file/URL to `raw/<subdir>/<slug>.md` with raw-file frontmatter. Prints a JSON result.           |
| `index`                                         | Regenerate `wiki/index.md`, `wiki/master-index.md`, `wiki/tag-index.md`.                                  |
| `lint [--check <name>] [-o file]`               | Structural checks. JSON report on stdout or in the `-o` file.                                             |
| `search index [--incremental]`                  | Build the FTS5 index. Without `--incremental` every page is re-indexed.                                   |
| `search embed [--incremental] [--reset]`        | Build vector embeddings (needed only for `search query --semantic`).                                      |
| `search query "<terms>" [--semantic] [--tag T] [--dir D] [--limit N] --json` | Keyword (default) or semantic search. `--tag` is an exact tag; `--dir` a path prefix. |

Conventions:

- JSON results go to stdout; log lines go to stderr. Use `-o <file>` to write the JSON to a file instead.
- Exit codes: `0` success; `2` usage/configuration problem (missing or non-existent vault root, unknown check, file not found); `1` failure. **`lint` also exits `1` when the report contains errors** - the report is still written, so read it rather than treating this as a crash.
- Run `wikiform` directly. Do not prefix with environment activation (pyenv, venv) unless the user asks.

## SCHEMA.md fields to extract

Once `SCHEMA.md` is located, read it and extract:

- `Path` - absolute vault root path (use this for all subsequent file operations)
- `Index Categories` - valid category names for frontmatter
- Required frontmatter fields - from the `## Wiki Page Frontmatter` block
- `Cross-References` - wikilink convention (`[[slug]]`)
- `Log Entry Format` - format for appending entries to `wiki/log.md`

`wikiform` itself parses `## Index Categories` (a bullet or one-per-line list) and the first ```` ```yaml ```` block under `## Wiki Page Frontmatter` (top-level keys, minus `sources` and `type`, are the required fields). Keep both sections in that shape.

## Plugin hooks

The plugin installs hooks that run automatically (they do nothing outside a vault):

- **Session start** - prints a one-glance vault status (pages, raw sources awaiting ingest, ingests since last lint, search-index freshness).
- **Guard (before Write/Edit)** - blocks edits to the generated `wiki/index.md`, `wiki/tag-index.md`, `wiki/master-index.md` once they exist, and blocks changes to the *body* of existing `raw/` files (frontmatter edits are allowed). If a write is blocked, follow the message - do not try to work around it.
- **Post-write (after Write/Edit on `wiki/pages/*.md`)** - validates slug naming and required frontmatter and reports problems immediately. Fix them before continuing.
- **End of turn** - if any page changed, regenerates the three index files and runs `search index --incremental`. The explicit index steps in the modes remain valid (they are idempotent); the hook is the safety net. It never runs `search embed`.

## Log entry convention

All operations that modify the vault append an entry to `wiki/log.md`. Entries are **prepended** (newest first). Follow the format defined in `SCHEMA.md` under `Log Entry Format`.
