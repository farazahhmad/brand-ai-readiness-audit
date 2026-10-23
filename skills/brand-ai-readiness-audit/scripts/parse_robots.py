#!/usr/bin/env python3
"""
parse_robots.py — parse an ALREADY-FETCHED robots.txt for two distinct
purposes:

1. Self-compliance: can THIS tool fetch a given path? (--check-path)
2. Policy analysis: which named bots (from bot-taxonomy.json) does this
   site's robots.txt disallow, and are any of them real-time-answer bots?

These are kept as one script because they share the same parse step, but
the two outputs must not be conflated in the report — see SKILL.md
Step 1.2 (self-compliance) vs. Step 1.5 (policy analysis).

This script does NOT fetch anything itself. In this build, all HTTP
fetching (robots.txt included) is done exactly once, by the invoking
agent's own native fetch/search tool — see SKILL.md Step 1. This script
only parses whatever text that fetch returned, which you pass in via
--input, or reports a degraded state via --not-found / --fetch-failed if
the fetch didn't succeed. There is no fallback path to reconcile here
anymore, because there is only one fetch mechanism in this build — see
references/evidence-states.md.

Usage:
    python3 parse_robots.py <base_url> --input /tmp/robots.txt \
        [--check-path /some/path] [--user-agent brand-ai-readiness-audit] \
        [--bot-taxonomy ../references/bot-taxonomy.json]

    # or pipe the already-fetched text in directly:
    cat /tmp/robots.txt | python3 parse_robots.py <base_url> --input -

    # if the native fetch returned a 404 (no robots.txt = default-allow):
    python3 parse_robots.py <base_url> --not-found

    # if the native fetch itself failed (timeout, connection error, etc):
    python3 parse_robots.py <base_url> --fetch-failed "timeout"

Output: a single JSON object on stdout. Always exits 0.
"""
import argparse
import json
import sys
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

DEFAULT_UA = "brand-ai-readiness-audit/2.0 (+read-only site audit; no JS execution)"


def parse_disallow_map(raw_text: str) -> dict:
    """Build {user_agent: {"disallow": [...], "allow": [...]}} from raw robots.txt text."""
    rules = {}
    current_agents = []
    for line in raw_text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if current_agents and current_agents[-1] in rules and not rules[current_agents[-1]]["disallow"] and not rules[current_agents[-1]]["allow"]:
                current_agents.append(value)
            else:
                current_agents = [value]
            rules.setdefault(value, {"disallow": [], "allow": []})
        elif field == "disallow" and current_agents:
            for ua in current_agents:
                if value:  # empty Disallow: means "allow everything"
                    rules[ua]["disallow"].append(value)
        elif field == "allow" and current_agents:
            for ua in current_agents:
                rules[ua]["allow"].append(value)
    return rules


def read_input(input_arg: str) -> str:
    if input_arg == "-":
        return sys.stdin.read()
    with open(input_arg) as f:
        return f.read()


def main():
    parser = argparse.ArgumentParser(description="Parse an already-fetched robots.txt (this script performs no fetching itself).")
    parser.add_argument("base_url", help="e.g. https://example.com — used only to label the robots_txt_url in the output.")
    parser.add_argument("--input", default=None,
                         help="Path to a file containing the already-fetched robots.txt text, or '-' for stdin.")
    parser.add_argument("--not-found", action="store_true",
                         help="The native fetch tool returned a 404 for robots.txt. Treated as default-allow everywhere, not a defect.")
    parser.add_argument("--fetch-failed", default=None, metavar="REASON",
                         help="The native fetch tool failed to retrieve robots.txt at all (timeout, connection error, non-2xx, etc). Pass a short reason string.")
    parser.add_argument("--check-path", default=None,
                         help="Path to check for THIS tool's own fetch permission, e.g. /category/shoes")
    parser.add_argument("--user-agent", default=DEFAULT_UA)
    parser.add_argument("--bot-taxonomy", default=None,
                         help="Path to bot-taxonomy.json for policy classification")
    args = parser.parse_args()

    robots_url = urljoin(args.base_url.rstrip("/") + "/", "robots.txt")
    result = {
        "robots_txt_url": robots_url,
        "fetched": False,
        "raw_text": None,
        "rules_by_user_agent": {},
        "self_compliance_check": None,
        "bot_policy_analysis": None,
        "fetch_degraded": False,
        "degraded_reason": None,
    }

    if args.fetch_failed:
        result["fetch_degraded"] = True
        result["degraded_reason"] = args.fetch_failed
    elif args.not_found:
        # No robots.txt = default-allow everywhere. Not a defect (see severity-rules.md).
        result["fetched"] = True
        result["raw_text"] = ""
        result["rules_by_user_agent"] = {}
    elif args.input:
        raw_text = read_input(args.input)
        result["fetched"] = True
        result["raw_text"] = raw_text
        result["rules_by_user_agent"] = parse_disallow_map(raw_text)
    else:
        print(json.dumps({"error": "one of --input, --not-found, or --fetch-failed is required — this script no longer fetches robots.txt itself, see module docstring"}, indent=2))
        sys.exit(1)

    # 1. Self-compliance check (governs the audit tool's OWN fetching — SKILL.md Step 1.2)
    if result["fetched"] and args.check_path:
        rfp = RobotFileParser()
        rfp.parse((result["raw_text"] or "").splitlines())
        allowed = rfp.can_fetch(args.user_agent, args.check_path)
        result["self_compliance_check"] = {
            "path": args.check_path,
            "user_agent_checked": args.user_agent,
            "allowed": allowed,
        }

    # 2. Bot-policy analysis (informational, for the report — SKILL.md Step 1.5)
    if result["fetched"] and args.bot_taxonomy:
        try:
            with open(args.bot_taxonomy) as f:
                taxonomy = json.load(f)
            all_bots = taxonomy.get("non_rendering_crawlers", []) + taxonomy.get("rendering_crawlers", [])
            blocks_training = []
            blocks_real_time_answer = []
            for bot in all_bots:
                ua = bot["user_agent"]
                if ua in result["rules_by_user_agent"] and result["rules_by_user_agent"][ua]["disallow"]:
                    if bot["role"] == "training":
                        blocks_training.append(ua)
                    elif bot["role"] in ("real_time_answer", "search_and_answer"):
                        blocks_real_time_answer.append(ua)
            wildcard_disallow = result["rules_by_user_agent"].get("*", {}).get("disallow", [])
            result["bot_policy_analysis"] = {
                "blocks_training_bots_by_name": blocks_training,
                "blocks_real_time_answer_bots_by_name": blocks_real_time_answer,
                "wildcard_disallow_rules": wildcard_disallow,
                "note": "Named blocks only reflect bots present in bot-taxonomy.json. A wildcard (*) Disallow rule affects any bot not given its own more specific block, including unnamed/future AI crawlers.",
            }
        except (OSError, json.JSONDecodeError) as e:
            result["bot_policy_analysis"] = {"error": f"could_not_load_taxonomy:{str(e)[:200]}"}

    print(json.dumps(result, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
