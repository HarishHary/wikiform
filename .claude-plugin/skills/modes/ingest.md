---
name: wiki-ingest
description: Use when adding a new source to a wiki - a paper, article, URL, file, transcript, or any document.
---

# Wiki Ingest

Add a source to the wiki. Read it, discuss with the user, write a summary page, update entity/concept pages, and maintain the index, overview, and log.

## Pre-condition

Before doing anything, run `which wikiform`. If not found, tell the user to run `pip install wikiform` and stop.

Search for `SCHEMA.md` starting from the current directory and upward. If not found, tell the user to run `wiki-init` first.

Read `SCHEMA.md` to learn: wiki root path, page frontmatter format, cross-reference convention, log entry format, indexes taxonomy.

## Ingest count calculation

Several steps in this skill compute **ingests since last lint**. Use this procedure wherever that count is needed:

1. Read `wiki/log.md` from top to bottom.
2. Find the most recent entry whose operation is `lint`. Record its position.
3. Count all entries with operation `ingest` that appear **above** that position (i.e., after it chronologically, since entries are prepended).
4. If no `lint` entry exists, count = total number of `ingest` entries in the log.

Store as `INGESTS_SINCE_LINT`. This value is computed once per session and reused in steps 13 and 14.

## Workflow

### 1. Accept the source

Identify the source type and route it to the correct `raw/` subdirectory. Do not proceed to step 2 until the file is saved.

| Source type                                           | How to read                                                                    | Save to                        |
| ----------------------------------------------------- | ------------------------------------------------------------------------------ | ------------------------------ |
| File path - document (`.pdf`, `.md`, `.txt`, `.docx`) | Read directly                                                                  | `raw/papers/<filename>`        |
| File path - data (`.csv`, `.json`, `.yaml`, `.toml`)  | Read directly                                                                  | `raw/datasets/<filename>`      |
| File path - image (`.png`, `.jpg`, `.svg`)            | Read directly                                                                  | `raw/images/<filename>`        |
| File path - code (`.py`, `.go`, `.ts`, etc.)          | Read directly                                                                  | `raw/code/<filename>`          |
| URL                                                   | Fetch with `browse` skill. If `browse` is unavailable, tell the user and stop. | `raw/articles/<slug>.<ext>`    |
| Pasted text                                           | Format as markdown                                                             | `raw/papers/<slug>.md`         |
| Code snippet                                          | Format as markdown with fenced code block and language tag                     | `raw/code/<slug>.md`           |
| Repository                                            | Clone or copy                                                                  | `raw/repos/<slug>/`            |
| Other                                                 | Ask the user: what is this and how should it be accessed? Do not guess.        | Determined after clarification |

**Conflict check:** Before saving, check whether a file with the same name already exists in the target directory.
- If yes: tell the user, show the existing file's `ingested_date` if present, and ask whether to overwrite or abort.
- If no: save and proceed.

### 2. Read the source in full

Read the entire source before proceeding to step 3. While reading, maintain a working note of the following - you will use this in step 3:

- **Claims:** What does the source assert? List the main ones.
- **Entities & Concepts:** What named things (systems, people, methods, terms) does it introduce or rely on?
- **Evidence:** What supports the claims? Note type: empirical, anecdotal, theoretical, none.
- **Limitations:** What does the source not address, assume without justification, or explicitly scope out?
- **Contradictions:** Does anything conflict with existing wiki pages? Check `wiki/index.md` and any directly relevant pages now, during reading, not after.

**Reading strategy by source type:**

| Source type                    | Strategy                                                                                                                                                               |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Short document (< 2,000 words) | Read in full in one pass                                                                                                                                               |
| Long document (≥ 2,000 words)  | Read in sections of ~500 words. Do not summarize as you go - complete the full read first, then form conclusions.                                                      |
| Code file                      | Read top to bottom: imports → types/structs → functions → entry point. Note what each exported symbol does.                                                            |
| Repository                     | Do not read all files. Required: `README`, any docs in `docs/` or `wiki/`. Optional: read source files only if the README is insufficient to understand the mechanism. |
| Image                          | Describe what is depicted. Note any text, labels, axes, or annotations present. If the image is a diagram, describe the structure and relationships it shows.          |
| Dataset                        | Read the header and a representative sample (first 20 rows or equivalent). Note schema, value ranges, and any apparent anomalies.                                      |

