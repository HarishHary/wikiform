---
name: wiki-lint
description: Use when auditing a wiki for health issues - contradictions between pages, orphan pages, broken cross-references, stale claims, missing pages, or coverage gaps. Run after every 5-10 ingests.
---

# Wiki Lint

Audit the wiki. Produce a categorised report. Offer concrete fixes. Log the operation.

## Pre-condition

Before doing anything, run `which wikiform`. If not found, tell the user to run `pipx install wikiform` and stop.

Search for `SCHEMA.md` in this order:

1. Current directory
2. Each parent directory, up to 3 levels up
3. Stop at the first match

If not found, tell the user to run `wiki-init` first and stop.

Read `SCHEMA.md` to extract:
- `Path` — absolute wiki root path
- `Index Categories` — valid category names
- Required frontmatter fields — from the Page Frontmatter block

## Ingest count calculation

This skill uses the same procedure as `wiki-ingest` to compute **ingests since last lint**:

1. Read `wiki/log.md` from top to bottom.
2. Find the most recent entry whose operation is `lint`. Record its position.
3. Count all entries with operation `ingest` that appear **above** that position (i.e., after it chronologically).
4. If no `lint` entry exists, count = total number of `ingest` entries in the log.

Store as `INGESTS_SINCE_LINT`. Surface at the top of the lint report.

## Outstanding overview-review check

Before running any lint checks, scan `wiki/log.md` for `overview-review-needed` entries that appear after the most recent `lint` entry. If any exist, note them at the start of the session:

> "Outstanding: `overview-review-needed` was logged on `<date>` for `[[<slug>]]`. Consider running a dedicated overview rewrite pass after this lint session."

This is informational only — do not block lint on it.

## Workflow

### 1. Build the page inventory

**First, run `wikiform lint`:**

```bash
wikiform lint --vault-root <WIKI_ROOT> --output /tmp/vault-lint-result.json
```

Read the JSON output from `/tmp/vault-lint-result.json`. Extract and store:
- `summary.files_scanned` - total files scanned
- `issues` - the full list of findings, each with `type`, `check`, `file`, `message`

**Normalise check names** using this mapping before storing:

| wikiform lint name | Normalised name       | Notes                                |
| ------------------ | --------------------- | ------------------------------------ |
| `broken_link`      | `broken_link`         | E1                                   |
| `frontmatter`      | `missing_frontmatter` | E2                                   |
| `orphan`           | `orphan`              | W1                                   |
| `cross_refs`       | `missing_cross_ref`   | I3                                   |
| `naming`           | `naming`              | no wiki-lint equivalent - keep as-is |
| `empty`            | `empty`               | no wiki-lint equivalent - keep as-is |
| `stale_raw`        | `stale_raw`           | no wiki-lint equivalent - keep as-is |
| `tag_consistency`  | `tag_consistency`     | no wiki-lint equivalent - keep as-is |

Store all imported findings in the findings list. These are treated identically to findings produced by step 2's semantic checks - they flow into step 3's report and step 4's fix offers without distinction.

---

**Then, build the LLM inventory:**

Read the following files to support the semantic checks in step 2. The structural checks (broken links, missing frontmatter, orphans, naming, empty, stale_raw, tag_consistency, cross_refs) are already covered by `wikiform lint` - do not re-run them.

**Files to read:**

| File               | Purpose                                            |
| ------------------ | -------------------------------------------------- |
| `wiki/pages/*.md`  | Body text for contradiction and stale claim checks |
| `wiki/overview.md` | Open questions for coverage gap check              |
| `raw/` frontmatter | Source integrity for E3 - broken source references |

**Inventory map - build these three structures** (the full five-structure map from the original design is no longer needed - link graph and inbound links are handled by `wikiform lint`):

**A. Page registry** - one entry per file in `wiki/pages/`:

```json
slug → {
  path,
  title,
  tags,
  sources,         # list of raw file slugs from frontmatter
  updated,         # date string from frontmatter
  type,            # entity | concept | paper | article | etc.
  has_stub_tag,    # true if "stub" in tags
  body_text,       # full body content - needed for W2, W3
}
```

