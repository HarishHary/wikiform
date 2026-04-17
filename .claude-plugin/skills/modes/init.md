---
name: wiki-init
description: Use when bootstrapping a new personal wiki for any knowledge domain - research, codebase documentation, reading notes, competitive analysis, or any long-term knowledge accumulation project.
---

# Wiki Init

Bootstrap a new LLM-backed wiki at a user-specified path.

Here's the rewritten pre-flight section:

## Pre-condition

Before doing anything, run `which wikiform`. If not found, tell the user to run `pipx install wikiform` and stop.

**Step 1 - Locate existing SCHEMA.md:**

Search for `SCHEMA.md` in this order:

1. Current directory
2. Each parent directory, up to a maximum of 3 levels up
3. Stop at the first match. If no match is found, proceed to the workflow - this is a fresh initialization.

**Step 2 - If SCHEMA.md is found, assess the wiki state:**

Read `SCHEMA.md` and check for the following files:

| File                   | Required                                 |
| ---------------------- | ---------------------------------------- |
| `SCHEMA.md`            | Yes                                      |
| `wiki/index.md`        | Yes                                      |
| `wiki/tag-index.md`    | Yes                                      |
| `wiki/master-index.md` | Yes                                      |
| `wiki/log.md`          | Yes                                      |
| `wiki/overview.md`     | Yes                                      |
| `wiki/pages/`          | Yes - directory must exist, may be empty |
| `raw/`                 | Yes - directory must exist, may be empty |
| `outputs/`             | Yes - directory must exist, may be empty |
| `_meta/`               | Yes - directory must exist, may be empty |

Then classify the wiki state as one of three cases:

**Case A - Complete:** All required files and directories are present.
→ Tell the user: "A wiki already exists at `<path>` for domain: `<domain>`. It was created on `<created date>` and has `<N>` pages."
→ Ask: "Do you want to (1) continue using it, (2) repair it, or (3) reinitialize it from scratch?"

**Case B - Partial:** `SCHEMA.md` exists but one or more required files or directories are missing.
→ Tell the user: "A wiki was found at `<path>` but initialization appears incomplete. Missing: `<list of missing files/directories>`."
→ Ask: "Do you want to (1) complete the initialization by creating the missing files, or (2) reinitialize from scratch?"

**Case C - Schema only:** Only `SCHEMA.md` exists, nothing else.
→ Treat as Case B.

**Step 3 - Handle the user's response:**

| Choice                             | Action                                                                                                                                                                                                                                                                                                                            |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Continue (Case A)                  | Stop. Tell the user to run `wiki-ingest` to add sources or `wiki-lint` to check health. Do not modify any files.                                                                                                                                                                                                                  |
| Repair (Case A)                    | Re-run only the steps that produce missing files. Do not overwrite existing files.                                                                                                                                                                                                                                                |
| Complete initialization (Case B/C) | Run only the steps that produce the missing files. Do not overwrite existing files.                                                                                                                                                                                                                                               |
| Reinitialize from scratch          | Ask: "This will delete all existing wiki pages, indexes, and logs at `<path>`. The `raw/` directory will not be touched. Type CONFIRM to proceed." If the user types CONFIRM: delete `wiki/` and `_meta` contents only, leave `raw/` and `outputs/` intact, then run the full workflow. If the user does not type CONFIRM: abort. |

**Step 4 - Schema compatibility check (Case A only):**

Read the `Created` date in `SCHEMA.md`. If the schema predates the current skill version or is missing expected fields (check for: `Path`, `Domain`, `Source types`, `Created`), flag it:

> "The existing SCHEMA.md may be outdated - some expected fields are missing. Continuing may cause compatibility issues with wiki-ingest. Recommend running a schema migration or reinitializing."

Do not block on this - it is a warning, not an error. Proceed with the user's chosen action.

## Workflow

### 1. Gather configuration (one question at a time)

Ask each question in order. Wait for the user's response before asking the next. Validate each answer before proceeding - if an answer is invalid or ambiguous, explain why and re-ask the same question. Do not proceed to the next question until the current one is resolved.

---

**Question 1 - Wiki location:**

> "Where should the wiki live? Provide an absolute path, e.g. `~/wikis/ml-research`."

Validation rules:

