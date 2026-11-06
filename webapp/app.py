"""Ancestor Finder web interface (prototype).

    python -m webapp                                   # invented demo family
    python -m webapp --records data/real/records.csv   # imported census data

Commercial use is NOT cleared: no licence is stated for the census files and
Digitalarkivet's robots.txt bars AI agents (see docs/access-findings.md). The
page shows a prototype notice until AF_COMMERCIAL_CLEARED=1 is set, which
should only happen once Nasjonalarkivet has confirmed the terms in writing.
"""

from __future__ import annotations

import datetime as dt
import os
import time
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request

from ancestor_finder.cache import Cache
from ancestor_finder.models import PersonQuery, Record, cutoff_year
from ancestor_finder.names import canonical_given
from ancestor_finder.pipeline import PrivacyError, find
from ancestor_finder.sources import LocalFileSource

ROOT = Path(__file__).resolve().parents[1]
DEMO_RECORDS = ROOT / "data" / "demo" / "demo_records.csv"
MAX_RESULTS = 25

QUERY_FIELDS = ("given_name", "surname", "name_variants", "birth_year", "birth_year_tolerance",
                "birthplace", "county", "sex", "father_name", "mother_name", "spouse_name")


def _source_link(r: Record) -> str | None:
    return r.url if r.url.startswith(("http://", "https://")) else None


def _person_brief(r: Record) -> dict:
    return {"record_id": r.record_id, "name": r.full_name, "sex": r.sex, "birth_year": r.birth_year,
            "birthplace": r.birthplace, "role": r.role}


def _parse_query(data: dict) -> PersonQuery:
    clean = {}
    for k in QUERY_FIELDS:
        v = data.get(k)
        if v in (None, "", []):
            continue
        if k == "name_variants" and isinstance(v, str):
            v = [x.strip() for x in v.split(",") if x.strip()]
        clean[k] = v
    if not clean.get("given_name"):
        raise ValueError("Skriv inn minst et fornavn.")
    if not clean.get("birth_year"):
        raise ValueError("Skriv inn et omtrentlig fødselsår.")
    try:
        clean["birth_year"] = int(clean["birth_year"])
        if "birth_year_tolerance" in clean:
            clean["birth_year_tolerance"] = max(0, min(10, int(clean["birth_year_tolerance"])))
    except (TypeError, ValueError):
        raise ValueError("Fødselsåret må være et tall, for eksempel 1851.")
    return PersonQuery.from_dict(clean)


def _word_index(app: Flask, year: int) -> dict[str, list[Record]]:
    """Census year -> phonetic surname/farm word -> records, built once per year."""
    from ancestor_finder import names as N
    index = app.config.setdefault("WORD_INDEX", {})
    if year not in index:
        idx: dict[str, list[Record]] = {}
        for r in app.config["SOURCE"].records:
            if r.year == year:
                for w in set(N.clean(f"{r.surname} {r.farm}").split()):
                    k = N.phonetic(w)
                    if len(k) > 2:
                        idx.setdefault(k, []).append(r)
        index[year] = idx
    return index[year]


def _given_index(app: Flask, year: int) -> dict[str, list[Record]]:
    """Census year -> canonical first given name -> records, built once per year."""
    from ancestor_finder import names as N
    index = app.config.setdefault("GIVEN_INDEX_BY_YEAR", {})
    if year not in index:
        idx: dict[str, list[Record]] = {}
        for r in app.config["SOURCE"].records:
            if r.year == year and r.given_name:
                idx.setdefault(N.canonical_given(r.given_name), []).append(r)
        index[year] = idx
    return index[year]


def _namesakes(app: Flask, r: Record, house: list[Record]) -> dict:
    """Others in the same census and municipality with the same first name,
    sex and about the same age. None means the record picks out one person
    there, which is evidence in
    itself; several mean the family has to tell them apart."""
    from ancestor_finder import names as N
    place = r.municipality or r.parish
    in_house = {h.record_id for h in house}
    others = [o for o in _given_index(app, r.year).get(N.canonical_given(r.given_name), [])
              if o.record_id != r.record_id and o.record_id not in in_house
              and (o.municipality or o.parish) == place and (not r.sex or not o.sex or o.sex == r.sex)
              and o.birth_year is not None and abs(o.birth_year - r.birth_year) <= 2]
    return {"count": len(others), "place": place, "year": r.year,
            "given_name": r.given_name.split()[0],
            "examples": [_person_brief(o) | {"farm": o.farm} for o in others[:5]]}


