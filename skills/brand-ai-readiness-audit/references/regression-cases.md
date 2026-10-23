# Regression Patterns (from field testing — check new findings against these)

These are generalized error *shapes* observed during field testing across
several live e-commerce sites. They are documented here as patterns to
recognize on **any** unseen site — not as a fixed list of sites to
special-case. Before finalizing any finding of type fact-cross-
representation, entity identity, fact-pair-disagreement, navigation, or
claim-support, check whether it matches one of the false-positive shapes
below without stronger evidence than what's documented here as
insufficient. If it does, downgrade to `insufficient_evidence` or drop it.

## Known false-positive shapes — do not reproduce these without stronger evidence

**Pattern: unresolved link mistaken for a specific destination.** A
site's nav labels had unresolved client-side routing targets; these were
reported as "resolving to the homepage" or as "broken navigation" without
actually verifying either. **Correct behavior:** unresolved destinations
must be recorded as `destination_unknown` or
`unresolved_due_to_fetch_failure`, never `destination_homepage`, unless
the actual resolved URL is verified to be the homepage.

**Pattern: single-representation gap mistaken for absence.** A product
description was called "absent" based on one retrieved representation of
the page. **Correct behavior:** record `not_observed`/
`insufficient_evidence` for that representation, scoped `page_local`; do
not claim the description is absent without checking rendered/
structured-data representations too.

**Pattern: stale reconciliation mistaken for a current defect.** A price
was reported as "metadata-only" based on an earlier check, without
re-reconciling against the current rendered/visible content. **Correct
behavior:** always reconcile against the current state at audit time
before asserting a fact is locked to one representation — this specific
shape turned out to be a false positive once current-state reconciliation
was applied.

**Pattern: point-in-time observation presented as a permanent property.**
Facts were reported as "unavailable before rendering" without preserving
whether this reflected historical or current behavior. **Correct
behavior:** use the time states in `scope-and-time.md`
(`confirmed_currently` vs. `historically_supported_but_changed`) rather
than presenting a point-in-time observation as a permanent property.

**Pattern: fetched-representation gap mistaken for site-wide absence.**
Policy text was reported "absent" based on the fetched policy page shell.
**Correct behavior:** the safer claim is non-observation in the retrieved
representation (`page_local`, `not_observed`), not universal absence.

**Pattern: legitimate contextual interaction mistaken for an engagement
defect.** Location-gated availability (e.g., a delivery check requiring a
postal code) was treated as an engagement problem. **Correct behavior:**
classify as `contextual_computation` per `interaction-states.md` — this is
legitimate, location-dependent behavior, not a defect.

**Pattern: "no support detected" mistaken for "claim is false."** A
claim-support check inferred weakness from promotional wording, while
concrete supporting facts existed elsewhere on the same page. **Correct
behavior:** search the whole page before concluding
`SUPPORT_NOT_OBSERVED`; even then, that state is weaker than "unsupported
claim" and must be reported as such, at low severity and confidence.

**Pattern: multi-seller marketplace structure mistaken for entity
inconsistency.** On a marketplace-type site (many independent sellers
listing under one platform), different products legitimately declare
different sellers/importers of record. **Correct behavior:** the
entity-identity check only compares the same entity role on the same
product/page across representations (see the marketplace guard in
`cross-page-checks.md` #1) — never across two unrelated products just
because they're on the same domain.

**Pattern: an ungrounded ad hoc check introduced at execution time.** A
generic "page X is missing a meta description / canonical tag" finding
was produced without any corresponding entry in `page-level-checks.md`,
meaning it had no defined gate, severity cap, or research traceability —
it happened to be reasonable, but arrived through the system's checks
rather than through it. **Correct behavior:** only run checks enumerated
in `page-level-checks.md`/`cross-page-checks.md`; if a new check seems
warranted, either it belongs as a properly documented, gated check (see
`page-level-checks.md` §2b for how this specific one was formalized) or it
stays as a Step-7 `opportunities[]` suggestion, never a silently-invented
`findings[]` entry.

**Pattern (no-render build specific): guessing at JavaScript behavior
from static markup.** An element with a placeholder href (`#`,
`javascript:void(0)`, missing) was reported as "broken navigation"
without any way to actually test whether a client-side router intercepts
it — which is exactly the legitimate, extremely common
progressive-enhancement pattern (`javascript_route` in
`navigation-states.md`). **Correct behavior:** without a real render,
this distinction cannot be made at all — see `cross-page-checks.md` §3,
which downgrades this entire mechanism to an `opportunities[]`-only
verification suggestion rather than guessing. The general lesson: when a
capability gap (no JS execution) makes two very different real-world
explanations indistinguishable from the available evidence, the correct
response is to weaken the check's output shape (finding → opportunity, or
opportunity → nothing), not to keep guessing at higher confidence than
the evidence supports.

## Known true-positive shape — the gold-standard pattern to preserve

**Pattern: same entity, same attribute, genuinely incompatible values,
both representations fetched cleanly.** In one case, the same product
page stated two different countries of origin in two different page
sections. In another, the same named legal entity had two different
addresses on the same product page. Both are exactly what a
`contradictory` fact-pair finding should look like: same entity, same
attribute, incompatible values, both representations fetched
successfully. High confidence, high severity, and the source
representation for each value preserved (not flattened).

**Pattern: a real numeric contradiction with a preserved qualifying
context.** A general shipping-policy threshold differed from a
payment-method-specific offer's threshold on the same site. The
underlying values genuinely disagreed, but the payment-method context was
a real, stated qualifier. **Correct behavior:** record this as
`CONFIRMED_WITH_CONTEXT` (preserve both values and both contexts), not a
flattened, context-free contradiction, and not suppressed either.

**Pattern: claims that exist but lack detected nearby support.** Brand
claims were flagged as unsupported because no nearby certification/test
reference was detected. **Correct behavior:** the claims exist and were
observed; lack of detected nearby support is `SUPPORT_NOT_OBSERVED`, not
proof the claims are false or globally unsupported — keep this at low
severity/confidence regardless of phrasing.

## How to use this file

The point is the *shape* of each error, which will recur on sites this
skill has never seen. When a check is about to produce a finding, ask:
"does this match a known false-positive shape (declared destination/
absence/unsupported-claim without full reconciliation), or does it match
the known true-positive shape (same entity + same attribute +
incompatible values, fully reconciled)?" Answer that before finalizing
severity, confidence, and priority. Do not key any check's logic to a
specific brand, domain, or site structure — these patterns must transfer
to unseen sites, which is the whole point of documenting them abstractly.
