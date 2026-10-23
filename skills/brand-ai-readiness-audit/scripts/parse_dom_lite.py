#!/usr/bin/env python3
"""
parse_dom_lite.py — extract structural signals (title, meta tags,
canonical link, JSON-LD blocks, interactive elements, an approximate
visible-text string) from RAW, SERVER-DELIVERED HTML only.

This is the no-Chromium replacement for what render_page.py used to
extract from a real headless render. It is intentionally named "lite" —
stdlib `html.parser` only, no third-party dependency, no browser, no
JavaScript execution of any kind. That is the whole point of this build:
see references/runtime-budget.md for why rendering was removed entirely,
and references/evidence-states.md for the resulting, explicitly narrower
capability boundary (this skill can now only ever see what a
non-rendering crawler sees — it can no longer confirm what a page looks
like AFTER JavaScript runs).

Consequences worth stating plainly:
- On a server-rendered (SSR/SSG/traditional multi-page) site, this
  extracts real, complete interactive-element/structured-data
  information — nothing is lost for that class of site.
- On a pure client-side-rendered (CSR) SPA, the raw HTML is often a
  near-empty shell (a `<div id="root">` plus bundled `<script>` tags), so
  `interactive_elements`/`visible_text_approx` will legitimately come back
  sparse or empty. That is not a parsing failure — it's the actual raw
  content a non-rendering crawler receives — and is exactly what
  `page-level-checks.md` §7's heuristic markers exist to flag.

Usage:
    python3 parse_dom_lite.py <path-to-fetch-results.json> [--write]
    cat fetch_results.json | python3 parse_dom_lite.py - [--write]

Input: a JSON object in this shape —
    {"results": [{"url": ..., "ok": true, "html": "...", ...}, ...], ...}
This build has no fetching script of its own (see SKILL.md Step 1): the
invoking agent fetches each sampled page with its own native fetch tool,
then assembles this JSON itself (one entry per page: `url`, `ok`, and
`html` if the fetch succeeded, else `ok: false` and whatever
`fetch_degraded`/`degraded_reason` fields are relevant). This script only
consumes that shape — it doesn't care which mechanism produced it.

Output: the same object, with each result that had `ok: true` augmented
with: title, meta_tags, canonical, json_ld, interactive_elements,
visible_text_approx, dom_parse_degraded, dom_parse_degraded_reason.
Results that were not `ok` (fetch_degraded) are passed through unchanged
— there is no HTML to parse. Always exits 0.

Caveat worth noting explicitly: some native fetch tools strip or don't
return raw <script> tag content as part of their own text-extraction
step. If that happens, JSON-LD (which lives inside a
<script type="application/ld+json"> tag) and the structural markers in
page-level-checks.md §7 may be under-detected — this shows up here as an
empty `json_ld` list even though the page may genuinely have some. Don't
treat that silently as confirmed absence; see evidence-states.md.
"""
import argparse
import json
import sys
from html.parser import HTMLParser

INTERACTIVE_ROLES = {"link", "button"}
INTERACTIVE_TAGS = {"a", "button"}
TEXT_SKIP_TAGS = {"script", "style"}


