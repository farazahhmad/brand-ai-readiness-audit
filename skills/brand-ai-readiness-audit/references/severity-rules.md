# Severity, Confidence, Priority — and the Diagnosis Gate

These are **three separate axes**. Never collapse them into one number or
let one silently stand in for another.

- **Severity** = how bad the condition would be *if the mechanism holds* —
  independent of how sure we are that it does.
- **Confidence** = how certain the reconciled evidence is — derived
  directly from which evidence states were involved (see below).
- **Priority** = what a site owner should fix first — derived from
  severity **and** confidence together, not from severity alone.

## Step 0 — Diagnosis gate (apply before assigning anything)

**No-render build:** the mechanisms below that required a confirmed
render (the old "Fact cross-representation gap" row, and "Orphaned
navigation") have been removed from this table or downgraded — see
`evidence-states.md`'s Capability note and `cross-page-checks.md` §3.
Nothing in this table can be satisfied by fetch-method metadata alone
implying rendering fidelity, because this build has exactly one fetch
mechanism (the invoking agent's native fetch tool) and it never produces
rendered evidence.

An observation may become a finding only if it satisfies the specific gate
for its mechanism, below. If it doesn't, do not emit a finding — instead
emit it as neutral coverage evidence (see the `coverage` block in
`output-schema.json`) or mark it `insufficient_evidence` and drop it from
`findings[]` entirely.

| Mechanism | Gate condition to become a finding |
|---|---|
| Structured-data absence/invalidity | `page_type_hint` confidently determined; type-appropriate schema absent or missing a required property. A deviation that does **not** break parsing per the schema.org/JSON-LD spec (e.g. non-standard property casing, which schema.org treats case-insensitively) is capped at low severity and should usually go to `opportunities[]` instead of `findings[]`, since there's no demonstrated functional consequence. |
| Basic on-page metadata absence (title tag, meta description, canonical link) | `page_type_hint` confidently determined as a brand-identity or otherwise non-boilerplate page (not a utility/legal page where absence is common and low-impact); the element is absent on a non-degraded fetch. Use `check_id: "basic-metadata-absence"` — keep this distinct from `structured-data-absence` (JSON-LD/Microdata), since they're different mechanisms with different research grounding (see `page-level-checks.md` §2b). Capped at medium severity — this is a foundational readability signal (Appendix B), not itself a load-bearing fact. |
| Structured-data vs. visible mismatch | Both sides fetched successfully; normalized values genuinely disagree |
| Claim-support (`SUPPORT_NOT_OBSERVED`) | Whole-page search performed, nothing found — always low severity/confidence regardless |
| In-page label collision | Not inside a well-structured, headed nav/menu; not on a page §7's heuristic flags as likely CSR (see `page-level-checks.md` §6 — on such a page, record `insufficient_evidence` instead, since the real interactive surface wasn't observable) |
| Entity identity | Same entity role, incompatible core values, both representations fetched successfully |
| Fact-pair disagreement | Same entity + same attribute + incompatible values + both sides non-degraded; if a qualifying context clause exists on either side, this becomes `CONFIRMED_WITH_CONTEXT`, not a plain contradiction |
| Interaction-based | Classified as `machine_unresolvable` (see `interaction-states.md`) — `contextual_computation`, `navigation`, `optional_ui`, `progressive_enhancement` never gate a finding; in this build, most interaction categories can only be inferred, not confirmed — default to `insufficient_evidence` unless the raw markup is unambiguous |
| `heuristic_client_side_rendering_suspected` | Two or more markers found (see `page-level-checks.md` §7); even then, becomes at most a low-severity `opportunities[]` entry suggesting verification with a true rendering tool — never a confirmed render-parity finding. **In this build this is the only JS-render-risk signal that exists at all** — there is no higher-confidence version to compare it against. |
| Placeholder/empty navigation target | **Never a finding in this build** — see `cross-page-checks.md` §3. At most an `opportunities[]` entry. |

## Step 1 — Confidence (assign from the evidence state, not from a guess)

| Evidence state pattern | Confidence |
|---|---|
| `contradictory` across two independently, successfully fetched representations (e.g., a same-page country-of-origin or legal-address contradiction) | high |
| `CONFIRMED_WITH_CONTEXT` (contradiction with a preserved qualifying clause) | high (the underlying difference is real; the qualifier changes framing, not certainty) |
| `SUPPORT_NOT_OBSERVED` | low (absence of detected support is inherently weak evidence) |
| `heuristic_client_side_rendering_suspected` (this build's only JS-render-risk signal — no higher-fidelity version exists to compare it against) | low, always — this is an inference from static markers, not an observed render, regardless of how many markers matched |
| Entity identity disagreement without stronger corroboration | medium (real false-positive risk from legitimate multi-brand/DBA structures) |
| Anything resolved only via `insufficient_evidence` | do not emit as a finding at all |

## Step 2 — Severity (consequence if the mechanism holds)

| Condition | Severity |
|---|---|
| Load-bearing fact (price, availability, primary claim) confirmed contradictory across representations | high |
| Structured data missing/invalid on a load-bearing page | high |
| Structured data missing/invalid on a non-load-bearing page | medium |
| robots.txt blocks a real-time-answer bot specifically | medium (policy fact, not an error) |
| robots.txt blocks only training-bot user-agents | low (often deliberate) |
| Entity identity disagreement | medium (never higher — see false-positive risk note) |
| Fact-pair disagreement / `CONFIRMED_WITH_CONTEXT` | medium, capped, single pair only |
| Claim-support (`SUPPORT_NOT_OBSERVED`) | low, always |
| `heuristic_client_side_rendering_suspected` | low, always (this build's only JS-render-risk signal — see Step 0) |
| Machine-unresolvable interaction | medium, framed as difficulty risk, never certainty |

## Step 3 — Priority (derive from severity × confidence)

| Severity | Confidence | Priority |
|---|---|---|
| high | high | high |
| high | medium | medium |
| high | low | low — flag for validation before acting, don't tell the owner to treat it as urgent |
| medium | high | medium |
| medium | medium/low | low |
| low | any | low |

Priority should never exceed what confidence supports — a severe-sounding
but low-confidence observation must not be presented as top-priority.

## No composite score

Never combine severity, confidence, or priority into a single numeric
"AI-readiness score" anywhere in the pipeline or the output.

## Language guard

Before finalizing any finding, check the `evidence` string against this
list and rewrite if any appear:

- "will never be cited" / "guarantees non-citation"
- "will cause hallucination" / "guarantees hallucination"
- "will cause visitors to abandon" / "guarantees abandonment"
- "is fraud" / "is illegal"
- "the site lacks/is missing X" when `affected_scope` is `page_local` or
  `sampled_pages` — must instead say "the sampled pages" / "this page"
- "broken" / "missing" / "unsupported" applied directly to a
  `not_observed`, `insufficient_evidence`, or `SUPPORT_NOT_OBSERVED` state
  that hasn't passed the diagnosis gate above
- Any specific percentage, ranking position, or conversion-rate claim not
  directly measured by the check itself
- "rendered," "in the DOM," or "after JavaScript execution" describing
  **any** observation in this build, regardless of how the page was
  fetched — this build's single fetch mechanism never executes
  JavaScript (see `evidence-states.md`); say "present in the fetched page
  content (raw/text representation)" instead, unless the observation is
  explicitly the low-confidence `heuristic_client_side_rendering_suspected`
  inference from `page-level-checks.md` §7, phrased as such
- "orphaned," "broken navigation," or "resolves to homepage" describing a
  placeholder-href element — this check is `opportunities[]`-only in this
  build (see `cross-page-checks.md` §3); phrase as a verification
  suggestion, never a diagnosed defect
- A specific fact, number, or named capability in an `opportunities[]`
  entry's `summary`/`rationale` with no `evidence` field backing it (e.g.
  a review count, a named integration the site "already has") — either add
  the `evidence` field or rewrite the entry as a general, non-fact-specific
  recommendation

Correct pattern: state the mechanical fact and its scope, then (if useful)
a bounded, non-certain risk framing — "may make this control harder for an
assistant or screen-reader user to disambiguate," not "will cause task
failure."

## Final self-check before emitting (mechanical — run the script, don't do it by hand)

`summary` must be recomputed by literally counting `findings[]` entries,
one severity at a time — `summary.critical = count(findings where
severity == "critical")`, and likewise for `high`, `medium`, `low`, with
`summary.total_findings == len(findings)` and
`critical + high + medium + low == total_findings`. A report that had
the *total* right but the *breakdown* wrong (e.g. a low-severity finding
silently counted as high) has happened in practice.

This used to be a manual arithmetic step and was a real source of slow,
error-prone report assembly. `scripts/validate_report.py --write` now
does exactly this recomputation, plus the required-field/enum checks
above, deterministically in well under a second — see `SKILL.md` Step 8.
Run it; don't re-derive this by hand.