**Do not begin writing until step 3 is complete.** The working note is internal - do not show it to the user unprompted.

### 3. Surface takeaways - BEFORE writing anything

Using the working note from step 2, present the following to the user in this exact structure:

**Primary claim:** One sentence. What is the source's central assertion or contribution?
**Key mechanism or argument:** One to two sentences. How does it work or how is the claim supported?
**Entities & concepts introduced or updated:** Bullet list. For each: name, and one clause on whether it's new to the wiki or updates an existing page.
**Contradictions with existing wiki:** If any were found in step 2, list them explicitly: `[[existing-page]]` - what conflicts and how. If none, write "None found."
**Suggested emphasis:** Based on your reading, what aspect is most likely to be useful to the wiki's domain? State it as a single sentence and make clear it's your judgment, not the source's.

Then ask the user exactly this:

> "Does this match your reading? Anything to add, correct, or shift emphasis on before I write?"

**Handling the response:**

- If the user confirms or adds specifics → incorporate and proceed to step 4.
- If the user says "looks good" or equivalent with no additions → proceed to step 4 as-is.
- If the user corrects something → update the working note, restate the corrected point back to the user in one sentence to confirm, then proceed.
- If the user raises a contradiction not found in step 2 → note it explicitly in the working note as a user-identified contradiction, then proceed.

Do not proceed to step 4 until the user has responded.

### 4. Tag the raw file with frontmatter

Write the following frontmatter to the raw file immediately after saving it in step 1. Do not wait until later steps.

```yaml
---
title: <source title, or filename if title is not yet known>
source_type: <paper | article | code | repo | image | dataset | other>
status: raw
slug: <leave blank - filled in step 5>
ingested_date: <leave blank - filled in step 12>
ingested_to: []
added: <today>
---
```

**Field rules:**

| Field           | Rule                                                                                    |
| --------------- | --------------------------------------------------------------------------------------- |
| `title`         | Use the source's own title if present. If not, use the filename. Do not invent a title. |
| `source_type`   | Must match the routing decision made in step 1.                                         |
| `status`        | Always `raw` at this point. Only two valid values: `raw` and `ingested`.                |
| `slug`          | Leave blank now. Step 5 will generate it. Write it back here after step 5 completes.    |
| `ingested_date` | Leave blank now. Step 12 will fill it.                                                  |
| `ingested_to`   | Empty list. Step 12 will populate it.                                                   |
| `added`         | Today's date. This never changes after being set.                                       |

**If the raw file is a binary format** (PDF, image) that does not support inline frontmatter: create a sidecar file at `<same path>/<filename>.meta.yaml` with the same fields.

### 5. Generate the slug

The slug is the permanent identifier for the wiki page. It must be unique, stable, and meaningful enough to identify the page without opening it. It cannot be changed after ingestion without breaking wikilinks.

**Generation rules:**

| Case                    | Rule                                                               | Example                                                                                         |
| ----------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| Normal title            | Lowercase, hyphens, strip special characters                       | "Attention Is All You Need" → `attention-is-all-you-need`                                       |
| Long title (> 6 words)  | Use the first 4-5 meaningful words, drop articles and prepositions | "A Survey of Large Language Models and Their Applications" → `survey-large-language-models`     |
| Acronym in title        | Keep the acronym as-is, lowercase                                  | "BERT: Pre-training of Deep Bidirectional Transformers" → `bert-pretraining-deep-bidirectional` |
| Version number in title | Include the version                                                | "Kubernetes 1.29 Release Notes" → `kubernetes-1-29-release-notes`                               |
| Non-English title       | Transliterate to ASCII, do not translate                           | "Über die Hypothesen" → `uber-die-hypothesen`                                                   |
| No title available      | Use the filename without extension                                 | `raw/papers/2024_survey.pdf` → `2024-survey`                                                    |

