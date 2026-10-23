# Interaction Purpose States

A location-gated availability check (e.g. a pincode/ZIP lookup) was
once wrongly treated as an engagement defect during field testing. `interaction_required` is an observation, not a
diagnosis — it must always be classified into one of the categories below
before it can factor into any finding.

## Categories

- `contextual_computation` — the interaction supplies context needed for a
  legitimately variable answer (e.g., a pincode/ZIP for delivery
  availability, a size selector for stock-per-variant). **Never** a
  defect by itself — this is normal, expected behavior for
  location/variant-dependent data.
- `content_retrieval` — the interaction reveals content that could, in
  principle, have been static (e.g., a "read more" that hides a
  description already present elsewhere in the DOM). Only worth surfacing
  as a low-severity opportunity, and only if the same fact is **also**
  `not_observed` in raw/metadata/structured data after reconciliation —
  if the fact is available elsewhere without interaction, this is not
  worth flagging at all.
- `navigation` — the interaction is a normal step in getting from one page
  to another (a menu toggle, a "next" button). Not a finding.
- `optional_ui` — accordions, tabs, tooltips, and similar UI that hide
  secondary/supplementary information by design. Not a finding.
- `progressive_enhancement` — a real `<a href>` intercepted by a client-side
  handler for a smoother transition. Not a finding — this is correct
  engineering, not an obstacle. (See also `navigation-states.md`'s
  `javascript_route`.)
- `machine_unresolvable` — the control has no accessible name, no
  resolvable destination, and no structural way for an automated agent (or
  assistive technology) to determine its purpose or outcome before
  activating it. This is the **only** category that may, on its own,
  support an engagement-difficulty finding — and even then the finding
  must be framed as increased difficulty risk, never a guaranteed failure
  (per the language guard in `severity-rules.md`).

## Rule

**No-render build note:** without JavaScript execution, this skill
cannot actually click/activate anything to observe `interaction_required`
in the first place — it can only infer that an interaction *might* be
needed from static signals (e.g. a variant selector present in raw HTML
with no default-selected price nearby). Treat any such inference as
`insufficient_evidence` by default rather than confidently classifying it
into one of the categories above, unless the raw markup itself makes the
behavior unambiguous (e.g. a `<select>` with no option marked `selected`
and no price anywhere in the raw content). `machine_unresolvable` in
particular now requires that the control have no accessible name **and**
no resolvable destination as literally present in raw HTML — it can no
longer be confirmed by testing what a click actually does.

`interaction_required` alone never crosses the diagnosis gate. Classify it
first. Only `machine_unresolvable` (optionally combined with
`content_retrieval` blocking a load-bearing fact that's confirmed absent
elsewhere) may become a finding, and it is capped at medium severity with
explicit "may increase difficulty" language.
