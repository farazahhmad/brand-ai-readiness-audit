# Scope and Time States

## Scope — never let a small sample become a site-wide claim

- `page_local` — the condition was observed on exactly one sampled page.
  Default assumption unless proven otherwise.
- `sampled_pages` — the condition was observed consistently across the
  small bounded sample (typically 2–3 pages), but the full site was not
  checked. This is the **maximum** scope this skill can honestly claim in
  a normal run.
- `site_wide` — reserved for conditions verified against a site-level
  artifact itself (e.g., a `robots.txt` rule, which by definition applies
  site-wide). Do not assign this to a content/structure finding based on a
  bounded page sample.
- `unknown` — scope could not be determined (e.g., the sample was too
  degraded to tell how representative it is).

### Rule
Every finding must carry an explicit scope. Report language must match it:
"the sampled pages lack X," not "the site lacks X," unless scope is
genuinely `site_wide`. This directly addresses the recurring pattern of
a one-page observation being written up as a general site property.

## Time — separate current state from historical claims

- `confirmed_currently` — observed in this run, right now. This is the
  default and, for a normal single-pass audit with no prior baseline, the
  only state you'll usually need.
- `historically_supported_but_changed` — use only when this audit has
  access to a specific prior claim (e.g., from `regression-cases.md` or a
  previous report the user supplied) and the current run does not
  reproduce it. Do not conclude the earlier claim was false — the site may
  simply have changed.
- `not_reproducible_now` — a previously reported condition could not be
  reproduced in this run, but there isn't enough information to say
  whether the site changed or the original observation was itself
  degraded/wrong. Prefer this over silently dropping the discrepancy or
  silently asserting either side is correct.
- `unverifiable` — no baseline exists to compare against, and no
  meaningful time claim can be made either way.

### Rule
If this skill is being re-run against a site with a known prior audit
(e.g., one of the four regression sites), it must use these states rather
than silently overwriting the old result or treating the new result as
automatically authoritative.
