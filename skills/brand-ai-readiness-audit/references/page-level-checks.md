# Page-Level Checks (run once per sampled page)

**Read `evidence-states.md` first — especially its "Capability note" at
the top.** This build never executes JavaScript. Every check below runs
against raw, server-delivered HTML plus whatever `parse_dom_lite.py`
extracts from it (title, meta tags, canonical, JSON-LD, interactive
elements, an approximate visible-text string) — never a real render.
Every check below produces evidence states, not diagnoses. A check may
only escalate to a finding after the reconciliation and gating rules
stated inline here, cross-referenced with `severity-rules.md`.

**Only run the checks enumerated in this file and `cross-page-checks.md`.**
Do not invent an additional ad hoc check at execution time just because
something looks off on a specific site — every check here traces to a PS
Appendix A–F mechanism or a verified paper (see the Lead Research Auditor
Report), and an untraceable check risks being arbitrary rather than
generalizable. If something noteworthy is observed that doesn't fit an
existing check, it can still be surfaced as a Step-7 `opportunities[]`
entry (never a scored `findings[]` entry) rather than being silently
scored under a check_id that was never defined.

Inputs available for each page: `url`, `raw_html`, `title`, `meta_tags`,
`canonical`, `json_ld`, `interactive_elements` (all from
`scripts/parse_dom_lite.py`, parsed from raw HTML only), and an optional
`page_type_hint`.

## 1. Fact cross-representation check (no-render build — heuristic only)

There is no rendered DOM in this build, so the original three-way
compare (raw vs. rendered vs. metadata/structured-data) collapses to a
**two-way** compare: metadata/structured data vs. raw HTML body text —
both of which come from the exact same single fetch, so they can never
meaningfully disagree with each other about presence. What this check
can still honestly do is exactly what a non-rendering AI crawler itself
experiences: **does the fact appear anywhere in the server-delivered
content at all?**

For each field in the fixed list (title/H1, price, availability, address,
primary claim):

1. Check for presence in raw HTML body text, `meta_tags`, and `json_ld`.
   Record `present_in_raw` / `present_in_metadata` /
   `present_in_structured_data` for each that succeeds; `not_observed`
   for each that doesn't. **`present_in_rendered` and
   `present_after_interaction` cannot be produced in this build — do not
   claim either state; see `evidence-states.md`.**
2. If **none** of raw/metadata/structured-data show the fact, run the
   heuristic client-side-rendering-likelihood check in §7 against the
   same raw content. If it fires, the correct, capped-confidence
   observation is `heuristic_client_side_rendering_suspected` — **not**
   a confirmed render-parity gap (that confirmation is structurally
   unavailable without executing JavaScript). If it doesn't fire, this is
   `insufficient_evidence` / `absent` per the existing rule below —
   record honestly, don't guess which explanation applies.
3. **Reconciled outcome:**
   - If observed in any of raw/metadata/structured-data → `observed`,
     not a finding by itself; may still feed the mismatch check in §3.
   - If `not_observed` in **all** representations checked, **and** §7's
     heuristic fires → `heuristic_client_side_rendering_suspected`,
     capped low confidence/severity per `severity-rules.md`. Phrase as "not
     observed in the server-delivered content of this sampled page, and
     the page shows markers commonly associated with client-side
     rendering" — never "missing from the site," never "confirmed
     JS-only."
   - If `not_observed` in all representations and §7 does **not** fire →
     record `insufficient_evidence` or, if genuinely exhausted every
     representation available in this build, `absent` — scoped
     `page_local` — phrased as "not observed in any checked
     representation of this sampled page," not "missing from the site."
   - If any fetch involved was `fetch_degraded` or `extractor_degraded`
     (including `dom_parse_degraded` from `parse_dom_lite.py`), record
     that explicitly and do not treat the resulting `not_observed` as
     informative about the page's actual content.

## 2. Structured-data presence & validity

