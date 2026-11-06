import json

import pytest

from webapp.app import create_app

EXAMPLE = {"given_name": "Ole Andreas", "surname": "Larsen", "birth_year": "1851", "birthplace": "Rakkestad",
           "county": "Østfold", "sex": "m", "father_name": "Lars Olsen", "spouse_name": "Marte Kristine"}


@pytest.fixture(scope="module")
def client():
    return create_app().test_client()   # invented demo family


def test_index_shows_prototype_notice(client):
    html = client.get("/").get_data(as_text=True)
    assert "Prototype." in html and "invented example family" in html


def test_search_finds_the_demo_ancestor_in_three_censuses(client):
    data = client.post("/api/search", json=EXAMPLE).get_json()
    top = [c for c in data["candidates"] if c["record_name"].startswith("Ole Andreas Lars")
           and c["birth_year_in_record"] == 1851]
    assert {c["year"] for c in top} == {1865, 1900, 1910}
    namesake = next(c for c in data["candidates"] if c["birth_year_in_record"] == 1852)
    assert namesake["confidence"] != "high"
    first = data["candidates"][0]
    assert len(first["household"]) > 1 and first["explanation"] and first["demo"] is True and first["link"] is None


def test_privacy_guard(client):
    res = client.post("/api/search", json={"given_name": "Kari", "birth_year": "1960"})
    assert res.status_code == 422 and res.get_json()["kind"] == "privacy"


def test_input_errors(client):
    assert client.post("/api/search", json={"given_name": "Ole"}).status_code == 400
    assert client.post("/api/search", json={"given_name": "Ole", "birth_year": "abc"}).status_code == 400


def test_report_lists_only_confirmed(client):
    data = client.post("/api/search", json=EXAMPLE).get_json()
    a, b = data["candidates"][0]["record_id"], data["candidates"][1]["record_id"]
    payload = {"query": data["query"], "decisions": {a: {"status": "confirmed", "reasons": ["First name: same"]},
                                                     b: {"status": "rejected"}}}
    html = client.post("/report", data={"payload": json.dumps(payload)}).get_data(as_text=True)
    assert a in html and b not in html and "1 ruled out" in html and "Example report" in html
