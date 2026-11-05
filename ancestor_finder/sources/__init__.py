from .base import Source, SourceUnavailable, RateLimiter, USER_AGENT
from .local import LocalFileSource
from .digitalarkivet import DigitalarkivetSource

__all__ = ["Source", "SourceUnavailable", "RateLimiter", "USER_AGENT",
           "LocalFileSource", "DigitalarkivetSource", "get_source"]


def get_source(name: str, **kwargs) -> Source:
    if name == "local":
        return LocalFileSource(**kwargs)
    if name == "digitalarkivet":
        return DigitalarkivetSource(**kwargs)
    raise ValueError(f"Unknown source {name!r}; choose 'local' or 'digitalarkivet'")
