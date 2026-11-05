# Ancestor Finder: proof of concept (phase 1)

A command-line prototype that takes a known historical person (name, about
when and where they were born, optionally parents or spouse) and returns ranked
candidate archive records. Each candidate comes with its source, a direct link,
a confidence level (high, medium or low), and a plain-language explanation of
the score.

The question this phase answers: **can it reliably find the right person and
the right record?** The answer goes in `reports/accuracy.md`.

## Current status

| Item | Status |
| --- | --- |
| Access investigation (`docs/access-findings.md`) | Written. **Blocked:** archive hosts unreachable from the dev environment, nothing verified |
| Pipeline (search, name normalisation, scoring, ranking) | Works end to end on a fictional local sample |
| Model steps (Haiku extraction, Sonnet same-person check) | Built and tested with a fake client. **Not yet run against the real API** |
| Unit tests | 53 passing |
| Accuracy report | Generated for 5 fictional cases. Ready to rerun on 20 real ancestors |
| Live Digitalarkivet source | Intentionally not implemented until access terms are confirmed |

The sample records in `data/sample_records.csv` are **invented** and marked
`FICTIONAL SAMPLE`. The scoring rules were tuned on those same fictional cases,
so the current report shows only that the pipeline works, not real-world
accuracy.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11 or newer.

## Run

Find candidates for one person:

```bash
python find.py examples/kristine.yaml
python find.py examples/kristine.yaml --json
```

Person file (YAML or JSON). Only `given_name` and `birth_year` are required:

```yaml
given_name: Kristine
surname: Olsdatter
name_variants: [Christine Olsdatter, Kirstine Olsen]
birth_year: 1848
birth_year_tolerance: 2      # default ±2
birthplace: Skjeberg         # parish or municipality
county: Østfold
sex: f
father_name: Ole Larsen
mother_name: Marte Hansdatter
spouse_name: ""
```

Run the test set and write the accuracy report:

```bash
python evaluate.py                       # fictional cases
python evaluate.py --kind real --records path/to/records.csv   # Thomas's ancestors
```

Run the unit tests:

```bash
python -m pytest
```

## Model steps (optional)

Add `--llm` to `find.py` or `evaluate.py`:

* **Claude Haiku 5.5** (`claude-haiku-5-5`) extracts fields from records that
  only have a raw transcription.
* **Claude Sonnet 5.5** (`claude-sonnet-5-5`) judges whether each of the top 5
  candidates is the same person. It can lower confidence freely, but can raise
  it by at most one level.
* No top-tier model is used in this phase.

Credentials come from the environment (`ANTHROPIC_API_KEY`, or an `ant auth
login` profile). Without credentials the pipeline falls back to deterministic
scoring and says so.

Cost controls:

* Every model answer is cached in SQLite (`cache/`), so it is never paid for twice.
* The stable system prompts are marked for prompt caching.
* Each call is logged to `logs/usage.jsonl` with tokens and cost per test case.
  The accuracy report shows cost per case.
* Soft limit: `ANCESTOR_SOFT_LIMIT_USD` (default `2.00`). Model calls stop once
  it is reached, and the run continues with deterministic scoring. Set the hard
  limit in the Anthropic Console.

## How scoring works

Factors (each 0 to 1, weights rescaled when the query lacks a factor):
given name 0.30, surname 0.20, birth year 0.20 (±2 years), place 0.12, family 0.18.

Name handling (`ancestor_finder/names.py`):

* spelling variants: Christine / Kristine / Kirstine, Thore / Tore, aa / å, ch / k, th / t
* patronymics: Olsen, Olsdatter, Olsd. and Olssøn share the root "Ol". Hansen
  vs Larsen counts as different, not as similar.
* farm names as surnames: "Anders Pedersen Holm" matches "Anders Holm" and
  "Anders Pedersen" on the farm Holm
* baptisms with no surname: the father's name in the record implies the patronymic

Safeguards:

* A listed parent or spouse who clearly differs counts as a conflict and cuts the score.
* A different sex, or a birth year outside the tolerance, cuts the score.
* A record that lists none of the queried family members is capped at medium,
  because namesakes can't be ruled out.
* Candidates below 0.50 are not reported. If nothing is left, the output says
  no record was found.
* Records less than 100 years old are skipped, and queries for people born in
  the last 100 years are refused.

## Layout

```
find.py                 CLI for one person
evaluate.py             runs tests/known_people.yaml -> reports/accuracy.md
ancestor_finder/
  names.py              normalisation and name similarity
  scoring.py            scoring, confidence, ranking
  pipeline.py           search -> extract -> score -> judge -> rank
  llm.py                Claude calls, budget, usage log
  cache.py              SQLite cache
  sources/local.py      CSV/JSON records file
  sources/digitalarkivet.py  placeholder; refuses until access is confirmed
data/                   fictional sample records + format notes
docs/access-findings.md
tests/                  unit tests + known_people.yaml
```

## Open questions and next steps

1. **Get access answers from Arkivverket.** See the question list in
   `docs/access-findings.md`. Licence, commercial use and automated access
   decide the whole approach.
2. **Allow the archive hosts in the dev environment** (digitalarkivet.no,
   arkivverket.no, data.norge.no, histreg.no) and redo the access check against the
   real pages.
3. **Thomas: fill in 20 real ancestors** in `tests/known_people.yaml` (copy
   the `R01` block, set `enabled: true`), including a few very common names.
4. **Get real records** for Østfold: a downloaded dataset converted to the
   `data/README.md` format, or a permitted live source. Then run
   `python evaluate.py --kind real --records ...`.
5. **Run with `--llm`** on the real set. Compare accuracy and cost with and
   without the model steps.
6. **Re-tune the weights on real data**, keeping some cases out of tuning
   to check calibration honestly.
7. Not yet handled: household context (a child's siblings and parents in the
   same census household), linking records to each other before matching, and
   the Historisk befolkningsregister.
