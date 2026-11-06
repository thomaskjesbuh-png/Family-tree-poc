import pytest

from ancestor_finder.models import PersonQuery
from ancestor_finder.pipeline import PrivacyError, find
from ancestor_finder.sources import DigitalarkivetSource, LocalFileSource, SourceUnavailable
from ancestor_finder.cache import Cache
from ancestor_finder.llm import cost_usd


def test_end_to_end_on_sample():
    q = PersonQuery(given_name="Ole", surname="Hansen", birth_year=1851, birthplace="Rakkestad",
                    sex="m", father_name="Hans Olsen")
    res = find(q, LocalFileSource())
    assert res.candidates[0].record.record_id == "S010"
    assert all(c.record.url for c in res.candidates)


def test_recent_records_are_never_returned():
    q = PersonQuery(given_name="Ole", surname="Hansen", birth_year=1898, birthplace="Rakkestad")
    res = find(q, LocalFileSource())
    assert "S099" not in [c.record.record_id for c in res.candidates]


def test_living_people_refused():
    with pytest.raises(PrivacyError):
        find(PersonQuery(given_name="Ola", birth_year=1950), LocalFileSource())
    with pytest.raises(PrivacyError):
        find(PersonQuery(given_name="Ola"), LocalFileSource())


def test_no_match_returns_nothing():
    q = PersonQuery(given_name="Gunhild", surname="Torstensdatter", birth_year=1835, birthplace="Glemmen")
    assert find(q, LocalFileSource()).candidates == []


def test_raw_text_skipped_without_model():
    q = PersonQuery(given_name="Marie", surname="Johansdatter", birth_year=1880, birthplace="Idd")
    res = find(q, LocalFileSource())
    assert any("S033" in w for w in res.warnings)


def test_digitalarkivet_refuses_until_access_confirmed():
    with pytest.raises(SourceUnavailable):
        DigitalarkivetSource().search(PersonQuery(given_name="Ole", birth_year=1850))


def test_cache_roundtrip(tmp_path):
    c = Cache(tmp_path / "c.sqlite")
    c.put("ns", "k", {"a": 1})
    assert c.get("ns", "k") == {"a": 1}
    assert c.get("ns", "missing") is None


def test_cost_calculation():
    usage = {"input_tokens": 1_000_000, "output_tokens": 0}
    assert cost_usd("claude-haiku-5-5", usage) == pytest.approx(0.10)
    usage = {"input_tokens": 0, "output_tokens": 1_000_000, "cache_read_input_tokens": 1_000_000}
    assert cost_usd("claude-sonnet-5-5", usage) == pytest.approx(10.0 + 0.2)


def test_no_census_before_birth():
    # born 1898: the 1865 records can't be this person
    q = PersonQuery(given_name="Ole", surname="Hansen", birth_year=1898, birthplace="Rakkestad")
    res = find(q, LocalFileSource())
    assert all(c.record.year >= 1896 for c in res.candidates)
