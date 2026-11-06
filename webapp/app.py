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
