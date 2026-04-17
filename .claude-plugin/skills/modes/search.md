---
name: wiki-query
description: Use when asking a question against a personal wiki built with wiki-init and wiki-ingest. Do not answer from general knowledge - always read the wiki pages first.
---

# Wiki Query

Ask a question. Read the wiki. Synthesize with citations. Offer to file the answer back.

## Pre-condition

Before doing anything, run `which wikiform`. If not found, tell the user to run `pipx install wikiform` and stop.

Search for `SCHEMA.md` in this order:

1. Current directory
2. Each parent directory, up to 3 levels up
3. Stop at the first match

If not found, tell the user to run `wiki-init` first and stop.

Read `SCHEMA.md` to extract:
- `Path` - absolute wiki root path
- `Index Categories` - valid category names
- `Cross-References` - wikilink convention (`[[slug]]`)
- `Log Entry Format` - format for appending to `wiki/log.md`

**Empty wiki check:** After reading `SCHEMA.md`, verify that `wiki/index.md` exists and contains at least one entry. If the index is empty or the file is missing, tell the user:

> "The wiki has no pages yet. Run `wiki-ingest` to add sources before querying."
Then stop.

## Workflow

### 1. Read `wiki/index.md` first

Scan the full index to identify which pages are likely relevant. Do NOT answer from general knowledge - the wiki is the source of truth here, even if you think you know the answer.

Read `wiki/index.md` in full. For each listed page, assign a relevance score:

| Score | Meaning                                                              |
| ----- | -------------------------------------------------------------------- |
| 2     | Title or summary directly names an entity or concept in the question |
| 1     | Title or summary shares a significant term with the question         |
| 0     | No apparent connection                                               |

Collect all pages with score ≥ 1. If no pages score ≥ 1, widen to any page whose category matches the question's domain. If still none, tell the user:
> "No pages in the wiki appear relevant to this question. The wiki may not yet cover this topic."

Then stop - do not answer from general knowledge.

### 2. Read relevant pages

Read all pages with score 2 first, then score 1 pages. For each page read, apply the link traversal rule below.

**Link traversal rule:**

For each `[[slug]]` link found in a page's body:
- Check whether that slug is already in your read list.
- If not: score it against the question using the same 0/1/2 criteria.
- If score ≥ 1: add it to the read list.
- If score 0: do not follow it.
Traversal depth is exactly one level. Do not follow links found in pages that were themselves added via traversal - only follow links found in the directly relevant pages from step 1.

**Read limit:** If the read list exceeds 20 pages, stop adding and note: "Query scope is large - results may be incomplete. Consider narrowing the question or running `wiki-lint` to check index coverage."

### 3. Synthesize the answer

Do not begin writing until all pages in the read list are read.

Write a response that:

- Is grounded exclusively in the wiki pages you read - not general knowledge
- Cites inline using `[[slug]]` for every factual claim
- Notes agreements between pages explicitly when two or more pages support the same claim
- Notes disagreements explicitly when pages conflict: "[[page-a]] states X; [[page-b]] states Y - see open question below"
- Flags every gap using one of these forms:
  - "The wiki has no page on X." - when a concept is referenced but has no page
  - "[[page]] does not cover Y." - when a relevant page exists but is silent on a specific aspect
- Lists suggested follow-up actions (ingest targets or open questions) at the end, not inline

Format by question type:

| Question type           | Format                                                                                         |
| ----------------------- | ---------------------------------------------------------------------------------------------- |
| Factual                 | Prose with inline `[[slug]]` citations                                                         |
| Comparison              | Table with one row per dimension; cite sources per cell                                        |
| How-it-works            | Numbered steps; cite the page that establishes each step                                       |
| What-do-we-know-about X | Structured summary: what is known, what is contested, what is unknown; end with open questions |

**Confidence marker:** End the synthesis with one line:

```text
Confidence: [HIGH | MEDIUM | LOW] - based on <N> pages; <N> gaps flagged.
```

| Level  | Condition                                                |
| ------ | -------------------------------------------------------- |
| HIGH   | ≥ 2 directly relevant pages, 0 gaps flagged              |
| MEDIUM | 1 directly relevant page, or ≥ 1 gap flagged             |
| LOW    | All pages score 1 (no direct match), or ≥ 3 gaps flagged |

### 4. Act on gaps

For each gap flagged in step 3, offer a concrete action - do not leave gaps as passive observations.

Present each gap in order. Wait for the user's response before presenting the next.

**Gap offer format:**

> "Gap: The wiki has no page on `<topic>`.
> Options: (1) create a stub now, (2) ingest a source - suggest query: `<suggested search terms>`, (3) skip"

- **Option 1 - create stub:** Create `wiki/pages/<slug>.md` using the stub template from `wiki-ingest` Rule C. Add to `wiki/index.md` under the most relevant category. Log as `ingest | stub created: [[slug]]`.
- **Option 2 - ingest:** Hand off to `wiki-ingest` with the suggested source or search terms.
- **Option 3 - skip:** Note the gap in the log entry only.

If there are no gaps, skip this step entirely.

### 5. Offer to save the answer

After step 4 (or after step 3 if no gaps), say:

> "Worth saving as `wiki/pages/<suggested-slug>.md`?"

**Slug generation:** Apply the same rules as `wiki-ingest` step 5 - kebab-case, max 6 words, collision check against existing pages.

If yes:

Write `wiki/pages/<suggested-slug>.md` with complete, lint-compliant frontmatter:

```yaml
---
title: <question restated as a noun phrase>
tags: [<primary category from SCHEMA.md Index Categories>, query, analysis]
sources: [<all slugs cited in the synthesis>]
type: analysis
updated: <today YYYY-MM-DD>
---
```

**Primary category rule:** The first tag must be one of the Index Categories defined in `SCHEMA.md`. Choose the category that best fits the question's domain. If no category fits, use the first listed category and note the mismatch to the user.

Page body: the full synthesis from step 3, verbatim. Do not summarise or rewrite.

Add entry to `wiki/index.md` under the chosen primary category:

```markdown
- [[slug]] - <one-line summary of the question answered>
```

Append to `wiki/log.md` using the format defined in `SCHEMA.md`:

```markdown
## [<today>] query | <question summary>
Filed as: [[<slug>]]
Sources consulted: <N> pages
Gaps: <N flagged>, <N resolved>, <N skipped>
```

If no, append to `wiki/log.md`:

```markdown
## [<today>] query | <question summary>
Not filed.
Sources consulted: <N> pages
Gaps: <N flagged>, <N resolved>, <N skipped>
```

## Common mistakes

- **Answering from memory** - The wiki is the source of truth. If the wiki contradicts what you think you know, surface the contradiction - do not silently correct it.
- **Skipping the save offer** - Good query answers compound the wiki's value. Always offer, even for short answers.
- **No citations** - Every factual claim must trace back to a `[[slug]]`. Uncited claims are indistinguishable from hallucination.
- **Passive gap handling** - Flagging a gap without offering an action is incomplete. Every gap gets an offer in step 4.
- **Incomplete frontmatter on save** - The saved page must pass `wiki-lint` E2. All five required fields (`title`, `tags`, `sources`, `type`, `updated`) must be present. The first tag must be a valid Index Category.
- **Inventing a category on save** - Only use Index Categories defined in `SCHEMA.md`. Do not create new categories.