**Collision check:**

Before finalising the slug, check whether `wiki/pages/<slug>.md` already exists.

- If no collision: proceed.
- If collision with a different source: append a short disambiguator, prefer year if available. Example: `bert-pretraining-2018` vs `bert-pretraining-2019`. If year is not available, append `-2` and increment.
- If collision with the same source: the source has already been ingested. Tell the user and stop. Do not re-ingest unless the user explicitly confirms.

**Write-back:**

After finalising the slug, write it to the `slug` field in the raw file's frontmatter (or sidecar `.meta.yaml` for binary files). This is the only persistent link from the raw file back to its wiki page.

### 6. Write the source summary page

Write `wiki/pages/<slug>.md`:

```markdown
---
title: <source title>
original: <URL or file path>
tags: [<relevant tags>]
sources: [<raw-file-slug>]
type: <paper | article | code | repo | image | dataset | other>
updated: <today>
---

# <Source Title>

## Claim
<One to two sentences. What does this source assert or demonstrate? State it as a falsifiable claim where possible. Do not evaluate it here.>

## Mechanism
<How does it work? For a paper: the method, architecture, or theoretical argument. For an article: the chain of reasoning or narrative structure. For code: what it does and how. Be concrete - name components, steps, or stages. Use a numbered list if there is a clear sequence, bullet points if not.>

## Evidence
<What supports the claim? Data, experiments, benchmarks, examples, citations. If the source provides none, say so explicitly. Do not infer evidence that isn't present.>

## Limitations
<What does the source not cover, assume without justification, or fail to test? Include contradictions with existing wiki pages if any were found in step 3. If no limitations are apparent, write "None identified" - do not omit the section.>

## Entities & Concepts
<One [[slug]] per line. These are the entities and concepts this source introduces or significantly updates. If a page doesn't exist yet, list it anyway - it will be created in step 7.>

## Connections
<Wikilinks only. One line per connection, format: [[slug]] - <one clause on why it's relevant>. No prose paragraph.>
```

### 7. Update entity and concept pages

For each entity or concept listed in `## Entities & Concepts` of the new source page, follow this sequence:

**Step 1 - Check if the page exists:**

- If yes: read it in full, then apply Rule A or Rule B below.
- If no: apply Rule C below.

**Rule A - Appearance only:** The source mentions or uses the entity but does not materially change how it should be defined or understood. → Append to `## Appearances in Sources` only. Do not touch other sections. Update frontmatter `updated` date and add the new raw file slug to `sources`.

**Rule B - Material update:** The source revises the entity's definition, extends its mechanism, or contradicts the current description. → Rewrite `## Definition` and/or `## How It Works` to reflect the updated understanding. Append to `## Appearances in Sources`. Update frontmatter `updated` date and add the new raw file slug to `sources`.

**Rule C - Page does not exist:**

- If the source introduces or substantially defines the entity: create the page using the template below.
- If the source only mentions the entity in passing: create a stub page with `## Definition` only, tag it `stub`, and add it to the log for future expansion. Do not leave it unlisted - a stub is better than a missing page because it preserves the wikilink target.

If uncertain whether Rule A or Rule B applies, default to **Rule A** and flag the entity in the log for manual review.

**Page template (Rule C, full page):**

```markdown
---
title: <Entity or Concept Name>
tags: [<entity | concept>, <additional tags>]
sources: [<raw-file-slug>]
updated: <today>
---

# <Name>

## Definition
<One to two sentences. What is this, precisely? Avoid "is a type of" unless taxonomy is the point.>

## How It Works
<Mechanism, structure, or behavior. Be concrete - name components, steps, or stages. If this is a concept rather than a system, describe the logical content: what it asserts or entails.>

## Open Questions
<What is not yet settled or understood about this entity based on current wiki sources? Omit section if none.>

## Appearances in Sources
- [[raw-file-slug]] - <role: introduced / used / challenged / extended>

## Related Concepts
- [[related-slug]] - <relationship: depends on / contrasts with / generalizes / instantiates>
```

