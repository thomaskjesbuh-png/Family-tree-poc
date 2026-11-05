#!/usr/bin/env python3
"""Run the test set and write reports/accuracy.md.

    python evaluate.py                         # fictional cases, sample records
    python evaluate.py --llm                   # include Haiku/Sonnet steps
    python evaluate.py --kind real --records path/to/dataset.csv
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from ancestor_finder.cache import Cache
from ancestor_finder.models import PersonQuery
from ancestor_finder.pipeline import PrivacyError, find
from ancestor_finder.sources import SourceUnavailable, get_source

LEVELS = ("high", "medium", "low")


def evaluate_case(case: dict, source, helper) -> dict:
    person = dict(case["person"])
    person["case_id"] = case["id"]
    q = PersonQuery.from_dict(person)
    expected = set(case.get("expected", {}).get("record_ids") or [])
    try:
        res = find(q, source, helper=helper)
    except (PrivacyError, SourceUnavailable) as e:
        return {"id": case["id"], "status": "error", "error": str(e), "candidates": [],
                "expected": sorted(expected), "note": case.get("note", "")}

    ids = [c.record.record_id for c in res.candidates]
    rank = next((i + 1 for i, rid in enumerate(ids) if rid in expected), None)
    claimed = [c for c in res.candidates if c.confidence in ("high", "medium")]
    false_matches = [c for c in claimed if c.record.record_id not in expected]

    if not expected:
        status = "correct: no match" if not claimed else "false claim"
    elif rank == 1:
        status = "top 1"
    elif rank and rank <= 3:
        status = "top 3"
    elif rank:
        status = f"found at rank {rank}"
    else:
        status = "missed"

    return {
        "id": case["id"], "note": case.get("note", ""), "status": status, "rank": rank,
        "expected": sorted(expected),
        "candidates": [(c.record.record_id, c.confidence, round(c.score, 2),
                        c.record.record_id in expected, (c.judge or {}).get("verdict"))
                       for c in res.candidates],
        "false_matches": [(c.record.record_id, c.confidence) for c in false_matches],
        "warnings": res.warnings, "llm_used": res.llm_used,
    }


def write_report(results: list[dict], path: Path, *, source_desc: str, llm: bool, budget) -> None:
    n = len(results)
    with_answer = [r for r in results if r["expected"]]
    no_answer = [r for r in results if not r["expected"]]
    top1 = sum(r["status"] == "top 1" for r in with_answer)
    top3 = sum(r["status"] in ("top 1", "top 3") for r in with_answer)
    missed = sum(r["status"] == "missed" for r in with_answer)
    correct_none = sum(r["status"] == "correct: no match" for r in no_answer)
    false_total = sum(len(r.get("false_matches", [])) for r in results)

    calib = defaultdict(lambda: [0, 0])  # level -> [candidates, correct]
    for r in results:
        for rid, conf, _score, ok, _v in r["candidates"]:
            calib[conf][0] += 1
            calib[conf][1] += int(ok)

    per_case = getattr(budget, "per_case", {}) if budget else {}
    total_cost = getattr(budget, "spent_usd", 0.0) if budget else 0.0

    L = [
        "# Accuracy report",
        "",
        f"Generated {dt.date.today().isoformat()} · source: {source_desc} · "
        f"model steps: {'on' if llm else 'off (deterministic scoring only)'}",
        "",
    ]
    if "FICTIONAL" in source_desc.upper() or "sample" in source_desc:
        L += ["> These results come from **fictional sample records** built to exercise the pipeline. "
              "They show that it runs end to end and handles the tricky cases. They say nothing yet about "
              "accuracy on real archives. Rerun on the 20 real ancestors once access is confirmed.", ""]
    L += [
        "## Summary",
        "",
        "| Measure | Result |",
        "| --- | --- |",
        f"| Test people | {n} ({len(with_answer)} with a known record, {len(no_answer)} with none) |",
        f"| Correct record ranked first | {top1} of {len(with_answer)} |",
        f"| Correct record in top 3 | {top3} of {len(with_answer)} |",
        f"| Missed | {missed} of {len(with_answer)} |",
        f"| \"No match\" cases correctly left empty | {correct_none} of {len(no_answer)} |",
        f"| False matches at medium or high confidence | {false_total} |",
        f"| Model cost, whole run | ${total_cost:.4f} |",
        "",
        "## Confidence calibration",
        "",
        "Share of reported candidates at each level that are the right person.",
        "",
        "| Confidence | Candidates | Correct | Precision |",
        "| --- | --- | --- | --- |",
    ]
    for lvl in LEVELS:
        c, ok = calib[lvl]
        L.append(f"| {lvl} | {c} | {ok} | {(ok / c * 100):.0f}% |" if c else f"| {lvl} | 0 | 0 | n/a |")
    L += ["", "## Per person", "",
          "| Case | Result | Correct rank | False matches | Model cost |",
          "| --- | --- | --- | --- | --- |"]
    for r in results:
        fm = ", ".join(f"{rid} ({conf})" for rid, conf in r.get("false_matches", [])) or "none"
        cost = per_case.get(r["id"], 0.0)
        L.append(f"| {r['id']} | {r['status']} | {r.get('rank') or '-'} | {fm} | ${cost:.4f} |")
    L += ["", "## Details", ""]
    for r in results:
        L += [f"### {r['id']}", "", r.get("note") or "", "",
              f"Expected: {', '.join(r['expected']) or 'no match'}", ""]
        if r.get("error"):
            L += [f"Error: {r['error']}", ""]
            continue
        if r["candidates"]:
            L += ["| Rank | Record | Confidence | Score | Correct | Model verdict |",
                  "| --- | --- | --- | --- | --- | --- |"]
            for i, (rid, conf, score, ok, verdict) in enumerate(r["candidates"], 1):
                L.append(f"| {i} | {rid} | {conf} | {score} | {'yes' if ok else 'no'} | {verdict or '-'} |")
            L.append("")
        else:
            L += ["No candidates reported.", ""]
        for w in r.get("warnings", []):
            L.append(f"- warning: {w}")
        if r.get("warnings"):
            L.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", type=Path, default=Path("tests/known_people.yaml"))
    ap.add_argument("--kind", default="fictional", choices=["fictional", "real", "all"])
    ap.add_argument("--source", default="local", choices=["local", "digitalarkivet"])
    ap.add_argument("--records", type=Path)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("reports/accuracy.md"))
    ap.add_argument("--cache", type=Path, default=Path("cache/ancestor_finder.sqlite"))
    args = ap.parse_args(argv)

    cases = yaml.safe_load(args.cases.read_text(encoding="utf-8"))["cases"]
    cases = [c for c in cases
             if (args.kind == "all" or c.get("kind") == args.kind) and c.get("enabled", True)]
    if not cases:
        print(f"No enabled {args.kind} cases in {args.cases}.", file=sys.stderr)
        return 1

    try:
        source = get_source(args.source, path=args.records)
    except (SourceUnavailable, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    helper = budget = None
    cache = Cache(args.cache)
    if args.llm:
        from ancestor_finder.llm import ClaudeHelper
        if ClaudeHelper.available():
            helper = ClaudeHelper(cache)
            budget = helper.budget
        else:
            print("warning: --llm given but no Anthropic credentials found; deterministic only",
                  file=sys.stderr)

    results = [evaluate_case(c, source, helper) for c in cases]
    desc = (f"local file {args.records or 'data/sample_records.csv (FICTIONAL sample)'}"
            if args.source == "local" else args.source)
    write_report(results, args.out, source_desc=desc, llm=helper is not None, budget=budget)
    for r in results:
        print(f"{r['id']:<32} {r['status']}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
