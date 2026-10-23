# Cross-Page & Entity Consistency Checks (run once, across the whole batch)

**Read `evidence-states.md` first — especially its "Capability note."**
These checks require the strongest reconciliation discipline in the whole
skill, because they produce the highest-confidence findings when done
right (see the gold-standard pattern in `regression-cases.md`) and the
most damaging false positives when done wrong (see the false-positive
patterns in the same file).

Inputs available: `pages` — array of `{url, raw_html, title, meta_tags,
canonical, json_ld, interactive_elements}` for every sampled page (all
from `scripts/parse_dom_lite.py`, parsed from raw HTML only — no
rendered DOM in this build) — and `sitemap_urls` (may be empty).

## 1. Entity identity consistency

1. Extract organization/name/address strings from each page's footer,
   About section, and any JSON-LD `Organization` block.
2. Normalize legal suffixes (Private Limited/Pvt Ltd/Ltd/LLP/Inc/Corp/LLC)
   and compare only the remaining core name.
3. **Gate:** only record `contradictory` when the **same entity role**
   (e.g., "seller of record," "importer/marketer") is stated with
   **incompatible values** (different core name, or different address for
   what claims to be the same legal entity) across two representations
   that both fetched successfully. Preserve which representation each
   value came from (footer vs. JSON-LD vs. About page) — do not flatten
   this into a single "names disagree" statement.
4. If only one representation exists, or the comparison would require
   guessing which entity role a string refers to, record
   `insufficient_evidence` rather than flagging.
5. **Marketplace guard:** if different sampled pages are different
   products/listings that each declare their *own* seller/importer of
   record (a multi-seller marketplace pattern), different sellers across
   *different* products is expected structure, not an inconsistency —
   only flag when the **same** entity role on the **same** product/page
   states incompatible values. Do not compare a seller string on one
   product page against a seller string on an unrelated product page and
   call it a contradiction.
6. Frame any resulting finding as "not machine-resolvable within this
   site" — never as fraud. Cap severity at medium; this check's
   false-positive risk against legitimate DBA/multi-brand/multi-location/
   multi-seller-marketplace structures is real and documented (see
   `regression-cases.md`).

## 2. Same-entity, same-attribute fact-pair disagreement

This is the check that a real same-page country-of-origin/address
contradiction case validates as the gold-standard positive pattern — and
that other field-testing cases show how easy it is to get wrong (see
`regression-cases.md`).

1. Use a small, fixed trigger-phrase list: "return", "warranty",
   "shipping", "price valid until", "cancellation", "country of origin".
2. For each trigger phrase, extract the nearest numeric/date/text value on
   each page, **and the surrounding context** (any qualifying clause —
   e.g., "for Paytm orders," "eligible categories," "except").
3. **Gate — before flagging anything, confirm all four:**
   - Same entity (same product / same named legal entity).
   - Same attribute (the same trigger phrase / same real-world fact).
   - Incompatible values.
   - Both source representations fetched successfully (not
     `fetch_degraded`).
4. **If a qualifying context clause is present on either side** (e.g., a
   payment-method-specific shipping threshold, a category exception),
   this is **not** a plain contradiction — record it as
   `CONFIRMED_WITH_CONTEXT` and preserve both values and both contexts in
   the evidence. Do not suppress it (the underlying difference is real and
   worth surfacing) and do not flatten it into an unqualified
   contradiction (that overstates the problem — see the ₹299/₹399
   Paytm-clause case in `regression-cases.md`).
5. If no qualifying context is found and the four gate conditions hold,
   record plain `contradictory` — this is eligible for a real finding.
6. Report only a single, clearly conflicting pair per trigger phrase per
   product/entity — do not compound multiple weak signals into one
   finding.

## 3. Placeholder/empty navigation targets (downgraded from "orphaned navigation" — opportunities only, never a scored finding)

**This check was retired as a scored `findings[]` mechanism in the
no-render build, and here is exactly why, stated plainly per this
project's own evidence-discipline rule:** the original check's gate
required distinguishing `destination_unknown`/`empty_href` (a real
problem) from `javascript_route` (a completely legitimate, extremely
common progressive-enhancement pattern — a real `<a href>` intercepted by
a client-side router for a smoother transition). That distinction is only
resolvable by actually activating the element and observing whether the
browser's route changes — i.e., executing JavaScript. Without that, any
attempt to still call this a confirmed finding would systematically
false-positive on a large fraction of modern sites (any site using
client-side routing at all), which is precisely the false-positive shape
`regression-cases.md` exists to prevent. See `navigation-states.md` for
the full state taxonomy this reasoning is built on.

What raw HTML **can** still honestly support: identifying elements whose
**static** href is a placeholder (`#`, `javascript:void(0)`, or missing
entirely) on an element with real link-like visible text, that also has
no matching entry in `sitemap_urls`. This is genuine, observable evidence
— but it cannot distinguish "broken" from "JS-enhanced and working fine,"
so it belongs in `opportunities[]` (a suggestion to verify), never in
`findings[]` (a diagnosed problem):

1. Build the union of raw-HTML `<a href>` targets (non-placeholder) across
   all pages in `pages`.
2. From `interactive_elements`, collect elements with a placeholder or
   missing `href` and non-trivial `accessible_name`.
3. For each, check `sitemap_urls` for anything that plausibly corresponds
   (by accessible-name/slug similarity) — if a plausible match exists,
   drop it; this is very likely a legitimate JS-routed link.
4. Whatever remains goes into `opportunities[]` only, phrased as: "N
   elements with placeholder hrefs and no obvious sitemap match were
   found on the sampled pages — this may be intentional client-side
   routing (in which case no action is needed) or a genuine gap; a tool
   capable of executing JavaScript would be needed to tell the two apart
   with confidence." Never assign a `severity`, never call it "orphaned"
   or "broken" in the summary/rationale text, and never let it appear in
   `findings[]` regardless of how many are found.

## Output shape

```json
{
  "mechanism": "fact-pair-disagreement",
  "page_urls": ["https://example.com/shipping-policy", "https://example.com/paytm-offer-terms"],
  "evidence_state": "CONFIRMED_WITH_CONTEXT",
  "values": [
    { "value": "₹399", "context": "standard site shipping policy" },
    { "value": "₹299", "context": "Paytm-specific offer terms" }
  ],
  "scope": "page_local",
  "time": "confirmed_currently",
  "category": "discoverability"
}
```
Return `[]` if nothing fires — do not fabricate a finding to avoid an
empty result.
