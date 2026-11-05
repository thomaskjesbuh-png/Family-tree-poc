"""Optional Claude calls, used deliberately and cheaply.

* Haiku tier  -> extract structured fields from a raw transcription.
* Sonnet tier -> judge whether a query person and a record are the same person.
* No top-tier model in this phase.

Every answer is cached in SQLite (never paid for twice), the stable system
prompts use prompt caching, every call is logged with tokens and cost to
logs/usage.jsonl, and a soft spend limit stops calls before the hard limit set
in the Anthropic Console is reached.

The pipeline runs without any of this (deterministic scoring only) when no
credentials are available or --no-llm is passed.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .cache import Cache, key_for
from .models import PersonQuery, Record

EXTRACT_MODEL = os.environ.get("ANCESTOR_EXTRACT_MODEL", "claude-haiku-5-5")
JUDGE_MODEL = os.environ.get("ANCESTOR_JUDGE_MODEL", "claude-sonnet-5-5")

# USD per million tokens (Anthropic first-party list prices, checked 2026-11).
# Cache writes cost 1.25x input, cache reads 0.1x input (5-minute TTL).
PRICES = {
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
}

DEFAULT_SOFT_LIMIT_USD = float(os.environ.get("ANCESTOR_SOFT_LIMIT_USD", "2.00"))
USAGE_LOG = Path(os.environ.get("ANCESTOR_USAGE_LOG", "logs/usage.jsonl"))


class BudgetExceeded(RuntimeError):
    pass


def cost_usd(model: str, usage: dict) -> float:
    p = PRICES.get(model)
    if not p:
        return 0.0
    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cw = usage.get("cache_creation_input_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    return (inp * p["input"] + cw * p["input"] * 1.25 + cr * p["input"] * 0.1
            + out * p["output"]) / 1_000_000


@dataclass
class Budget:
    soft_limit_usd: float = DEFAULT_SOFT_LIMIT_USD
    spent_usd: float = 0.0
    calls: int = 0
    per_case: dict[str, float] = field(default_factory=dict)

    def check(self) -> None:
        if self.spent_usd >= self.soft_limit_usd:
            raise BudgetExceeded(
                f"Soft spend limit reached: ${self.spent_usd:.4f} of ${self.soft_limit_usd:.2f}. "
                "Raise ANCESTOR_SOFT_LIMIT_USD to continue.")

    def add(self, case_id: str, usd: float) -> None:
        self.spent_usd += usd
        self.calls += 1
        self.per_case[case_id] = self.per_case.get(case_id, 0.0) + usd


# --- structured outputs ----------------------------------------------------

class ExtractedRecord(BaseModel):
    given_name: str = Field(description="Given name(s) exactly as written, or empty")
    surname: str = Field(description="Surname or patronymic exactly as written, or empty")
    farm: str = Field(description="Farm or place of residence, or empty")
    sex: Literal["m", "f", ""] = Field(description="m, f, or empty if not stated")
    birth_year: int | None = Field(description="Birth year if stated or directly computable from a stated date, else null")
    birthplace: str = Field(description="Birthplace as written, or empty")
    father_name: str = Field(description="Father's name as written, or empty")
    mother_name: str = Field(description="Mother's name as written, or empty")
    spouse_name: str = Field(description="Spouse's name as written, or empty")


class SamePersonJudgement(BaseModel):
    verdict: Literal["same", "different", "unsure"]
    reasons: list[str] = Field(description="Short reasons, each tied to a field in the record")


EXTRACT_SYSTEM = """You extract fields from transcribed Norwegian historical records \
(censuses and church books, 1800-1920).

Rules:
- Copy names and places exactly as written in the transcription. Do not modernise spelling.
- Only fill a field when the transcription states it. Never guess or infer missing facts.
- Leave a field empty (or null for birth_year) when it is not in the text.
- birth_year: use a stated birth year or birth date. For a baptism, use the stated birth date \
if given; otherwise leave it null.
- Norwegian terms: "fødd"/"født" = born, "døbt" = baptised, "far"/"fader" = father, \
"mor"/"moder" = mother, "hustru"/"kone" = wife, "ektemand"/"mand" = husband, \
"gaard"/"gård" = farm, "pige"/"datter" = girl/daughter, "dreng"/"søn" = boy/son."""

JUDGE_SYSTEM = """You help a genealogist decide whether a historical archive record \
describes a specific known person.

You get the known facts about the person and one record from a Norwegian census or church \
book (1800-1920). Decide: "same", "different", or "unsure".