**B. Raw file registry** - one entry per file in `raw/`:

```json
raw-slug → {
  path,
  status,          # raw | ingested
  ingested_to,     # list of wiki page slugs
  added,           # date added
}
```

**C. Open questions list** - extracted from `wiki/overview.md`:

```yaml
["question text", ...]
```

Read the `## Open Questions` section. Each bullet is one question.

**Inventory health check:**

Before proceeding to step 2, verify:
- `wikiform lint` output was read successfully. If not, stop.
- `wiki/pages/` exists and is not empty. If empty, tell the user and stop.
- `wiki/overview.md` exists. If not, warn and skip I2 - coverage gaps.
- `raw/` exists. If not, warn and skip E3 - broken source references.

Log to console:

```yaml
wikiform lint: <N> findings imported
Pages: <N> | Raw files: <N> | Open questions: <N>
```

### 2. Run semantic checks

`wikiform lint` has already covered all structural checks - broken links, missing frontmatter, orphans, naming, empty files, stale raw, tag consistency, and cross-references. Step 2 runs only the checks that require reading and interpreting page content - checks the script cannot do.

Run all six checks. Do not skip any. Do not re-read files - use the inventory map from step 1.

Each finding has this structure:

```json
{
  severity:  error | warning | info,
  check:     <check name>,
  page:      <slug or "" if wiki-wide>,
  message:   <one sentence describing the issue>,
  fix:       <one sentence describing the concrete fix, or "manual review required">,
}
```

---

**E3 - Broken source references**

For each page in the page registry, iterate the `sources` list. For each raw file slug listed, check whether it exists in the raw file registry.

Flag if: raw file slug is not in the raw file registry.

```yaml
severity: error
check: broken_source
page: <slug>
message: "sources: [<raw-slug>] - no matching file in raw/"
fix: "Remove the stale source reference or restore the raw file"
```

Skip if `raw/` was absent at inventory time.

---

**W2 - Contradictions**

For each pair of pages that share at least one tag, compare `body_text` for conflicting claims about the same named entity.

Heuristic - flag if both of the following are true:
1. Both pages mention the same named entity - a proper noun or `[[slug]]` that appears in both `body_text` fields.
2. Both pages make a quantitative or categorical claim about that entity - a number, date, count, classification, or relationship - and the claims differ.

This check produces uncertain results. Every finding must be labelled as requiring manual review:

```yaml
severity: warning
check: contradiction
page: ""
message: "[[<page-a>]] and [[<page-b>]] make conflicting claims about <entity>: '<claim-a>' vs '<claim-b>'"
fix: "manual review required - verify which claim is correct and update the stale page"
```

Do not auto-fix contradictions. Do not present them as confirmed errors. If no contradictions are found with reasonable confidence, record zero findings - do not force findings.

Bound the cost: only compare pages that share at least one tag. Do not run exhaustive pairwise comparison across all pages.

---

**W3 - Stale claims**

For each page in the page registry:

1. Read `updated` from the page registry. If `updated` is absent or unparseable, skip this page.
2. Compute days since `updated`. If ≤ 90 days, skip this page.
3. Scan `body_text` for staleness markers: the strings `current`, `latest`, `recent`, `state-of-the-art`, and any 4-digit year that is 2 or more years before today.

Flag if: both conditions are true - page is older than 90 days AND contains at least one staleness marker.

```yaml
severity: warning
check: stale_claim
page: <slug>
message: "Last updated <date> (<N> days ago), contains staleness marker: '<marker>'"
fix: "Re-verify claims or add 'as of <updated date>' qualifier to each flagged sentence"
```

Exempt `type: entity` and `type: concept` pages from age-only flagging - only flag them if they contain explicit staleness markers.

---

**W4 - Stub pages not expanded**

For each page in the page registry where `has_stub_tag` is true:

