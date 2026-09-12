#!/usr/bin/env python3
"""
Resilient HTTP Client & Session Factory
=======================================
Provides Cloudflare-resilient HTTP sessions for web scrapers:
- Detects and utilizes `curl_cffi` for TLS/JA3/JA4 fingerprint impersonation when installed (ideal for Cloud CI/CD & datacenter runners).
- Gracefully falls back to hardened `requests.Session` with modern browser headers, connection pooling, and exponential backoff retries.
- Transparently supports HTTP/HTTPS proxies via `SCRAPER_PROXY`, `HTTPS_PROXY`, or `HTTP_PROXY` environment variables.
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("ResilientSession")

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Linux"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
}


def get_proxy_config() -> Optional[str]:
    """Returns proxy URL if configured via environment variables."""
    return os.environ.get("SCRAPER_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None


def create_resilient_session(
    retries: int = 3,
    backoff_factor: float = 0.5,
    impersonate: str = "chrome124"
) -> Any:
    """
    Creates an HTTP session optimized to minimize bot-detection and 403 blocks.
    Prioritizes curl_cffi for browser TLS fingerprinting if installed.
    Falls back to requests.Session with connection pooling and backoff retries.
    """
    proxy = get_proxy_config()

    try:
        from curl_cffi import requests as cffi_requests
        session = cffi_requests.Session(impersonate=impersonate)
        session.headers.update(DEFAULT_HEADERS)
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
        logger.info(f"Created curl_cffi session impersonating {impersonate} (proxy={'enabled' if proxy else 'none'})")
        return session
    except ImportError:
        pass

    import requests
    import urllib3
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    session.verify = False

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=15, pool_maxsize=30)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})

    logger.info(f"Created standard requests resilient session (proxy={'enabled' if proxy else 'none'})")
    return session

