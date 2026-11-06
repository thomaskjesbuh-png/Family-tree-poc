"""Deterministic candidate scoring with plain-language explanations.

Each factor gives a score in [0, 1] and a weight. Factors the query does not
provide (e.g. no father's name) are left out and the remaining weights are
rescaled, so a sparse query is not punished for what it did not ask.
"""

from __future__ import annotations

from .models import Candidate, PersonQuery, Record, ScorePart
from . import names

WEIGHTS = {
    "given name": 0.30,
    "surname": 0.20,
    "birth year": 0.20,
    "place": 0.12,
    "family": 0.18,
}

# Confidence thresholds on the combined score.
HIGH = 0.85
MEDIUM = 0.65
# Below this a candidate is not reported at all.
REPORT_MIN = 0.50
# If the runner-up is this close to the leader, neither can be "high".
AMBIGUITY_GAP = 0.04


def _given(q: PersonQuery, r: Record) -> ScorePart:
    best, best_name = 0.0, q.given_name
    for g in names.all_given_names(q.given_name, q.name_variants):
        s = names.given_name_similarity(g, r.given_name)
        if s > best:
            best, best_name = s, g
    if best == 1.0 and names.clean(best_name).split()[:1] != names.clean(r.given_name).split()[:1]:
        how = f"{best_name} and {r.given_name or '?'} are spellings of the same name"
    elif best == 1.0:
        how = f"same given name ({r.given_name})"
    else:
        how = f"{best_name} vs {r.given_name or '(none)'}: similarity {best:.2f}"
    return ScorePart("given name", best, WEIGHTS["given name"], how)


def _surname(q: PersonQuery, r: Record) -> ScorePart | None:
    surnames = names.all_surnames(q.surname, q.name_variants)
    if not surnames:
        return None
    best, how = 0.0, "no surname match"
    for s in surnames:
        score, h = names.surname_similarity(s, r.surname, r.farm)
        if score > best:
            best, how = score, h
    # A married woman is usually recorded under her husband's surname.
    if best < 0.9 and q.sex.lower()[:1] == "f" and q.spouse_name and r.surname:
        husband_sur = " ".join(q.spouse_name.split()[1:])
        if husband_sur:
            s_, _ = names.surname_similarity(husband_sur, r.surname)
            if s_ >= 0.9:
                best, how = 0.9, f"record surname {r.surname} is her husband's surname"
    # Baptisms often give the child's given name only; the father's name in the
    # record then implies the patronymic (Ole -> Olsen / Olsdatter).
    if best < 0.9 and not r.surname and r.father_name:
        q_roots = {pr[0] for s in surnames for t in names.clean(s).split()
                   if (pr := names.patronymic_root(t))}
        if q_roots & names.father_patronymic_roots(r.father_name):
            best, how = 0.9, f"no surname in record; father {r.father_name} implies the patronymic"
        elif not r.farm:
            best, how = 0.5, "no surname in record"
    # A father's name implies the patronymic; use it when the surname did not fit.
    if best < 0.9 and q.father_name:
        roots = names.father_patronymic_roots(q.father_name)
        for token in names.clean(r.surname).split():
            pr = names.patronymic_root(token)
            if pr and pr[0] in roots:
                best, how = 0.9, f"record patronymic {token} fits father {q.father_name}"
                break
    return ScorePart("surname", best, WEIGHTS["surname"], how)


def _birth_year(q: PersonQuery, r: Record) -> ScorePart | None:
    if q.birth_year is None:
        return None
    if r.birth_year is None:
        return ScorePart("birth year", 0.4, WEIGHTS["birth year"], "record has no birth year")
    diff = abs(q.birth_year - r.birth_year)
    tol = max(q.birth_year_tolerance, 0)
    if diff == 0:
        score, how = 1.0, f"same birth year ({r.birth_year})"
    elif diff <= tol:
        score = 1.0 - 0.2 * diff
        how = f"born {r.birth_year}, {diff} year(s) from {q.birth_year} (within ±{tol})"
    else:
        score = 0.0
        how = f"born {r.birth_year}, {diff} years from {q.birth_year} (outside ±{tol})"
    return ScorePart("birth year", score, WEIGHTS["birth year"], how)


