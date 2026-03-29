---
name: job-search
description: Automated job search across LinkedIn, ATS APIs, and web boards with configurable match scoring. Searches 7+ job board APIs, optional LinkedIn via Playwright, and scores opportunities against your profile.
---

# Job Search Skill

## When to Use
User says: "job search", "search jobs", "find opportunities", "buscar trabajo", "/job-search"

## Invocation
```
/job-search           # Full run: Python script + LinkedIn (if enabled) + scoring
/job-search apis      # API sources only (skip LinkedIn)
/job-search linkedin  # LinkedIn only (skip Python script)
```

---

## IMPORTANT: Path References

Throughout this skill, `{SKILL_DIR}` refers to the directory containing this SKILL.md file.
When Claude Code loads a skill via plugin, the skill directory path is available from the plugin
runtime. Use it to construct the path to the Python script:

```
{SKILL_DIR}/scripts/fetch_opportunities.py
```

The user's working directory (`$CWD`) is where `job-search.yaml` and the output file live.
These are two separate paths — never confuse them.

---

## Phase 0 — Setup

This phase runs inline (no subagents). Complete all steps before launching Phase 1.

### Step 0.1 — Read Config

Look for `job-search.yaml` in the current working directory (`$CWD`).

**If the file exists:**
- Read it in full
- Validate that the following required fields are present:
  - `profile.title` — non-empty string
  - `keywords` — at least one language key with at least one non-empty entry
- If validation fails, report the missing fields and stop. Do not proceed to Phase 1.
- Continue to Step 0.2.

**If the file does NOT exist:**

Inform the user:

> "No `job-search.yaml` found in the current directory. How would you like to set up?
>
> A) I'll create it manually — copy the example template to `job-search.yaml` and fill it in
> B) Walk me through a setup wizard
> C) Parse my resume — provide a path to your resume file (PDF, YAML, or MD)"

Execute the chosen option:

#### Option A — Manual
- Copy `{SKILL_DIR}/../../../templates/config.example.yaml` to `$CWD/job-search.yaml`
- Tell the user: "Template copied to `job-search.yaml`. Fill in your profile and keywords, then re-run `/job-search`."
- Stop. Do not proceed to Phase 1.

#### Option B — Wizard
Ask these questions **one at a time** (wait for each answer before asking the next):

1. "What role or job title are you looking for? (e.g., Engineering Manager, Backend Developer, Product Designer)"
2. "What are your key skills or technologies? (comma-separated, e.g., Go, TypeScript, AWS, Kubernetes)"
3. "What is your seniority level? (junior / mid / senior / lead / executive)"
4. "What is your preferred location or region? (e.g., Latin America, Europe, Remote-US)"
5. "Remote only? (yes / no)"
6. "What language should results be in? (en / es / pt / fr / de — default: en)"
7. "Do you have a resume file I can read for deeper context? (provide path or press Enter to skip)"

Generate `job-search.yaml` from the answers (see Config Schema in Section 4 of the spec for structure).
- For `keywords`, generate sensible search terms from the role name and seniority (3–5 EN terms minimum).
- Use `output.file: "opportunities.md"` as the default output file name.
- Write the generated config to `$CWD/job-search.yaml`.
- Then continue to the **Scoring Proposal** step below.

#### Option C — Resume Parser
- Ask: "Provide the path to your resume (PDF, YAML, or MD):"
- Read the file using the Read tool (the Read tool natively supports PDF, YAML, and MD).
- Extract from the content:
  - Target role / job title
  - Skills and technologies
  - Seniority level (infer if not explicit)
  - Location preferences
- Generate `job-search.yaml` from the extracted data using the same structure as Option B.
- Write the config to `$CWD/job-search.yaml`.
- Report what was extracted: "Extracted profile: [title], skills: [skills], seniority: [seniority], location: [location]"
- Continue to the **Scoring Proposal** step below.

#### Scoring Proposal (after Options B and C only)
After the profile is established, analyze it and propose scoring dimensions:

> "Based on your profile as a [title], I recommend scoring on:
> - [Dimension 1] (25%)
> - [Dimension 2] (25%)
> - [Dimension 3] (25%)
> - [Dimension 4] (25%)
>
> Adjust the weights or names, or type 'accept' to use these."

Use contextually appropriate dimension names. For engineering roles, sensible defaults are
"Domain fit", "Tech stack fit", "Leadership fit", "Company stage fit". For other roles, adapt
accordingly (e.g., a designer might use "Product design fit", "Tool stack fit", "Industry fit",
"Team structure fit").

Wait for the user to confirm or adjust. Write the final dimensions and weights into the
`scoring` section of `$CWD/job-search.yaml`.

### Step 0.2 — Check Playwright MCP (LinkedIn)