1. Read `updated` from the page registry.
2. Compute days since `updated`.

Flag if: days since `updated` > 30.

```yaml
severity: warning
check: stale_stub
page: <slug>
message: "Stub page not expanded in <N> days"
fix: "Run wiki-ingest with a dedicated source for this entity, or promote to full page manually"
```

---

**I1 - Missing concept pages**

For each slug that appears in any page's `body_text` as a `[[slug]]` reference but is not in the page registry:

Compute the threshold:

```text
threshold = max(3, round(total_pages * 0.05))
```

where `total_pages` is the count of entries in the page registry.

Count how many distinct pages contain `[[slug]]`. Flag if count ≥ threshold.

```yaml
severity: info
check: missing_concept_page
page: ""
message: "[[<slug>]] referenced <N> times but no page exists"
fix: "Run wiki-ingest with a dedicated source, or create a stub with wiki-ingest"
```

Note: `wikiform lint`'s `missing_cross_ref` check flags pages that share tags but don't link to each other. This check flags slugs that are referenced but have no page at all. There is no overlap.

---

**I2 - Coverage gaps**

For each question in the open questions list:

1. Search the page registry for pages that address the question - check whether any page title or tag matches key terms in the question.
2. Flag if no existing page appears to address it.

Extract key terms by taking the 2-3 most specific nouns from the question, excluding stop words.

```yaml
severity: info
check: coverage_gap
page: ""
message: "Open question not covered by any wiki page: '<question>'"
fix: "Search for '<key terms>' or ingest a source that addresses this question"
```

Skip if the open questions list is empty.

---

**After all checks complete:**

Combine step 2 findings with the imported `wikiform lint` findings from step 1 into a single findings list. Count by severity across both sources:

```yaml
Checks complete: <N> errors, <N> warnings, <N> info
  - <N> from wikiform lint, <N> from semantic checks
```

### 3. Write the lint report

Write the report to `outputs/reports/lint-<today>.md`. Do not write it to `wiki/pages/` - lint reports are maintenance artifacts, not knowledge pages, and must not appear in the page inventory or search index.

Do not ask permission before writing. Always write the report regardless of finding count.

---

**Locate the previous lint report:**

Before writing, check `outputs/reports/` for any existing `lint-*.md` files. If found, identify the most recent one by date. Record its filename for the "Previous report" reference. If none found, record `null`.

**Report template:**

Only include sections that have at least one finding. If a severity level has no findings, omit its section entirely. If all checks are clean, write the clean state instead of any check sections.

```markdown
---
title: Lint Report <today>
tags: [lint]
updated: <today>
generated_by: wiki-lint
---

# Lint Report - <today>

**Previous report:** `outputs/reports/lint-<previous-date>.md` | **Wiki pages:** <N> | **Raw files:** <N>

## Summary

| Severity   | Count | Source              |
| ---------- | ----- | ------------------- |
| 🔴 Errors   | N     | <N> script, <N> LLM |
| 🟡 Warnings | N     | <N> script, <N> LLM |
| 🔵 Info     | N     | <N> script, <N> LLM |

<if all counts are zero, write instead:>
> ✅ No issues found. Wiki is healthy.
<then omit all check sections below>

---

<for each check that has findings, in this order:
E1 broken_link, E2 missing_frontmatter, E3 broken_source,
W1 orphan, W2 contradiction, W3 stale_claim, W4 stale_stub,
naming, empty, stale_raw, tag_consistency,
I1 missing_concept_page, I2 coverage_gap, I3 missing_cross_ref>

## 🔴 <Check Name>

<one entry per finding:>
- **[[<page>]]** - <message>
  → Fix: <fix>

<for wiki-wide findings where page is empty, omit the page link:>
- <message>
  → Fix: <fix>

<repeat for each severity, each check>

---

## Trend

<if previous report exists:>
- Errors: <previous N> → <current N> (<+N / -N / unchanged>)
- Warnings: <previous N> → <current N>
- Info: <previous N> → <current N>

<if no previous report:>
- First lint run - no trend data available.
```