- If the path is relative, convert it to absolute using the current working directory. Tell the user: "Interpreting as `<absolute path>` - is that correct?"
- If the path contains spaces, warn the user: "Paths with spaces can cause issues with some scripts. Consider using hyphens instead. Proceed anyway?"
- If the path already exists and is not empty, check whether it contains a `SCHEMA.md` - if yes, this should have been caught in pre-flight. If no, warn: "This directory exists and is not empty. Initialization will add new files without removing existing ones. Proceed?"
- If the path does not exist: note that it will be created in step 2. Do not create it yet.

Store as: `WIKI_ROOT`

---

**Question 2 - Domain and purpose:**

> "What is this wiki for? One sentence describing the domain or purpose, e.g. 'Research notes on transformer architectures' or 'Internal documentation for the payments service.'"

Validation rules:

- If the answer is more than two sentences, ask the user to condense it to one.
- If the answer is fewer than 5 words, ask for more specificity: "Can you be more specific? This will be used to label the wiki and guide ingestion decisions."

Store as: `WIKI_DOMAIN`

---

**Question 3 - Source types:**

> "What types of sources will you add? Examples: papers, web articles, code files, transcripts, datasets, images. List all that apply."

This answer is informational - it is written to `SCHEMA.md` as context for ingestion decisions but does not constrain the directory structure, which is fixed. Tell the user this explicitly:

> "This is recorded in SCHEMA.md as context. All source type directories are created regardless of what you list here."

Validation rules:

- If the user lists a source type not supported by `wiki-ingest` (e.g. "videos", "audio"), flag it: "Note: `wiki-ingest` does not currently support `<type>`. You can still store these files in `raw/` but they will not be automatically ingested."
- No other validation required - this is metadata.

Store as: `WIKI_SOURCE_TYPES`

---

**Question 4 - Index categories:**

> "What categories should the wiki index use to organize pages? These become the top-level headings in `wiki/index.md`."

Present the defaults with a one-line explanation of each:

| Default set | Categories                                    | Best for                                                                            |
| ----------- | --------------------------------------------- | ----------------------------------------------------------------------------------- |
| Research    | `Sources`, `Entities`, `Concepts`, `Analyses` | Papers, articles, literature reviews - separates raw sources from derived knowledge |
| Codebase    | `Modules`, `APIs`, `Decisions`, `Flows`       | Software documentation - separates structural components from reasoning             |
| Custom      | User-defined                                  | Any domain that doesn't fit the above                                               |

> "Which would you like: Research, Codebase, or Custom? If Custom, list your categories."

Validation rules:

- Minimum 2 categories, maximum 8.
- Reserved names that cannot be used as categories: `pages`, `log`, `index`, `overview`, `raw`, `outputs`, `tags`. If the user provides any of these, explain the conflict and ask for an alternative.
- Category names must be title-case single words or short hyphenated phrases. If not, normalise and confirm: "Interpreting `<input>` as `<normalised>` - is that correct?"

Store as: `WIKI_CATEGORIES`

---

**Before proceeding to step 2, confirm the full configuration with the user:**

> "Here's the configuration I'll use:
>
> - **Path:** `<WIKI_ROOT>`
> - **Domain:** `<WIKI_DOMAIN>`
> - **Source types:** `<WIKI_SOURCE_TYPES>`
> - **Categories:** `<WIKI_CATEGORIES>`
>
> Proceed with initialization?"

If the user requests any changes, update the relevant stored value and re-confirm before proceeding.

Here's the rewritten step 2:

---

### 2. Create directory structure

Create the following structure under `WIKI_ROOT`. For each directory: if it already exists, leave it unchanged. If it does not exist, create it. After creating each empty directory, add a `.gitkeep` file so the directory is tracked if the wiki is version-controlled.

```text
<WIKI_ROOT>/
├── SCHEMA.md                  ← written in step 3
├── raw/                       ← source files; LLM writes frontmatter only, never modifies content
│   ├── articles/              ← web-clipped articles
│   ├── papers/                ← PDFs, paper summaries, research notes
│   ├── repos/                 ← repository dumps or clones
│   ├── datasets/              ← dataset files and descriptions
│   ├── images/                ← downloaded images
│   └── code/                  ← code files and snippets
├── wiki/
│   ├── index.md               ← written in step 4
│   ├── tag-index.md           ← written in step 5
│   ├── master-index.md        ← written in step 6
│   ├── log.md                 ← written in step 7
│   ├── overview.md            ← written in step 8
│   └── pages/                 ← all wiki pages, flat, slug-named, no subdirectories
├── outputs/
│   ├── slides/                ← Marp slideshows (populated by wiki-export or manually)
│   ├── charts/                ← matplotlib PNGs (populated by wiki-query or manually)
│   └── reports/               ← Q&A reports (populated by wiki-query or manually)
├── _meta/                     ← folder for internal objects
```

