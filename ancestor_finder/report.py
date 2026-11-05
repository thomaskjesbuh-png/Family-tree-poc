"""Human-readable output for one search."""

from __future__ import annotations

from .pipeline import Result


def to_markdown(res: Result) -> str:
    q = res.query
    lines = [f"# Candidates for {q.full_name} (born ~{q.birth_year}, {q.birthplace or q.county})", ""]
    if not res.candidates:
        lines.append("No matching record found in the searched source. Nothing is claimed.")
    for i, c in enumerate(res.candidates, 1):
        r = c.record
        lines += [
            f"## {i}. {r.full_name or '(no name)'}: {c.confidence} confidence (score {c.score:.2f})",
            f"- Source: {r.source}, {r.record_type} {r.year}",
            f"- Record: [{r.record_id}]({r.url})",
            f"- In record: born {r.birth_year or '?'}"
            + (f", {r.farm}" if r.farm else "")
            + (f", {r.parish or r.municipality}" if (r.parish or r.municipality) else ""),
            "- Why:",
            *("  " + l for l in c.explanation().splitlines()),
            "",
        ]
    if res.warnings:
        lines += ["## Warnings", *(f"- {w}" for w in res.warnings), ""]
    lines.append("_Model check used._" if res.llm_used else "_Deterministic scoring only (no model calls)._")
    return "\n".join(lines) + "\n"
