"""The model layer, exercised with a fake client (no network, no cost)."""

import json
from types import SimpleNamespace

import anthropic
import pytest

from ancestor_finder.cache import Cache
from ancestor_finder.llm import Budget, BudgetExceeded, ClaudeHelper, ExtractedRecord, SamePersonJudgement
from ancestor_finder.models import PersonQuery
from ancestor_finder.pipeline import find
from ancestor_finder.sources import LocalFileSource


class FakeMessages:
    def __init__(self, stop_reason="end_turn"):
        self.calls = []
        self.stop_reason = stop_reason

    def parse(self, **kw):
        self.calls.append(kw)
        schema = kw["output_format"]
        if schema is ExtractedRecord:
            out = ExtractedRecord(given_name="Marie", surname="", farm="Ystehede", sex="f",
                                  birth_year=1880, birthplace="Idd", father_name="Johan Kristiansen",
                                  mother_name="Anne Mathea Olsdatter", spouse_name="")
        else:
            out = SamePersonJudgement(verdict="same", reasons=["birth_year matches"])
        usage = SimpleNamespace(model_dump=lambda: {"input_tokens": 1000, "output_tokens": 100,
                                                    "cache_creation_input_tokens": 0,
                                                    "cache_read_input_tokens": 0})
        return SimpleNamespace(parsed_output=out, usage=usage, stop_reason=self.stop_reason)


def make_helper(tmp_path, budget=None, stop_reason="end_turn"):
    h = object.__new__(ClaudeHelper)
    h._anthropic = anthropic
    h.client = SimpleNamespace(messages=FakeMessages(stop_reason))
    h.cache = Cache(tmp_path / "c.sqlite")
    h.budget = budget or Budget(soft_limit_usd=1.0)
    h.usage_log = tmp_path / "usage.jsonl"
    return h


def test_extraction_and_judge_in_pipeline(tmp_path):
    h = make_helper(tmp_path)
    q = PersonQuery(given_name="Marie", surname="Johansdatter", birth_year=1880, birthplace="Idd",
                    sex="f", spouse_name="Karl Nilsen", case_id="T1")
    res = find(q, LocalFileSource(), helper=h)
    ids = [c.record.record_id for c in res.candidates]
    assert "S033" in ids                      # raw transcription became a candidate
    s033 = next(c for c in res.candidates if c.record.record_id == "S033")
    assert s033.record.extracted_by_model and any("extracted" in n for n in s033.notes)
    assert res.llm_used and all(c.judge for c in res.candidates[:3])
    models = {c["model"] for c in h.client.messages.calls}
    assert models == {"claude-haiku-5-5", "claude-sonnet-5-5"}
    # stable system prompt is marked for prompt caching
    assert all(c["system"][0]["cache_control"] == {"type": "ephemeral"} for c in h.client.messages.calls)


def test_answers_are_cached_and_logged(tmp_path):
    h = make_helper(tmp_path)
    q = PersonQuery(given_name="Ole", surname="Hansen", birth_year=1851, birthplace="Rakkestad",
                    father_name="Hans Olsen", case_id="T2")
    find(q, LocalFileSource(), helper=h)
    n_calls = len(h.client.messages.calls)
    spent = h.budget.spent_usd
    find(q, LocalFileSource(), helper=h)
    assert len(h.client.messages.calls) == n_calls     # second run fully cached
    assert h.budget.spent_usd == spent
    lines = [json.loads(l) for l in h.usage_log.read_text().splitlines()]
    assert any(l["cached_answer"] for l in lines)
    assert all("cost_usd" in l and l["case_id"] == "T2" for l in lines)
    assert h.budget.per_case["T2"] == pytest.approx(spent)


def test_soft_budget_stops_calls(tmp_path):
    h = make_helper(tmp_path, budget=Budget(soft_limit_usd=0.0))
    with pytest.raises(BudgetExceeded):
        h.judge(PersonQuery(given_name="Ole", birth_year=1851),
                LocalFileSource().records[0])
    assert h.client.messages.calls == []


def test_budget_failure_degrades_gracefully(tmp_path):
    h = make_helper(tmp_path, budget=Budget(soft_limit_usd=0.0))
    q = PersonQuery(given_name="Ole", surname="Hansen", birth_year=1851, birthplace="Rakkestad")
    res = find(q, LocalFileSource(), helper=h)
    assert res.candidates and any("Soft spend limit" in w for w in res.warnings)


def test_refusal_is_not_treated_as_an_answer(tmp_path):
    h = make_helper(tmp_path, stop_reason="refusal")
    with pytest.raises(RuntimeError, match="declined"):
        h.judge(PersonQuery(given_name="Ole", birth_year=1851), LocalFileSource().records[0])
