"""Data types shared across the pipeline."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field, asdict
from typing import Any

# Records and people must be at least this many years old (spec: no living
# people, no records less than 100 years old).
MIN_AGE_YEARS = 100


def cutoff_year(today: _dt.date | None = None) -> int:
    """Latest year a record (or a query person's birth) may have."""
    today = today or _dt.date.today()
    return today.year - MIN_AGE_YEARS


@dataclass
class PersonQuery:
    """A known historical person we want to find in the archives."""

    given_name: str
    surname: str = ""
    name_variants: list[str] = field(default_factory=list)
    birth_year: int | None = None
    birth_year_tolerance: int = 2
    birthplace: str = ""          # parish or municipality
    county: str = ""
    sex: str = ""                 # "m", "f" or ""
    father_name: str = ""
    mother_name: str = ""
    spouse_name: str = ""
    case_id: str = ""             # set by the test runner, used in cost logs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PersonQuery":
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"Unknown person fields: {sorted(unknown)}")
        if not d.get("given_name"):
            raise ValueError("given_name is required")
        data: dict[str, Any] = {}
        for key, value in d.items():
            if key == "name_variants":
                data[key] = [str(v).strip() for v in (value or [])]
            elif key in ("birth_year", "birth_year_tolerance"):
                if value not in (None, ""):
                    data[key] = int(value)
            else:
                data[key] = "" if value is None else str(value).strip()
        return cls(**data)

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.given_name, self.surname) if p)


@dataclass
class Record:
    """One person entry in a source record (a census line, a baptism, ...).

    Only fields present in the source are filled; nothing is inferred.
    """

    record_id: str
    source: str                   # human-readable source name
    record_type: str              # census, baptism, marriage, burial, ...
    year: int                     # year of the record itself
    url: str                      # direct link to the record
    given_name: str = ""
    surname: str = ""
    farm: str = ""                # farm / place of residence (often used as surname)
    sex: str = ""
    birth_year: int | None = None
    birthplace: str = ""
    parish: str = ""
    municipality: str = ""
    county: str = ""
    father_name: str = ""
    mother_name: str = ""
    spouse_name: str = ""
    role: str = ""                # e.g. "child", "head", "wife", "baptised"
    raw_text: str = ""            # transcription text, if fields are not split out
    extracted_by_model: bool = False  # True when fields came from LLM extraction
    relations_inferred: bool = False  # parents/spouse derived from household position
    birth_year_from_age: bool = False # birth year computed from stated age

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Record":
        known = set(cls.__dataclass_fields__)
        data = {k: v for k, v in d.items() if k in known}
        for k in ("year", "birth_year"):
            v = data.get(k)
            data[k] = int(v) if v not in (None, "") else None
        flags = {"extracted_by_model", "relations_inferred", "birth_year_from_age"}
        for k in known - {"year", "birth_year"} - flags:
            if data.get(k) is None:
                data[k] = ""
        for k in flags:
            v = data.get(k, False)
            data[k] = v.strip().lower() in ("1", "true", "yes") if isinstance(v, str) else bool(v)
        return cls(**data)

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.given_name, self.surname) if p)


@dataclass
class ScorePart:
    name: str
    score: float      # 0..1
    weight: float
    explanation: str


@dataclass
class Candidate:
    record: Record
    score: float
    confidence: str                      # high, medium, low
    parts: list[ScorePart] = field(default_factory=list)
    judge: dict[str, Any] | None = None  # LLM same-person verdict, if used
    notes: list[str] = field(default_factory=list)

    def explanation(self) -> str:
        lines = [f"- {p.name}: {p.explanation}" for p in self.parts]
        if self.judge:
            lines.append(f"- model check: {self.judge.get('verdict')} "
                         f"({'; '.join(self.judge.get('reasons', []))})")
        lines.extend(f"- note: {n}" for n in self.notes)
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        r = self.record
        return {
            "record_id": r.record_id,
            "source": r.source,
            "record_type": r.record_type,
            "year": r.year,
            "url": r.url,
            "name_in_record": r.full_name,
            "birth_year_in_record": r.birth_year,
            "place_in_record": ", ".join(p for p in (r.farm, r.parish or r.municipality, r.county) if p),
            "score": round(self.score, 3),
            "confidence": self.confidence,
            "explanation": [asdict(p) for p in self.parts],
            "judge": self.judge,
            "notes": self.notes,
        }