Only run this step if `sources.linkedin.enabled` is `true` in the config.

Attempt to detect Playwright MCP by calling `browser_navigate` with a no-op URL such as
`about:blank`. If the call succeeds, Playwright is available — continue.

If the call fails (tool not found or error):
- Run: `claude mcp add playwright -- npx @anthropic-ai/mcp-playwright`
- Inform the user: "Installed Playwright MCP for LinkedIn search."
- If the install command itself fails:
  - Warn: "Could not install Playwright MCP. LinkedIn search will be skipped for this run."
  - Treat `linkedin.enabled` as `false` for the rest of this run (do not modify the config file).

### Step 0.3 — Load Existing Output for Dedup

Read the output file specified in `output.file` (relative to `$CWD`).

If the file does not exist: `known_urls = []`, continue.

If the file exists: parse every URL that appears in the file. Collect them into `known_urls`
(list of strings, lowercased, trailing slashes stripped). These are used in Phase 2 dedup.

Also extract the current WATCHLIST section (if present) so it can be updated in Phase 4.

---

## Phase 1 — Discovery

Launch **both** tasks in a **single parallel response**. Do not wait for one to finish before
starting the other.

Skip 1a if invocation mode is `linkedin`. Skip 1b if invocation mode is `apis` or if
`sources.linkedin.enabled` is false (including if disabled in Step 0.2).

### 1a. Python Script (API Sources)

Run the following Bash command:

```bash
python3 {SKILL_DIR}/scripts/fetch_opportunities.py \
  --config "$CWD/job-search.yaml" \
  --output /tmp/discoveries.json
```

The script reads all source flags, keywords, and watchlist from `job-search.yaml`. It writes:
- `/tmp/discoveries.json` — JSON array of `{title, company, location, url, posted_date, source}`
- `/tmp/discoveries_meta.json` — object with keys:
  - `stats`: `{total_found: N, sources: {source_name: {ok: bool, count: N, slugs_failed: []}}}`
  - `discovered_slugs`: array of `{company, ats, slug}` — new ATS slugs found via URL pattern matching

If the script exits with a non-zero code:
- Print the stderr output as a warning
- Set `api_results = []` and continue — do not abort the run

If the script exits successfully but `/tmp/discoveries.json` is missing or empty:
- Set `api_results = []` and continue

### 1b. LinkedIn Subagent (if enabled)

Spawn a subagent using the agent spec at `{SKILL_DIR}/agents/linkedin-searcher.md`.

Pass the following parameters in the subagent prompt (append them after the spec content):

```
## Parameters for this run

keywords: {all entries from config.keywords, all languages, flattened into a single list}
cookie: {config.sources.linkedin.cookie}
location: {config.profile.location}
output_file: /tmp/linkedin_discoveries.json
```

The subagent writes its results to `/tmp/linkedin_discoveries.json` as a JSON array of
`{title, company, location, url, posted_date, source: "linkedin"}`.

**Cookie expired / CAPTCHA handling:**

After the subagent returns, check `/tmp/linkedin_discoveries.json`:
- If the file contains `{"error": "cookie_expired", ...}` or `{"error": "captcha_detected", ...}`:
  - For `cookie_expired`: ask the user: "LinkedIn cookie has expired. Paste a new `li_at` value or type 'skip'."
    - If new cookie provided: update `config.sources.linkedin.cookie` in `$CWD/job-search.yaml`,
      re-launch the LinkedIn subagent with the new cookie, wait for result.
    - If 'skip': set `linkedin_results = []`, warn "LinkedIn skipped — cookie expired."
  - For `captcha_detected`: warn "LinkedIn CAPTCHA detected. Partial results may be included."
    Set `linkedin_results` to whatever partial results were returned.
- Otherwise: read the array as `linkedin_results`.

---

## Phase 2 — Merge & Dedup

Run inline after both Phase 1 tasks complete.

### Step 2.1 — Read Results
- Read `/tmp/discoveries.json` → `api_results` (JSON array; empty array if file missing)
- Read `/tmp/discoveries_meta.json` → `meta` (object; null if file missing)
- Read `/tmp/linkedin_discoveries.json` → `linkedin_results` (JSON array; empty array if file missing or LinkedIn was not run)

### Step 2.2 — Combine
Concatenate `api_results` and `linkedin_results` into `all_results`.

### Step 2.3 — Cross-Source Dedup
Normalize each URL: lowercase, strip trailing slash, strip common query parameters
(e.g., `?utm_source=...`, `?gh_src=...`).

Remove duplicates within `all_results` by normalized URL. When the same job appears from
multiple sources, prefer the ATS-direct URL (greenhouse or lever) over a LinkedIn URL.

