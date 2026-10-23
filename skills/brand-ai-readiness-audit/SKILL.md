---
name: brand-ai-readiness-audit
description: Audit a website for AI-discoverability problems (why a brand isn't found or cited by AI assistants) and on-site-engagement problems (why visitors who do arrive don't stay), read-only, and produce a schema-locked findings report with evidence, severity, confidence, and prioritized suggested actions. Follows an evidence-state-first discipline — records what was actually observed in the fetched page content before diagnosing, reconciles across raw/metadata/structured-data before concluding absence or contradiction, and never treats a single sampled page's condition as a site-wide claim. Use whenever asked to audit a website's AI readiness, check why a brand is missing/misrepresented in AI assistants, or diagnose why visitors bounce.
license: MIT
allowed-tools:
  - bash        # required to run the parsing/validation scripts in scripts/ (Python) — no longer used for fetching, see Step 1
  - web_fetch   # required — this build's only HTTP fetch mechanism (robots.txt, sitemap, and every sampled page)
---

## Runtime budget — read this before Step 1

This audit must finish in **under 5 minutes** (PS requirement); this
build typically finishes in under two. Read `references/runtime-budget.md`
once before your first run. **This build never executes JavaScript** —
there is no headless-Chromium render step, no browser dependency, and no
"one-time setup" to manage at all. Every check runs against raw,
server-delivered HTTP content. This is a deliberate trade-off, not an
oversight: see `references/runtime-budget.md`'s "Why rendering was
removed" section for exactly what that costs and who it's right for, and
`references/evidence-states.md`'s Capability note for how every check
below was adjusted to stay honest about it.

# Brand AI-Readiness Audit (discoverability + engagement) — no-Chromium build

## When to use
Invoke this skill whenever the user gives a URL and asks to audit it for AI discoverability or on-site engagement, or asks something like "why isn't this site getting cited," "why do visitors bounce," or "check this site's AI readiness."

## Before you start
Read `references/evidence-states.md` first — it defines the controlled
vocabulary and the order of operations (observe → reconcile → scope →
time → diagnose → severity/confidence/priority) that every step below
depends on, and its Capability note explains exactly what this build can
and cannot observe. The single most important rule in this skill: **not
observing a fact in one representation is not the same as that fact
being absent, broken, inaccessible, or client-side-only.** Field testing
across multiple live sites produced false positives specifically by
skipping that distinction — see `references/regression-cases.md` for the
generalized error patterns (documented abstractly, not tied to any
specific site, so the lesson transfers to unseen sites), including the
no-render-specific pattern of guessing at JavaScript behavior from static
markup.

## Inputs
- `url` (required): the site or page to audit.
- `max_pages` (optional, default 2): number of pages to sample beyond the homepage — 3 total including the homepage, matching the PS's own "2-3 sampled pages."

## Procedure

### Step 1 — Fetch (read-only, respects robots.txt — including its own; time-boxed per `references/runtime-budget.md`)

**Single-mechanism fetch architecture.** This build has exactly **one**
way to retrieve anything over HTTP: the invoking agent's own native
fetch/search tool (e.g. a `web_fetch`/`web_search`-style tool). There is
no bundled fetch script and no fallback chain — earlier builds of this
skill ran a bash-based `fetch_raw.py` first and fell back to the native
tool only when that was blocked; that script has been removed entirely,
because the native tool proved the more reliable path across different
Claude surfaces during testing anyway. Every fetch below — robots.txt,
the sitemap, and every sampled page — goes through that one mechanism.
The `scripts/parse_*.py` scripts in this build never fetch anything
themselves anymore; they only **parse** content you've already fetched
and pass in. **Note the wall-clock time now** — see
`references/runtime-budget.md` for the per-fetch budget.

**Step 1.1 — Discovery.**
Fetch `robots.txt` with your native fetch tool. Then parse it:
```
python3 scripts/parse_robots.py "$BASE_URL" --input /tmp/robots.txt --bot-taxonomy references/bot-taxonomy.json > /tmp/robots_parsed.json
```
(If the fetch returned a 404, pass `--not-found` instead of `--input`; if the fetch failed outright, pass `--fetch-failed "<reason>"`.)

