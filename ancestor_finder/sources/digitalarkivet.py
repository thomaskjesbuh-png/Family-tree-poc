"""Placeholder for live Digitalarkivet access. Deliberately not implemented.

Findings (docs/access-findings.md, checked 2026-11-05):
  * robots.txt on www.digitalarkivet.no and api.digitalarkivet.no disallows
    AI agents (ClaudeBot, Claude-User, anthropic-ai and ~140 others) from the
    whole site.
  * Nasjonalarkivet staff confirm there is no bulk download API.
  * A documented 1910 census API exists (CC BY 3.0 NO), but sits on the same
    AI-restricted host.

Do not implement this until Nasjonalarkivet confirms in writing that this use
is allowed (question 1 in docs/access-findings.md). Use the downloadable census
files from xml.arkivverket.no through the local source instead.
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
            "Live Digitalarkivet access is not implemented: its robots.txt disallows "
            "AI agents and there is no confirmed permission. See docs/access-findings.md. "
            "Use --source local with a records file instead."
        )
