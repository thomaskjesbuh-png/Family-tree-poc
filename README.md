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
| Census importer | Any county. Imported so far: Østfold, Nord-Trøndelag and Hedmark, 1,198,969 person records from the 1801, 1865, 1900 and 1910 censuses. Booklet counts match the booklets' own totals to within 210 of 1,045,283 (0.02%) |
| Model steps (Haiku extraction, Sonnet same-person check) | Built and tested with a fake client. **Not yet run against the real API** |
| Unit tests | 104 passing |
| Accuracy report | Fictional: `reports/accuracy.md`. Real, from Thomas's family tree: `reports/accuracy_real.md` (private, git-ignored). 13 people with a confirmed record, searched across 1.2 million records: all 13 in the top 3, 8 first (the rest behind what is very likely the same person in an earlier census); all 4 "born after 1910" cases correctly return nothing; no wrong record rated high. Small sample, so a first signal only |
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

## Real census data

```bash
python tools/fetch_census.py --counties 01Ostfold 17Nord-Trondelag 04Hedmark   # ~320 MB into data/raw/
python import_census.py             # every downloaded county -> data/real/records.csv (~5 min for three)
python tools/validate_import.py     # compare parsed counts with each booklet's totals
```

The import stops without writing anything if it finds no downloaded files, and the
web app refuses to start on an empty records file. The booklets are read with
poppler's `pdftotext` when installed, otherwise with `pypdf` (slower, about 98%
identical records). `pip install -r requirements.txt` brings pypdf and certifi;
certifi fixes CERTIFICATE_VERIFY_FAILED with Python from python.org on a Mac.

```bash
python find.py person.yaml --records data/real/records.csv
```

County folder names are the ones on xml.arkivverket.no (`01Ostfold` …
`20Finnmark`). The table below shows Østfold; Nord-Trøndelag and Hedmark
follow the same pattern.

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

## Web interface (prototype)

```bash
pip install -r requirements.txt
python -m webapp                                   # invented example family, http://127.0.0.1:8000
python -m webapp --records data/real/records.csv   # imported census data (~20 s to start)
```

The customer starts with themselves, then adds parents, grandparents and so
on; the tree grows backwards one generation per column and is kept in the
browser only. People born after the 100-year limit are "living memory" and are
never searched. For anyone born earlier, "Follow the trail" opens a census
search prefilled from the tree: name, birth year, birthplace, sex, both parents
and the spouse (the other parent of their child), so the strongest clues come
for free. Records kept are attached to that person, and each person can be
read as a printable chapter. When the customer has added everyone they know, "Let etter slektninger"
looks for the parents of everyone in the tree who is old enough for the
censuses and is missing a father or mother. It reads them from the census
household (records the customer already added first, otherwise strong and
possible matches), merges different spellings of the same parent across
censuses, and flags competing families when namesakes fit equally well. Each
suggestion can be added to the tree with the record as its source; running it
again goes one generation further. Sparse trees still get traces:
someone born between the last census (1910) and the 100-year limit is not in
any census, so the app lists families with the same surname in the 1910
census whose parents are the right age (same place first) and offers to add
them as parents (`/api/families`). A person with no birth year gets an
estimate from their child (father about 30 years older, mother about 27),
shown as "omkr." and searched with ± 5 years; people born too recently are
told why, and what the next step is. The search does not stop at a dead end:
a missing birth year is estimated and searched straight away; a father born
around 1900 is looked for as a boy in 1910 (`/api/parent-leads`: men 18–55
years older with the surname, or named after a patronymic surname, so
Samuelsen also tries Samuel), and adding him brings his parents too, two
generations from one record; a woman sharing her husband's surname is asked
for her maiden name; and every uncertain or empty result points to where the
trail goes on outside Spor: the 1920 census at Digitalarkivet (all of Norway),
Danish sources when the family has a Danish birthplace, gravestones, and
relatives. Spor only links to those sites; it never fetches them. Nothing is added straight from a
suggestion: "Undersøk nærmere" opens an investigation page that puts what the
tree knows next to what the source says, looks for the same person with the
same family in the other censuses (`/api/investigate`; namesakes without the
family don't count), asks questions only the family can answer (the father's
and grandparents' names, where the family came from), and asks the reader to
read the source. Adding is offered at "Sannsynlig" (an independent check plus
enough agreement) and "Bekreftet"; below that only as "usikker", shown dashed in
the tree. Every decision goes into a research log on the person. For each search the customer gets ranked
census records. Each card shows the confidence, the reason behind every part of the
score, the people listed at the same place, and a link to the page in the
archive's booklet. The customer marks each record "This is them" or "Not them"
(saved in their browser), then creates a printable report with source
citations for the confirmed records. Searches for people born in the last
100 years are refused.

The interface follows the **Spor design system**
(https://claude.ai/artifact/HYYfBZ8zAjUJN3CqMxQtjA): Norwegian (bokmål) first,
the "spor" logo lockup, its colour, spacing, radius and shadow tokens
(`webapp/static/spor-tokens.css`, generated from its `tokens.json`), its
component classes (`webapp/static/spor-components.css`, copied from its
`bundle.css`), Literata / Schibsted Grotesk / IBM Plex Mono, and its pen
drawings copied unchanged (`webapp/templates/_art_*.html`, `_logo_mark.html`).
The research view is two panes (the FamilyTree, oldest generation at the top,
and the PersonCard); the best result is a FindCard ("Nytt spor") quoting the
record's own words; dead ends use the EmptyState ("Sporet stopper her,
foreløpig"); the chapter follows the StoryPage. Confidence uses the fixed
words: Sannsynlig for a strong match, Ubekreftet for weaker ones, Bekreftet
once the user adds a record to the tree, Motstridende kilder when a family
member conflicts with the tree. The engine's explanations are translated to
Norwegian in the browser. The name is still a working name: change it with
`AF_APP_NAME` (default "Spor").

The default data is an invented family (`data/demo/demo_records.csv`, made by
`tools/make_demo_data.py`), so the demo can be shown to anyone.

**Not ready for paying customers.** The page shows a prototype notice until
`AF_COMMERCIAL_CLEARED=1` is set. Set it only after Nasjonalarkivet has
confirmed in writing that the census files may be used commercially and with
AI (see `docs/access-findings.md`). Other gaps before launch: user accounts and
saved projects on the server, payment, terms of service and a privacy policy,
hosting, and faster search (about 5 s per search on 1.2 million records). Set
`AF_USE_LLM=1` to add the Claude same-person check (needs API credentials).

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
import_census.py        downloaded files -> data/real/records.csv
tools/fetch_census.py   download Østfold census files (1 request/second)
tools/validate_import.py  parsed counts vs booklet totals
tools/make_demo_data.py   invented demo family -> data/demo/demo_records.csv
webapp/                 web interface (Flask): search, review, report
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
   `python evaluate.py --cases tests/family_people.yaml --kind real --records data/real/records.csv`.
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