**Rendering rules:**
- Sort findings within each check section alphabetically by page slug.
- Do not truncate findings - every finding must appear in the report.
- Trend counts are read from the previous report's `## Summary` table - do not re-run checks.

**After writing the report:**

Do not add the report to `wiki/index.md`. Lint reports are not wiki content and should not appear in the category index. They are discoverable via `outputs/reports/` directly.

Update `wiki/log.md` - but do not do it here. This is handled in step 5.

### 4. Offer concrete fixes

Present fix offers in priority order: errors first, then warnings, then info. Only present offers for checks that produced findings. Do not present offers for checks with zero findings.

Present one offer at a time. Wait for the user's response before presenting the next. Do not batch all offers into a single message.

**Fix offer format:**

For each offer, present:
1. The check name and finding count
2. A one-sentence description of what will be changed
3. The exact diff for each affected file in before/after block format:

```yaml
File: wiki/pages/<slug>.md

BEFORE:
<exact current content of the affected line(s)>

AFTER:
<exact proposed content>
```

Then ask: **"Apply this fix? (yes / no / skip all remaining fixes)"**

- **yes** - apply the fix, log it, present the next offer
- **no** - skip this fix, present the next offer
- **skip all** - stop presenting offers, proceed to step 5

Do not apply any fix without explicit confirmation. Do not batch multiple file changes into a single confirmation - each file change is confirmed individually.

**After applying a fix:**

1. Update the affected file.
2. Update the page registry in memory to reflect the change.
3. Note the fix in a running list of applied fixes - used in step 5's log entry.
4. Do not re-run checks after each fix - the report was already written in step 3.

---

**Fix offers by check, in presentation order:**

**E1 - Broken links**
> "Found <N> broken wikilinks across <N> pages. I can remove each broken `[[slug]]` reference. I'll show each change before writing."

Show one diff per page. If a page has multiple broken links, show all in one diff block for that page, confirmed together.

**E2 - Missing frontmatter**
> "Found <N> pages with missing required frontmatter fields. I can add placeholder values for each missing field."

Placeholder values:

| Field     | Placeholder                                           |
| --------- | ----------------------------------------------------- |
| `title`   | `<slug with hyphens replaced by spaces, title-cased>` |
| `tags`    | `[]`                                                  |
| `sources` | `[]`                                                  |
| `updated` | `<today>`                                             |
| `type`    | `other`                                               |

Show one diff per page.

**E3 - Broken source references**
> "Found <N> pages referencing raw files that don't exist. I can remove the stale source slugs from each page's `sources` field."

Show one diff per page.

**W1 - Orphan pages**
> "Found <N> pages with no inbound links. For each one, I'll suggest the most relevant page to add a link from, based on shared tags."

For each orphan, identify the page in the page registry that shares the most tags with it. Show a diff adding `[[orphan-slug]]` to that page's `## Connections` section. If no tag-sharing page exists, note: "No obvious link target found - manual review required."

**W2 - Contradictions**
> "Found <N> possible contradictions. These require manual review - I cannot auto-fix them. I'll show each one and ask which claim to keep."

For each contradiction finding, show:

```yaml
Entity: <entity name>

[[<page-a>]] says:
"<claim-a>"

[[<page-b>]] says:
"<claim-b>"
```

Ask: **"Which is correct: (a) / (b) / neither - I'll update manually / skip"**

- **a** or **b** - update the losing page to remove or qualify the conflicting claim. Show diff before applying.
- **neither** - add a `## Open Questions` entry to `wiki/overview.md` noting the unresolved contradiction.
- **skip** - move to next contradiction.

**W3 - Stale claims**
> "Found <N> pages with potentially stale claims. I can add an 'as of <updated date>' qualifier to each flagged sentence."

Show one diff per page. The qualifier is appended inline: `<original sentence> (as of <updated date>)`. Do not rewrite the sentence - append only.

**W4 - Stub pages**
> "Found <N> stub pages not expanded in 30+ days. I can't expand them automatically - here's the list so you can decide which to ingest next."

