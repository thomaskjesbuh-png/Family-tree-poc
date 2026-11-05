"""Source interface plus the politeness helpers every online source must use."""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod

from ..models import PersonQuery, Record
from .. import __version__

# Clear, honest User-Agent for any request to an archive.
USER_AGENT = (f"AncestorFinder-PoC/{__version__} "
              "(research prototype; low-volume; contact via the repository owner)")


class SourceUnavailable(RuntimeError):
    """The source cannot be used (no permitted access, network blocked, ...)."""


class RateLimiter:
    """At most one request per `min_interval` seconds (default 1 req/s)."""

    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            delay = self._last + self.min_interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


class Source(ABC):
    name: str = "source"

    @abstractmethod
    def search(self, query: PersonQuery) -> list[Record]:
        """Return candidate records worth scoring (a loose, recall-first filter)."""
