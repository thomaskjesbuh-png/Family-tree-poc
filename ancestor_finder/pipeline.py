"""Search -> (extract) -> score -> (judge) -> rank."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .models import Candidate, PersonQuery, Record, cutoff_year
from .scoring import confidence_for, rank, score_record
from .sources import Source

# Only the best few candidates go to the (paid) model check.
JUDGE_TOP_N = 5
# ...and only when the deterministic score leaves room for doubt or a rival is close.
JUDGE_MIN_SCORE = 0.55


class PrivacyError(ValueError):
    pass


@dataclass
class Result:
    query: PersonQuery
    candidates: list[Candidate]
    warnings: list[str] = field(default_factory=list)
    llm_used: bool = False

    @property
    def found(self) -> bool:
        return bool(self.candidates)


def check_privacy(q: PersonQuery) -> None:
    limit = cutoff_year()
    if q.birth_year is None:
        raise PrivacyError("birth_year is required, so living people can be excluded")
    if q.birth_year > limit:
        raise PrivacyError(
            f"{q.full_name} was born {q.birth_year}; only people born in {limit} or earlier "
            "are processed (records must be over 100 years old and the person not living).")


def find(q: PersonQuery, source: Source, helper=None) -> Result:
    """Run the pipeline. `helper` is an optional llm.ClaudeHelper."""
    check_privacy(q)
    warnings: list[str] = []
    records = source.search(q)
    limit = cutoff_year()
    records = [r for r in records if r.year <= limit]

    ready: list[Record] = []
    for r in records:
        if r.raw_text and not r.given_name:
            if helper is None:
                warnings.append(f"{r.record_id}: only a raw transcription; skipped (model extraction disabled)")
                continue
            try:
                ex = helper.extract(r, case_id=q.case_id)
            except Exception as e:  # budget, API, refusal
                warnings.append(f"{r.record_id}: extraction failed ({e}); skipped")
                continue
            r = replace(r, **ex.model_dump(), extracted_by_model=True)
        ready.append(r)

    candidates = rank([score_record(q, r) for r in ready])

    used = False
    if helper is not None:
        for c in candidates[:JUDGE_TOP_N]:
            if c.score < JUDGE_MIN_SCORE:
                continue
            try:
                j = helper.judge(q, c.record, case_id=q.case_id)
            except Exception as e:
                warnings.append(f"{c.record.record_id}: model check failed ({e})")
                continue
            used = True
            c.judge = j.model_dump()
            _apply_judgement(c)
        candidates = sorted(candidates, key=lambda c: c.score, reverse=True)

    return Result(query=q, candidates=candidates, warnings=warnings, llm_used=used)


def _apply_judgement(c: Candidate) -> None:
    """Combine the model's verdict with the deterministic score.

    The model can lower confidence freely but can raise it by at most one level,
    and never to "high" unless the deterministic score was at least medium.
    """
    verdict = (c.judge or {}).get("verdict")
    before = c.confidence
    if verdict == "different":
        c.score *= 0.5
        c.confidence = "low"
    elif verdict == "unsure":
        c.score *= 0.9
        c.confidence = "medium" if before == "high" else confidence_for(c.score)
    elif verdict == "same":
        c.score = min(1.0, c.score + 0.05)
        if before == "medium" and c.score >= 0.80:
            c.confidence = "high"
        else:
            c.confidence = before if before != "low" else confidence_for(c.score)
    # a close-rival note from ranking keeps the cap at medium
    if any(n.startswith("close rival") for n in c.notes) and c.confidence == "high" and verdict != "same":
        c.confidence = "medium"
