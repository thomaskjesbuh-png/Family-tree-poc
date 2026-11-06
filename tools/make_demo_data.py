#!/usr/bin/env python3
"""Write data/demo/demo_records.csv: an INVENTED family for demos and screenshots.

Nobody in this file existed. The places are real parish names so the matching
behaves as it would on real data, but every person, farm and link is made up.
The story: Ole Andreas Larsen (b. 1851, Rakkestad) followed from his parents'
household in 1865 to his own farm in 1900 and 1910, with namesakes nearby.
"""

import csv
from dataclasses import fields
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ancestor_finder.models import Record  # noqa: E402

SRC = {1865: "DEMO: 1865 census (invented)", 1900: "DEMO: 1900 census (invented)",
       1910: "DEMO: 1910 census (invented)"}

# (year, farm, municipality, [(given, surname, sex, birth_year, birthplace, role, father, mother, spouse)])
H = [
    (1865, "Bakken", "Rakkestad", [
        ("Lars", "Olsen", "m", 1822, "Rakkestad", "Husfader", "", "", "Berte Hansdatter"),
        ("Berte", "Hansdatter", "f", 1826, "Degernes", "hans Kone", "", "", "Lars Olsen"),
        ("Hans", "Larsen", "m", 1848, "Rakkestad", "deres Søn", "Lars Olsen", "Berte Hansdatter", ""),
        ("Ole Andreas", "Larsen", "m", 1851, "Rakkestad", "deres Søn", "Lars Olsen", "Berte Hansdatter", ""),
        ("Karen", "Larsdatter", "f", 1855, "Rakkestad", "deres Datter", "Lars Olsen", "Berte Hansdatter", ""),
        ("Marte", "Pedersdatter", "f", 1846, "Eidsberg", "Tjenestepige", "", "", ""),
    ]),
    (1865, "Haugen (plads)", "Rakkestad", [
        ("Lars", "Olsen", "m", 1820, "Rakkestad", "Husmand", "", "", "Anne Olsdatter"),
        ("Anne", "Olsdatter", "f", 1824, "Rakkestad", "hans Kone", "", "", "Lars Olsen"),
        ("Ole", "Larsen", "m", 1852, "Rakkestad", "deres Søn", "Lars Olsen", "Anne Olsdatter", ""),
        ("Mari", "Larsdatter", "f", 1857, "Rakkestad", "deres Datter", "Lars Olsen", "Anne Olsdatter", ""),
    ]),
    (1865, "Vestre Ramstad", "Eidsberg", [
        ("Lars", "Andersen", "m", 1818, "Eidsberg", "Husfader", "", "", "Kari Olsdatter"),
        ("Kari", "Olsdatter", "f", 1821, "Eidsberg", "hans Kone", "", "", "Lars Andersen"),
        ("Ole Andreas", "Larsen", "m", 1849, "Eidsberg", "deres Søn", "Lars Andersen", "Kari Olsdatter", ""),
    ]),
    (1900, "Nordre Lie", "Rakkestad", [
        ("Ole Andreas", "Lars.", "m", 1851, "Rakkestad herred", "hf", "", "", "Marte Kristine Lars."),
        ("Marte Kristine", "Lars.", "f", 1854, "Degernes", "hm", "", "", "Ole Andreas Lars."),
        ("Lars", "Oles.", "m", 1879, "Rakkestad herred", "s", "Ole Andreas Lars.", "Marte Kristine Lars.", ""),
        ("Berte", "Olsd.", "f", 1882, "Rakkestad herred", "d", "Ole Andreas Lars.", "Marte Kristine Lars.", ""),
        ("Kristian", "Oles.", "m", 1886, "Rakkestad herred", "s", "Ole Andreas Lars.", "Marte Kristine Lars.", ""),
        ("Anna", "Olsd.", "f", 1891, "Rakkestad herred", "d", "Ole Andreas Lars.", "Marte Kristine Lars.", ""),
        ("Berte", "Hansdatter", "f", 1826, "Degernes", "føderaadskone", "", "", ""),
    ]),
    (1900, "Haugen", "Rakkestad", [
        ("Ole", "Lars.", "m", 1852, "Rakkestad herred", "hf", "", "", "Inger Olsd."),
        ("Inger", "Olsd.", "f", 1858, "Rakkestad herred", "hm", "", "", "Ole Lars."),
        ("Anne", "Olsd.", "f", 1885, "Rakkestad herred", "d", "Ole Lars.", "Inger Olsd.", ""),
    ]),
    (1900, "Ramstad", "Eidsberg", [
        ("Ole Andreas", "Lars.", "m", 1849, "Eidsberg herred", "hf", "", "", "Marte Hansd."),
        ("Marte", "Hansd.", "f", 1853, "Eidsberg herred", "hm", "", "", "Ole Andreas Lars."),
        ("Hans", "Oles.", "m", 1881, "Eidsberg herred", "s", "Ole Andreas Lars.", "Marte Hansd.", ""),
    ]),
    (1910, "Lie nordre", "Rakkestad", [
        ("Ole Andreas", "Larsen", "m", 1851, "Rakkestad", "hf", "", "", "Marte Kristine Larsen"),
        ("Marte Kristine", "Larsen", "f", 1854, "Degernes", "hm", "", "", "Ole Andreas Larsen"),
        ("Anna", "Olsen", "f", 1891, "Rakkestad", "d", "Ole Andreas Larsen", "Marte Kristine Larsen", ""),
        ("Kristian", "Olsen", "m", 1886, "Rakkestad", "s", "Ole Andreas Larsen", "Marte Kristine Larsen", ""),
        ("Ole", "Kristiansen", "m", 1909, "Rakkestad", "sønnesøn", "", "", ""),
    ]),
    (1910, "Haugen", "Rakkestad", [
        ("Ole", "Larsen", "m", 1852, "Rakkestad", "hf", "", "", "Inger Larsen"),
        ("Inger", "Larsen", "f", 1858, "Rakkestad", "hm", "", "", "Ole Larsen"),
    ]),
]


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "data" / "demo" / "demo_records.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, seq = [], 0
    for year, farm, muni, people in H:
        for (g, s, sex, by, bp, role, fa, mo, sp) in people:
            seq += 1
            rid = f"demo{year}-{seq:03d}"
            rows.append(Record(
                record_id=rid, source=SRC[year], record_type="census", year=year,
                url=f"demo://{rid}", given_name=g, surname=s, farm=farm, sex=sex, birth_year=by,
                birthplace=bp, parish=muni, municipality=muni, county="Østfold",
                father_name=fa, mother_name=mo, spouse_name=sp, role=role,
                relations_inferred=bool(fa or mo or sp), birth_year_from_age=(year == 1865)))
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[f.name for f in fields(Record)])
        w.writeheader()
        for r in rows:
            w.writerow(r.to_dict())
    print(f"wrote {len(rows)} invented records to {out}")


if __name__ == "__main__":
    main()