### Step 2.4 — Dedup Against Existing Output
For each opportunity in `all_results`:
- Normalize its URL
- If the normalized URL appears in `known_urls` (from Step 0.3): discard it
- Secondary check: normalize `company + title` (lowercase, strip whitespace, strip "(Remote)",
  "with verification", punctuation). If it matches any entry already in `known_urls`'s
  corresponding company+title pairs: discard it.

Result: `new_opportunities` — the list of truly new opportunities.

### Step 2.5 — Count
Record:
- `total_found` = len(all_results)
- `duplicate_count` = total_found - len(new_opportunities)
- `new_count` = len(new_opportunities)

---

## Phase 3 — Score

If `new_opportunities` is empty: skip directly to Phase 4.

### Step 3.1 — Prepare Context

Read the scoring config from `job-search.yaml`:
- `scoring.dimensions` — array of `{name, weight}`
- `scoring.thresholds` — `{apply, evaluate, skip}`
- `profile` — title, skills, seniority, location

If `profile.resume_path` is set (non-empty), read that file using the Read tool and store its
content as `resume_content`. Otherwise `resume_content = null`.

### Step 3.2 — Launch Scorer Subagents in Parallel

Split `new_opportunities` into batches of 5 (last batch may be smaller).
Spawn **all batches in a single parallel response** using the agent spec at
`{SKILL_DIR}/agents/match-scorer.md`.

For each batch, append these parameters to the spec content in the subagent prompt:

```
## Parameters for this batch

opportunities:
{JSON array of opportunities in this batch — include: title, company, location, url, source}

scoring_config:
  dimensions: {scoring.dimensions from config}
  thresholds: {scoring.thresholds from config}

profile:
{profile section from config, as YAML}

resume_content: |
{resume_content if available, else "(not provided)"}

language: {config.language}
```

Each subagent returns a JSON array of scored results:
```json
[
  {
    "url": "https://...",
    "match_pct": 78,
    "recommendation": "APPLY",
    "rationale": "...",
    "breakdown": {
      "Dimension name": score,
      ...
    }
  }
]
```

Where `recommendation` is one of: `APPLY`, `EVALUATE`, `SKIP`.
`match_pct` may be `null` if the job description could not be fetched.

### Step 3.3 — Collect & Merge Scorer Results

Collect all subagent outputs. For each subagent response:

1. Try to parse the full output as JSON.
2. If that fails: extract the substring between the first `[` and the last `]`, then parse.
3. If still no valid JSON found: log a warning ("Scorer batch returned unparseable output —
   batch skipped") and treat all opportunities in that batch as unscored.

Merge all parsed results into `scored_results` keyed by URL.

### Step 3.4 — Join Scores Back

For each opportunity in `new_opportunities`, look up its URL in `scored_results`.
- If found: attach `match_pct`, `recommendation`, `rationale`, `breakdown`.
- If not found (batch was unscored): set `match_pct = null`, `recommendation = "EVALUATE"`,
  `rationale = "Scoring unavailable — evaluate manually."`, `breakdown = {}`.

---

## Phase 4 — Output

Run inline. Read the output file again if it has been modified externally between Phase 0
and now. The file path is `$CWD/{config.output.file}`.

### Step 4.1 — Initialize Output File (if new)

If the output file does not exist yet, create it with this skeleton:

```markdown
# Job Search Results

> Profile: {config.profile.title} | Location: {config.profile.location} | Remote: {yes if remote_only else no}
> Last run: {today's date, ISO format YYYY-MM-DD}
> Scope: {all keywords from config, comma-separated}

---

## APPLIED
| Company | Role | Match | Date | Notes |
|---------|------|-------|------|-------|

## PENDING
| Company | Role | Match | Date | Notes |
|---------|------|-------|------|-------|

## DISCARDED
| Company | Role | Match | Reason | Date |
|---------|------|-------|--------|------|

## CLOSED
| Company | Role | Date | Notes |
|---------|------|------|-------|

## WATCHLIST
| Company | Domain | Career Page | ATS | Slug | Last checked |
|---------|--------|-------------|-----|------|--------------|
```

If the file already exists but the expected section headers (`## PENDING`, `## DISCARDED`,
`## WATCHLIST`) are not found: warn the user:
> "Output file structure does not match the expected skeleton. New entries could not be inserted.
> Consider backing up the file and letting the skill recreate it, or manually add the required
> section headers."
Then skip Steps 4.2 and 4.3 (still print the summary in 4.4).

### Step 4.2 — Insert New Opportunities

Process each opportunity in `new_opportunities` (with scores attached from Phase 3):

**For APPLY and EVALUATE recommendations** (or match_pct >= config.scoring.thresholds.evaluate,
or match_pct is null):

Insert a row into the PENDING summary table immediately after the `## PENDING` header line:
```
| {company} | {title} | {match_pct}% | {today} | {recommendation} — {rationale, truncated to 80 chars} |
```
If `match_pct` is null, use `N/A` instead of a percentage.

Also insert a detail block. Place it after the PENDING table (before the next `##` section).
Each detail block follows this format:

```markdown
### {company} — {title} — {source}
| Field | Value |
|-------|-------|
| Link | {url} |
| Location | {location} |
| Posted | {posted_date or "—"} |
| Source | {source} |

**Match: {match_pct}%** ({breakdown as: "Dimension: score | Dimension: score | ..."})
**Recommendation: {recommendation}**
{rationale}

---
```

If `match_pct` is null, write `**Match: N/A**` and omit the breakdown.

**For SKIP recommendations** (match_pct < config.scoring.thresholds.evaluate):

Insert a row into the DISCARDED summary table immediately after the `## DISCARDED` header line:
```
| {company} | {title} | {match_pct}% | {rationale, truncated to 80 chars} | {today} |
```

Do **not** add a detail block for SKIP entries.

**Never modify entries that already exist in the file.** Only insert new rows and blocks.

### Step 4.3 — Update Watchlist

**Update Last checked dates:**

If `meta` is not null, for each entry in the config `watchlist`:
- If the entry's `ats` + `slug` combination is NOT listed in `meta.stats.sources[ats].slugs_failed`:
  - Find the corresponding row in the `## WATCHLIST` section of the output file
  - Update its `Last checked` column to today's date
- If the slug failed (listed in `slugs_failed`): leave the date unchanged

**Add newly discovered slugs:**

If `meta.discovered_slugs` is non-empty, for each entry `{company, ats, slug}`:
- Check whether this slug already appears in the `## WATCHLIST` section
- If not: append a new row to the WATCHLIST table:
  ```
  | {company} | (discovered) | {ATS URL: boards.greenhouse.io/v1/boards/{slug}/jobs OR jobs.lever.co/{slug}} | {ats} | {slug} | {today} |
  ```

**Update Last run date:**

Find the `> Last run:` line in the file header and replace its date with today's date.

### Step 4.4 — Print Summary

Print the following to the terminal (in the language specified by `config.language`; default English):

```
Job Search — {today}
================================================
Sources: APIs ({n} slugs checked, {ok_count} OK) | LinkedIn ({n_queries} queries, {status}) | Scoring ({scored_count} opps scored)

Found: {total_found} total | {duplicate_count} duplicates | {new_count} new

NEW OPPORTUNITIES:
| Company | Role | Match | Rec. | Rationale |
|---------|------|-------|------|-----------|
| {company} | {title} | {match_pct}% | {rec} | {rationale, truncated} |
...

NEW WATCHLIST SLUGS DISCOVERED:
| Company | ATS | Slug |
|---------|-----|------|
| {company} | {ats} | {slug} |
(These have been appended to the WATCHLIST section and will be checked on the next run.)

Output file: {output.file}
================================================
```

If `new_count` is 0: print "No new opportunities found." and exit cleanly — this is not an error.

If no new watchlist slugs were discovered, omit that section entirely.

Adjust column names to the configured language when applicable. The opportunity content
(titles, rationale) is written in the language returned by the scorer, which is passed
`config.language` as an instruction.

---

## Error Handling Rules

- **Any single source fails (Python script, one ATS, one LinkedIn query):** warn and continue.
  Never abort the entire run because one source failed.
- **All sources return zero results:** complete the run normally; print "No new opportunities found."
- **Output file write fails:** report the error and print the full results to the terminal so
  the user can save them manually.
- **Config file unreadable or invalid YAML:** stop immediately and report the parsing error.
  Do not attempt partial execution.
- **Scorer subagent returns no parseable JSON:** log a warning per batch, mark those
  opportunities as unscored (EVALUATE / N/A), and continue.
- **LinkedIn cookie expired mid-run:** prompt the user for a new cookie or to skip, as
  described in Phase 1b. Never abort the rest of the run.

---

## Config Reference (Summary)

All behavior is driven by `job-search.yaml`. The skill reads — and never hardcodes — the following:

| Config field | What it controls |
|---|---|
| `profile.*` | Passed to scorer for context |
| `language` | Output language for rationale and summary |
| `keywords.*` | Search terms sent to Python script and LinkedIn |
| `sources.*` | Which sources are enabled |
| `sources.linkedin.cookie` | LinkedIn auth token |
| `watchlist` | Companies checked directly via ATS APIs |
| `scoring.dimensions` | Dimension names and weights for scorer |
| `scoring.thresholds` | apply / evaluate / skip cutoffs |
| `output.file` | Path to tracking markdown file (relative to $CWD) |

Never substitute hardcoded values for any of the above fields.