**Creation order:**

Create directories in this sequence to ensure parent directories exist before children:

1. `WIKI_ROOT/`
2. `raw/` and all subdirectories
3. `wiki/` and `wiki/pages/`
4. `outputs/` and all subdirectories
5. `_meta/`

**After creating each empty directory, create a `.gitkeep` file:**

```bash
touch <directory>/.gitkeep
```

Do not add `.gitkeep` to `wiki/pages/` - it will be populated in step 4 of `wiki-ingest` and an empty pages directory is a valid initial state.

**Immutability policy for `raw/`:**

`raw/` content is immutable - wiki skills never modify the body of a raw file. The one exception is frontmatter: `wiki-ingest` writes and updates YAML frontmatter (and sidecar `.meta.yaml` files for binaries) to track ingestion status. This is metadata about the file, not modification of its content. Document this distinction in `SCHEMA.md` step 3.

**Conflict handling:**

| Condition                                           | Action                                                                                                                            |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Directory exists, is empty                          | Leave unchanged, add `.gitkeep` if missing                                                                                        |
| Directory exists, has files                         | Leave unchanged, do not add `.gitkeep`                                                                                            |
| File exists at a path where a directory is expected | Stop. Tell the user: "A file exists at `<path>` where a directory is required. Resolve this conflict manually before proceeding." |

**`outputs/` note:**

The `outputs/` subdirectories are placeholders for artifacts produced by other skills (`wiki-export`, `wiki-query`). They are not populated by `wiki-init` or `wiki-ingest`. If those skills do not exist in the current setup, `outputs/` will remain empty - this is expected.

### 3. Write `SCHEMA.md`

`SCHEMA.md` is the authoritative reference file for all wiki skills. Every skill reads it on startup to locate the wiki and understand its conventions. Write it carefully - errors here propagate to every subsequent operation.

