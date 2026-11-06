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
    assert "Prototype." in html and "ingen av disse personene har levd" in html
    assert "Hver historie begynner med deg" in html and "Sporet etter" in html and 'lang="nb"' in html


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
    assert "privatlivet" in res.get_json()["error"]


def test_input_errors(client):
    assert client.post("/api/search", json={"given_name": "Ole"}).status_code == 400
    assert client.post("/api/search", json={"given_name": "Ole", "birth_year": "abc"}).status_code == 400


def test_report_lists_only_confirmed(client):
    data = client.post("/api/search", json=EXAMPLE).get_json()
    a, b = data["candidates"][0]["record_id"], data["candidates"][1]["record_id"]
    payload = {"query": data["query"], "decisions": {a: {"status": "confirmed", "reasons": ["First name: same"]},
                                                     b: {"status": "rejected"}}}
    html = client.post("/report", data={"payload": json.dumps(payload)}).get_data(as_text=True)
    assert a in html and b not in html and "1 mulig post ble lagt til side" in html
    assert "Et eksempelkapittel" in html and "Et kapittel i The Book of Me" in html


def test_app_name_is_configurable(monkeypatch):
    monkeypatch.setenv("AF_APP_NAME", "Slektspor")
    html = create_app().test_client().get("/").get_data(as_text=True)
    assert "<title>Slektspor</title>" in html


def test_relatives_from_a_strong_match(client):
    person = {"given_name": "Ole Andreas", "surname": "Larsen", "birth_year": "1851", "birthplace": "Rakkestad",
              "sex": "m", "spouse_name": "Marte Kristine"}
    data = client.post("/api/relatives", json={"person": person}).get_json()
    names = {(s["relation"], s["name"], s["birth_year"]) for s in data["suggestions"]}
    assert ("father", "Lars Olsen", 1822) in names and ("mother", "Berte Hansdatter", 1826) in names
    father = next(s for s in data["suggestions"] if s["relation"] == "father")
    assert father["record_id"] and father["evidence"][0]["year"] == 1865 and father["role"] == "Husfader"
    # the namesake next door has another Lars Olsen as father: shown as a rival, not hidden
    fathers = [s for s in data["suggestions"] if s["relation"] == "father"]
    assert len(fathers) == 2 and all(s["rivals"] == 1 and s["confidence"] == "medium" for s in fathers)


def test_relatives_prefers_kept_records_and_skips_the_living(client):
    person = {"given_name": "Kristian", "surname": "Olsen", "birth_year": "1886", "birthplace": "Rakkestad"}
    kept = client.post("/api/search", json=person).get_json()["candidates"][0]["record_id"]
    data = client.post("/api/relatives", json={"person": person, "kept": [kept]}).get_json()
    assert data["basis"] == "kept" and all(e["how"] == "kept" for s in data["suggestions"] for e in s["evidence"])
    living = client.post("/api/relatives", json={"person": {"given_name": "Dorthe", "birth_year": "1955"}}).get_json()
    assert living == {"suggestions": [], "basis": "living"}


def test_relatives_merges_spellings_of_one_parent(client):
    person = {"given_name": "Kristian", "surname": "Olsen", "birth_year": "1886", "birthplace": "Rakkestad", "sex": "m"}
    data = client.post("/api/relatives", json={"person": person}).get_json()
    mothers = [s for s in data["suggestions"] if s["relation"] == "mother"]
    assert len(mothers) == 1 and mothers[0]["rivals"] == 0 and len(mothers[0]["evidence"]) == 2
    assert mothers[0]["also_written"]
