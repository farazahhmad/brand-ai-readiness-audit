# Runtime Budget (no-Chromium build)

The PS requires the audit to finish in **under 5 minutes on a standard
machine for a typical website**, with graceful degradation on timeout.
This build removes headless-Chromium rendering entirely, which is by far
the single biggest lever on runtime — see "Why rendering was removed"
below for the full trade-off, honestly stated.

## Budget table (soft internal targets — the hard ceiling is 5:00)

| Phase | Target | Hard stop | On overrun |
|---|---|---|---|
| Discovery: robots.txt + sitemap, native-tool fetch (sequential — see below) | 15s | 30s | Proceed with whatever came back |
| Fetch, all sampled pages, one native-tool call per page | 30s | 60s | A page still not fetched when the budget runs out is recorded `fetch_time_budget_exceeded`, not fabricated — see below |
| Static structural parse, all sampled pages (`parse_dom_lite.py`) | <1s | 2s | Pure in-memory string parsing — not a realistic bottleneck at any page count this skill samples |
| Steps 2-3: observe (single-page + cross-page checks) | 30s | 60s | Reasoning over already-fetched data, no network wait |
| Steps 4-7: reconcile, diagnose, severity/confidence/priority, language guard, opportunities | 30s | 60s | Same |
| Step 8: validate + emit (`validate_report.py`) | <2s | 5s | Mechanical, not a realistic bottleneck |
| **Total (typical site, 3 sampled pages)** | **~2:00** | **~3:15** | Still leaves real margin under the PS's 5:00 cap |

There is no browser-launch phase, no capability probe, and no render
batch at all in this build — those steps simply don't exist anymore.
Compare this table to the Chromium-enabled build's
(`~3:00 target / 4:30 hard stop`, with its own browser-launch and
render-batch phases) to see exactly where the time went.

### Why fetch is now sequential, and why the budget grew slightly from before

Earlier versions of this build had a bundled `fetch_raw.py` script that
fetched all sampled pages concurrently from a thread pool inside `bash`.
That script has been removed entirely: bash's own outbound network proved
to be the less reliable of the two fetch paths across different Claude
surfaces during testing, so this build standardizes on the one that
proved more reliable — the invoking agent's own native fetch/search
tool — for every fetch, including robots.txt and the sitemap, not only as
a fallback for pages a script-based fetch couldn't reach. The trade-off:
a native fetch tool is normally invoked once per call, not as a
concurrent batch, so fetching 3 pages now typically takes roughly 3x a
single fetch's latency rather than ~1x. The budget above reflects that.
If a given fetch fails or times out, record it as `fetch_degraded` (see
`evidence-states.md`) exactly as before — do not retry indefinitely or
fabricate content for it, and do not let one slow/failed page block the
rest of the sample.

## Why rendering was removed — the honest trade-off

**What this buys:** a typical audit now runs in well under two minutes
instead of three-to-five, with a much smaller, simpler dependency
footprint (stdlib + `requests` only — no Playwright, no ~150-300MB
Chromium download, no browser-process flakiness in constrained sandboxes).
Every network call is a plain HTTP GET; there is nothing left in the
pipeline that can hang waiting on a browser process.

**What this costs — stated plainly, not hidden:**
- The **render-parity mechanism** (PS Appendix C — a fact assembled only
  after a page loads can be invisible to a program that doesn't execute
  JS) can no longer be **confirmed**. This build can only ever produce
  the capped-confidence `heuristic_client_side_rendering_suspected`
  inference (`page-level-checks.md` §7) — never the high-evidence-strength
  "fact present in rendered DOM, absent everywhere else" finding the
  Lead Research Auditor Report rated evidence-strength A. See
  `evidence-states.md`'s Capability note.
- The **orphaned-client-side-navigation** check (also evidence-strength A
  in that report) cannot be confirmed at all without activating an
  element to see what it does. It is downgraded to an `opportunities[]`
  -only suggestion in `cross-page-checks.md` §3, never a scored finding —
  see that file for exactly why, and `navigation-states.md` for the state
  taxonomy the reasoning is built on.
- The **in-page interactive-label-collision** check still runs, but only
  sees elements literally present in server-delivered HTML — JS-attached
  or JS-relabeled elements are invisible to it (a false-negative risk,
  not a false-positive one; see `page-level-checks.md` §6).
- On a page the CSR-likelihood heuristic itself flags as likely
  client-rendered, several checks correctly downgrade to
  `insufficient_evidence` rather than reporting a false "all clear" —
  this is intentional and matches the skill's existing evidence
  discipline, not a new gap.

**Who this trade-off is right for:** sites that are server-rendered or
hybrid (the majority of commercial sites, including most SSR/SSG
frameworks) lose essentially nothing — `parse_dom_lite.py` sees the same
interactive elements, JSON-LD, and text a render would have shown. Pure
CSR single-page-apps lose the most: this build can flag them as
*suspected* CSR (still useful — that's exactly the actionable signal a
site owner needs) but can no longer *confirm* exactly which facts are
gated behind JavaScript on that specific page.

If a submission needs the confirmed-render checks back, the Chromium-
enabled build (`scripts/render_page.py` + `scripts/check_capability.py`,
still available in version control / the other submission variant) trades
~1-3 extra minutes of runtime for that confirmation — still comfortably
under the PS's 5-minute cap on its own, per its own runtime-budget.md.

## The one rule that matters more than the table

**Never let the absence of a capability turn into fabricated evidence.**
A check this build cannot honestly perform (confirmed render-parity,
confirmed orphaned navigation) is not silently skipped and not silently
approximated as if it were still authoritative — it is either downgraded
to a clearly-labeled low-confidence heuristic, downgraded to
`opportunities[]`, or recorded as `insufficient_evidence`. A narrower,
honest report beats a fuller one that quietly overclaims what a static
fetch can actually tell you.

## Page-count default (unchanged from the Chromium build)

`max_pages` still defaults to **2** (3 total pages including the
homepage) — this was already sized for the PS's "2-3 sampled pages," and
removing rendering doesn't change what a reasonable sample size is; it
only changes how expensive fetching that sample is.