**Page template (Rule C, stub):**

```markdown
---
title: <Entity or Concept Name>
tags: [<entity | concept>, stub]
sources: [<raw-file-slug>]
type: <entity | concept>
updated: <today>
---

# <Name>

## Definition
<One to two sentences from the source that mentions this entity. Do not expand beyond what the source supports.>

## Appearances in Sources
- [[raw-file-slug]] - mentioned
```

**Canonical stub log format** (used by this skill, wiki-query, and wiki-update whenever a stub is created):

```markdown
## [<today>] ingest | stub created: [[<slug>]]
Source: [[<raw-file-slug>]] (or: <triggering skill> - <question or reason>)
Expand when: <suggested ingest target or condition>
```

**Tag rule:**

Use exactly one primary tag per entity page:

| Tag       | When to use                                                                                |
| --------- | ------------------------------------------------------------------------------------------ |
| `entity`  | A named thing that exists in the world: system, tool, person, organisation, dataset, model |
| `concept` | An idea, method, principle, or theoretical construct                                       |

Additional tags are allowed and encouraged but must follow the wiki's tag taxonomy from `SCHEMA.md`. The primary tag (`entity` or `concept`) must always be first in the list.


### 8. Backlink audit

For each entity or concept page created or updated in step 7, scan existing wiki pages for mentions that are not yet wikilinks. This step must run before the index is updated in step 9 - backlinks affect index density.

**Scan method:**

For each entity name from step 7's list:

1. Search `wiki/pages/` for pages that contain the entity's name as plain text but do not already have `[[<slug>]]` linking to it.
2. For each match found, identify the most appropriate insertion point using this priority order:
   - `## Related Concepts` section - add `[[slug]] - <relationship>`
   - `## Connections` section - add `[[slug]] - <one clause on relevance>`
   - Inline in body text - only if the entity name appears in a sentence where a link would add navigational value. Do not add inline links mechanically to every occurrence - one per page is sufficient.
3. Do not add a backlink if the mention is incidental (e.g. the entity name appears in a quote, a log entry, or a list of unrelated examples).

**After manual scan, run the lint script:**

```bash
pyenv activate obsidian && wikiform lint
```

If the `obsidian` pyenv environment is unavailable, run:

```bash
wikiform lint
```

If neither works, note the failure in the log and proceed - do not block ingestion on lint failure.

**Lint output priority:**

| Priority | Type                                                                 | Action                                                                                                     |
| -------- | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 1        | Errors - broken wikilinks, missing frontmatter                       | Fix before proceeding                                                                                      |
| 2        | Warnings - naming violations, empty files, missing required sections | Fix if the affected page was created or modified in this ingestion. Defer others to a dedicated lint pass. |
| 3        | Suggestions - low link density, missing tags                         | Optional. Log for future pass.                                                                             |

**Log any deferred warnings and suggestions:**

```markdown
## [<today>] lint-deferred | <source slug>
Deferred: <list of warnings/suggestions deferred to future pass>
```

### 9. Update the index pages

The wiki maintains three index files. All three must reflect every page created or updated in steps 6 and 7 before proceeding to step 10.

| Index file             | Purpose                                    | Updated by       |
| ---------------------- | ------------------------------------------ | ---------------- |
| `wiki/index.md`        | Every page, one-line summary, by category  | Script or manual |
| `wiki/tag-index.md`    | Every page, by tag alphabetically          | Script or manual |
| `wiki/master-index.md` | Every page, by title letter alphabetically | Script or manual |

**Run the index script:**

```bash
pyenv activate obsidian && wikiform index
```

If the `obsidian` pyenv environment is unavailable, run:

