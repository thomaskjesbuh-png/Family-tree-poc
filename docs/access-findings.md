# Access findings: Digitalarkivet and Nasjonalarkivet

Checked 2026-11-05 from the development environment. Every claim below comes
from a page or file opened that day, unless it is marked otherwise.

## Summary

1. **Digitalarkivet's website and API forbid AI agents.** The robots.txt on both
   `www.digitalarkivet.no` and `api.digitalarkivet.no` lists about 140 AI agents
   under `Disallow: /`, including `ClaudeBot`, `Claude-User`, `Claude-Web`,
   `Claude-SearchBot` and `anthropic-ai`. All other clients get `Crawl-delay: 5`.
   As an AI agent, I fetched nothing else from those hosts.
2. **There is no bulk download API.** Nasjonalarkivet staff said so on their
   forum on 2025-07-28: apart from a few entries in the national data catalogue,
   "there are no API services for downloading content in Digitalarkivet."
   Digitalarkivet staff also said on 2025-04-14 that the 1875 and 1885 censuses
   cannot be exported.
3. **Downloadable census data exists.** `xml.arkivverket.no` is an open
   directory (no robots.txt) holding:
   * the **1801 census** as full CSV research files, for the whole country and
     per county, Østfold included;
   * **printed-booklet PDFs** with full transcriptions per municipality for the
     **1801, 1865, 1900 and 1910** censuses (Østfold: 22, 26, 26 and 30 booklets).
4. **A documented 1910 census API** (`api.digitalarkivet.no/v1/census/1910/...`)
   supports person search by field and returns whole households. It is listed as
   open data under **CC BY 3.0 NO**, but its host's robots.txt bans AI agents
   (point 1).
5. **No licence is stated** for the 1801 files or the booklets. Only the 1910
   catalogue entry names one (CC BY 3.0 NO). Commercial use is not addressed
   anywhere I could read.
6. **Not found as data:** the 1875 census, church records, and the
   Historisk befolkningsregister (HBR). HBR has open search at histreg.no but no
   public API or bulk download.

**Recommendation:** build the prototype on the downloadable census files from
xml.arkivverket.no (start with 1865 and 1900 for Østfold, plus the 1801 CSV),
not on live Digitalarkivet access. Before any commercial use, get written
answers from Nasjonalarkivet to the questions at the end of this document,
above all on AI use, given point 1.

## Sources checked

| Host | robots.txt | What I found |
| --- | --- | --- |
| www.digitalarkivet.no | AI agents (Claude included) `Disallow: /`; others `Crawl-delay: 5` | Not visited beyond robots.txt |
| api.digitalarkivet.no | Identical to the above | Not called |
| xml.arkivverket.no | None (404), so no restrictions | Open file directory of census data (below) |
| www.arkivverket.no, arkivverket.no | Redirect to nasjonalarkivet.no | Arkivverket is now **Nasjonalarkivet** |
| www.nasjonalarkivet.no | Allows all except WordPress admin | Every page behind a Cloudflare bot challenge, so terms of use could not be read. I did not try to bypass it |
| forum.nasjonalarkivet.no | `Crawl-delay: 5` (followed) | Staff answers on API and export (below) |
| data.norge.no | Public pages allowed; `/api/` and query URLs disallowed; `Crawl-delay: 1` | Arkivverket catalogue entries (below) |
| histreg.no | `Crawl-delay: 10` (followed) | Front page only |

## Details

### Staff answers on the forum

* **API**, thread "API-tilgang til Digitalarkivet",
  https://forum.nasjonalarkivet.no/topic/358505-api-tilgang-til-digitalarkivet/
  * 2025-05-19, user: asks whether there are API services for data and documents.
  * 2025-07-19, user: has asked before without result. Would like bulk download,
    and says, "but I don't want to 'scrape' it (and I don't suppose Digitalarkivet
    wants me to either)."
  * **2025-07-28, Kristian Hunskaar (Nasjonalarkivet):** "Arkivverket has some
    entries in Felles datakatalog (data.norge.no). Apart from this, there are no
    API services for downloading content in Digitalarkivet." (translated)