Check `json_ld`/Microdata for a type appropriate to `page_type_hint`.
Absence is **not** automatically a defect — first confirm `page_type_hint`
itself is reasonably confident (based on URL path, nav context, or visible
page content). If page type is ambiguous, record `insufficient_evidence`
rather than flagging absence. If page type is confident and the
appropriate structured-data type is absent or missing a required property,
that may become a finding, scoped `page_local`.

## 2b. Basic on-page metadata presence (title, meta description, canonical)

Distinct mechanism from #2 above — this is about the page's basic
readability/quotability, not its schema.org structured data.
Research grounding: PS Appendix B ("the pages that get picked as sources
tend to be the ones a machine could easily reach, easily read, and easily
quote a clear fact from") — a missing title/meta description removes the
exact text many summarization and snippet pipelines quote first; a
missing canonical link on a duplicated-content-prone page makes the
canonical source ambiguous to a crawler.

1. Only run this on a page whose `page_type_hint` is confidently a
   brand-identity or primary-content page (home, about, product, category)
   — **not** a legal/utility page (privacy policy, terms, sitemap page)
   where absence is common and low-impact; if page type is ambiguous,
   record `insufficient_evidence`.
2. Check `title`, `meta_tags` (for a non-trivial `description`), and
   `canonical` — all already extracted from raw HTML by
   `parse_dom_lite.py`.
3. **Gate:** the element is confirmed absent on a non-`fetch_degraded`,
   non-`dom_parse_degraded` fetch. Absence of just one of the three (e.g.
   canonical only) is a real but narrower finding than absence of all
   three — report exactly which element(s) were checked and found absent,
   don't bundle unrelated absences into one vague finding.
4. Use `check_id: "basic-metadata-absence"` — keep separate from
   `structured-data-absence` (JSON-LD/Microdata, check #2 above); they are
   different mechanisms with different severity ceilings (see
   `severity-rules.md`).
5. Severity is capped at medium (see `severity-rules.md`) — this is a
   foundational readability signal, not a load-bearing fact by itself.

## 3. Cross-representation reconciliation: price/availability

Only compare JSON-LD-declared price/availability against visible
page content (`visible_text_approx`) if the fetch succeeded (not
`fetch_degraded`/`dom_parse_degraded`). Normalize currency before comparing.
If both sides are clean and disagree, this is a `contradictory` evidence
state for the same entity (this page/product) and same attribute (price)
— eligible to become a finding per the diagnosis gate in
`severity-rules.md`. If the fetch was degraded, record
`fetch_degraded`/`extractor_degraded` instead of `contradictory`.

## 4. Claim-support check (experimental — keep conservative)

Identify factual/promotional claims in `visible_text_approx`. Search the
**whole page** (not just the immediately adjacent paragraph) for a nearby
structured, checkable statement (a cited figure, linked source, dated
stat, or certification reference) before concluding anything. If none is
found, record `SUPPORT_NOT_OBSERVED` — **never** "unsupported claim" or
"claim is false." This check stays experimental: cap it at low severity
and low confidence regardless of how many claims lack detected support,
and never score by raw digit/keyword density.

## 5. Fact-extractability shape

For a fact confirmed `observed` somewhere, check whether it's stated as a
short, self-contained, labeled unit versus requiring assembly across
multiple sentences. This is a structural test, scoped `page_local`, not a
length penalty.

## 6. In-page interactive-label collision (raw-HTML-visible elements only)

Parse `interactive_elements` from `parse_dom_lite.py`'s output. Hash
accessible-name → destination (`href`) pairs. Flag name collisions or
ungrouped-flat-duplicates. Do not flag a single label repeated inside one
clearly labeled `<nav>` or a well-structured mega-menu.

**No-render caveat — read before running this check:** this only sees
interactive elements that are literally present in the server-delivered
HTML. On a server-rendered (SSR/SSG/traditional) page this is the real,
complete picture. On a heavily client-side-hydrated page, elements added
or re-labeled by JavaScript after load are **structurally invisible**
here — this is a false-negative risk (the check may under-report), never
a false-positive risk (it cannot invent a collision that isn't in the raw
markup). Do not describe a "no collisions found" result on a page the
heuristic in §7 flags as likely CSR as if it were a confirmed clean
result — record it as `insufficient_evidence` for that specific page
instead, since the real interactive surface wasn't observable.

**Reproduction requirement dropped from this build:** the original
"reproduce on a second parse" rule existed to guard against a live
browser's render-timing flakiness. Parsing the same already-fetched raw
HTML twice is deterministic — it cannot produce a different result — so
that specific guard no longer applies; the well-structured-nav exclusion
above still does.

## 7. Heuristic client-side-rendering likelihood (this build's only signal for JS-render risk — always run)

**In earlier builds of this skill that had real headless rendering
available, this heuristic was only a fallback used when a true render
wasn't possible. In this build there is no true render at all, so this is
the sole, always-run signal for "this page might depend on JavaScript to
show its real content."** It is a deterministic, explainable pattern
check on the raw content — but it is an **inference about likelihood**,
not a confirmed observation, and must never be treated as equivalent to
an actual `present_in_rendered`/`not_observed` result (which this build
cannot produce at all — see `evidence-states.md`).

Look for markers commonly left behind by client-side-rendering
frameworks, using the raw HTML `parse_dom_lite.py` already extracted from
whatever the native fetch tool returned. **Caveat:** this assumes the
fetched HTML still has intact `<script>` tag content. Some native fetch
tools strip or summarize scripts as part of their own text-extraction —
if that happened for a given page, both marker groups below may be
under-detected on it; see `parse_dom_lite.py`'s module docstring and
record that explicitly rather than treating "no markers found" as a
confirmed clean result for that page.

**Structural markers:**
- A hydration/state-embedding script tag or global (e.g. a script
  containing `__NEXT_DATA__`, `__NUXT__`, `window.__INITIAL_STATE__`, or
  a similarly named embedded-JSON blob).
- A near-empty root container (e.g. `<div id="root">` or `<div id="app">`
  with little or no visible text as a direct child) immediately followed
  by references to bundled/chunked JavaScript files.

**Text-only behavioral markers:**
- The URL path matches a commerce listing/detail pattern (contains
  `/product`, `/p/`, `/shop`, `/category`, `/s/`, a SKU-like segment, or
  similar), **and**
- `visible_text_approx` contains navigation/category/promotional content
  but **no price-like pattern** (currency symbol or code plus a number)
  and **no item-level purchase call-to-action** ("add to cart," "add to
  bag," or a genuine "buy now" tied to a specific item — **not** generic
  promotional/banner phrasing like "shop now," which appears on category
  pages regardless of whether individual item data loaded, and must be
  excluded from this marker or it silently masks the exact case this
  check exists to catch).

**Gate:** flag `heuristic_client_side_rendering_suspected` if **either**
one structural marker is found, **or** both parts of the text-only
behavioral marker are found together (URL pattern AND absent
price/CTA — either alone is too weak and common on legitimately
non-commerce pages to flag by itself), with the specific markers found as
`raw_evidence`. This is capped at **low confidence** in
`severity-rules.md` regardless of how many markers are found, and must be
phrased as a suggestion to verify with a true rendering tool (an
`opportunities[]` entry, or a low-severity finding at most) — never as a
confirmed render-parity defect.

## Output shape

Each check returns a raw evidence observation — not a finding:
```json
{
  "mechanism": "fact-cross-representation",
  "page_urls": ["https://example.com/product/a"],
  "evidence_state": {
    "present_in_raw": false,
    "present_in_metadata": false,
    "present_in_structured_data": false,
    "heuristic_client_side_rendering_suspected": true,
    "fetch_degraded": false
  },
  "field": "price",
  "scope": "page_local",
  "time": "confirmed_currently",
  "category": "discoverability"
}
```
This observation is handed to Step 4 (Reconcile & Diagnose) in the main
`SKILL.md` procedure — it is not itself a finding until it passes the gate
in `severity-rules.md`.