```bash
wikiform index
```

**After the script runs, verify the output:**

For each page created or updated in steps 6 and 7, confirm:

1. It appears in `wiki/index.md` under the correct category.
2. All its tags appear in `wiki/tag-index.md` with a link to the page.
3. It appears in `wiki/master-index.md` under the correct letter.

If any entry is missing or incorrect, do not proceed - fix it manually using the manual update instructions below.

**If the script fails or is unavailable:**

Fall back to manual updates for each page created or updated in steps 6 and 7:

**`wiki/index.md`** - add under the correct category:

```markdown
- [[slug]] - <one-line summary matching the page title and claim>
```

**`wiki/tag-index.md`** - for each tag in the page's frontmatter, add under the correct tag heading:

```markdown
- [[slug]] - <one-line summary>
```

If the tag heading does not exist yet, create it in alphabetical order.

**`wiki/master-index.md`** - add under the correct letter heading:

```markdown
- [[slug]] - <one-line summary>
```

If the letter heading does not exist yet, create it in alphabetical order.

**Log script failures:**

```markdown
## [<today>] lint-deferred | <source slug>
Index script failed: <error or reason>
Manual update applied to: index.md, tag-index.md, master-index.md
```

### 10. Update the search index

The search index enables full-text lookup across all wiki pages. It must be updated after every ingestion so that pages created or updated in steps 6 and 7 are immediately searchable.

**Incremental vs full reindex:**

| Mode            | When to use                                                                                                                |
| --------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `--incremental` | Default. Indexes only new or modified pages. Use after normal ingestion.                                                   |
| `--full`        | Use when: a page was renamed or its slug changed, a page was deleted, or the incremental index produces incorrect results. |

**Run the search index script:**

```bash
pyenv activate obsidian && wikiform search index --incremental
```

If the `obsidian` pyenv environment is unavailable, run:

```bash
wikiform search index --incremental
```

**After the script runs, verify the output:**

For each page created or updated in steps 6 and 7, run a test query using a distinctive term from the page's `## Claim` section:

```bash
wikiform search query "<distinctive term>"
```

Confirm the new page appears in results. If it does not:

1. Check that the page's frontmatter is valid - malformed frontmatter is the most common cause of indexing failure.
2. Run a full reindex:

```bash
wikiform search index --full
```

3. If the full reindex does not resolve it, log the failure and proceed - do not block ingestion on search index failure.

**If the script is unavailable entirely:**

Log the failure and proceed:

```markdown
## [<today>] search-deferred | <source slug>
Search index not updated: <error or reason>
Affected pages: <list of slugs from steps 6 and 7>
```

### 11. Update `wiki/overview.md`

The overview is the single file that synthesizes everything known across all wiki sources. It is not a table of contents and not a summary of the latest source - it is a running model of the domain. Update it to reflect how this ingestion changes the overall picture, not just what the new source says.

**Read the current overview in full before writing anything.**

Then apply the following update rules:

**Rule 1 - Current Understanding:**

Update if the new source does any of the following:

- Introduces a mechanism or finding that changes how a core aspect of the domain should be understood
- Contradicts or qualifies something already stated in "Current Understanding"
- Fills a gap that was previously noted as unknown

Do not append. Rewrite the affected sentences or paragraph to integrate the new understanding. The section should read as a coherent synthesis at all times, not an append-only log.

If the source does not materially change the current understanding, do not touch this section.

**Rule 2 - Key Entities / Concepts:**

Add an entry if the new source introduces an entity or concept that:

- Has a dedicated page in `wiki/pages/` after step 7
- Is load-bearing for understanding the domain - not every entity qualifies

Format:

```markdown
- [[slug]] - <one sentence on why this entity matters to the domain, not just what it is>
```

Do not add stub pages here. Stubs are placeholders, not settled knowledge.

**Rule 3 - Open Questions:**

Add a question if the new source:

