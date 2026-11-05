#!/usr/bin/env python3
"""Find archive records for a known historical person.

    python find.py examples/kristine.yaml
    python find.py person.yaml --source local --records data/sample_records.csv --json
    python find.py person.yaml --llm          # add the Haiku/Sonnet steps
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from ancestor_finder.cache import Cache
from ancestor_finder.models import PersonQuery
from ancestor_finder.pipeline import PrivacyError, find
from ancestor_finder.report import to_markdown
from ancestor_finder.sources import SourceUnavailable, get_source


def load_person(path: Path) -> PersonQuery:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)
    return PersonQuery.from_dict(data)


def make_helper(enabled: bool, cache: Cache):
    if not enabled:
        return None
    from ancestor_finder.llm import ClaudeHelper
    if not ClaudeHelper.available():
        print("warning: --llm given but no Anthropic credentials found; "
              "running deterministic scoring only", file=sys.stderr)
        return None
    return ClaudeHelper(cache)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("person", type=Path, help="YAML or JSON file describing the person")
    ap.add_argument("--source", default="local", choices=["local", "digitalarkivet"])
    ap.add_argument("--records", type=Path, help="records file for --source local")
    ap.add_argument("--llm", action="store_true", help="use Claude for extraction and same-person checks")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    ap.add_argument("--cache", type=Path, default=Path("cache/ancestor_finder.sqlite"))
    args = ap.parse_args(argv)

    try:
        q = load_person(args.person)
        source = get_source(args.source, path=args.records)
        cache = Cache(args.cache)
        res = find(q, source, helper=make_helper(args.llm, cache))
    except (PrivacyError, SourceUnavailable, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"query": q.__dict__, "found": res.found,
                          "candidates": [c.to_dict() for c in res.candidates],
                          "warnings": res.warnings, "llm_used": res.llm_used},
                         ensure_ascii=False, indent=2))
    else:
        print(to_markdown(res), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