To find the sitemap URL, run `parse_sitemap.py --discover-only` against the robots.txt text you already have in memory (no extra fetch needed for this step):
```
python3 scripts/parse_sitemap.py "$BASE_URL" --discover-only --robots-text /tmp/robots.txt
```
This returns `recommended_next_fetch` — fetch that URL with your native tool, then parse it:
```
python3 scripts/parse_sitemap.py "$SITEMAP_URL" --input /tmp/sitemap.xml > /tmp/sitemap_parsed.json
```
If the sitemap is gzip-compressed and your native tool can only return
text (most can), you may not be able to retrieve it as valid gzip bytes —
if so, record it as `fetch_degraded` (`degraded_reason:
"gzip_sitemap_needs_binary_fetch"`) and fall back to the homepage plus
any links you can otherwise discover, rather than guessing at the sample.

Pick a bounded sample of up to `max_pages` candidate pages from the sitemap (plus the homepage) — 3 total pages by default (see Inputs above).

**Step 1.2 — Self-compliance check (governs this tool's own fetching only).**
For each candidate path, run `python3 scripts/parse_robots.py "$BASE_URL" --input /tmp/robots.txt --check-path "$PATH"` and check `self_compliance_check.allowed` — drop the page from the sample (reason `"robots_txt_disallowed_for_this_tool"`) if `false`, before it ever reaches fetch. This is separate from the bot-policy analysis used for the report (Step 1.5 below).

**Step 1.3 — Fetch each sampled page.**
Fetch every remaining sampled URL with your native fetch tool, one call
per page (this tool has no batch/concurrent fetch of its own anymore —
see `references/runtime-budget.md` for the time-budget consequence of
that). For each page, record `ok`, `html` (if the fetch succeeded), and
`fetch_degraded`/`degraded_reason` (if it didn't) — a timeout, a non-2xx
status, or your own time budget running out are all valid degraded
reasons; label whichever applies (`fetch_time_budget_exceeded` for the
last one) rather than guessing at page content. If a fetch fails for a
given page, there is no second mechanism left to try — record that page
under `coverage.checks_skipped_insufficient_evidence` and do not
fabricate any observation for it.

**Step 1.4 — Static structural parse (all sampled pages, one process call).**
Assemble what you fetched into the shape `parse_dom_lite.py` expects —
`{"results": [{"url": ..., "ok": true, "html": "..."}, ...]}`, one entry
per sampled page in Step 1.3 — write it to a file, then run:
```
python3 scripts/parse_dom_lite.py /tmp/raw.json --write
```
`parse_dom_lite.py` is a stdlib-only (`html.parser`) parser — no third-party dependency, no JS execution. It augments each successfully-fetched result with `title`, `meta_tags`, `canonical`, `json_ld`, `interactive_elements`, and `visible_text_approx`, all extracted from the raw HTML you fetched. This is the **only** structural-signal extraction in this build — there is no separate rendered-DOM pass. Pages that were `fetch_degraded` in Step 1.3 are passed through unchanged (`dom_parse_degraded: true`, reason `"no_html_to_parse"`) — there's nothing to parse for them. If your native fetch tool stripped `<script>` tag content during its own text extraction, JSON-LD and the structural markers in §7 of `page-level-checks.md` may be under-detected — note that explicitly rather than silently treating "not found" as confirmed absence (see `evidence-states.md`).

**Step 1.5 — Bot-policy analysis (informational, for the report).**
The `bot_policy_analysis` produced by `parse_robots.py` in Step 1.1 is the analysis of robots.txt's effect on *other* crawlers (training vs. real-time-answer bots) — report this as a policy fact for the audit, never as an error. No extra fetch needed here; it comes from the same `robots.txt` content already fetched in Step 1.1.

Record each page's fetch outcome (fetched successfully, or
`fetch_degraded`/`skipped` with a reason) as part of every individual
observation from Steps 2–3, not just as a page-level coverage note — it
carries through into `evidence_detail` in the final report (see
`output-schema.json`). Earlier builds tracked *which of several fetch
mechanisms* produced each observation (`fetch_tier`); with only one
mechanism left, that field no longer exists — only success/failure does.
Also build a running `self_compliance_checked` list (path + whether it was allowed for this tool) as you go — this is the concrete evidence that the tool itself respected robots.txt, distinct from the `bot_policy_analysis` about the site's stance toward other crawlers.

### Step 2 — Observe (single-page checks, run once per sampled page)
Follow `references/page-level-checks.md` for each sampled page individually. Every check there emits a raw **evidence observation** — presence/absence per representation, in the controlled vocabulary — not a diagnosis. Do not let any check jump straight to "absent," "broken," or "unsupported" here. Note that §1 and §7 of that file work together in this build (§7's heuristic is the only JS-render-risk signal, always run, not a fallback).

### Step 3 — Observe (cross-page checks, run once across the whole batch)
Follow `references/cross-page-checks.md`, holding all sampled pages (plus the sitemap) together. It covers entity identity, same-entity/same-attribute fact-pair disagreement (with context preservation), and placeholder/empty navigation targets (an `opportunities[]`-only signal in this build — see that file §3 for why). These also emit evidence observations, not diagnoses.

### Step 4 — Reconcile and diagnose
For every observation collected in Steps 2–3:
1. If it involves `interaction_required`, classify it per `references/interaction-states.md` before proceeding — most interaction categories never justify a finding, and in this build most can only be inferred, not confirmed.
2. Reconcile across representations per the specific check's rules (e.g., a `not_observed` in raw is not meaningful until metadata/structured-data have also been checked).
3. Establish scope per `references/scope-and-time.md` — default to `page_local`; only use `sampled_pages` if the condition held consistently across the sample; never claim `site_wide` for a content/structure observation.
4. Establish time context per the same file — default `confirmed_currently` unless comparing against a specific prior claim.
5. Check the observation against `references/regression-cases.md` — does it match a known false-positive shape without stronger evidence, or the known true-positive shape (same entity + same attribute + incompatible values, fully reconciled)?
6. Apply the diagnosis gate for that mechanism in `references/severity-rules.md`. If it doesn't pass, do **not** emit a finding — record it under `coverage.checks_skipped_insufficient_evidence` in the final report instead.

### Step 5 — Assign severity, confidence, and priority (separately)
For every observation that passed the gate, assign all three independently per the tables in `references/severity-rules.md`. Never derive one from the others informally, and never combine them into a single score.

### Step 6 — Apply the language guard
Rewrite every finding's `evidence` string against the disallowed-phrasing list in `references/severity-rules.md` — no predicted downstream outcomes, no scope inflation beyond what was actually checked, no stronger word than the evidence state supports, and (this build specifically) no "rendered"/"in the DOM" language for any observation, ever.

### Step 7 — Proactive opportunities (beyond detected problems)
Independent of whether a defect was found, review what was actually observed during Steps 2–3 and propose 1–4 non-obvious, mechanism-sound improvements the site could make to strengthen discoverability or engagement — even where no explicit defect exists. Examples: adding `sameAs` links between an already-consistent entity's representations to make future drift easier to catch automatically; adding structured data to a page-type that currently has none but isn't strictly required; tightening a fact that is technically present everywhere but not in a short, labeled span; the placeholder-navigation verification suggestion from `cross-page-checks.md` §3. Each goes into the `opportunities[]` array (see `references/output-schema.json`) with a `summary`, one-line `rationale`, and a `priority` — never a `severity`, since these are not diagnosed problems. **The same evidence discipline as findings applies here too:** if a `summary`/`rationale` states a specific fact about the site as true rather than a generic recommendation, that fact must be backed by an `evidence` field grounded in what was actually observed.

### Step 8 — Deduplicate, validate, and emit (mechanical — should take seconds, not minutes)
1. Deduplicate observations describing the same underlying condition seen from more than one check.
2. Write the assembled report to a file (e.g. `/tmp/report.json`), including the optional `coverage` block (pages sampled, degraded fetches, `self_compliance_checked` built up in Step 1, checks run, checks skipped for insufficient evidence) and the optional `opportunities[]` array.
3. Run `python3 scripts/validate_report.py /tmp/report.json --write`. This mechanically checks required fields, `evidence` being a plain string on every finding, and **recomputes `summary` by literally counting `findings[]` by severity and overwrites the `summary` block with the correct counts.** If it exits non-zero, its `errors` list tells you exactly what to fix.
4. Read the (now corrected) report back from the file as the final output.
5. If a human-readable rendering is also requested, produce a Markdown/HTML view of the exact same JSON — never a second, competing report structure.

## Output

A JSON object matching `references/output-schema.json`. The required PS-floor shape is unchanged from before:

```json
{
  "site": "example.com",
  "audited_at": "2026-09-05T15:30:00Z",
  "summary": { "total_findings": 2, "critical": 0, "high": 1, "medium": 0, "low": 1 },
  "findings": [
    {
      "id": "F-001",
      "title": "Product page shows markers commonly associated with client-side rendering, and no price was observed in the fetched page content",
      "severity": "low",
      "confidence": "low",
      "category": "discoverability",
      "check_id": "heuristic-client-side-rendering-suspected",
      "affected_scope": "page_local",
      "evidence": "This sampled product page's raw HTML contains a __NEXT_DATA__ hydration script and no price-like pattern or purchase call-to-action was found in the fetched content. This is a pattern-based inference, not a confirmed render-parity gap — this build does not execute JavaScript.",
      "affected_urls": ["https://example.com/product/a"],
      "evidence_detail": {
        "evidence_state": "heuristic_client_side_rendering_suspected",
        "time_state": "confirmed_currently"
      },
      "suggested_action": {
        "summary": "Verify with a JS-capable rendering tool whether the price is available before JavaScript executes; if not, expose it in server-rendered HTML or structured data.",
        "priority": "medium"
      }
    },
    {
      "id": "F-002",
      "title": "Homepage title tag present but no meta description or canonical link observed in raw HTML",
      "severity": "low",
      "confidence": "medium",
      "category": "discoverability",
      "check_id": "basic-metadata-absence",
      "affected_scope": "page_local",
      "evidence": "The homepage has a non-empty <title> tag but no <meta name=\"description\"> and no <link rel=\"canonical\"> were observed in the fetched raw HTML on a non-degraded fetch.",
      "affected_urls": ["https://example.com/"],
      "evidence_detail": {
        "evidence_state": "not_observed in raw (meta description, canonical link)",
        "time_state": "confirmed_currently"
      },
      "suggested_action": {
        "summary": "Add a meta description and a canonical link to the homepage.",
        "priority": "low"
      }
    }
  ],
  "opportunities": [
    {
      "summary": "Add a sameAs link between the JSON-LD Organization block and the footer entity string, even though both currently agree, so future drift is machine-detectable.",
      "rationale": "Strengthens entity resolvability proactively rather than waiting for a disagreement to occur.",
      "priority": "low"
    }
  ],
  "coverage": {
    "pages_sampled": ["https://example.com/", "https://example.com/product/a"],
    "degraded_fetches": [],
    "self_compliance_checked": [
      { "path": "/", "allowed": true, "fetched": true },
      { "path": "/product/a", "allowed": true, "fetched": true }
    ],
    "checks_run": ["fact-cross-representation", "structured-data-presence", "basic-metadata-absence", "entity-identity"],
    "checks_skipped_insufficient_evidence": []
  }
}
```

The `opportunities[]` entry above is deliberately a *general* recommendation with no specific unverified fact in it, so it needs no `evidence` field. An opportunity that instead asserted something like "the site already has X integration" or "already gets N reviews" would need an `evidence` field grounding that specific claim — see Step 7.

`evidence` is a **required plain string**, matching the PS floor's shown shape exactly. `confidence`, `category`, `check_id`, `affected_scope`, `why_it_matters`, `affected_urls`, `evidence_detail`, `opportunities` (including its optional `evidence`), and `coverage` (including `self_compliance_checked`) are optional additions on top of the required PS floor (`site`, `audited_at`, `summary`, `findings[].{id,title,severity,evidence,suggested_action.summary,suggested_action.priority}`) — they add traceability, proactive value, and honesty, without changing the type of any required field.

The following must never appear in this output: an overall 0–100 health score, an unsupported "AI readiness" percentage, a claim that a finding guarantees citation failure/hallucination/abandonment/ranking loss, a site-wide claim built from a page-local observation, a claim that anything was observed "rendered" or "in the DOM" (this build never executes JavaScript — see `evidence-states.md`), internal research-paper citations, or a hidden weighting system.
