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
        raise ValueError("Enter at least a first name.")
    if not clean.get("birth_year"):
        raise ValueError("Enter an approximate birth year.")
    try:
        clean["birth_year"] = int(clean["birth_year"])
        if "birth_year_tolerance" in clean:
            clean["birth_year_tolerance"] = max(0, min(10, int(clean["birth_year_tolerance"])))
    except (TypeError, ValueError):
        raise ValueError("Birth year must be a number, for example 1851.")
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
        except PrivacyError as e:
            return jsonify({"error": str(e), "kind": "privacy"}), 422
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
