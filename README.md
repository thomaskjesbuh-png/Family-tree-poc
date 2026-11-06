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
| Access investigation (`docs/access-findings.md`) | Done (2026-11-05). Digitalarkivet's robots.txt bars AI agents; no bulk API; census files for 1801, 1865, 1900 and 1910 downloadable from xml.arkivverket.no, licence unstated |
| Pipeline (search, name normalisation, scoring, ranking) | Works end to end on the fictional sample and on real Østfold census records |
| Census importer | 444,560 Østfold person records from the 1801, 1865, 1900 and 1910 censuses. Counts match the booklets' own totals to within 23 of 394,442 (0.006%) |
| Model steps (Haiku extraction, Sonnet same-person check) | Built and tested with a fake client. **Not yet run against the real API** |
| Unit tests | 73 passing |
| Accuracy report | Fictional: `reports/accuracy.md`. Real, from Thomas's family tree: `reports/accuracy_real.md` (private, git-ignored). 6 people with a confirmed 1910 record are all in the top 3 (3 first, the other 3 behind their probable 1900 record); both "born after 1910" cases correctly return nothing; no wrong record rated high |
| Live Digitalarkivet source | Intentionally not implemented: robots.txt bars AI agents |

The sample records in `data/sample_records.csv` are **invented** and marked
`FICTIONAL SAMPLE`. The scoring rules were tuned on those same fictional cases,
so the current report shows only that the pipeline works, not real-world
accuracy.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Python 3.11 or newer. The census importer also needs `pdftotext` from
poppler-utils (`apt-get install poppler-utils` or `brew install poppler`).

## Real census data (Østfold)

```bash
python tools/fetch_census.py        # ~120 MB from xml.arkivverket.no into data/raw/
python import_census.py             # -> data/real/ostfold_records.csv (about 2.5 minutes)
python tools/validate_import.py     # compare parsed counts with each booklet's totals
python find.py person.yaml --records data/real/ostfold_records.csv
```

| Census | Source file | Persons | Birth year | Relations |
| --- | --- | --- | --- | --- |
| 1801 | Research CSV for Østfold | 50,141 | Computed from age (`faar`) | Machine-made links to mother, father and spouse in the household (the archive warns they contain errors) |
| 1865 | 26 municipality booklets (PDF) | 98,846 | Computed from age (±1) | Inferred from family role ("hans Søn", "deres Datter") |
| 1900 | 26 booklets | 139,850 | As written (year or date) | Inferred from coded role (hf, hm, s, d) |
| 1910 | 30 booklets | 155,723 | As written (date) | Inferred from coded role |

The 1875 census and church records are not available as data.

Notes on the imported records:

* **Links:** booklet records link to the page in the archive's PDF, e.g.
  `.../hefter/1910/01Ostfold/f9100112_hefte.pdf#page=12`. 1801 records link to
  `https://www.digitalarkivet.no/census/person/<PFID>`. That URL pattern couldn't
  be checked from here, because Digitalarkivet bars AI agents.
* **Inferred relations:** parents and spouse come from household position, not
  from a stated link. Stepchildren, foster children, grandchildren, in-laws and
  servants get no parents. A "child" whose patronymic can't come from the head's
  name loses the inferred father. Matches that rely on inferred relations say so.
* **Licence:** none is stated for these files (see `docs/access-findings.md`),
  so `data/raw/` and `data/real/` are git-ignored and nothing from them is
  committed. Use them for personal testing until Nasjonalarkivet answers.
* Spelling in the 1900 booklets abbreviates patronymics ("Ols." for
  Olsen/Olsdatter), and the name matching handles this.

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
  sources/digitalarkivet.py  placeholder; refuses (robots.txt bars AI agents)
  importers/booklets.py      1865/1900/1910 census booklet PDFs -> records
  importers/ft1801.py        1801 research CSV -> records
  importers/households.py    parents/spouse from household position
import_census.py        downloaded files -> data/real/ostfold_records.csv
tools/fetch_census.py   download Østfold census files (1 request/second)
tools/validate_import.py  parsed counts vs booklet totals
data/                   fictional sample records + format notes
docs/access-findings.md
tests/                  unit tests + known_people.yaml
```

## Open questions and next steps

1. **Ask Nasjonalarkivet** the questions in `docs/access-findings.md`. The
   first one matters most: whether its AI-agent ban covers this use of the
   downloadable files and of the 1910 API. Licence and commercial use come next.
2. **Census import is done** for Østfold (1801, 1865, 1900, 1910). Not
   available as data: the 1875 census and church records.
3. **Thomas: confirm the suggestions** in the "To check by hand" section of
   `reports/accuracy_real.md` and the `probable_record_ids` in
   `tests/family_people.yaml` (both private and git-ignored, because this
   repository is public), by opening the linked booklet pages. Move
   confirmed ids into `expected.record_ids`. Add more people any time; the
   test set has no fixed size, and people found by hand in your browser are
   the best test cases.
4. **Run the real test set** on the imported records:
   `python evaluate.py --kind real --records data/real/ostfold_records.csv`.
   Since there are no church records, use census entries as the expected
   answers (`expected.record_ids` take the ids printed by `find.py`).
5. **Run with `--llm`** on the real set. Compare accuracy and cost with and
   without the model steps.
6. **Re-tune the weights on real data**, keeping some cases out of tuning
   to check calibration honestly.
7. Not yet handled: using siblings in the same household as evidence, linking
   the same person across censuses before matching, a faster loader
   (about 9 s to load 444k records), and
   the Historisk befolkningsregister (search only, no API; its person links
   would be the strongest evidence).