- Explicitly identifies an unresolved problem or limitation
- Contradicts an existing wiki page without resolving the contradiction
- Introduces a claim that depends on assumptions not yet examined in the wiki

Format:

```markdown
- <question as a single interrogative sentence> - raised by [[slug]]
```

Remove a question if the new source resolves it. Do not let resolved questions accumulate.

**Rule 4 - Staleness check:**

If the overview has more than 10 entries in "Key Entities / Concepts" or more than 7 open questions, it is becoming a list rather than a synthesis. Flag this in the log:

```markdown
## [<today>] overview-review-needed | <source slug>
Overview has <N> entities and <N> open questions. Consider a dedicated overview rewrite pass.
```

Do not perform the rewrite during ingestion - log it and proceed.

**Update the frontmatter:**

```yaml
updated: <today>
sources: [<all raw-file-slugs ingested so far>]
```

### 12. Update the raw file frontmatter

This step closes the traceability loop between the raw file and the wiki pages it produced. After this step, it must be possible to look at any raw file and know exactly what wiki pages it generated and when.

**Locate the raw file:**

Check that the raw file still exists at the path recorded in step 1. If it has been moved or deleted:

- Search for it by filename within `raw/`.
- If found at a new path: update the path in the source summary page's `original` field, then proceed.
- If not found: log the missing file and proceed. Do not block ingestion on a missing raw file - the wiki pages are the primary record.

```markdown
## [<today>] raw-missing | <source slug>
Raw file not found at original path: <path>
Wiki pages produced: <list of slugs>
```

**For text-based files** (`.md`, `.txt`, `.html`, `.py`, etc.) - update the frontmatter in place:

```yaml
---
title: <unchanged>
source_type: <unchanged>
status: ingested
slug: <slug generated in step 5>
ingested_date: <today>
ingested_to:
  - <source summary page slug from step 6>
  - <entity/concept page slug 1 from step 7>
  - <entity/concept page slug 2 from step 7>
  - <...all pages created or updated in steps 6 and 7>
added: <unchanged>
---
```

**For binary files** (`.pdf`, `.png`, `.jpg`, etc.) - update the sidecar file at `<same path>/<filename>.meta.yaml`:

```yaml
title: <unchanged>
source_type: <unchanged>
status: ingested
slug: <slug generated in step 5>
ingested_date: <today>
ingested_to:
  - <source summary page slug from step 6>
  - <entity/concept page slug 1 from step 7>
  - <entity/concept page slug 2 from step 7>
  - <...all pages created or updated in steps 6 and 7>
added: <unchanged>
```

If no sidecar file exists yet, create it now at the correct path.

**Verification:**

After writing, confirm:

1. `status` is `ingested`.
2. `ingested_to` lists every page created or updated in steps 6 and 7 - not just the source summary page.
3. `slug` matches the slug generated in step 5.
4. `ingested_date` is today's date.

If any field is incorrect, fix it before proceeding.

### 13. Append to `wiki/log.md`

The log is the append-only audit trail of all wiki operations. Each ingestion produces a single consolidated entry that records what was done, what changed, and what was deferred. New entries are added at the top of the file.

Compute `INGESTS_SINCE_LINT` using the procedure defined at the top of this document.

**Log entry format:**

```markdown
## [<today>] ingest | <source title>

**Raw file:** `<path to raw file or sidecar>`
**Source type:** <paper | article | code | repo | image | dataset | other>
**Slug:** [[<slug>]]
**Ingests since last lint:** <INGESTS_SINCE_LINT>

### Pages created
- [[slug]] - <one clause on what this page covers>

### Pages updated
- [[slug]] - <one clause on what changed and why>

### Entity/concept pages
- [[slug]] - <created | updated | stub created> - <one clause on why>

### Overview changes
- Current Understanding: <updated | unchanged> - <one clause on what changed if updated>
- Key Entities / Concepts: <N added> - <list of [[slug]] added>
- Open Questions: <N added, N removed> - <list of questions added or removed>

### Deferred items
- <item> - <reason deferred> - <step that generated this deferral>
<if none, omit section>

### Errors
- <error description> - <step where it occurred> - <how it was handled>
<if none, omit section>
```