def _place(q: PersonQuery, r: Record) -> ScorePart | None:
    if not (q.birthplace or q.county):
        return None
    rec_places = [p for p in (r.birthplace, r.parish, r.municipality) if p]
    if not rec_places and not r.county:
        return ScorePart("place", 0.4, WEIGHTS["place"], "record has no place")
    best, best_place = 0.0, ""
    if q.birthplace:
        for p in rec_places:
            s = max(names.word_similarity(q.birthplace, t) for t in p.split())
            if s > best:
                best, best_place = s, p
    if best >= 0.95:
        return ScorePart("place", 1.0, WEIGHTS["place"], f"same place ({best_place})")
    if best >= 0.88:
        return ScorePart("place", best, WEIGHTS["place"],
                         f"{q.birthplace} vs {best_place}: likely the same place, spelled differently")
    if q.county and r.county and names.word_similarity(q.county, r.county) >= 0.95:
        how = f"same county ({r.county})" + (", different parish" if q.birthplace else "")
        return ScorePart("place", max(best, 0.6 if q.birthplace else 1.0), WEIGHTS["place"], how)
    where = ", ".join(rec_places) or r.county
    return ScorePart("place", best, WEIGHTS["place"], f"{q.birthplace or q.county} vs {where}: does not match")


def _family(q: PersonQuery, r: Record) -> ScorePart | None:
    pairs = [("father", q.father_name, r.father_name),
             ("mother", q.mother_name, r.mother_name),
             ("spouse", q.spouse_name, r.spouse_name)]
    asked = [(rel, qv, rv) for rel, qv, rv in pairs if qv]
    if not asked:
        return None
    scores, hows = [], []
    for rel, qv, rv in asked:
        if not rv:
            # Many records simply do not list the relation: neutral, not negative.
            scores.append(0.5)
            hows.append(f"{rel} not listed in record")
            continue
        sim, female = _relation_similarity(rel, qv, rv, q.sex)
        scores.append(sim)
        if sim >= 0.9:
            hows.append(f"{rel} {rv} vs {qv}: match" + (" (first name; surname can change at marriage)" if female else ""))
        elif sim < CONFLICT_BELOW:
            hows.append(f"{rel} {rv} vs {qv}: CONFLICT")
        else:
            hows.append(f"{rel} {rv} vs {qv}: similarity {sim:.2f}")
    return ScorePart("family", sum(scores) / len(scores), WEIGHTS["family"], "; ".join(hows))


# A listed relation this far from the query is evidence of a different person.
CONFLICT_BELOW = 0.75


def _relation_similarity(rel: str, qv: str, rv: str, q_sex: str) -> tuple[float, bool]:
    """Similarity of a queried relative's name to the one in the record.

    Women usually appear under their husband's surname after marriage, so a
    mother, or the wife of a man, is compared on given name only. Men keep
    their surname, so a clearly different surname or patronymic means a
    different person (common given names like Ole or Hans identify no one).
    Returns (similarity, compared_on_given_name_only).
    """
    g = names.given_name_similarity(qv, rv)
    female = rel == "mother" or (rel == "spouse" and q_sex.lower()[:1] != "f")
    q_sur = " ".join(qv.split()[1:])
    r_sur = " ".join(rv.split()[1:])
    if female or not (q_sur and r_sur):
        return g, female
    s_, _ = names.surname_similarity(q_sur, r_sur)
    sim = 0.5 * g + 0.5 * s_
    return (min(sim, 0.6) if s_ < 0.6 else sim), False


