#!/usr/bin/env python3
"""Convert downloaded census files into one records CSV for --source local.

    python tools/fetch_census.py                 # download first
    python import_census.py                      # -> data/real/ostfold_records.csv
    python find.py person.yaml --records data/real/ostfold_records.csv

Needs `pdftotext` (poppler-utils) for the booklets.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import fields
from pathlib import Path

from ancestor_finder.importers.booklets import parse_booklet
from ancestor_finder.importers.ft1801 import parse_1801
from ancestor_finder.models import Record, cutoff_year


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--county", default="01Ostfold")
    ap.add_argument("--years", nargs="+", type=int, default=[1801, 1865, 1900, 1910])
    ap.add_argument("--out", type=Path, default=Path("data/real/ostfold_records.csv"))
    args = ap.parse_args(argv)

    records: list[Record] = []
    for year in args.years:
        if year > cutoff_year():
            print(f"skipping {year}: less than 100 years old", file=sys.stderr)
            continue
        if year == 1801:
            files = sorted((args.raw / "1801").glob("Ft1801_forsk_*.txt"))
            for f in files:
                recs = parse_1801(f)
                records += recs
                print(f"1801 {f.name}: {len(recs)} persons")
        else:
            files = sorted((args.raw / str(year) / args.county).glob("*_hefte.pdf"))
            total = 0
            for f in files:
                recs = parse_booklet(f, year, args.county)
                total += len(recs)
                records += recs
            print(f"{year}: {len(files)} booklets, {total} persons")
        if not files:
            print(f"  no files for {year} under {args.raw}; run tools/fetch_census.py", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    names = [f.name for f in fields(Record)]
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=names)
        w.writeheader()
        for r in records:
            w.writerow(r.to_dict())
    print(f"wrote {len(records)} records to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
