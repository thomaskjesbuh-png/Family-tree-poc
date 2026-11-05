"""Read the 1801 census research file (Ft1801_forsk_<county>_v1.txt).

Semicolon-separated, one row per person, published by Arkivverket at
https://xml.arkivverket.no/folketellinger/ft1801/. Relevant columns:
fornavn, patr, slektsnavn, kjonn, faar (birth year computed from age),
famst (family role as written), bosted, prgj, amt, PFID (Digitalarkivet
person id), HHOLD/PERNUM with MOMLOC/POPLOC/SPLOC (machine-made links to
mother, father and spouse within the household; the guide warns they
contain errors, so relations are marked as inferred).
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from pathlib import Path

from ..models import Record

PERSON_URL = "https://www.digitalarkivet.no/census/person/{pfid}"
FILE_URL = "https://xml.arkivverket.no/folketellinger/ft1801/{name}"


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def parse_1801(path: Path, county: str = "Østfold") -> list[Record]:
    rows = list(csv.DictReader(io.StringIO(_read_text(path)), delimiter=";"))
    by_hh: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        if r.get("HHOLD"):
            by_hh[r["HHOLD"]][r.get("PERNUM", "")] = r

    def full_name(r: dict) -> str:
        return " ".join(x for x in (r.get("fornavn", ""), r.get("patr", ""), r.get("slektsnavn", "")) if x).strip()

    records = []
    for r in rows:
        hh = by_hh.get(r.get("HHOLD", ""), {})
        rel = {}
        for key, field in (("MOMLOC", "mother"), ("POPLOC", "father"), ("SPLOC", "spouse")):
            loc = (r.get(key) or "").strip()
            if loc and loc not in ("0", "00"):
                other = hh.get(loc.zfill(4))
                if other:
                    rel[field] = full_name(other)
        surname = " ".join(x for x in (r.get("patr", ""), r.get("slektsnavn", "")) if x).strip()
        faar = (r.get("faar") or "").strip()
        pfid = (r.get("PFID") or "").strip()
        records.append(Record(
            record_id=pfid or f"ft1801-{r.get('kildeID', '')}-{r.get('persnr', '')}",
            source=f"Folketelling 1801, {r.get('prgj', '')} (Arkivverket research file {path.name})",
            record_type="census", year=1801,
            url=PERSON_URL.format(pfid=pfid) if pfid else FILE_URL.format(name=path.name),
            given_name=(r.get("fornavn") or "").strip(), surname=surname,
            farm=(r.get("bosted") or "").strip(),
            sex={"m": "m", "k": "f"}.get((r.get("kjonn") or "").strip(), ""),
            birth_year=int(faar) if faar.isdigit() else None,
            birthplace="",  # not recorded in 1801
            parish=(r.get("prgj") or "").strip(), municipality=(r.get("prgj") or "").strip(),
            county=county, father_name=rel.get("father", ""), mother_name=rel.get("mother", ""),
            spouse_name=rel.get("spouse", ""), role=(r.get("famst") or "").strip(),
            relations_inferred=bool(rel), birth_year_from_age=True,
        ))
    return records
