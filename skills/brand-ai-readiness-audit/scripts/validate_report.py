#!/usr/bin/env python3
"""
validate_report.py — deterministic, dependency-free schema check and
summary-recompute for the final audit report.

Why this exists: SKILL.md's own severity-rules.md already specifies that
`summary` must be recomputed by literally counting `findings[]`, not
asserted — a mismatch between the emitted summary and the actual
findings has happened in practice. Doing that counting, plus the basic
required-field/enum checks, by hand in prose is exactly the kind of slow,
error-prone step that padded the old "report generation" phase. This
script does the same checks mechanically, in well under a second,
regardless of how many findings there are.

This is NOT a replacement for the judgment calls in severity-rules.md /
evidence-states.md (diagnosis gates, language guard, scope discipline) —
those still require the reasoning steps in SKILL.md. This only handles
the part of Step 8 that is purely mechanical.

Usage:
    python3 validate_report.py <path-to-report.json> [--write]

Without --write: prints a validation result (errors + the recomputed
summary) to stdout and exits 1 if there are structural errors, 0
otherwise. The input file is not modified.

With --write: additionally overwrites the input file's `summary` block
with the recomputed counts (only `summary` — nothing else is touched),
so the emitted report is guaranteed to match its own findings[] list.
"""
import argparse
import json
import sys

REQUIRED_TOP_LEVEL = ["site", "audited_at", "summary", "findings"]
REQUIRED_FINDING_FIELDS = ["id", "title", "severity", "evidence", "suggested_action"]
VALID_SEVERITIES = {"critical", "high", "medium", "low"}
VALID_PRIORITIES = {"critical", "high", "medium", "low"}
DISALLOWED_PHRASES = [
    "will never be cited", "guarantees non-citation",
    "will cause hallucination", "guarantees hallucination",
    "will cause visitors to abandon", "guarantees abandonment",
    "is fraud", "is illegal",
]


def validate(report: dict) -> tuple:
    """Returns (errors: list[str], warnings: list[str], recomputed_summary: dict)."""
    errors = []
    warnings = []

    for field in REQUIRED_TOP_LEVEL:
        if field not in report:
            errors.append(f"missing required top-level field: {field}")

    findings = report.get("findings", [])
    if not isinstance(findings, list):
        errors.append("'findings' must be a list")
        findings = []

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for i, f in enumerate(findings):
        label = f.get("id", f"findings[{i}]")
        for field in REQUIRED_FINDING_FIELDS:
            if field not in f:
                errors.append(f"{label}: missing required field '{field}'")

        sev = f.get("severity")
        if sev is not None:
            if sev not in VALID_SEVERITIES:
                errors.append(f"{label}: invalid severity '{sev}'")
            else:
                counts[sev] += 1

        evidence = f.get("evidence")
        if evidence is not None and not isinstance(evidence, str):
            errors.append(f"{label}: 'evidence' must be a plain string, not an object")

        if isinstance(evidence, str):
            lowered = evidence.lower()
            for phrase in DISALLOWED_PHRASES:
                if phrase in lowered:
                    warnings.append(f"{label}: evidence contains disallowed phrase pattern: '{phrase}' — see severity-rules.md language guard")

        sa = f.get("suggested_action")
        if isinstance(sa, dict):
            if "summary" not in sa:
                errors.append(f"{label}: suggested_action missing 'summary'")
            if "priority" not in sa:
                errors.append(f"{label}: suggested_action missing 'priority'")
            elif sa["priority"] not in VALID_PRIORITIES:
                errors.append(f"{label}: suggested_action has invalid priority '{sa['priority']}'")
        elif sa is not None:
            errors.append(f"{label}: 'suggested_action' must be an object")



    recomputed_summary = {
        "total_findings": len(findings),
        "critical": counts["critical"],
        "high": counts["high"],
        "medium": counts["medium"],
        "low": counts["low"],
    }

    declared_summary = report.get("summary")
    if isinstance(declared_summary, dict):
        for k, v in recomputed_summary.items():
            if declared_summary.get(k) != v:
                warnings.append(
                    f"summary.{k} was declared as {declared_summary.get(k)!r} but recomputed as {v!r} "
                    f"from findings[] — corrected in output"
                )

    for opp in report.get("opportunities", []) or []:
        if "summary" not in opp or "priority" not in opp:
            errors.append("an opportunities[] entry is missing 'summary' or 'priority'")
        if opp.get("priority") not in (None,) and opp.get("priority") not in VALID_PRIORITIES:
            errors.append(f"opportunities[] entry has invalid priority '{opp.get('priority')}'")
        if "severity" in opp:
            errors.append("an opportunities[] entry has a 'severity' field — opportunities are never diagnosed problems, see output-schema.json")

    return errors, warnings, recomputed_summary


def main():
    parser = argparse.ArgumentParser(description="Validate and recompute the summary of an audit report JSON file.")
    parser.add_argument("report_path")
    parser.add_argument("--write", action="store_true",
                         help="Overwrite the report file's summary block with the recomputed counts.")
    args = parser.parse_args()

    try:
        with open(args.report_path) as f:
            report = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(json.dumps({"errors": [f"could not read/parse report file: {e}"], "warnings": [], "recomputed_summary": None}, indent=2))
        sys.exit(1)

    errors, warnings, recomputed_summary = validate(report)

    if args.write:
        report["summary"] = recomputed_summary
        with open(args.report_path, "w") as f:
            json.dump(report, f, indent=2)

    print(json.dumps({
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "recomputed_summary": recomputed_summary,
        "written": bool(args.write),
    }, indent=2))
    sys.exit(0 if len(errors) == 0 else 1)


if __name__ == "__main__":
    main()
