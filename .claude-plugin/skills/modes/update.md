---
name: wiki-update
description: Use when revising existing wiki pages because knowledge has changed, a new piece of information updates or contradicts existing content, or the user wants to directly edit wiki content with LLM assistance.
---

# Wiki Update

Revise existing wiki pages. Always show diffs before writing. Always log. Always cite the source of new information.

## Pre-condition

Search for `SCHEMA.md` in this order:
1. Current directory
2. Each parent directory, up to 3 levels up
3. `~/wikis/`

Stop at the first match. If not found, tell the user to run `wiki-init` first and stop.

Read `SCHEMA.md` to extract:
- `Path` - absolute wiki root path
- `Index Categories` - valid category names
- `Tag Rules` - valid primary tags and constraints
- `Log Entry Format` - format for appending to `wiki/log.md`

## Workflow

### 1. Identify what to update

The user may provide one of three triggers. Route to the appropriate intake path:

**Trigger A - specific page names:**
The user names one or more pages to update directly. Proceed to step 2 with those pages.

**Trigger B - new information:**
The user provides a fact, URL, file, or description of changed knowledge. Before touching any pages:

1. Read `wiki/index.md` in full.
2. Score each page for relevance using the same 0/1/2 scoring from `wiki-query`:
   - 2: title or summary directly names an entity or concept in the new information
   - 1: title or summary shares a significant term
   - 0: no apparent connection
3. Read all pages scoring ≥ 1.
4. Proceed to step 2 with the affected pages identified.
**Trigger C - lint report:**
The user provides a lint report from `wiki-lint`. This skill handles only content-level recommendations - items that require reading and rewriting page body text. Structural fixes (broken links, missing frontmatter, orphans, naming) belong to `wiki-lint`'s own fix flow.

Filter the lint report to these checks only:
- W2 contradiction
- W3 stale claim
- W4 stale stub (expand only - do not just remove the stub tag)
- I1 missing concept page (create the page, not just a stub)

Work through filtered items in priority order: W2 first, then W3, then W4, then I1. Present each item to the user before acting. Do not skip items silently - if an item is out of scope, say so explicitly.

### 2. Assess the source

Before proposing any edits, assess the credibility of the new information relative to what the wiki already contains.

For each affected page, check whether it already has a sourced claim on the same topic:
- Read the page's `sources:` frontmatter field.
- Read the `## Evidence` section if present.
Then classify the update as one of:

| Class           | Condition                                                              | Action                                                                |
| --------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `additive`      | New information covers something the wiki does not address             | Proceed to step 3                                                     |
| `corroborating` | New information agrees with existing sourced claims                    | Note agreement; proceed to step 3                                     |
| `superseding`   | New information is more recent or higher-quality than existing sources | Proceed to step 3; flag old source for review                         |
| `contradicting` | New information conflicts with an existing sourced claim               | Surface the conflict explicitly before proposing any edit - see below |

**Contradiction handling:**

If the update class is `contradicting`, do not proceed directly to a diff. First present:

```text
Conflict detected on [[<slug>]]:

Wiki currently states: "<existing claim>" (source: <existing source>)
New information states: "<new claim>" (source: <new source>)

Options:
(1) Accept new information - update the page and flag the old source
(2) Keep existing - discard the new information for this page
(3) Record both - add the new claim as a contested alternative with both sources cited
(4) Defer - add to wiki/overview.md Open Questions and skip this page for now
```

Wait for the user's choice before proceeding. Do not default to accepting the new information.

### 3. Propose edits as structured diffs

For each page to update, read the current content in full. Then propose changes using this format for every edit:

```text
Page: wiki/pages/<slug>.md

--- current (line <N>)
<exact current text, including surrounding context of 1-2 lines>

+++ proposed
<replacement text>

Reason: <one sentence on why this change is warranted>
Source: <URL, file path, or description - required; do not omit>
```

Rules for the diff format:
- Always include the line number of the change (`line <N>`).
- Always include 1-2 lines of surrounding context so the location is unambiguous.
- For multi-line replacements, show the full block in both current and proposed sections.
- For frontmatter changes, show the full frontmatter block in both sections - do not show only the changed field.
- If a page requires more than 5 separate edits, ask the user whether to proceed page-by-page or rewrite the page wholesale.

**Frontmatter validation:**

If the proposed edit changes any frontmatter field, validate the new values against `SCHEMA.md` before showing the diff:
- `tags[0]` must be one of the Index Categories.
- `type` must be one of: `paper | article | code | repo | image | dataset | entity | concept | analysis | other`.
- `updated` must be today's date in `YYYY-MM-DD` format.
- `sources` must remain a YAML array; slugs must exist in `raw/` or be flagged as unverifiable.

If validation fails, report the specific violation and do not show the diff until it is resolved.

Ask for confirmation before writing each page. Do not batch-apply changes. The user may accept some edits and reject others within the same page.

### 4. Impact sweep

After identifying the primary pages to update (step 2) and before writing anything, run a full impact sweep across all of `wiki/pages/`. This replaces the separate downstream check and contradiction sweep from earlier versions - they are the same operation.

For each page being updated, collect:

**A - wikilink references:** pages that contain `[[<slug>]]` linking to the updated page.

