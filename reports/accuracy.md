# Accuracy report

Generated 2026-11-06 · source: local file data/sample_records.csv (FICTIONAL sample) · model steps: off (deterministic scoring only)

> These results come from **fictional sample records** built to exercise the pipeline. They show that it runs end to end and handles the tricky cases. They say nothing yet about accuracy on real archives. Rerun on the 20 real ancestors once access is confirmed.

## Summary

| Measure | Result |
| --- | --- |
| Test people | 5 (4 with a known record, 1 with none) |
| Correct record ranked first | 4 of 4 |
| Correct record in top 3 | 4 of 4 |
| Missed | 0 of 4 |
| "No match" cases correctly left empty | 1 of 1 |
| Top suggestion wrong but rated medium or high | 0 of 5 |
| Wrong records rated high (anywhere in the list) | 0 |
| Wrong records rated medium or high (anywhere in the list) | 1 |
| Model cost, whole run | $0.0000 |

## Confidence calibration

Share of reported candidates at each level that are the right person.

| Confidence | Candidates | Correct | Precision |
| --- | --- | --- | --- |
| high | 5 | 5 | 100% |
| medium | 5 | 4 | 80% |
| low | 2 | 0 | 0% |

## Per person

| Case | Result | Correct rank | False matches | Model cost |
| --- | --- | --- | --- | --- |
| F1-kristine-spelling | top 1 | 1 | none | $0.0000 |
| F2-ole-hansen-namesakes | top 1 | 1 | S013 (medium) | $0.0000 |
| F3-farm-name-surname | top 1 | 1 | none | $0.0000 |
| F4-marie-spouse-and-raw-text | top 1 | 1 | none | $0.0000 |
| F5-no-record | correct: no match | - | none | $0.0000 |

## Details

### F1-kristine-spelling

Spelling variants (Kirstine/Christine/Kristine), patronymic Olsdatter vs Olsen, decoy namesake in Tune.

Expected: S001, S002, S003

| Rank | Record | Confidence | Score | Correct | Model verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | S002 | high | 1.0 | yes | - |
| 2 | S001 | high | 0.98 | yes | - |
| 3 | S003 | medium | 0.87 | yes | - |
| 4 | S004 | low | 0.5 | no | - |

- warning: S033: only a raw transcription; skipped (model extraction disabled)

### F2-ole-hansen-namesakes

Two Ole Hansens born a year apart in Rakkestad; only the father separates them in 1865.

Expected: S010, S012

| Rank | Record | Confidence | Score | Correct | Model verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | S010 | high | 1.0 | yes | - |
| 2 | S012 | medium | 0.91 | yes | - |
| 3 | S013 | medium | 0.87 | no | - |
| 4 | S011 | low | 0.52 | no | - |

- warning: S033: only a raw transcription; skipped (model extraction disabled)

### F3-farm-name-surname

Farm name used as surname (Anders Holm) and a move from Tune to Glemmen.

Expected: S020, S021

| Rank | Record | Confidence | Score | Correct | Model verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | S020 | high | 1.0 | yes | - |
| 2 | S021 | medium | 0.91 | yes | - |

- warning: S033: only a raw transcription; skipped (model extraction disabled)

### F4-marie-spouse-and-raw-text

Identified by spouse; one correct record is a raw transcription that needs --llm extraction.

Expected: S030, S031, S033

| Rank | Record | Confidence | Score | Correct | Model verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | S030 | high | 0.96 | yes | - |
| 2 | S031 | medium | 0.91 | yes | - |

- warning: S033: only a raw transcription; skipped (model extraction disabled)

### F5-no-record

Nobody matching exists; a weak lookalike (Gunhild Thorsdatter, born 1841 in Hvaler) must not be claimed.

Expected: no match

No candidates reported.

- warning: S033: only a raw transcription; skipped (model extraction disabled)