How to judge:
- Norwegian names vary a lot in spelling (Christine/Kristine/Kirstine, Thore/Tore), and \
patronymics change form (Olsen, Olsdatter, Olsd., Olssøn all mean child of Ole). Farm names \
are often used as surnames and change when people move.
- Birth years in censuses are often off by 1-2 years.
- Common names mean namesakes are frequent: two people with the same name, born a year or two \
apart in the same parish, are common. Parents' and spouse's names are the strongest evidence.
- Say "different" when a firm fact conflicts (different father, different sex, impossible \
dates). Say "unsure" when the record lacks the facts that would separate namesakes.
- Use only the facts given. Do not add facts from outside knowledge. Each reason must name \
the field it is based on."""


class ClaudeHelper:
    """Thin wrapper that adds caching, budget checks and usage logging."""

    def __init__(self, cache: Cache, budget: Budget | None = None, usage_log: Path = USAGE_LOG):
        import anthropic  # imported lazily so the pipeline runs without the SDK

        self._anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.cache = cache
        self.budget = budget or Budget()
        self.usage_log = usage_log
        self.usage_log.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def available() -> bool:
        """True when the SDK is installed and some credential source is configured."""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        env = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE",
               "ANTHROPIC_FEDERATION_RULE_ID")
        if any(os.environ.get(k) for k in env):
            return True
        return (Path.home() / ".config" / "anthropic").exists()

    # -- public calls --

    def extract(self, record: Record, case_id: str = "") -> ExtractedRecord:
        user = f"Transcription ({record.source}, {record.record_type}, {record.year}):\n{record.raw_text}"
        return self._parse(EXTRACT_MODEL, EXTRACT_SYSTEM, user, ExtractedRecord,
                           purpose="extract", case_id=case_id, max_tokens=2000)

    def judge(self, query: PersonQuery, record: Record, case_id: str = "") -> SamePersonJudgement:
        person = {k: v for k, v in {
            "name": query.full_name, "name_variants": query.name_variants,
            "birth_year": query.birth_year, "birthplace": query.birthplace,
            "county": query.county, "sex": query.sex, "father": query.father_name,
            "mother": query.mother_name, "spouse": query.spouse_name}.items() if v}
        rec = {k: v for k, v in record.to_dict().items()
               if v not in ("", None, False) and k not in ("url", "record_id", "extracted_by_model")}
        user = ("Known person:\n" + json.dumps(person, ensure_ascii=False, indent=1) +
                "\n\nRecord:\n" + json.dumps(rec, ensure_ascii=False, indent=1))
        return self._parse(JUDGE_MODEL, JUDGE_SYSTEM, user, SamePersonJudgement,
                           purpose="judge", case_id=case_id, max_tokens=4000)

    # -- internals --

    def _parse(self, model: str, system: str, user: str, schema: type[BaseModel], *,
               purpose: str, case_id: str, max_tokens: int):
        ckey = key_for(model, system, user, schema.__name__)
        cached = self.cache.get("llm", ckey)
        if cached is not None:
            self._log(model, purpose, case_id, {}, 0.0, cached=True)
            return schema.model_validate(cached)

        self.budget.check()
        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            # Stable instructions first, marked for prompt caching. (Prefixes
            # below the model's minimum cacheable length are simply not cached.)
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": "low"},
        )
        response = self._call_with_retries(kwargs)
        usage = response.usage.model_dump() if response.usage else {}
        usd = cost_usd(model, usage)
        self.budget.add(case_id or "-", usd)
        self._log(model, purpose, case_id, usage, usd, cached=False, stop=response.stop_reason)

        if response.stop_reason == "refusal":
            raise RuntimeError(f"{model} declined the {purpose} request")
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"{model} hit max_tokens on {purpose}")
        parsed = response.parsed_output
        if parsed is None:
            raise RuntimeError(f"{model} returned no parsable {purpose} output")
        self.cache.put("llm", ckey, parsed.model_dump())
        return parsed

    def _call_with_retries(self, kwargs: dict, attempts: int = 3):
        a = self._anthropic
        for i in range(attempts):
            try:
                return self.client.messages.parse(**kwargs)
            except a.RateLimitError as e:
                wait = int(e.response.headers.get("retry-after", "10"))
                if i == attempts - 1:
                    raise
                time.sleep(min(wait, 60))
            except a.APIStatusError as e:
                if e.status_code >= 500 and i < attempts - 1:
                    time.sleep(2 ** (i + 1))
                    continue
                raise
            except a.APIConnectionError:
                if i == attempts - 1:
                    raise
                time.sleep(2 ** (i + 1))
        raise RuntimeError("unreachable")

    def _log(self, model: str, purpose: str, case_id: str, usage: dict, usd: float,
             cached: bool, stop: str | None = None) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "case_id": case_id, "purpose": purpose, "model": model,
            "cached_answer": cached, "stop_reason": stop,
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
            "cost_usd": round(usd, 6),
            "session_spent_usd": round(self.budget.spent_usd, 6),
        }
        with self.usage_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
