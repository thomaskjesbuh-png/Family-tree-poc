#!/usr/bin/env python3
"""Compare parsed person counts with the totals printed in each booklet."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ancestor_finder.importers.booklets import parse_booklet, pdf_to_pages  # noqa: E402

TOTAL = re.compile(r"Personar i alt: (\d+) \(kvinner: (\d+), menn: (\d+)\)")
KRETS = re.compile(r"Personar (?:i )?kre(?:t|in)sen: (\d+) \(kvinner: (\d+), menn: (\d+)\)")


def stated(pdf: Path) -> tuple[int, int, int] | None:
    text = "\f".join(pdf_to_pages(pdf))
    m = TOTAL.search(text)
    if m:
        return tuple(int(x) for x in m.groups())
    ks = KRETS.findall(text)
    if ks:
        return tuple(sum(int(k[i]) for k in ks) for i in range(3))
    return None


def main() -> int:
    raw = Path("data/raw")
    bad = 0
    missing = expected = 0
    for year in (1865, 1900, 1910):
        tot_p = tot_s = 0
        for pdf in sorted((raw / str(year) / "01Ostfold").glob("*_hefte.pdf")):
            recs = parse_booklet(pdf, year)
            sx = Counter(r.sex for r in recs)
            want = stated(pdf)
            got = (len(recs), sx["f"], sx["m"])
            tot_p += len(recs)
            tot_s += want[0] if want else 0
            if want != got:
                bad += 1
                print(f"{year} {pdf.name}: parsed {got}, booklet says {want}")
        print(f"{year}: parsed {tot_p}, booklets say {tot_s} ({tot_p - tot_s:+d})")
        missing += abs(tot_p - tot_s)
        expected += tot_s
    share = missing / expected if expected else 0
    print(f"overall: {missing} of {expected} persons differ ({share:.3%}); {bad} booklets not exact")
    # Tolerate tiny layout glitches; fail if more than 0.1% of persons are off.
    return 1 if share > 0.001 else 0


if __name__ == "__main__":
    sys.exit(main())
