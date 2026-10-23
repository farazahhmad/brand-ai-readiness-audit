# brand-ai-readiness-audit (no-Chromium build)

An Agent Skill Marketplace that audits a website for problems hurting its
AI discoverability (being found/cited by AI assistants) and its on-site
engagement (keeping the visitors who do arrive), and emits a single
schema-locked findings report.

**This build removes headless-Chromium rendering entirely** to minimize
runtime and dependency footprint. See "What changed vs. the
Chromium-enabled build" below for the full, honest trade-off before
choosing which variant to submit.

## Skills in this marketplace

This submission ships as **one skill** — `brand-ai-readiness-audit` — set
as the sole entrypoint in `marketplace.json`. Per the problem statement,
"a marketplace with only one skill is accepted as a floor — it's a valid
submission, not the target." A single, well-built skill was chosen here
deliberately after an earlier multi-skill split was found to add
coordination overhead without a genuine data-dependency boundary strong
enough to justify separate skills for this scope; all the reasoning is
kept in one place, in `skills/brand-ai-readiness-audit/`, with detail
pushed into `references/` per the progressive-disclosure guidance.

## What the skill does

Given a URL, it:
1. Fetches `robots.txt` and the sitemap with the invoking agent's own native fetch tool (the sole fetch mechanism in this build — see below), then parses each with `scripts/parse_robots.py` and `scripts/parse_sitemap.py` (stdlib-only — `urllib.robotparser` + `xml.etree.ElementTree`; neither script fetches anything itself anymore), picks a bounded sample of pages, and **skips any path disallowed for its own fetching by robots.txt** — separately from analyzing robots.txt's effect on other crawlers.
2. Fetches each sampled page with the same native fetch tool, one call per page, then runs `scripts/parse_dom_lite.py` — a stdlib-only (`html.parser`) structural parser, no third-party dependency — to extract title, meta tags, canonical link, JSON-LD, interactive elements, and an approximate visible-text string from that raw HTML.
3. Runs single-page checks (structured-data integrity, basic metadata presence, claim-support, label collisions, the CSR-likelihood heuristic) and cross-page checks (entity identity, fact-pair disagreement, placeholder-navigation verification suggestions) — each recording a controlled-vocabulary **evidence state**, not a diagnosis.
4. Reconciles every observation across the representations this build can actually produce (raw / metadata / structured data), establishes scope
   (page-local vs. sampled vs. site-wide) and time context, and only then
   applies a per-mechanism diagnosis gate before anything becomes a
   finding.
5. Assigns **severity, confidence, and priority as three separate axes**
   — never collapsed into one score.
6. Proposes proactive, beyond-defect **opportunities** in addition to any
   detected problems.
7. Emits a single JSON report matching the PS floor schema exactly
   (`site`, `audited_at`, `summary`, `findings[].{id,title,severity,
   evidence,suggested_action}`), with optional additive fields
   (`confidence`, `category`, `affected_scope`, `evidence_detail`,
   `opportunities[]`, `coverage`) that never change the type or meaning of
   a required field — validated and its `summary` counts recomputed
   mechanically by `scripts/validate_report.py` rather than by hand.

## What changed vs. the Chromium-enabled build

| | Chromium-enabled build | This build (no-Chromium) |
|---|---|---|
| Typical runtime | ~1:30-3:00 (target), 4:30 hard stop | ~1:00-2:00 (target), ~3:15 hard stop |
| Dependencies | `requests` + Playwright + a ~150-300MB Chromium binary | None — stdlib only. Fetching is done by the invoking agent's own native fetch tool, not by any bundled script. |
| Setup required | One-time, out-of-band Chromium install | None |
| Render-parity check (PS Appendix C) | Confirmed (`present_in_rendered` vs. `not_observed` elsewhere) — evidence-strength A | Heuristic-only inference, always capped low confidence (`heuristic_client_side_rendering_suspected`) — evidence-strength B/C at best |
| Orphaned client-side navigation | Confirmed finding, evidence-strength A | Downgraded to an `opportunities[]`-only verification suggestion — cannot be confirmed without executing JS, so it's never scored as a finding (see below) |
| In-page label collision | Sees the full post-JS interactive surface | Only sees elements present in server-delivered HTML (false-negative risk on heavily-hydrated pages, not a false-positive risk) |
| Everything else (structured data, metadata, entity identity, fact-pair disagreement, claim-support) | Identical | Identical — these were always raw-HTML-based |

**Why the navigation check was downgraded rather than kept as a weaker
finding:** its original gate required distinguishing a real problem
(`destination_unknown`/`empty_href`) from `javascript_route` — a
completely legitimate, extremely common pattern where a real `<a href>`
is intercepted by a client-side router. That distinction can only be
made by actually activating the element and watching what happens, i.e.
executing JavaScript. Keeping it as a "weaker" finding without a real
render would have meant systematically false-positiving on any site
using client-side routing at all — precisely the false-positive shape
this skill's own `regression-cases.md` exists to prevent. See
`skills/brand-ai-readiness-audit/references/cross-page-checks.md` §3 and
`references/runtime-budget.md` for the full reasoning.