* **Export**, thread "Nedlasting av folketellingsdata",
  https://forum.nasjonalarkivet.no/topic/356732-nedlasting-av-folketellingsdata/
  * **2025-04-14, Renathe-Johanne Wågenes (Digitalarkivet):** it is not possible
    to export the 1875 and 1885 censuses for offline analysis.
* **Spreadsheets**, thread "Laste ned folketellinger til regneark" (2023),
  https://forum.nasjonalarkivet.no/topic/320920-laste-ned-folketellinger-til-regneark/
  Users only, no staff answer. They point to PDF versions of the censuses at
  `digitalarkivet.no/content/267/folketellinger-som-pdffiler`, which I didn't open
  (that host bans AI agents). One user guesses copyright is why the databases
  aren't downloadable.

### Catalogue entries on data.norge.no (publisher: Nasjonalarkivet)

| Dataset | Distribution | Licence | Page |
| --- | --- | --- | --- |
| Folketeljinga 1910 | xml/json "API against Digitalarkivet's meta and content database"; documentation PDF | **CC BY 3.0 NO** | [link](https://data.norge.no/nb/datasets/c05ebfb7-bef9-3a10-8318-6c8be87a7000/folketeljinga-1910) |
| Folketellingen 1865 | None (landing page is Digitalarkivet search) | Not stated | [link](https://data.norge.no/nb/datasets/54149e6c-c1e5-3a48-b4e9-3aa62ca1c47b/folketellingen-1865) |
| Folketellingen 1801 | None (landing page is Digitalarkivet search) | Not stated | [link](https://data.norge.no/nb/datasets/f72a519c-fad5-3fd5-821d-104b48f85fef/folketellingen-1801) |
| Emigrantprotokollene 1866–1930 | None; about 700,000 entries | Not stated | [link](https://data.norge.no/nb/datasets/81bc8434-0887-380a-8405-db094f919242/emigrantprotokollene-1866-1930) |

The contact on the 1801 and 1865 entries is "Arkivverket, avdeling Publikum",
postmottak@arkivverket.no.

### The 1910 census API

Documentation: https://xml.arkivverket.no/folketellinger/API_1910_koord.pdf
(version 7, 2022-06-16). In its own words, Arkivverket "can offer interested
developers an API". Endpoints, all under `https://api.digitalarkivet.no/v1/census/1910/`:

* `search_person?s=...`: free-text person search (AND/OR, `limit`, `page`)
* `search_person_advanced?fornavn=&etternavn=&fodselsaar=&fodested=&kjonn=...`: search by field
* `person/<pf-id>`: one person plus the rest of the household
* `property/<id>`, `search_property`, `search_property_geo`: dwellings, including coordinates

Person fields include first name, surname (patronymic or family name), sex, birth
year (with a flag when it was computed from age), birth date, birthplace,
dwelling, and position in the family and occupation. Fields for links to father,
mother and partner exist but are marked "not yet in use". The document names a
general and a technical contact at Arkivverket.

No terms of use, rate limit or API key are mentioned. **I didn't call the
API**, because its host's robots.txt bans AI agents. Whether a script that sends
results to Claude counts as an "AI agent" under that rule is for
Nasjonalarkivet to answer.

### Downloadable files on xml.arkivverket.no

All files are dated 2024-08-15 in the directory listing.

* `folketellinger/f1801.txt` (about 200 MB, whole country) and
  `folketellinger/ft1801/Ft1801_forsk_01Ostfold_v1.txt` (14 MB, Østfold), plus
  code lists, a variable list and an Excel guide
  (`Samlefil_veiledning_revisjon_nov_2019.pdf`).
  * Format: CSV, ISO-8859-1. One row per person: amt, parish, sub-parish,
    farm or house, new-household marker `*`, first name, surname, household
    position ("Hans søn", "Hans kone"), age, marital status, occupation, sex, and
    coded versions of these.
  * The guide says Arkivverket "publishes census files with coded and
    transcribed information on Digitalarkivet, for the whole country and by
    county … The files can be loaded into various tools for analysis, look-up or
    description." So downloading them is intended. The guide states no licence.
  * There is **no birth year**, only age (count date 1801-02-01), and no parents' names
    (relations come only from the household role). The spec's period starts at
    1800, so 1801 mainly helps with parents and grandparents.
* `folketellinger/hefter/{1801,1865,1900,1910}/01Ostfold/*.pdf`: one booklet
  per municipality, e.g. `f8650117_hefte.pdf` = 1865, municipality 0117 (Id),
  197 pages, generated 2014-09-22.
  * Full transcription as text-extractable PDF: dwelling (farm, farm and holding
    numbers), then each person with name, sex, marital status, family position,
    occupation, age (1865) and birthplace, plus name and birthplace indexes.
  * Parsable with `pdftotext -layout`, though long values wrap onto a second line.
  * The booklet credits Digitalarkivet as its source ("Utskrift frå
    Digitalarkivet") and states no licence. `hefter/Hefteprisliste 2017.pdf`
    suggests the booklets were also sold in print.
  * There is no 1875 folder.

### Historisk befolkningsregister (histreg.no)

Front page, read 2026-11-05: HBR is a research infrastructure being built in
two Research Council projects (2014–18 and 2022–29). It links appearances of the
same person, and family members, across church books and censuses from
Digitalarkivet. The open part, on histreg.no, covers deceased people, mostly from
sources before 1923. A closed part is only for approved researchers.
Contributors can link records by hand (contact histreg@nr.no). Person ids on
histreg.no use the same `pf…` form as the 1910 API. There is no public API or
bulk download. Its record links would be the strongest evidence for matching,
so data access is worth asking about.

## What this means for the prototype

| Spec item | Status |
| --- | --- |
| 1801 census | Downloadable CSV for Østfold. Licence not stated |
| 1865 census | Downloadable transcription PDFs for Østfold. Licence not stated |
| 1875 census | Not available as data. Staff say it can't be exported |
| 1900 census | Downloadable transcription PDFs for Østfold. Licence not stated |
| 1910 census | PDFs, plus an API under CC BY 3.0 NO whose host bans AI agents |
| Church records | Not found as data |
| HBR | Search only; ask for data access |
| Live search of Digitalarkivet | **Not allowed for AI agents** under robots.txt; none planned |

## Questions for Nasjonalarkivet

Send to postmottak@arkivverket.no (the contact on the data.norge.no entries;
check whether a nasjonalarkivet.no address has replaced it).

1. **AI use.** Digitalarkivet's robots.txt bars AI agents, Claude included. Does
   that also cover (a) a script that downloads your published census files from
   xml.arkivverket.no and processes them with an AI model, and (b) a script that
   calls the 1910 API and passes results to an AI model for matching?
2. **Licence.** What licence covers the 1801 research files and the census
   booklets on xml.arkivverket.no? Is it the same CC BY 3.0 NO listed for 1910?
   Does it differ for volunteer-made transcriptions?
3. **Commercial use.** May the files, or the 1910 API, be used in a paid
   genealogy service that cites the records and links back to Digitalarkivet?
4. **Machine-readable versions.** Can we get the 1865, 1875 and 1900
   transcriptions as CSV like the 1801 files, rather than PDF booklets, at least
   for Østfold?
5. **Church records.** Is any transcribed church-book data (baptisms,
   marriages, burials) available as files or through an API?
6. **1910 API terms.** Is it still offered to developers, and with what rate
   limit, registration or key?
7. **Storage and display.** May we keep the data locally and show excerpts to
   customers with a link to the record?
8. **HBR.** Can its person links be used by a third party, and on what terms
   (via histreg@nr.no)?

## Rules the code follows

* No requests to www.digitalarkivet.no or api.digitalarkivet.no
  (`DigitalarkivetSource` refuses to run).
* Each host's crawl delay is followed, with at least 1 request per second
  (`RateLimiter`), and a clear User-Agent is sent (`USER_AGENT`).
* Data is downloaded once and cached locally.
* Only records over 100 years old are used, and queries about people born within the last 100 years are refused.
* Every candidate links to its source record.