No diff shown - present the list of stub slugs with their age in days. Ask: **"Would you like to run wiki-ingest on any of these now?"** If yes, hand off to wiki-ingest for the selected slug.

**naming, empty, stale_raw, tag_consistency** (imported from wikiform lint, no wiki-lint equivalent)
> "Found <N> <check name> issues flagged by wikiform lint. These require manual attention - no auto-fix available."

Present the list of findings. No diff shown. No confirmation required - these are informational.

**I1 - Missing concept pages**
> "Found <N> frequently referenced slugs with no dedicated page. I can create stub pages for each."

For each slug, show the stub template from wiki-ingest step 7 Rule C, pre-filled with the slug and a placeholder definition. Confirm before writing each stub.

**I2 - Coverage gaps**
> "Found <N> open questions not addressed by any wiki page. Here are suggested search queries for each."

No diff shown - present each question with a suggested search query extracted from its key terms. Ask: **"Would you like to run wiki-ingest on any of these now?"** If yes, hand off to wiki-ingest.

**I3 - Missing cross-references**
> "Found <N> page pairs that discuss the same entity but don't link to each other. I can add the missing links."

Show one diff per page pair - two diffs per finding, one for each page. Confirm both together as a single unit since they are bidirectional.

### 5. Append to `wiki/log.md`

Always append. Do not ask permission. New entries go at the top of the log, below the header.

```markdown
## [<today>] lint | <N errors>, <N warnings>, <N info>

**Report:** `outputs/reports/lint-<today>.md`
**Pages scanned:** <N> | **Raw files scanned:** <N>
**Health:** <CLEAN | ERRORS | WARNINGS_ONLY>

### Findings
| Check                | Severity  | Count | Source |
| -------------------- | --------- | ----- | ------ |
| broken_link          | 🔴 error   | N     | script |
| missing_frontmatter  | 🔴 error   | N     | script |
| broken_source        | 🔴 error   | N     | LLM    |
| orphan               | 🟡 warning | N     | script |
| contradiction        | 🟡 warning | N     | LLM    |
| stale_claim          | 🟡 warning | N     | LLM    |
| stale_stub           | 🟡 warning | N     | LLM    |
| naming               | 🟡 warning | N     | script |
| empty                | 🟡 warning | N     | script |
| stale_raw            | 🔵 info    | N     | script |
| tag_consistency      | 🔵 info    | N     | script |
| missing_concept_page | 🔵 info    | N     | LLM    |
| coverage_gap         | 🔵 info    | N     | LLM    |
| missing_cross_ref    | 🔵 info    | N     | script |

### Fixes applied
<for each fix applied in step 4, one line:>
- <check name> | [[<slug>]] | <one clause on what changed>

<if no fixes were applied:>
- none

### Fixes declined
<for each fix offered but declined by the user:>
- <check name> | [[<slug>]] | declined

<if no fixes were declined:>
- none

### Requires manual review
<for each finding flagged as "manual review required" in step 4:>
- <check name> | <one clause on what needs attention>

<if none:>
- none

### Trend
- Errors: <previous N> → <current N> (<+N / -N / unchanged>)
- Warnings: <previous N> → <current N>
- Info: <previous N> → <current N>

<if no previous lint run:>
- First lint run - no trend data available.
```

---

**Health field rules:**

| Value           | Condition                                          |
| --------------- | -------------------------------------------------- |
| `CLEAN`         | Zero findings across all checks                    |
| `ERRORS`        | One or more error-severity findings                |
| `WARNINGS_ONLY` | Zero errors, one or more warnings or info findings |

---

**Omission rules:**

- Omit rows from the Findings table where count is 0 - do not write `broken_link | 🔴 error | 0`.
- If Findings table would be entirely empty (CLEAN), replace it with: `All checks passed.`
- Fixes applied, Fixes declined, and Requires manual review sections are always present - write "none" if empty. Do not omit these sections even on a clean run.