**B - claim overlap:** pages that assert something about the same named entity or concept being changed, regardless of whether they link to the updated page. Identify these by scanning for the entity name as plain text in other pages' body content.

For each page found in A or B:

1. Read it in full.
2. Determine whether the proposed update changes anything that page asserts.
3. Classify the effect:

| Effect                           | Action                                                                         |
| -------------------------------- | ------------------------------------------------------------------------------ |
| No effect                        | Note as checked; no action needed                                              |
| Needs update                     | Add to the update queue; process with the same step 3 diff flow                |
| Potential inconsistency, unclear | Flag to the user: "[[other-page]] may be affected - manual review recommended" |

Present the impact sweep results before writing any page:

```text
Impact sweep: <N> pages checked
  <N> need updating - will be added to this session
  <N> flagged for manual review
  <N> unaffected
```

If the impact sweep would add more than 10 additional pages to the session, ask the user whether to continue or defer the downstream updates to a separate session.

### 5. Write confirmed edits

Apply edits in this order:

1. Primary pages (from step 2), in the order the user confirmed them.
2. Downstream pages (from step 4), in the order they were added to the queue.

For each page written:

- Apply the confirmed diff.
- Update `updated:` in frontmatter to today's date.
- Add the new source slug or URL to `sources:` in frontmatter if it is not already present.

Do not write any page that has not received explicit confirmation in step 3.

### 6. Update index files

After all page writes are complete, update the three index files for any page whose title, primary tag, or one-line summary changed.

**`wiki/index.md`:** Update the one-line entry under the page's category. If the primary tag changed, move the entry to the new category.

**`wiki/tag-index.md`:** If tags were added or removed, add or remove the page's entry under the affected tag headings. If a tag heading no longer has any entries, remove the heading.

**`wiki/master-index.md`:** If the page title changed, move the entry to the correct letter heading. Update the one-line summary if it changed.

Run `wikiform index` if available to perform these updates automatically. If unavailable, apply manually. Log script failures as `lint-deferred` per the `wiki-ingest` convention.

### 7. Update `wiki/overview.md`

Re-read `wiki/overview.md` in full. Apply the same four update rules as `wiki-ingest` step 11:

**Rule 1 - Current Understanding:** Update if the change revises how a core aspect of the domain should be understood, contradicts or qualifies something already stated, or fills a previously noted gap. Rewrite affected sentences - do not append. If unchanged, do not touch.

**Rule 2 - Key Entities / Concepts:** Add an entry if an updated page is now load-bearing for understanding the domain and is not yet listed. Remove an entry if the page was deprecated or substantially narrowed. Do not add stub pages.

**Rule 3 - Open Questions:** Add a question if the update introduces a contradiction that was not resolved, or reveals an assumption that is now in doubt. Remove a question if the update resolves it.

**Rule 4 - Staleness check:** If after updates the overview has more than 10 Key Entities or more than 7 Open Questions, log `overview-review-needed` and note it to the user. Do not perform the rewrite during this session.

If none of the four rules trigger, do not modify `wiki/overview.md`. State explicitly: "Overview unchanged - no rules triggered."

Propose all overview changes using the same step 3 diff format. Confirm before writing.

### 8. Append to `wiki/log.md`

Always append. Do not ask permission. New entries go at the top of the log, below the header.

```yaml
## [<today>] update | <comma-separated list of updated page slugs>

**Source:** <URL, file path, or description of the new information>
**Update class:** <additive | corroborating | superseding | contradicting>

### Pages updated
- [[slug]] - <one clause on what changed and why>
- [[slug]] - <one clause on what changed and why>

### Impact sweep
- Pages checked: <N>
- Pages updated downstream: <N>
- Pages flagged for manual review: <N> (list slugs if any)
- Pages unaffected: <N>

### Edits declined
- [[slug]] - <reason declined>
<if none: "none">

### Conflicts encountered
- [[slug]] - <how the conflict was resolved: accepted / kept / both / deferred>
<if none: "none">

### Overview changes
- Current Understanding: <updated with one clause | unchanged>
- Key Entities / Concepts: <N added, N removed | unchanged>
- Open Questions: <N added, N removed | unchanged>

### Deferred
- <item> - <reason>
<if none: "none">
```

## Common mistakes

- **Accepting new information without checking for conflicts** - The wiki may have a well-sourced claim that contradicts the update. Step 2 must run before any diff is proposed.
- **Updating without citing the source** - Every diff must include a Source line. An edit without a source is unauditable.
- **Grep-only impact sweep** - Pages can assert the same claim without linking to the updated page. Step 4 checks both wikilink references and plain-text entity mentions.
- **Skipping tag and master index** - Step 6 covers all three index files. Updating only `wiki/index.md` leaves `wiki/tag-index.md` and `wiki/master-index.md` stale.
- **Vague overview trigger** - Step 7 uses four explicit rules. If none trigger, the overview is not touched. Do not update it speculatively.
- **Batch-writing without confirmation** - Show each diff individually. The user may accept some changes and reject others within the same page.
- **Removing the stub tag without expanding the page** - W4 items from a lint report require actual expansion, not just tag removal.
- **Inventing frontmatter values** - All tags and types must be valid per `SCHEMA.md`. Validate before showing any diff that touches frontmatter.
