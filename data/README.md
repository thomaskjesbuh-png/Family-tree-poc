# Record file format

`sample_records.csv` holds **fictional** records invented for testing the
pipeline. They are not real people, and the `sample://` links point nowhere.
Do not cite them.

Columns (UTF-8 CSV with a header row, or a JSON list of objects with the same keys):

| Column | Meaning |
| --- | --- |
| record_id | Unique id of the person entry in the source |
| source | Source name as it should be cited |
| record_type | census, baptism, marriage, burial, ... |
| year | Year of the record itself (records newer than 100 years are skipped) |
| url | Direct link to the record |
| given_name, surname | As written in the record |
| farm | Farm or place of residence |
| sex | m / f / empty |
| birth_year | Stated birth year, if any |
| birthplace, parish, municipality, county | As written |
| father_name, mother_name, spouse_name | As written, if listed |
| role | Role in the record (son, wife, head, baptised, ...) |
| raw_text | Transcription text, for rows whose fields are not split out (needs `--llm`) |

Row S099 is from a 1930 census on purpose: it must be skipped by the
100-year rule. Row S033 has only `raw_text` and is used to test model extraction.
