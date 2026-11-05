"""Records from a local CSV or JSON file in the expected format.

This is the stand-in for the archive while live access is unconfirmed, and
also the intended path if Arkivverket offers downloadable datasets.
See data/README.md for the column format.
"""

from __future__ import annotations

import csv
import json
import pickle
from collections import defaultdict
from pathlib import Path

from ..models import PersonQuery, Record, cutoff_year
from .. import names
from .base import Source

DEFAULT_FILE = Path(__file__).resolve().parents[2] / "data" / "sample_records.csv"


def load_records(path: Path | str) -> list[Record]:
    """Load records; large files are cached as a pickle next to the source."""
    path = Path(path)
    cache = path.with_suffix(path.suffix + ".pickle")
    if path.stat().st_size > 5_000_000:
        if cache.exists() and cache.stat().st_mtime >= path.stat().st_mtime:
            with cache.open("rb") as fh:
                return pickle.load(fh)
        recs = _load_uncached(path)
        with cache.open("wb") as fh:
            pickle.dump(recs, fh, protocol=pickle.HIGHEST_PROTOCOL)
        return recs
    return _load_uncached(path)


def _load_uncached(path: Path) -> list[Record]:
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
        # index by canonical given name so similarity is computed per distinct name
        self._by_given: dict[str, list[Record]] = defaultdict(list)
        self._raw_only: list[Record] = []
        for r in self.records:
            if r.raw_text and not r.given_name:
                self._raw_only.append(r)
            else:
                self._by_given[names.canonical_given(r.given_name)].append(r)

    def search(self, query: PersonQuery) -> list[Record]:
        limit = cutoff_year()
        q_keys = {names.canonical_given(g) for g in names.all_given_names(query.given_name, query.name_variants)}
        keys = [k for k in self._by_given
                if k in q_keys or any(names.given_name_similarity(q, k) >= 0.8 for q in q_keys)]
        out: list[Record] = list(r for r in self._raw_only if r.year <= limit)
        for k in keys:
            for r in self._by_given[k]:
                if r.year > limit:
                    self.skipped_recent += 1
                    continue
                if query.birth_year and r.birth_year and abs(query.birth_year - r.birth_year) > 10:
                    continue
                out.append(r)
        return out
