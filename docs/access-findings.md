# Access findings: Digitalarkivet and Arkivverket

Status as of 2026-11-05: **blocked, nothing verified.**

The development environment could not reach any Arkivverket host, so no terms
of use, robots.txt, API documentation or dataset page was actually read. As the
spec requires, I did not guess or work around this. The pipeline runs against
a small fictional local file in the expected format (see `data/README.md`). The
live source (`ancestor_finder/sources/digitalarkivet.py`) refuses to run until
the questions below are answered.

## What was tried

| Host | Purpose | Result |
| --- | --- | --- |
| www.digitalarkivet.no | robots.txt, terms of use, search | Blocked by the environment's network policy (proxy 403) |
| api.digitalarkivet.no | possible API | Blocked (proxy 403) |
| xml.arkivverket.no | possible census file downloads | Blocked (proxy 403) |
| www.arkivverket.no, forum.arkivverket.no | terms, forum answers about API and downloads | Blocked |
| data.norge.no | national open-data catalogue (Arkivverket datasets) | Blocked |
| histreg.no | Historisk befolkningsregister | Blocked |

To fix this for the next run, add these hosts under Allowed domains in the
Claude Code cloud environment's network settings:
digitalarkivet.no, arkivverket.no, data.norge.no, histreg.no. Alternatively,
run the investigation from a normal machine.

## Unverified leads (from web-search snippets only, not opened)

These came from search-result summaries. They are leads to check, not findings.
Do not rely on them.

1. **No public download API (unconfirmed).** An Arkivverket forum thread
   ("API-tilgang til Digitalarkivet") reportedly says there are no API services
   for downloading content from Digitalarkivet, beyond some entries in the
   Felles datakatalog (data.norge.no). The reply is undated.
   https://forum.arkivverket.no/topic/358505-api-tilgang-til-digitalarkivet/
2. **Internal API used by histreg.no (unconfirmed).** A forum thread mentions that
   histreg.no depends on a Digitalarkivet API and slows down when it is busy. It is
   unknown whether that API is public, documented or allowed for third parties.
   https://forum.arkivverket.no/topic/338303-bruk-historisk-befolkningsregister-hbr-histregno-som-felles-plattform/
3. **Census material on xml.arkivverket.no (unconfirmed).** Search results show
   census booklet PDFs under `xml.arkivverket.no/folketellinger/hefter/...`, so
   that host may also serve census data files. Not checked.
4. **Bulk census downloads have been requested by users (unconfirmed).** Forum
   threads ask how to download census data to spreadsheets. One commenter
   suspects copyright issues with the underlying database. That is an informal
   opinion, not an official statement.
   https://forum.arkivverket.no/topic/356732-nedlasting-av-folketellingsdata/
   https://forum.arkivverket.no/topic/320920-laste-ned-folketellinger-til-regneark/
5. **Historisk befolkningsregister (HBR).** Run by Arkivverket at histreg.no,
   with Norsk Regnesentral involved. It is open to search, and adding links needs
   a password requested from histreg@nr.no. Data beyond what the site shows can
   reportedly be released to research projects. No public API or bulk download
   was found.
   https://home.nr.no/~holden/Histreg-2024-Nov.pdf
6. **Licence.** NLOD (Norsk lisens for offentlige data) is the likely candidate
   for Arkivverket's own data, but no source confirmed that it covers the
   census or church-book transcriptions. Some transcriptions were made by
   volunteers and organisations (e.g. through Digitalpensjonatet) and may carry
   other terms.

## Open questions to ask Arkivverket

Send to Arkivverket (postmottak@arkivverket.no was listed as a contact in
search results; confirm on their site):

1. Is there a public, documented API or search endpoint for Digitalarkivet's
   transcribed sources (censuses 1801 to 1910 and church books)? If so, where is
   the documentation?
2. Are the transcribed censuses (1801, 1865, 1875, 1900, 1910) and church
   books available as downloadable datasets? In what format, and for which
   counties? Is Østfold complete?
3. Which licence applies to the transcriptions: NLOD, CC BY, or something else?
   Does it differ for volunteer-made transcriptions?
4. Is **commercial use** allowed? We are testing a possible paid genealogy
   service that cites and links to Digitalarkivet records.
5. Are automated queries allowed at all? If yes, what rate limit, and do they
   require registration or an API key?
6. May we store transcribed record data locally (as a cache) and show
   excerpts to customers with a link back to the record?
7. Is the API that histreg.no uses open to third parties? Can HBR's linked
   person data be used, and under what terms?
8. Is there a contact person for research or partnership access?

## What the code assumes once access is confirmed

* At most 1 request per second unless the terms allow more (`RateLimiter`).
* A clear User-Agent naming the prototype (`USER_AGENT`).
* Every fetched record cached in SQLite, so nothing is fetched twice.
* Only records more than 100 years old. Queries for people born within the last
  100 years are refused.
* Every reported candidate links directly to its record page.

If downloadable datasets exist, prefer them. Convert them to the CSV format in
`data/README.md` and use `--source local --records <file>`. No scraping is needed.