```markdown
# Wiki Schema

## Identity

- **Path:** <WIKI_ROOT - absolute path, no trailing slash>
- **Domain:** <WIKI_DOMAIN>
- **Source types:** <WIKI_SOURCE_TYPES>
- **Created:** <today YYYY-MM-DD>
- **Schema version:** 2

## Directory Structure

- `raw/` - source files. LLM skills write frontmatter only. Body content is never modified.
- `raw/articles/` - web-clipped articles
- `raw/papers/` - PDFs, paper summaries, research notes
- `raw/repos/` - repository dumps or clones
- `raw/datasets/` - dataset files and descriptions
- `raw/images/` - downloaded images
- `raw/code/` - code files and snippets
- `wiki/` - all LLM-maintained wiki files
- `wiki/pages/` - flat directory of all wiki pages, slug-named, no subdirectories
- `outputs/` - LLM-generated artifacts (slides, charts, reports)
- `_meta/` - internal object used by scripts etc...

## Wiki Page Frontmatter

Every file in `wiki/pages/` must start with this frontmatter:

\`\`\`yaml
---
title: <page title>
tags: [<primary tag>, <additional tags>]
sources: [<raw-file-slug>]
type: <paper | article | code | repo | image | dataset | entity | concept | other>
updated: YYYY-MM-DD
---
\`\`\`

Field rules:

- `tags`: YAML array. First tag is the primary category and must be one of the Index Categories defined below.
- `sources`: YAML array of raw file slugs. References the raw file that produced this page, not the page itself.
- `type`: required on all pages. Use `entity` or `concept` for entity/concept pages; use source type for source summary pages.

## Raw File Frontmatter

Every file in `raw/` must have frontmatter (inline for text files, sidecar `.meta.yaml` for binary files):

\`\`\`yaml
---
title: <source title or filename>
source_type: <paper | article | code | repo | image | dataset | other>
status: <raw | ingested>
slug: <slug of the wiki page produced - blank until step 5 of wiki-ingest>
ingested_date: <YYYY-MM-DD - blank until ingestion complete>
ingested_to: [<list of wiki page slugs produced by ingestion>]
added: <YYYY-MM-DD - date added to raw/, never changes>
---
\`\`\`

## Cross-References

Use `[[slug]]` where slug = filename without `.md`.
Example: `[[transformer-architecture]]` → `wiki/pages/transformer-architecture.md`
Slugs are kebab-case, lowercase, no special characters.

## Log Entry Format

`wiki/log.md` is append-only. New entries are added at the top. Never rewrite or delete existing entries.

\`\`\`yaml
## [YYYY-MM-DD] <operation> | <title>
\`\`\`

Valid operations:

- `init` - wiki initialization
- `ingest` - source ingestion
- `lint-deferred` - lint warnings deferred to a future pass
- `search-deferred` - search index update failed or deferred
- `raw-missing` - raw file not found during ingestion
- `overview-review-needed` - overview has grown too large and needs a rewrite pass
- `query` - wiki query or report generated
- `update` - manual page update
- `lint` - dedicated lint pass

## Index Categories

<one per line, from WIKI_CATEGORIES>

## Tag Rules

- First tag in every page's frontmatter must be one of the Index Categories above.
- Additional tags are unrestricted but should be consistent across pages.
- Entity pages: primary tag is `entity` or `concept`. These are not Index Categories - entity and concept pages appear in the index under whichever category is most relevant to the domain.
- `stub` tag: reserved for incomplete pages created by `wiki-ingest` step 7 Rule C. Remove when the page is fully written.

## Slug Rules

- Lowercase, hyphen-separated, no special characters, kebab-case.
- Maximum 6 words. Drop articles and prepositions for long titles.
- Must be unique across all files in `wiki/pages/`.
- Cannot be changed after ingestion without breaking wikilinks.

## Immutability Policy

- `raw/` body content is immutable - skills never modify the text of a raw file.
- Exception: skills may write and update YAML frontmatter blocks at the top of raw text files, and sidecar `.meta.yaml` files for binary raw files. This is metadata tracking, not content modification.
- `wiki/`, `outputs/` and `_meta` are fully writable by skills.
- `wiki/log.md` is append-only - entries are never edited or deleted.

## Compatibility

- Schema version 2 is required by wiki-ingest v2 and later.
- If a skill reports schema incompatibility, run wiki-init repair to update this file.
```

### 4. Write `wiki/index.md`

`wiki/index.md` is the primary content catalog. Every wiki page appears here exactly once, under its primary category. It is populated and maintained by `wiki-ingest` step 9 - never edited manually.

```markdown
---
title: Wiki Index
updated: <today>
auto_generated: true
description: Primary content catalog. Every wiki page listed once, by category. Maintained by wiki-ingest.
---

# Wiki Index - <WIKI_DOMAIN>

> Auto-generated. Do not edit manually - changes will be overwritten by wiki-ingest.

<for each category in WIKI_CATEGORIES, in the order the user specified>
## <Category Name>
<!-- wiki-ingest adds entries here in format: - [[slug]] - <one-line summary> -->
</for each category>
```

**Note:** Category headings are pre-populated from `WIKI_CATEGORIES` collected in step 1. Do not add placeholder entries - leave each category section empty. `wiki-ingest` will populate them.

### 5. Write `wiki/tag-index.md`

`wiki/tag-index.md` indexes every wiki page by tag, alphabetically. Tag headings are not pre-populated - they are created by `wiki-ingest` step 9 as pages with new tags are added. It is maintained by `wiki-ingest` - never edited manually.

```markdown
---
title: Wiki Tag Index
updated: <today>
auto_generated: true
description: Every wiki page indexed by tag, alphabetically. Maintained by wiki-ingest.
---

# Wiki Tag Index - <WIKI_DOMAIN>

> Auto-generated. Do not edit manually - changes will be overwritten by wiki-ingest.

<!-- wiki-ingest adds tag headings and entries here in format:
## <tag>
- [[slug]] - <one-line summary>
-->
```

**Note:** No tag headings are pre-populated because no pages exist yet. The first ingestion will create the first tag entries.

### 6. Write `wiki/master-index.md`

`wiki/master-index.md` indexes every wiki page by the first letter of its title, alphabetically. Letter headings are not pre-populated - they are created by `wiki-ingest` step 9 as pages are added. It is maintained by `wiki-ingest` - never edited manually.