def family_status(q: PersonQuery, r: Record) -> tuple[int, int, int]:
    """(relations asked, relations listed in record, conflicts)."""
    asked = listed = conflicts = 0
    for rel, qv, rv in (("father", q.father_name, r.father_name), ("mother", q.mother_name, r.mother_name),
                        ("spouse", q.spouse_name, r.spouse_name)):
        if not qv:
            continue
        asked += 1
        if not rv:
            continue
        listed += 1
        sim, _ = _relation_similarity(rel, qv, rv, q.sex)
        if sim < CONFLICT_BELOW:
            conflicts += 1
    return asked, listed, conflicts


def _sex_conflict(q: PersonQuery, r: Record) -> bool:
    return bool(q.sex and r.sex and q.sex[0].lower() != r.sex[0].lower())


def score_record(q: PersonQuery, r: Record) -> Candidate:
    parts = [p for p in (_given(q, r), _surname(q, r), _birth_year(q, r),
                         _place(q, r), _family(q, r)) if p is not None]
    total_w = sum(p.weight for p in parts)
    score = sum(p.score * p.weight for p in parts) / total_w if total_w else 0.0
    notes: list[str] = []
    if _sex_conflict(q, r):
        score *= 0.3
        notes.append(f"sex in record ({r.sex}) differs from query ({q.sex})")
    by = next((p for p in parts if p.name == "birth year"), None)
    if by is not None and by.score == 0.0:
        score *= 0.6
        notes.append("birth year outside tolerance")
    asked, listed, conflicts = family_status(q, r)
    if conflicts:
        score *= 0.6 ** conflicts
        notes.append(f"{conflicts} listed family member(s) conflict with the query")
    if r.extracted_by_model:
        notes.append("fields were extracted from the transcription by a model; check the source")
    if r.relations_inferred and listed:
        notes.append("parents/spouse in this record are inferred from household position")
    if r.birth_year_from_age:
        notes.append("birth year in record is computed from stated age (often ±1)")
    conf = confidence_for(score)
    if by is not None and by.score == 0.0:
        conf = "low"   # contradicts a known fact about the person
    if asked and not listed and conf == "high":
        conf = "medium"
        notes.append("record lists none of the queried family members, so namesakes cannot be ruled out")
    return Candidate(record=r, score=score, confidence=conf, parts=parts, notes=notes)


def confidence_for(score: float) -> str:
    if score >= HIGH:
        return "high"
    if score >= MEDIUM:
        return "medium"
    return "low"


def rank(candidates: list[Candidate]) -> list[Candidate]:
    """Sort, drop weak candidates, and downgrade ambiguous leaders."""
    ranked = sorted((c for c in candidates if c.score >= REPORT_MIN),
                    key=lambda c: c.score, reverse=True)
    # Several records can describe the same person (census + baptism), so a
    # rival only counts when it looks like a different person. If two strong
    # candidates are clearly different people, neither can be "high".
    # every candidate strong enough to be rated high, however far down the list
    strong = [c for c in ranked if c.score >= HIGH - AMBIGUITY_GAP]
    for c in strong:
        rival = next((o for o in strong if o is not c and o.score >= c.score - AMBIGUITY_GAP * 3
                      and _looks_like_different_person(c.record, o.record)), None)
        if rival is not None:
            if c.confidence == "high":
                c.confidence = "medium"
            c.notes.append(f"close rival: {rival.record.record_id} looks like a different person "
                           "with a similar score")
    return ranked


def _looks_like_different_person(a: Record, b: Record) -> bool:
    if a.birth_year and b.birth_year and abs(a.birth_year - b.birth_year) > 1:
        return True
    if a.spouse_name and b.spouse_name and names.given_name_similarity(a.spouse_name, b.spouse_name) < 0.9:
        return True
    # birthplace never changes for a person (residence does, so it isn't used)
    pa, pb = a.birthplace, b.birthplace
    if pa and pb and max(
            (names.word_similarity(x, y) for x in pa.split() for y in pb.split()), default=0) < 0.85:
        return True
    if a.father_name and b.father_name and names.given_name_similarity(a.father_name, b.father_name) < 0.9:
        return True
    if a.record_type == b.record_type and a.year == b.year and a.source == b.source:
        return True  # two entries in the same census can't be one person
    return False
