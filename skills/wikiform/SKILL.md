---
name: wikiform
description: Use when working with a personal wiki vault - initialising, ingesting sources, querying, linting, or updating pages. Pasting a file path or URL auto-triggers ingest mode.
argument-hint: "[init|ingest|search|lint|update] [file, URL, question, or page]"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Wikiform Router

Routes vault operations to the appropriate mode. Each mode has full instructions in `modes/`.

Configured vault root (may be empty - then auto-detect it as described in `_shared.md`): `${user_config.vault_root}`

## Auto-routing rules

| Input                                 | Mode              |
| ------------------------------------- | ----------------- |
| No arguments                          | Show menu (below) |
| File path, URL, or raw document text  | `ingest`          |
| A question about wiki content         | `search`          |
| "lint", "audit", "check"              | `lint`            |
| "update", "revise", "edit `[[slug]]`" | `update`          |
| "init", "bootstrap", "new wiki"       | `init`            |

If the first argument is a mode name (`init`, `ingest`, `search`, `lint`, `update`), use that mode and treat the rest as its input.

## Menu (no arguments)

When invoked with no arguments, display:

```
Wikiform - vault operations

  /wikiform:wikiform init      Bootstrap a new wiki
  /wikiform:wikiform ingest    Add a source (file, URL, text)
  /wikiform:wikiform search    Ask a question against the wiki
  /wikiform:wikiform lint      Audit vault health
  /wikiform:wikiform update    Revise existing pages

Or just describe what you want - file paths, URLs and questions are routed automatically.
```

## Mode dispatch

Once the mode is determined, first read `${CLAUDE_SKILL_DIR}/_shared.md` (binary check, vault root resolution, SCHEMA.md parsing, how to invoke the `wikiform` CLI), then read the mode file and execute it exactly:

- **init** → `${CLAUDE_SKILL_DIR}/modes/init.md`
- **ingest** → `${CLAUDE_SKILL_DIR}/modes/ingest.md`
- **search** → `${CLAUDE_SKILL_DIR}/modes/search.md`
- **lint** → `${CLAUDE_SKILL_DIR}/modes/lint.md`
- **update** → `${CLAUDE_SKILL_DIR}/modes/update.md`

The mode files refer to each other by their original skill names. Map them as: `wiki-init` → init mode, `wiki-ingest` → ingest mode, `wiki-query` → search mode, `wiki-lint` → lint mode, `wiki-update` → update mode.
