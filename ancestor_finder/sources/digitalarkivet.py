"""Placeholder for live Digitalarkivet access.

Deliberately not implemented. As of the access investigation
(docs/access-findings.md) no documented public search API was found, the
terms of use for automated access could not be read, and this environment
cannot reach digitalarkivet.no at all. The spec says not to guess or work
around this, so this source refuses to run until the open questions in
docs/access-findings.md are answered by Arkivverket.

When access is confirmed, implement `search` here using:
  * RateLimiter (1 request/second unless the terms allow more)
  * USER_AGENT
  * the SQLite Cache, so the same record is never fetched twice
and map each hit to a Record with a direct link to the record page.
"""

from __future__ import annotations

from ..models import PersonQuery, Record
from .base import Source, SourceUnavailable


class DigitalarkivetSource(Source):
    name = "digitalarkivet"

    def __init__(self, **_: object):
        pass

    def search(self, query: PersonQuery) -> list[Record]:
        raise SourceUnavailable(
            "Live Digitalarkivet access is not implemented: programmatic access and "
            "terms of use are unconfirmed. See docs/access-findings.md. "
            "Use --source local with a sample file instead."
        )