def split_families(house: list[Record]) -> list[dict]:
    """One dwelling can hold several families: start a new one at each
    husband-head, or at a wife-coded woman with no husband before her."""
    from ancestor_finder.importers.households import is_head, is_wife
    fams, cur = [], None
    for h in house:
        starts_male = h.sex == "m" and is_head(h.role, h.sex)
        starts_female = h.sex == "f" and is_wife(h.role) and (cur is None or cur["mother"] is not None)
        if starts_male or starts_female:
            cur = {"father": h if starts_male else None, "mother": h if starts_female else None, "members": [h]}
            fams.append(cur)
        elif cur is not None and cur["mother"] is None and h.sex == "f" and is_wife(h.role):
            cur["mother"] = h; cur["members"].append(h)
        elif cur is not None:
            cur["members"].append(h)
    return fams


def warm_indexes(app: Flask) -> None:
    """Build the word and given-name indexes for the last census, so the first
    search for a family doesn't wait for them."""
    years = app.config["COVERAGE"]["years"]
    if years:
        _word_index(app, max(years))
        _given_index(app, max(years))


def _brief_named(h: Record | None) -> dict | None:
    return _person_brief(h) | {"given_name": h.given_name, "surname": h.surname} if h else None


def create_app(records_path: Path | str | None = None) -> Flask:
    app = Flask(__name__)
    path = Path(records_path) if records_path else DEMO_RECORDS
    t0 = time.time()
    source = LocalFileSource(path)
    is_demo = path.resolve() == DEMO_RECORDS.resolve()
    years = sorted({r.year for r in source.records})
    counties = sorted({r.county for r in source.records if r.county})
    app.config.update(
        SOURCE=source, IS_DEMO=is_demo, RECORDS_PATH=str(path), LOAD_SECONDS=round(time.time() - t0, 1),
        COMMERCIAL_CLEARED=os.environ.get("AF_COMMERCIAL_CLEARED") == "1",
        # The design manual leaves the name open (candidates: Sporene, Slektspor,
        # Ætt, Kilde, Gården; trademark check pending), so it is configurable.
        APP_NAME=os.environ.get("AF_APP_NAME", "Spor"),
        COVERAGE={"years": years, "counties": counties, "records": len(source.records)},
    )
    helper = None
    if os.environ.get("AF_USE_LLM") == "1":
        from ancestor_finder.llm import ClaudeHelper
        if ClaudeHelper.available():
            helper = ClaudeHelper(Cache(ROOT / "cache" / "ancestor_finder.sqlite"))
    app.config["HELPER"] = helper

    def status() -> dict:
        return {"demo": app.config["IS_DEMO"], "coverage": app.config["COVERAGE"],
                "app_name": app.config["APP_NAME"],
                "commercial_cleared": app.config["COMMERCIAL_CLEARED"],
                "model_checks": helper is not None, "cutoff_year": cutoff_year()}

    @app.get("/")
    def index():
        return render_template("index.html", status=status())

    @app.get("/api/status")
    def api_status():
        return jsonify(status())

    @app.post("/api/search")
    def api_search():
        data = request.get_json(silent=True) or {}
        try:
            q = _parse_query(data)
            res = find(q, source, helper=helper)
        except PrivacyError:
            return jsonify({"error": f"Vi søker bare etter personer født i {cutoff_year()} eller tidligere, "
                                     "slik at de levende får beholde privatlivet sitt.", "kind": "privacy"}), 422
        except ValueError as e:
            return jsonify({"error": str(e), "kind": "input"}), 400
        out = []
        for rank, c in enumerate(res.candidates[:MAX_RESULTS], 1):
            d = c.to_dict()
            r = c.record
            d.update(rank=rank, link=_source_link(r), demo=r.url.startswith("demo://"),
                     farm=r.farm, municipality=r.municipality or r.parish, county=r.county,
                     record_name=r.full_name, sex=r.sex, role=r.role, birthplace=r.birthplace,
                     father=r.father_name, mother=r.mother_name, spouse=r.spouse_name,
                     household=[_person_brief(h) for h in source.household(r.record_id)])
            out.append(d)
        return jsonify({"query": {k: getattr(q, k) for k in QUERY_FIELDS},
                        "total": len(res.candidates), "shown": len(out), "candidates": out,
                        "warnings": res.warnings, "model_checks_used": res.llm_used})

    @app.post("/api/relatives")
    def api_relatives():
        """Suggest a person's parents from their census household.

        Uses the records the user already added for this person; otherwise only
        strong (high) matches. Parents are read from the household position, so
        every suggestion is a lead to confirm, never a stated fact.
        """
        data = request.get_json(silent=True) or {}
        try:
            q = _parse_query(data.get("person") or {})
        except ValueError as e:
            return jsonify({"error": str(e), "kind": "input"}), 400
        if q.birth_year and q.birth_year > cutoff_year():
            return jsonify({"suggestions": [], "basis": "living"})

        bases = []   # (record, how, confidence)
        for rid in data.get("kept") or []:
            r = source.get(str(rid))
            if r is not None:
                bases.append((r, "kept", "high"))
        if not bases:
            try:
                res = find(q, source, helper=helper)
            except PrivacyError:
                return jsonify({"suggestions": [], "basis": "living"})
            # strong and possible matches; a parent found only through a possible
            # match is shown as unconfirmed, and rival families are flagged
            bases = [(c.record, "match", c.confidence) for c in res.candidates
                     if c.confidence in ("high", "medium")][:5]

        found: dict[tuple, dict] = {}
        for r, how, conf in bases:
            house = source.household(r.record_id)
            for relation, pname in (("father", r.father_name), ("mother", r.mother_name)):
                if not pname:
                    continue
                prec = next((h for h in house if h.full_name == pname), None)
                given = prec.given_name if prec else " ".join(pname.split()[:-1]) or pname
                surname = prec.surname if prec else (pname.split()[-1] if len(pname.split()) > 1 else "")
                by = prec.birth_year if prec else None
                # the same parent is often spelled differently in two censuses
                # ("Marte Kristine Larsen" / "Marte Kristine Lars."): merge on the
                # first name and a birth year within a year
                key = next((k for k in found if k[0] == relation and k[1] == canonical_given(pname)
                            and (k[2] is None or by is None or abs(k[2] - by) <= 1)),
                           (relation, canonical_given(pname), by))
                if key in found and pname != found[key]["name"] and pname not in found[key]["also_written"]:
                    found[key]["also_written"].append(pname)
                s = found.setdefault(key, {
                    "relation": relation, "name": pname, "given_name": given, "surname": surname,
                    "birth_year": prec.birth_year if prec else None,
                    "birthplace": prec.birthplace if prec else "",
                    "role": prec.role if prec else "", "record_id": prec.record_id if prec else None,
                    "also_written": [], "evidence": []})
                s["evidence"].append({
                    "how": how, "confidence": conf, "child_record_id": r.record_id, "year": r.year,
                    "child_name": r.full_name, "child_role": r.role,
                    "place": ", ".join(x for x in (r.farm, r.municipality or r.parish) if x),
                    "source": f"{r.source} · {r.record_id}", "link": _source_link(r)})
        for sgg in found.values():
            sgg["confidence"] = "high" if any(e["how"] == "kept" or e["confidence"] == "high"
                                              for e in sgg["evidence"]) else "medium"
        per_relation: dict[str, int] = {}
        for sgg in found.values():
            per_relation[sgg["relation"]] = per_relation.get(sgg["relation"], 0) + 1
        for sgg in found.values():
            sgg["rivals"] = per_relation[sgg["relation"]] - 1
        suggestions = sorted(found.values(), key=lambda s: (
            0 if any(e["how"] == "kept" for e in s["evidence"]) else 1, s["confidence"] != "high",
            s["relation"], -len(s["evidence"])))
        return jsonify({"suggestions": suggestions,
                        "basis": "kept" if any(h == "kept" for _, h, _ in bases) else ("match" if bases else "none")})

    @app.post("/api/families")
    def api_families():
        """Households that could be a person's family, for someone born after
        the last census we have (or with too little to search on).

        Looks in the last census before the child's birth for dwellings where a
        surname or farm name matches the child's surname, and ranks those in
        the child's birthplace first. Every result is a lead, never a fact.
        """
        from ancestor_finder import names as N
        data = request.get_json(silent=True) or {}
        surname = (data.get("surname") or "").strip()
        if not surname:
            return jsonify({"error": "Etternavn trengs for å lete etter familien.", "kind": "input"}), 400
        try:
            child_year = int(data.get("birth_year")) if data.get("birth_year") else None
        except ValueError:
            child_year = None
        years = sorted(app.config["COVERAGE"]["years"])
        if not years:
            return jsonify({"year": None, "families": [], "total": 0})
        year = max([y for y in years if child_year is None or y <= child_year] or years[:1])
        place_k = N.place_key(data.get("birthplace") or "")
        tokens = [t for t in N.clean(surname).split() if len(t) > 2]

        idx = _word_index(app, year)
        keys = {k for k in idx for t in tokens if N.word_similarity(t, k) >= 0.92}
        hits = sorted({r.record_id: r for k in keys for r in idx[k]}.values(), key=lambda r: source._pos[r.record_id])
        brief = _brief_named

        seen_houses, seen_couples, families = set(), set(), []
        for r in hits:
            house = source.household(r.record_id)
            hkey = house[0].record_id if house else r.record_id
            if hkey in seen_houses:
                continue
            seen_houses.add(hkey)
            for fam in split_families(house or [r]):
                f, m = fam["father"], fam["mother"]
                couple = (f.record_id if f else None, m.record_id if m else None)
                if couple in seen_couples:
                    continue
                seen_couples.add(couple)
                lead = f or m
                # the family must carry the name: a member's surname or the farm
                carries = any(N.word_similarity(t, w) >= 0.92 for t in tokens
                              for h in fam["members"] for w in N.clean(f"{h.surname} {h.farm}").split())
                if not carries:
                    continue
                # parents must be of an age to have this child: mother 16–48, father 16–70
                if child_year:
                    if m and m.birth_year and not (child_year - 48 <= m.birth_year <= child_year - 16):
                        continue
                    if f and f.birth_year and not (child_year - 70 <= f.birth_year <= child_year - 16):
                        continue
                place = lead.municipality or lead.parish
                same_place = bool(place_k) and N.word_similarity(N.place_key(place), place_k) >= 0.88
                score = (2 if same_place else 0) + \
                        (1 if any(N.word_similarity(t, w) >= 0.92 for t in tokens for w in N.clean(lead.farm).split()) else 0) + \
                        (1 if f and m else 0)
                families.append({
                    "score": score, "year": year, "farm": lead.farm, "place": place, "county": lead.county,
                    "source": f"{lead.source} · {lead.record_id}", "link": _source_link(lead),
                    "father": brief(f), "mother": brief(m),
                    "members": [_person_brief(h) for h in fam["members"]]})
        families.sort(key=lambda f: -f["score"])
        return jsonify({"year": year, "families": families[:20], "total": len(families)})

    @app.post("/api/parent-leads")
    def api_parent_leads():
        """Possible fathers for someone born after the last census, found as
        men in that census: a father born around 1900 is a child in 1910,
        living with his own parents, so one find can add two generations.

        A man qualifies when his surname or farm carries the child's surname,
        or, when the child's surname is a patronymic (Samuelsen), when his
        given name is its root (Samuel). He must be 18–55 years older than the
        child. Every result is a lead, never a fact.
        """
        from ancestor_finder.importers.households import child_kind
        from ancestor_finder import names as N
        data = request.get_json(silent=True) or {}
        surname = (data.get("surname") or "").strip()
        try:
            child_year = int(data.get("birth_year"))
        except (TypeError, ValueError):
            return jsonify({"error": "Fødselsår trengs for å lete etter foreldrene.", "kind": "input"}), 400
        if not surname:
            return jsonify({"error": "Etternavn trengs for å lete etter foreldrene.", "kind": "input"}), 400
        years = sorted(app.config["COVERAGE"]["years"])
        if not years:
            return jsonify({"year": None, "leads": [], "total": 0})
        year = max([y for y in years if y <= child_year] or years[:1])
        lo, hi = child_year - 55, child_year - 18
        include_heads = bool(data.get("include_heads", True))
        place_k = N.place_key(data.get("birthplace") or "")
        tokens = [t for t in N.clean(surname).split() if len(t) > 2]

        found: dict[str, tuple[Record, str]] = {}
        idx = _word_index(app, year)
        for k in {k for k in idx for t in tokens if N.word_similarity(t, k) >= 0.92}:
            for r in idx[k]:
                found.setdefault(r.record_id, (r, "surname"))
        # a patronymic surname may come from the father's given name (Samuelsen -> Samuel)
        roots = {pr[0] for t in tokens if (pr := N.patronymic_root(t))}
        if roots:
            for key, recs in _given_index(app, year).items():
                if N._strip_genitive(key) in roots:
                    for r in recs:
                        found.setdefault(r.record_id, (r, "given"))

        leads = []
        for r, why in found.values():
            if r.sex != "m" or not r.birth_year or not (lo <= r.birth_year <= hi):
                continue
            house = source.household(r.record_id) or [r]
            fam = next((f for f in split_families(house) if any(h.record_id == r.record_id for h in f["members"])), None)
            head = bool(fam and fam["father"] and fam["father"].record_id == r.record_id)
            if head and not include_heads:
                continue
            father = mother = wife = None
            if head:
                wife = fam["mother"]
            elif fam and child_kind(r.role):
                father, mother = fam["father"], fam["mother"]
            place = r.municipality or r.parish
            same_place = bool(place_k) and N.word_similarity(N.place_key(place), place_k) >= 0.88
            score = (2 if same_place else 0) + (1 if why == "surname" else 0) + (1 if father or mother else 0) + \
                    (1 if abs((child_year - r.birth_year) - 30) <= 8 else 0)
            leads.append({
                "score": score, "why": why, "year": year, "farm": r.farm, "place": place, "county": r.county,
                "source": f"{r.source} · {r.record_id}", "link": _source_link(r), "head": head,
                "person": _brief_named(r), "father": _brief_named(father), "mother": _brief_named(mother),
                "wife": _brief_named(wife)})
        leads.sort(key=lambda x: (-x["score"], abs((child_year - x["person"]["birth_year"]) - 30)))
        return jsonify({"year": year, "leads": leads[:40], "total": len(leads)})

    @app.post("/api/investigate")
    def api_investigate():
        """Evidence for one suggested record: its household, and the same
        person in the other censuses, found by name, birth year, parents and
        spouse as written in this record. A second census with the same
        parents is the strongest check Spor can make on its own."""
        data = request.get_json(silent=True) or {}
        r = source.get(str(data.get("record_id") or ""))
        if r is None:
            return jsonify({"error": "Fant ikke posten.", "kind": "input"}), 404
        house = source.household(r.record_id) or [r]
        out = {"record": _brief_named(r) | {"farm": r.farm, "place": r.municipality or r.parish, "year": r.year,
                                           "father": r.father_name, "mother": r.mother_name, "spouse": r.spouse_name,
                                           "source": r.source, "link": _source_link(r)},
               "household": [_person_brief(h) for h in house], "elsewhere": []}
        if not r.given_name or not r.birth_year:
            return jsonify(out)
        out["namesakes"] = _namesakes(app, r, house)
        q = PersonQuery(given_name=r.given_name, surname=r.surname, birth_year=r.birth_year, birth_year_tolerance=2,
                        sex=r.sex, father_name=r.father_name or "", mother_name=r.mother_name or "",
                        spouse_name=r.spouse_name or "")
        try:
            res = find(q, source, helper=None)
        except (PrivacyError, ValueError):
            return jsonify(out)
        best: dict[int, dict] = {}
        for c in res.candidates:
            o = c.record
            if o.year == r.year or o.year in best or c.confidence not in ("high", "medium"):
                continue
            fam = next((p for p in c.parts if p.name == "family"), None)
            same = bool(fam and fam.score >= 0.85 and (q.father_name or q.mother_name or q.spouse_name))
            if not same and c.confidence != "high":
                continue   # a namesake without the same family is no evidence
            best[o.year] = {
                "year": o.year, "name": o.full_name, "birth_year": o.birth_year, "role": o.role,
                "farm": o.farm, "place": o.municipality or o.parish, "confidence": c.confidence,
                "father": o.father_name, "mother": o.mother_name, "spouse": o.spouse_name,
                # the family part scores parents and spouse against this record's
                "same_family": same,
                "record_id": o.record_id, "source": o.source, "link": _source_link(o)}
        out["elsewhere"] = sorted(best.values(), key=lambda x: x["year"])
        return jsonify(out)

    @app.post("/report")
    def report():
        """Printable report of the records the user confirmed."""
        import json
        try:
            payload = json.loads(request.form.get("payload", "{}"))
        except ValueError:
            abort(400)
        person = payload.get("query") or {}
        decisions = payload.get("decisions") or {}
        confirmed = []
        for rid, dec in decisions.items():
            if dec.get("status") != "confirmed":
                continue
            r = source.get(rid)
            if r is None:
                continue
            confirmed.append({"record": r, "link": _source_link(r), "note": dec.get("note", ""),
                              "reasons": dec.get("reasons", []), "confidence": dec.get("confidence", ""),
                              "household": source.household(rid)})
        confirmed.sort(key=lambda x: x["record"].year)
        rejected = sum(1 for d in decisions.values() if d.get("status") == "rejected")
        return render_template("report.html", person=person, confirmed=confirmed, rejected=rejected,
                               status=status(), generated=dt.date.today().isoformat())

    return app
