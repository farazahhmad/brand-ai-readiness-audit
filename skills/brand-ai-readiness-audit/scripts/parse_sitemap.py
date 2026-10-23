#!/usr/bin/env python3
"""
parse_sitemap.py — parse an ALREADY-FETCHED sitemap.xml (or sitemap
index), including gzip-compressed sitemaps if you pass the raw bytes as
base64.

This script does NOT fetch anything itself. In this build, all HTTP
fetching is done exactly once, by the invoking agent's own native
fetch/search tool — see SKILL.md Step 1. Discovering the sitemap URL from
robots.txt no longer requires a second network call here either: pass the
already-fetched robots.txt text (from parse_robots.py's Step 1.1 run) via
--robots-text, and this script extracts the `Sitemap:` line from it
in-memory.

Usage:
    # 1. Figure out which URL to fetch (optional — skip if you already
    #    know the sitemap URL, e.g. the conventional /sitemap.xml):
    python3 parse_sitemap.py --discover-only <base_url> --robots-text /tmp/robots.txt

    # 2. Parse the sitemap content the native tool already fetched:
    python3 parse_sitemap.py <sitemap_url> --input /tmp/sitemap.xml
    cat /tmp/sitemap.xml | python3 parse_sitemap.py <sitemap_url> --input -

    # gzip-compressed sitemap (native tool returned base64-encoded bytes):
    python3 parse_sitemap.py <sitemap_url> --input /tmp/sitemap.xml.b64 --input-is-base64-gzip

    # fetch didn't succeed:
    python3 parse_sitemap.py <sitemap_url> --not-found
    python3 parse_sitemap.py <sitemap_url> --fetch-failed "timeout"

Note on nested sitemaps (sitemap index files): this script parses one
sitemap document per call and returns any nested sitemap URLs it finds
under `nested_sitemaps` — it does not fetch or expand them itself, since
that would require additional native-tool fetch calls the agent must make
between calls to this script. SKILL.md Step 1.1 covers how many nested
sitemaps to expand, if any.

Output: a single JSON object on stdout. Always exits 0.
"""
import argparse
import base64
import gzip
import json
import sys
from urllib.parse import urljoin
import xml.etree.ElementTree as ET


def extract_sitemap_url_from_robots_text(robots_text: str) -> str | None:
    for line in (robots_text or "").splitlines():
        if line.strip().lower().startswith("sitemap:"):
            return line.split(":", 1)[1].strip()
    return None


def parse_sitemap_xml(raw_bytes: bytes) -> tuple[list, list]:
    """Returns (urls, nested_sitemaps). Handles both <urlset> and <sitemapindex>."""
    urls, nested = [], []
    try:
        root = ET.fromstring(raw_bytes)
    except ET.ParseError:
        return urls, nested

    tag = root.tag.lower()
    for child in root:
        loc_elem = None
        for sub in child:
            if sub.tag.lower().endswith("loc"):
                loc_elem = sub
                break
        if loc_elem is None or not loc_elem.text:
            continue
        if "sitemapindex" in tag:
            nested.append(loc_elem.text.strip())
        else:
            urls.append(loc_elem.text.strip())
    return urls, nested


def read_input_bytes(input_arg: str, is_base64_gzip: bool) -> bytes:
    if input_arg == "-":
        raw = sys.stdin.buffer.read()
    else:
        with open(input_arg, "rb") as f:
            raw = f.read()
    if is_base64_gzip:
        raw = base64.b64decode(raw)
    return raw


def main():
    parser = argparse.ArgumentParser(description="Parse an already-fetched sitemap.xml (this script performs no fetching itself).")
    parser.add_argument("sitemap_url_or_base_url", help="The sitemap URL being parsed, or (with --discover-only) the site's base URL.")
    parser.add_argument("--discover-only", action="store_true",
                         help="Just extract the Sitemap: line from --robots-text and print the URL to try — no sitemap parsing.")
    parser.add_argument("--robots-text", default=None,
                         help="Path to the already-fetched robots.txt text (used with --discover-only), or '-' for stdin.")
    parser.add_argument("--input", default=None,
                         help="Path to a file containing the already-fetched sitemap content, or '-' for stdin.")
    parser.add_argument("--input-is-base64-gzip", action="store_true",
                         help="The content in --input is base64-encoded gzip bytes (native tool fetched it as gzip and you passed the raw bytes through base64).")
    parser.add_argument("--not-found", action="store_true",
                         help="The native fetch tool returned a 404 for this sitemap URL.")
    parser.add_argument("--fetch-failed", default=None, metavar="REASON",
                         help="The native fetch tool failed to retrieve the sitemap at all. Pass a short reason string.")
    args = parser.parse_args()

    if args.discover_only:
        robots_text = ""
        if args.robots_text:
            robots_text = sys.stdin.read() if args.robots_text == "-" else open(args.robots_text).read()
        discovered = extract_sitemap_url_from_robots_text(robots_text)
        fallback = urljoin(args.sitemap_url_or_base_url.rstrip("/") + "/", "sitemap.xml")
        print(json.dumps({
            "sitemap_url_from_robots": discovered,
            "fallback_sitemap_url": fallback,
            "recommended_next_fetch": discovered or fallback,
        }, indent=2))
        sys.exit(0)

    sitemap_url = args.sitemap_url_or_base_url
    result = {
        "sitemap_url": sitemap_url,
        "fetched": False,
        "urls": [],
        "nested_sitemaps": [],
        "fetch_degraded": False,
        "degraded_reason": None,
    }

    if args.fetch_failed:
        result["fetch_degraded"] = True
        result["degraded_reason"] = args.fetch_failed
    elif args.not_found:
        result["fetch_degraded"] = True
        result["degraded_reason"] = "not_found"
    elif args.input:
        try:
            raw_bytes = read_input_bytes(args.input, args.input_is_base64_gzip)
        except (OSError, base64.binascii.Error) as e:
            result["fetch_degraded"] = True
            result["degraded_reason"] = f"could_not_read_input:{str(e)[:200]}"
            print(json.dumps(result, indent=2))
            sys.exit(0)

        is_gzip = (
            not args.input_is_base64_gzip
            and (sitemap_url.endswith(".gz") or raw_bytes[:2] == b"\x1f\x8b")
        )
        if is_gzip:
            try:
                raw_bytes = gzip.decompress(raw_bytes)
            except OSError as e:
                result["fetch_degraded"] = True
                result["degraded_reason"] = f"gzip_decompress_failed:{str(e)[:200]}"
                print(json.dumps(result, indent=2))
                sys.exit(0)

        urls, nested = parse_sitemap_xml(raw_bytes)
        result["fetched"] = True
        result["urls"] = urls
        result["nested_sitemaps"] = nested
    else:
        print(json.dumps({"error": "one of --input, --not-found, or --fetch-failed is required — this script no longer fetches sitemaps itself, see module docstring"}, indent=2))
        sys.exit(1)

    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