```markdown
---
title: Wiki Master Index
updated: <today>
auto_generated: true
description: Every wiki page indexed by title letter, alphabetically. Maintained by wiki-ingest.
---

# Wiki Master Index - <WIKI_DOMAIN>

> Auto-generated. Do not edit manually - changes will be overwritten by wiki-ingest.

<!-- wiki-ingest adds letter headings and entries here in format:
## <Letter>
- [[slug]] - <one-line summary>
-->
```

**Note:** No letter headings are pre-populated because no pages exist yet. The first ingestion will create the first letter entries.

**`auto_generated: true` policy** - applies to all three index files, `wiki/log.md`, and `wiki/overview.md`:

| File                   | Auto-generated | Implication                                                                                                    |
| ---------------------- | -------------- | -------------------------------------------------------------------------------------------------------------- |
| `wiki/index.md`        | Yes            | Never edit manually. `wiki-ingest` owns this file entirely.                                                    |
| `wiki/tag-index.md`    | Yes            | Never edit manually. `wiki-ingest` owns this file entirely.                                                    |
| `wiki/master-index.md` | Yes            | Never edit manually. `wiki-ingest` owns this file entirely.                                                    |
| `wiki/log.md`          | Yes            | Append-only. Never edit existing entries.                                                                      |
| `wiki/overview.md`     | Partial        | Sections are updated by `wiki-ingest` but the file may also be edited manually during a dedicated review pass. |
| `wiki/pages/*.md`      | No             | All page files are LLM-written but treated as primary content, not auto-generated artifacts.                   |

### 7. Write `wiki/log.md`

`wiki/log.md` is the append-only audit trail of all wiki operations. Write the file with the init entry as the first record.

```markdown
---
title: Wiki Log
auto_generated: true
description: Append-only audit trail of all wiki operations. Valid operations: init, ingest, lint-deferred, search-deferred, raw-missing, overview-review-needed, query, update, lint.
---

# Wiki Log

> Append-only. New entries are added at the top, below this line.
> Never edit or delete existing entries.
> Entry format: `## [YYYY-MM-DD] <operation> | <title>`

## [<today>] init | <WIKI_DOMAIN>

**Path:** `<WIKI_ROOT>`
**Schema version:** 2

### Configuration
- **Domain:** <WIKI_DOMAIN>
- **Source types:** <WIKI_SOURCE_TYPES>
- **Categories:** <WIKI_CATEGORIES>

### Directories created
- `raw/articles/`
- `raw/papers/`
- `raw/repos/`
- `raw/datasets/`
- `raw/images/`
- `raw/code/`
- `wiki/`
- `wiki/pages/`
- `outputs/slides/`
- `outputs/charts/`
- `outputs/reports/`

### Files created
- `SCHEMA.md`
- `wiki/index.md`
- `wiki/tag-index.md`
- `wiki/master-index.md`
- `wiki/log.md`
- `wiki/overview.md`

### Notes
<if any directories already existed and were left unchanged, list them here>
<if no notes, write "None">
```

### 8. Write `wiki/overview.md`

`wiki/overview.md` is the single file that synthesizes everything known across all wiki sources. It is partially maintained by `wiki-ingest` step 11 and partially editable during dedicated review passes. It is not a table of contents and not a summary of the latest source - it is a running model of the domain.

```markdown
---
title: Overview
tags: [overview, synthesis]
sources: []
updated: <today>
auto_generated: partial
---

# <WIKI_DOMAIN> - Overview

> Running synthesis of everything known in this wiki.
> Sections are updated by wiki-ingest when sources materially change the understanding.
> This file may also be edited manually during a dedicated overview review pass.
> Staleness rule: if Key Entities / Concepts exceeds 10 entries or Open Questions exceeds 7,
> flag with overview-review-needed in the log and schedule a rewrite pass.

## Key Entities / Concepts

> Populated by wiki-ingest. Load-bearing entities and concepts only - not every entity with a page belongs here.
> Entry format: `- [[slug]] - <one sentence on why this entity matters to the domain>`
> Stub pages are never listed here.

*No sources ingested yet.*

## Current Understanding

