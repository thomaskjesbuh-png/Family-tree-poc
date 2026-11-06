from ancestor_finder.models import PersonQuery, Record
from ancestor_finder.scoring import rank, score_record


def rec(**kw):
    base = dict(record_id="R", source="test", record_type="census", year=1865, url="sample://R")
    base.update(kw)
    return Record(**base)


Q = PersonQuery(given_name="Kristine", surname="Olsdatter", birth_year=1848,
                birthplace="Skjeberg", county="Østfold", sex="f", father_name="Ole Larsen")


def test_exact_match_is_high():
    c = score_record(Q, rec(given_name="Christine", surname="Olsdatter", birth_year=1848,
                             parish="Skjeberg", county="Østfold", sex="f", father_name="Ole Larsen"))
    assert c.confidence == "high" and c.score > 0.95


def test_every_part_is_explained():
    c = score_record(Q, rec(given_name="Kristine", surname="Olsen", birth_year=1847))
    assert {p.name for p in c.parts} == {"given name", "surname", "birth year", "place", "family"}
    assert all(p.explanation for p in c.parts)


def test_birth_year_tolerance():
    inside = score_record(Q, rec(given_name="Kristine", surname="Olsdatter", birth_year=1850, parish="Skjeberg"))
    outside = score_record(Q, rec(given_name="Kristine", surname="Olsdatter", birth_year=1851, parish="Skjeberg"))
    assert inside.score > outside.score
    assert "outside" in next(p for p in outside.parts if p.name == "birth year").explanation


def test_conflicting_father_is_penalised():
    good = score_record(Q, rec(given_name="Kristine", surname="Olsdatter", birth_year=1849,
                                parish="Skjeberg", father_name="Ole Larsen"))
    bad = score_record(Q, rec(given_name="Kristine", surname="Olsdatter", birth_year=1849,
                               parish="Skjeberg", father_name="Ole Hansen"))
    assert bad.score < good.score * 0.7
    assert bad.confidence != "high"


def test_missing_family_caps_at_medium():
    c = score_record(Q, rec(given_name="Kristine", surname="Olsdatter", birth_year=1848,
                             parish="Skjeberg", county="Østfold", sex="f"))
    assert c.confidence == "medium"
    assert any("namesakes" in n for n in c.notes)


def test_sex_conflict():
    c = score_record(Q, rec(given_name="Kristian", surname="Olsen", birth_year=1848, sex="m",
                             parish="Skjeberg", father_name="Ole Larsen"))
    assert c.confidence == "low"


def test_baptism_without_surname_uses_father():
    c = score_record(Q, rec(record_type="baptism", given_name="Kirstine", birth_year=1848,
                             parish="Skjeberg", father_name="Ole Larssen"))
    s = next(p for p in c.parts if p.name == "surname")
    assert s.score >= 0.9


def test_sparse_query_not_punished():
    q = PersonQuery(given_name="Ole", surname="Hansen", birth_year=1851)
    c = score_record(q, rec(given_name="Ole", surname="Hansen", birth_year=1851))
    assert c.score == 1.0


def test_rank_drops_weak_and_sorts():
    strong = score_record(Q, rec(record_id="A", given_name="Kristine", surname="Olsdatter",
                                 birth_year=1848, parish="Skjeberg", father_name="Ole Larsen"))
    weak = score_record(Q, rec(record_id="B", given_name="Berte", surname="Hansen", birth_year=1830))
    ranked = rank([weak, strong])
    assert [c.record.record_id for c in ranked] == ["A"]


def test_married_name_is_not_a_conflict():
    # the family knows her maiden name; the census uses her married name
    q = PersonQuery(given_name="Lars", surname="Larsen", birth_year=1877, sex="m",
                    spouse_name="Marte Sofie Pedersen")
    c = score_record(q, rec(given_name="Lars", surname="Larsen", birth_year=1877, sex="m",
                             spouse_name="Marte Larsen"))
    assert not any("conflict" in n for n in c.notes)
    child = PersonQuery(given_name="Johan", surname="Larsen", birth_year=1902, sex="m",
                        father_name="Lars Peder Larsen", mother_name="Marte Sofie Pedersen")
    c = score_record(child, rec(given_name="Johan", surname="Larsen", birth_year=1902, sex="m",
                                 father_name="Lars Larsen", mother_name="Marte Larsen"))
    assert c.confidence == "high" and not any("conflict" in n for n in c.notes)


def test_woman_found_under_husbands_surname():
    q = PersonQuery(given_name="Marte", surname="Pedersen", birth_year=1879, sex="f",
                    spouse_name="Lars Larsen")
    c = score_record(q, rec(given_name="Marte", surname="Larsen", birth_year=1879, sex="f"))
    assert next(p for p in c.parts if p.name == "surname").score >= 0.9


def test_father_with_other_surname_is_still_a_conflict():
    q = PersonQuery(given_name="Ole", surname="Hansen", birth_year=1851, father_name="Hans Olsen")
    c = score_record(q, rec(given_name="Ole", surname="Hansen", birth_year=1851, father_name="Hans Pedersen"))
    assert any("conflict" in n for n in c.notes)


def test_birth_year_outside_tolerance_is_low():
    q = PersonQuery(given_name="Ingrid", surname="Olsen", birth_year=1917)
    c = score_record(q, rec(given_name="Ingrid", surname="Olsen", birth_year=1909))
    assert c.confidence == "low"
