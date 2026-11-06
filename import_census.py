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
import shutil
import sys
from dataclasses import fields
from pathlib import Path

from ancestor_finder.importers.booklets import COUNTY_NAME, parse_booklet
from ancestor_finder.importers.ft1801 import parse_1801
from ancestor_finder.models import Record, cutoff_year


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--counties", nargs="+", default=None,
                    help="county folders to import (default: every county found under --raw)")
    ap.add_argument("--years", nargs="+", type=int, default=[1801, 1865, 1900, 1910])
    ap.add_argument("--out", type=Path, default=Path("data/real/records.csv"))
    args = ap.parse_args(argv)

    if not shutil.which("pdftotext"):
        print("pdftotext is missing; it reads the census booklets.\n"
              "  Mac:   brew install poppler\n  Linux: apt install poppler-utils", file=sys.stderr)
        return 1
    records: list[Record] = []
    counties = args.counties or sorted({p.name for p in args.raw.glob("[0-9]*/*") if p.is_dir()})
    for year in args.years:
        if year > cutoff_year():
            print(f"skipping {year}: less than 100 years old", file=sys.stderr)
            continue
        if year == 1801:
            files = sorted((args.raw / "1801").glob("Ft1801_forsk_*.txt"))
            for f in files:
                code = f.name.split("_")[2][:2]
                county = next((v for k, v in COUNTY_NAME.items() if k.startswith(code)), "")
                recs = parse_1801(f, county=county)
                records += recs
                print(f"1801 {f.name}: {len(recs)} persons")
            if not files:
                print("  no 1801 files; run tools/fetch_census.py", file=sys.stderr)
            continue
        for county in counties:
            files = sorted((args.raw / str(year) / county).glob("*_hefte.pdf"))
            if not files:
                continue
            total = 0
            for f in files:
                recs = parse_booklet(f, year, county)
                total += len(recs)
                records += recs
            print(f"{year} {county}: {len(files)} booklets, {total} persons")

    if not records:
        print(f"No census files found under {args.raw}/, so {args.out} was left as it was.\n"
              "Run tools/fetch_census.py first (from the project folder) and check it downloaded files.", file=sys.stderr)
        return 1
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