If there are no deferred items, omit the `### Deferred items` section. If there are no errors, omit the `### Errors` section.

**Consolidation rule:**

All deferred item log entries written during steps 8, 9, 10, and 11 are superseded by this consolidated entry. Do not leave scattered step-level log entries as the only record - they are temporary placeholders. The step 13 entry is the canonical ingestion record.

**Example entry:**

```markdown
## [2026-04-11] ingest | Attention Is All You Need

**Raw file:** `raw/papers/attention-is-all-you-need.pdf`
**Source type:** paper
**Slug:** [[attention-is-all-you-need]]

### Pages created
- [[attention-is-all-you-need]] - source summary page for the transformer architecture paper

### Pages updated
- [[sequence-to-sequence]] - added transformer as a successor architecture

### Entity/concept pages
- [[transformer]] - created - primary architecture introduced by this source
- [[multi-head-attention]] - created - key mechanism described in detail
- [[positional-encoding]] - stub created - mentioned in passing, not fully defined

### Overview changes
- Current Understanding: updated - transformer architecture replaces RNN as dominant sequence model
- Key Entities / Concepts: 2 added - [[transformer]], [[multi-head-attention]]
- Open Questions: 1 added - Does positional encoding generalise beyond fixed sequence lengths?

### Deferred items
- [[sequence-to-sequence]] warning: missing required section - step 8 - deferred to lint pass

### Errors
- Search index incremental run failed - step 10 - full reindex scheduled
```

### 14. Report to user

The report is the user-facing summary of what the ingestion produced. It must answer three questions: what does the wiki now know, what changed, and what needs attention.

**Report format:**

---

**Ingested:** `<source title>` → [[slug]]
**Source type:** <type> | **Raw file:** `<path>`

---

**What the wiki now knows**

<2-3 sentences. What can someone using this wiki now understand that they couldn't before this ingestion? Write this as domain knowledge, not as a file operation summary. Example: "The wiki now has a detailed account of the transformer architecture, including the multi-head attention mechanism and positional encoding. The current understanding of sequence modelling has been updated to reflect transformers as the dominant approach.">

---

**Pages produced**

| Page     | Status  | Notes                            |
| -------- | ------- | -------------------------------- |
| [[slug]] | created | Source summary                   |
| [[slug]] | created | Entity: <name>                   |
| [[slug]] | stub    | Entity: <name> - needs expansion |
| [[slug]] | updated | <one clause on what changed>     |

---

**Overview changes**

- Current Understanding: <updated with one clause on what changed | unchanged>
- Key Entities / Concepts: <list of [[slug]] added, or "none added">
- Open Questions: <list of questions added or removed, or "none changed">

---

**Needs attention**

List any deferred items or errors from steps 8–13 that require user action. If none, omit this section entirely.

| Item          | Reason                | Suggested action          |
| ------------- | --------------------- | ------------------------- |
| <description> | <why it was deferred> | <what the user should do> |

---

**Suggested next steps**

Based on what was produced, suggest 1-3 concrete follow-on actions. Choose only from the following:

- **Expand stub:** `[[slug]]` was created as a stub - consider ingesting a dedicated source for it.
- **Resolve contradiction:** `[[slug]]` contradicts `[[slug]]` - consider reviewing and updating one or both pages.
- **Resolve open question:** <question> was added to the overview - consider ingesting a source that addresses it.
- **Run lint pass:** <N> warnings were deferred in step 8. Run: `pyenv activate obsidian && wikiform lint` (or `wikiform lint` if pyenv is unavailable).
- **Run full reindex:** Search index incremental run failed in step 10 - run ` index --full`.


**Lint reminder rule:** Include "Run lint pass" in suggested next steps if and only if `INGESTS_SINCE_LINT` ≥ 5. Do not include it otherwise.