class LiteDOMParser(HTMLParser):
    """A best-effort, stdlib-only structural parser for raw HTML. Not a
    real DOM — no CSS visibility, no JS execution, no malformed-HTML
    recovery beyond what html.parser itself tolerates. See module
    docstring for what that means in practice."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = None
        self.meta_tags = {}
        self.canonical = None
        self.json_ld_raw = []
        self.interactive_elements = []
        self._visible_text_parts = []

        self._in_title = False
        self._title_captured = False
        self._skip_depth = 0  # inside <script>/<style>
        self._in_ld_json = False
        self._ld_json_buffer = []
        self._interactive_stack = []

    def _is_interactive(self, tag, attrs_d):
        return tag in INTERACTIVE_TAGS or attrs_d.get("role") in INTERACTIVE_ROLES

    def _push_interactive(self, tag, attrs_d):
        self._interactive_stack.append({
            "tag": tag,
            "href": attrs_d.get("href"),
            "role": attrs_d.get("role"),
            "aria_label": attrs_d.get("aria-label"),
            "text_parts": [],
        })

    def _pop_interactive_if_matches(self, tag):
        if self._interactive_stack and self._interactive_stack[-1]["tag"] == tag:
            el = self._interactive_stack.pop()
            text = " ".join("".join(el["text_parts"]).split())
            accessible_name = (el["aria_label"] or text or "").strip()[:200]
            self.interactive_elements.append({
                "tag": el["tag"],
                "href": el["href"],
                "accessible_name": accessible_name,
                "role": el["role"],
            })

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)

        if tag == "title":
            if not self._title_captured:
                self._in_title = True
            # else: a later <title> (e.g. inside an inline <svg> icon,
            # used for accessible icon names) — intentionally ignored so
            # it doesn't get concatenated onto the document title.
        elif tag == "link" and (attrs_d.get("rel") or "").lower() == "canonical":
            self.canonical = attrs_d.get("href")
        elif tag == "meta":
            name = attrs_d.get("name") or attrs_d.get("property")
            content = attrs_d.get("content")
            if name and content:
                self.meta_tags[name] = content
        elif tag in TEXT_SKIP_TAGS:
            self._skip_depth += 1
            if tag == "script" and (attrs_d.get("type") or "").lower() == "application/ld+json":
                self._in_ld_json = True
                self._ld_json_buffer = []

        if self._is_interactive(tag, attrs_d):
            self._push_interactive(tag, attrs_d)

    def handle_startendtag(self, tag, attrs):
        # Self-closed tag, e.g. <meta ... /> or an unusual <a .../>.
        self.handle_starttag(tag, attrs)
        if tag == "title":
            self._in_title = False
            self._title_captured = True
        if tag in TEXT_SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            if tag == "script" and self._in_ld_json:
                self._in_ld_json = False
        self._pop_interactive_if_matches(tag)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
            self._title_captured = True
        elif tag in TEXT_SKIP_TAGS:
            if tag == "script" and self._in_ld_json:
                raw = "".join(self._ld_json_buffer).strip()
                if raw:
                    self.json_ld_raw.append(raw)
                self._in_ld_json = False
            self._skip_depth = max(0, self._skip_depth - 1)
        self._pop_interactive_if_matches(tag)

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data
        if self._in_ld_json:
            self._ld_json_buffer.append(data)
        if self._interactive_stack:
            self._interactive_stack[-1]["text_parts"].append(data)
        if self._skip_depth == 0:
            self._visible_text_parts.append(data)

    def visible_text_approx(self, limit=20000):
        text = " ".join("".join(self._visible_text_parts).split())
        return text[:limit]


def parse_html(html: str) -> dict:
    result = {
        "title": None,
        "meta_tags": {},
        "canonical": None,
        "json_ld": [],
        "interactive_elements": [],
        "visible_text_approx": "",
        "dom_parse_degraded": False,
        "dom_parse_degraded_reason": None,
    }
    parser = LiteDOMParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as e:  # noqa: BLE001 - a malformed-HTML parse failure is a legitimate degraded state
        result["dom_parse_degraded"] = True
        result["dom_parse_degraded_reason"] = f"parse_exception:{str(e)[:200]}"
        return result

    result["title"] = (parser.title or "").strip() or None
    result["meta_tags"] = parser.meta_tags
    result["canonical"] = parser.canonical
    result["interactive_elements"] = parser.interactive_elements
    result["visible_text_approx"] = parser.visible_text_approx()

    for raw in parser.json_ld_raw:
        try:
            result["json_ld"].append(json.loads(raw))
        except json.JSONDecodeError:
            result["json_ld"].append({"_unparsed": raw[:500]})

    return result


def main():
    ap = argparse.ArgumentParser(description="Extract structural signals from raw HTML already fetched by the invoking agent's native tool — stdlib only, no JS execution.")
    ap.add_argument("input_path", help="Path to a fetch-results JSON file in the shape described above, or '-' for stdin.")
    ap.add_argument("--write", action="store_true", help="Overwrite the input file with the augmented result (ignored when reading from stdin).")
    args = ap.parse_args()

    if args.input_path == "-":
        raw = sys.stdin.read()
    else:
        with open(args.input_path) as f:
            raw = f.read()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"could not parse input JSON: {e}"}, indent=2))
        sys.exit(1)

    results = data.get("results", [])
    for r in results:
        if r.get("ok") and r.get("html"):
            r.update(parse_html(r["html"]))
        else:
            # Nothing to parse — a degraded fetch stays degraded; don't
            # fabricate structural fields for content that was never
            # actually retrieved.
            r.setdefault("title", None)
            r.setdefault("meta_tags", {})
            r.setdefault("canonical", None)
            r.setdefault("json_ld", [])
            r.setdefault("interactive_elements", [])
            r.setdefault("visible_text_approx", "")
            r["dom_parse_degraded"] = True
            r["dom_parse_degraded_reason"] = "no_html_to_parse (fetch itself was degraded)"

    output = json.dumps(data, indent=2)

    if args.write and args.input_path != "-":
        with open(args.input_path, "w") as f:
            f.write(output)

    print(output)
    sys.exit(0)


if __name__ == "__main__":
    main()