> Rewritten (not appended) by wiki-ingest when a source materially changes domain understanding.
> Must read as a coherent synthesis at all times - not an append-only log.
> Updated when a source: changes how a core aspect of the domain should be understood,
> contradicts or qualifies something already stated here, or fills a previously noted gap.

*No sources ingested yet.*

## Open Questions

> Questions added by wiki-ingest when a source raises an unresolved problem, contradiction,
> or unexamined assumption. Resolved questions are removed - do not let them accumulate.
> Entry format: `- <question as a single interrogative sentence> - raised by [[slug]]`

*No sources ingested yet.*
```

### 9. Confirm

Before reporting to the user, verify that initialization completed correctly by checking that every required file and directory exists:

| Path                               | Expected state                                                 |
| ---------------------------------- | -------------------------------------------------------------- |
| `<WIKI_ROOT>/SCHEMA.md`            | File exists, contains `Schema version: 2`                      |
| `<WIKI_ROOT>/raw/articles/`        | Directory exists                                               |
| `<WIKI_ROOT>/raw/papers/`          | Directory exists                                               |
| `<WIKI_ROOT>/raw/repos/`           | Directory exists                                               |
| `<WIKI_ROOT>/raw/datasets/`        | Directory exists                                               |
| `<WIKI_ROOT>/raw/images/`          | Directory exists                                               |
| `<WIKI_ROOT>/raw/code/`            | Directory exists                                               |
| `<WIKI_ROOT>/wiki/index.md`        | File exists, contains category headings from `WIKI_CATEGORIES` |
| `<WIKI_ROOT>/wiki/tag-index.md`    | File exists                                                    |
| `<WIKI_ROOT>/wiki/master-index.md` | File exists                                                    |
| `<WIKI_ROOT>/wiki/log.md`          | File exists, contains init entry for today                     |
| `<WIKI_ROOT>/wiki/overview.md`     | File exists                                                    |
| `<WIKI_ROOT>/wiki/pages/`          | Directory exists, is empty                                     |
| `<WIKI_ROOT>/outputs/slides/`      | Directory exists                                               |
| `<WIKI_ROOT>/outputs/charts/`      | Directory exists                                               |
| `<WIKI_ROOT>/outputs/reports/`     | Directory exists                                               |
| `<WIKI_ROOT>/_meta/`               | Directory exists                                               |

If any item fails the check: report it to the user as an initialization error, specify which step was responsible for creating it, and offer to retry that step.

If all checks pass: report to the user as follows.

---

**Report to user:**

---

**Wiki initialized successfully.**

**Configuration:**

- **Path:** `<WIKI_ROOT>`
- **Domain:** `<WIKI_DOMAIN>`
- **Source types:** `<WIKI_SOURCE_TYPES>`
- **Categories:** `<WIKI_CATEGORIES>`
- **Schema version:** 2

**Files created:**

- `SCHEMA.md` - wiki identity and conventions
- `wiki/index.md` - content catalog, pre-populated with category headings
- `wiki/tag-index.md` - tag index, empty until first ingestion
- `wiki/master-index.md` - master index, empty until first ingestion
- `wiki/log.md` - audit trail, init entry written
- `wiki/overview.md` - domain synthesis, empty until first ingestion

**What to do next:**

1. **Add your first source** - either copy a file into `raw/` and run `wiki-ingest <path>`, or run `wiki-ingest <URL>` directly.
2. **Review `SCHEMA.md`** - confirm the domain, source types, and categories reflect your intent. This is the only time editing `SCHEMA.md` directly is straightforward - later changes risk breaking skill compatibility.
3. **Install wikiform** - Without `wikiform` installed, `wiki-ingest` steps 8, 9, and 10 will fall back to manual procedures. <if wikiform is already present, omit this item>
4. **Run `wiki-lint`** periodically to check for broken wikilinks, missing frontmatter, and stale indexes. <note: wiki-lint is a separate skill not included in this initialization - install it separately>

**Important:**

- Do not move or delete `SCHEMA.md`. It is how all wiki skills locate this wiki. If it is accidentally deleted, recreate it by running `wiki-init` repair from the wiki root directory.
- Do not edit `wiki/index.md`, `wiki/tag-index.md`, or `wiki/master-index.md` manually - they are auto-generated and changes will be overwritten by `wiki-ingest`.
- `wiki/log.md` is append-only - do not edit or delete existing entries.
