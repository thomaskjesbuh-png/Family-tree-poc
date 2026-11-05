"""Records from a local CSV or JSON file in the expected format.

This is the stand-in for the archive while live access is unconfirmed, and
also the intended path if Arkivverket offers downloadable datasets.
See data/README.md for the column format.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ..models import PersonQuery, Record, cutoff_year
from .. import names
from .base import Source

DEFAULT_FILE = Path(__file__).resolve().parents[2] / "data" / "sample_records.csv"


def load_records(path: Path | str) -> list[Record]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        rows = json.loads(path.read_text(encoding="utf-8"))
    else:
        with path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
    return [Record.from_dict(r) for r in rows]


class LocalFileSource(Source):
    name = "local"

    def __init__(self, path: Path | str | None = None, **_: object):
        self.path = Path(path) if path else DEFAULT_FILE
        self.records = load_records(self.path)
        self.skipped_recent = 0

    def search(self, query: PersonQuery) -> list[Record]:
        limit = cutoff_year()
        given_keys = {names.canonical_given(g) for g in names.all_given_names(query.given_name, query.name_variants)}
        out = []
        for r in self.records:
            if r.year > limit:
                self.skipped_recent += 1
                continue
            if r.raw_text and not r.given_name:
                out.append(r)  # needs extraction before it can be judged
                continue
            close_name = any(names.given_name_similarity(g, r.given_name) >= 0.8 for g in given_keys) or \
                names.canonical_given(r.given_name) in given_keys
            if not close_name:
                continue
            if query.birth_year and r.birth_year and abs(query.birth_year - r.birth_year) > 10:
                continue
            out.append(r)
        return out