**Who should use this build:** anyone prioritizing runtime margin,
dependency simplicity, and reliability (no browser-automation flakiness)
over the render-parity/navigation confirmation that only a real headless
render can provide — which, per the Lead Research Auditor Report, is the
single strongest-evidence check in the whole project. Server-rendered and
hybrid sites lose essentially nothing in practice; pure CSR single-page
apps lose the most (they'll be flagged as *suspected* CSR, not
*confirmed*).

## Runtime & degradation

The PS requires **under 5 minutes** on a standard machine, with graceful
degradation on timeout. `skills/brand-ai-readiness-audit/references/
runtime-budget.md` has the full phase-by-phase budget; in short:

- **No browser, no install, no capability probe, and no third-party
  dependency at all.** `requirements.txt` is empty by design — every
  script in this build is stdlib-only. There's nothing to provision.
- **Fetches run one call per page** through the invoking agent's native
  fetch tool (see "Single-mechanism fetch architecture" below) — no
  concurrent batch, since that was a property of the bash-based fetch
  script this build no longer has.
- **Structural parsing is pure in-memory string parsing**
  (`scripts/parse_dom_lite.py`, stdlib `html.parser`) — not a realistic
  bottleneck at any page count this skill samples.
- **`max_pages` defaults to 2** (3 total pages including the homepage),
  matching the PS's own "2-3 sampled pages" language.
- **Each fetch is time-boxed** — a page still not fetched when its
  budget runs out is recorded as degraded (`fetch_time_budget_exceeded`)
  rather than left to block the rest of the audit.
- **Report assembly is mechanical.** `scripts/validate_report.py`
  recomputes the `summary` counts and checks required fields/enums in
  well under a second.

### Single-mechanism fetch architecture — no tiers, no fallback chain
Earlier versions of this build fetched with a bundled, bash-based
`scripts/fetch_raw.py` first and only fell back to the invoking agent's
native fetch/search tool when that was blocked — a two-step fallback
chain, with a third "nothing worked" state for pages neither could
reach. That fallback structure has been removed entirely, not just
simplified: `fetch_raw.py` is gone, and **every** fetch — robots.txt,
the sitemap, and every sampled page — now goes through the native fetch
tool directly and exclusively, because bash's own outbound network
proved the less reliable of the two across different Claude surfaces
during testing anyway, making the fallback redundant rather than
protective. `scripts/parse_robots.py`, `scripts/parse_sitemap.py`,
and `scripts/parse_dom_lite.py` no longer fetch anything themselves —
they only parse content already fetched and handed to them. If a fetch
fails for a given page, there's no second mechanism left to try: it's
recorded under `coverage.checks_skipped_insufficient_evidence` rather
than guessed at.

Every finding and every `coverage` entry still records whether its
underlying fetch succeeded or was skipped, so the report stays honest
about exactly how much of the audit had real evidence behind it versus
how much was skipped for insufficient evidence.

## Why the evidence-state discipline exists

Field testing surfaced a recurring failure: checks moved directly from
"not found in one fetched representation" to "absent / broken /
unsupported" without reconciling across representations first. That
produced false positives (e.g. an unresolved navigation target reported
as "resolves to homepage," or a fact reported "absent" when it was simply
`not_observed` in the one representation checked). `references/
evidence-states.md` and `references/regression-cases.md` document the
generalized shapes of these errors (abstractly — not tied to any specific
site) so the same mistakes don't recur on sites this skill has never
seen — including a no-render-specific pattern: guessing at JavaScript
behavior from static markup alone.

## Output contract

See `skills/brand-ai-readiness-audit/references/output-schema.json` for
the full JSON Schema. The required PS floor is untouched:

```json
{
  "site": "example.com",
  "audited_at": "2026-09-20T14:32:00Z",
  "summary": { "total_findings": 6, "critical": 1, "high": 2, "medium": 3 },
  "findings": [
    {
      "id": "F-001",
      "title": "No JSON-LD structured data on product pages",
      "severity": "high",
      "evidence": "Crawled 3 sampled product pages; 0/3 contain schema.org markup.",
      "suggested_action": { "summary": "Add Product/Offer JSON-LD to every product page.", "priority": "high" }
    }
  ]
}
```

## Scope & guardrails

- Recommend-only, read-only. No skill in this marketplace modifies a live
  site or performs an authenticated/destructive action.
- Respects `robots.txt` for its **own** fetching (skips disallowed paths
  before sampling) and applies basic rate-limiting between requests, in
  addition to analyzing robots.txt's effect on other crawlers for the
  report.
- Self-contained — no external service or API is required to resolve any
  check; nothing here relies on a specific LLM provider.
- Bounded to a small page sample (2-3 pages), each fetched through the
  invoking agent's native fetch tool under its own time budget, to keep
  runtime well under 5 minutes on a typical site — see "Runtime &
  degradation" above and `references/runtime-budget.md`.
- Zip size and dependency footprint are minimal — **zero third-party
  dependencies** (stdlib only), no pretrained weights, no bundled model
  files, no browser binary.
