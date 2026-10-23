# Navigation Destination States

**No-render build note:** this file's full state taxonomy is preserved
as documentation of *why* `cross-page-checks.md` §3 was downgraded to an
`opportunities[]`-only signal. `destination_resolved_internal`,
`destination_resolved_external`, and especially `javascript_route` all
require actually activating an element and observing the resulting
browser navigation — none of that is possible without executing
JavaScript, so none of these states can be produced by this build.
Everything this build can actually observe reduces to a **static** href
being present, a real internal path, or a placeholder (`#`,
`javascript:void(0)`, missing) — see `cross-page-checks.md` §3 for the
resulting opportunities-only check.

A recurring false positive during field testing was exactly this: an
unresolved link target got written up as "resolves to homepage" or
"broken navigation" without actually proving either. Use this explicit taxonomy instead of a
binary resolved/broken judgment.

## States

- `destination_resolved_internal` — following the link (or resolving the
  client-side route) lands on a distinct internal page. Not a finding.
- `destination_resolved_external` — resolves to a distinct external
  domain. Not a finding by itself.
- `destination_homepage` — use **only** when the actual resolved URL,
  after following any redirects, is verifiably the site's homepage. Do not
  assign this state just because resolution was unclear — that is
  `destination_unknown`, not this.
- `empty_href` — the raw `<a>` element has an empty, `#`, or
  `javascript:void(0)` href, with no accompanying client-side router that
  changes the URL on activation.
- `javascript_route` — the element has no meaningful raw `href`, but
  activating it (per the rendered DOM's event bindings) changes the
  browser's route to a real, distinct URL. This is the legitimate
  progressive-enhancement pattern and must **not** be flagged as broken.
- `destination_unknown` — resolution was attempted but the outcome could
  not be determined (e.g. the client-side router's target couldn't be
  statically inferred from the rendered DOM).
- `unresolved_due_to_fetch_failure` — resolution could not be attempted at
  all because the fetch itself failed (timeout, non-2xx, blocked). This is
  a fetch problem, not a navigation-design problem — do not conflate the
  two in the finding text.

## Gate before flagging a navigation finding (historical — kept for context; not reachable in this build)

This was the original gate for a **scored finding**. In this build,
`cross-page-checks.md` §3 never produces a `findings[]` entry at all
(only, at most, an `opportunities[]` suggestion) precisely because step 1
below can no longer be satisfied honestly — `javascript_route` is
unobservable without a real render, so it can never be ruled out. Kept
here so the reasoning stays legible if a future build re-adds rendering.

A navigation item could only be written up as a finding (e.g. "orphaned
client-side-only navigation") when **all** of the following held:

1. Its state is `destination_unknown` or `empty_href` (not
   `javascript_route`, not `unresolved_due_to_fetch_failure`).
2. It has no matching entry in `sitemap.xml`.
3. The check was reproduced on a second look at the same rendered DOM (not
   a single noisy parse) — this guards against transient render timing
   issues being mistaken for a structural problem.

If any of these three don't hold, record the more precise state
(`unresolved_due_to_fetch_failure`, `javascript_route`, etc.) as neutral
coverage evidence, not as a finding.
