"""Shared scraper utilities and resilient fetch wrapper."""

from __future__ import annotations

from typing import Tuple


def fetch_resilient_url(url: str, **kwargs) -> Tuple[int, str]:
    """Fetch URL delegating through scraper.fetch_resilient_url for mock and production dispatch."""
    try:
        import scraper
        if hasattr(scraper, "fetch_resilient_url"):
            return scraper.fetch_resilient_url(url, **kwargs)
    except ImportError:
        pass
    from http_session import fetch_resilient_url as _fetch
    return _fetch(url, **kwargs)
