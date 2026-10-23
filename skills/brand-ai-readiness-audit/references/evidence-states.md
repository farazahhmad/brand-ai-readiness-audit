# Evidence States (mandatory — read this before running any check)

## Capability note — read this first in this build

**This build never executes JavaScript.** `scripts/render_page.py` (real
headless-Chromium rendering) has been removed entirely to keep runtime
well under the PS's 5-minute cap — see `references/runtime-budget.md`
for the trade-off this represents. Every observation in this build comes
from raw, server-delivered HTTP content, parsed statically by
`scripts/parse_dom_lite.py`. Concretely:
- `present_in_rendered` and `present_after_interaction` **cannot be
  produced by this build at all.** Do not use either state; do not write
  "rendered," "in the DOM," or "after JavaScript execution" in any
  finding's evidence text, regardless of how the page was fetched — see
  the language guard in `severity-rules.md`.
- The render-parity mechanism (PS Appendix C: a fact assembled only after
  a page loads can be invisible to a program that doesn't execute JS) is
  still real and still worth flagging when it's *likely* — but this build
  can only ever produce the capped-confidence
  `heuristic_client_side_rendering_suspected` inference (see
  `page-level-checks.md` §7), never a confirmed gap.
- The orphaned-client-side-navigation mechanism cannot be confirmed at
  all without activating an element to see what it does — see
  `navigation-states.md` and `cross-page-checks.md` §3 for how this was
  downgraded to an `opportunities[]`-only signal rather than dropped
  silently or kept as a now-unreliable finding.

## The rule this file exists to enforce

**Not observing a fact in one representation is not the same as that fact
being absent, broken, inaccessible, or client-side-only.** Every check must
first record what it actually observed, in controlled vocabulary, before
any diagnosis is attempted. A finding may only be written after
reconciliation across representations (see `page-level-checks.md` /
`cross-page-checks.md`) and after passing the diagnosis gate in
`severity-rules.md`.

This is the single most important rule in this skill. Four real-site audits
(documented abstractly in `regression-cases.md`) produced false
positives specifically because a check skipped straight from "not found in the first representation I
looked at" to "this is broken/absent/client-side-only." Do not repeat that.

## Controlled vocabulary

Use these exact state labels internally when recording what a check found.
Never substitute a stronger word (e.g. "missing," "broken," "unsupported")
for a weaker observed state.

### Presence / absence
- `observed` — the fact was found in at least one checked representation.
- `not_observed` — the fact was not found in the representation(s) checked
  so far. This is the default state before reconciliation, not a
  conclusion.
- `absent` — reserved. Only usable after reconciliation has checked **all**
  available representations in this build (raw, metadata, structured
  data) and found the fact in none of them.

### Representation-specific presence
- `present_in_raw`
- `present_in_metadata`
- `present_in_structured_data`
- ~~`present_in_rendered`~~ / ~~`present_after_interaction`~~ — **not
  producible in this build** (see the Capability note above). The
  vocabulary entries themselves are kept here, unused, only so
  `output-schema.json` stays forward-compatible with a future build that
  re-adds rendering — do not use them.

Record each of the (still-producible) states independently per fact per
page — do not collapse them into one boolean.

### Interaction
- `interaction_required` — a value was only obtainable after some user
  action. This state alone is never a diagnosis — see
  `interaction-states.md` to classify *why* interaction was required
  before deciding whether it matters. In this build, `interaction_required`
  can only be **inferred** from static markup (see the no-render caveat in
  `interaction-states.md`), never confirmed by actually testing the
  interaction.

### Reconciliation outcomes
- `contradictory` — two or more representations state incompatible values
  for the **same entity and same attribute**, both retrieved successfully
  (see `cross-page-checks.md` for the full gating rule).
- `insufficient_evidence` — the check could not gather enough information
  to reconcile or diagnose confidently. This is a legitimate, expected
  output — do not force a stronger state to avoid reporting it.
- `heuristic_client_side_rendering_suspected` — in this build, this is
  the **only** signal this skill can produce about JS-render risk (see
  `page-level-checks.md` §7). It is a pattern-based inference, always
  capped at low confidence, never treated as equivalent to a confirmed
  render-parity gap — because this build cannot produce a confirmed one
  at all.

### Fetch/extraction health
**This build has a single fetch mechanism: the invoking agent's own
native fetch/search tool.** There is no bundled fetch script and no
fallback chain to reconcile between — every sampled page, plus
robots.txt and the sitemap, is fetched exactly once, by that one
mechanism (see `SKILL.md` Step 1). Because there's only one mechanism,
there's nothing to record about *which one* succeeded — only *whether*
the fetch itself succeeded. Use these states:
- `fetch_degraded` — the fetch itself failed, timed out, or returned a
  non-content response (e.g. a CAPTCHA wall, a 5xx, an empty shell). A
  `not_observed` result caused by `fetch_degraded` must be labeled as such,
  not treated as evidence about the page's actual content. This includes
  the time-budget reason from `runtime-budget.md`
  (`fetch_time_budget_exceeded`) — a page that ran out of *this tool's*
  time budget is exactly as uninformative about the page's actual content
  as a network error, and must be labeled the same way, never silently
  treated as `absent`.
- `dom_parse_degraded` — `scripts/parse_dom_lite.py` had HTML to work
  with but its own static parsing failed to make sense of it (e.g.
  severely malformed markup, or a native tool that stripped `<script>`
  tag content during its own extraction — see the caveat in
  `parse_dom_lite.py`'s module docstring). Same rule as `fetch_degraded`:
  label it, don't let it silently become a content finding.
- `extractor_degraded` — the fetch succeeded but this skill's own parsing
  failed to make sense of the response more generally (e.g. unexpected
  encoding). Same rule: label it, don't let it silently become a content
  finding.
- `skipped` — the fetch never succeeded for this page at all (and there
  is no second mechanism left to try); nothing was observed and nothing
  should be inferred. Record it under
  `coverage.checks_skipped_insufficient_evidence` in the final report.

A page's fetch outcome (succeeded / `fetch_degraded` / `skipped`, plus
`degraded_reason` where relevant) should be attached to every observation
derived from that page, and carried through into the corresponding
finding's `evidence_detail` — see `output-schema.json`. Earlier builds of
this skill tracked *which of several fetch mechanisms* produced each
observation (a `fetch_tier` field); that distinction no longer applies
now that there is only one mechanism, and the field has been removed
from the schema.

## Order of operations (do not skip steps)

1. **Observe** — for each check, record presence/absence per representation
   using the vocabulary above. Do not diagnose yet.
2. **Reconcile** — before concluding anything from a `not_observed` result,
   check the other available representations (raw ↔ metadata ↔ structured
   data) per the specific check's procedure.
3. **Establish scope** — see `scope-and-time.md`. Is this one page, the
   sampled batch, or (rarely) verifiably site-wide?
4. **Establish time context** — see `scope-and-time.md`. Is this confirmed
   in the current run, or does it relate to some earlier claim?
5. **Diagnose** — only now decide whether the reconciled evidence state
   crosses the diagnosis gate defined in `severity-rules.md` for that
   mechanism. If it doesn't cross the gate, do not emit a finding — either
   emit neutral coverage evidence or mark the item `insufficient_evidence`.
6. **Assign severity, confidence, and priority separately** — see
   `severity-rules.md`. Never collapse these into one number.

If you find yourself about to write "the site is missing X" or "this is
broken" or "this claim is unsupported" without having gone through steps
1–4 for that specific fact, stop and go back — that is exactly the
recurring error this file exists to prevent.
