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
import time
import logging
import urllib.parse
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


def fetch_resilient_url(
    url: str,
    post_data: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
    timeout: int = 25,
) -> tuple[int, str]:
    """
    Fetches a URL using HTTP/2 and browser TLS fingerprinting (pycurl / curl_cffi).
    Bypasses Cloudflare, WAFs, and bot challenges.
    Returns (status_code, body_string).
    """
    # 1. Try pycurl with HTTP/2 (highest TLS compatibility in local Python environments)
    try:
        import pycurl
        import io

        buf = io.BytesIO()
        c = pycurl.Curl()
        c.setopt(c.URL, url)
        c.setopt(c.HTTP_VERSION, pycurl.CURL_HTTP_VERSION_2_0)

        ua = user_agent or DEFAULT_HEADERS.get('User-Agent', '')
        c.setopt(c.USERAGENT, ua)

        merged_headers = dict(DEFAULT_HEADERS)
        if headers:
            merged_headers.update(headers)
        if user_agent:
            merged_headers['User-Agent'] = user_agent

        header_list = [f"{k}: {v}" for k, v in merged_headers.items()]
        c.setopt(c.HTTPHEADER, header_list)

        if post_data is not None:
            c.setopt(c.POSTFIELDS, post_data)

        proxy = get_proxy_config()
        if proxy:
            c.setopt(c.PROXY, proxy)

        c.setopt(c.WRITEDATA, buf)
        c.setopt(c.FOLLOWLOCATION, True)
        c.setopt(c.SSL_VERIFYPEER, 0)
        c.setopt(c.SSL_VERIFYHOST, 0)
        c.setopt(c.TIMEOUT, timeout)

        c.perform()
        code = c.getinfo(pycurl.RESPONSE_CODE)
        c.close()
        if code not in (403, 429, 202, 0):
            return code, buf.getvalue().decode("utf-8", errors="ignore")
        logger.info(f"pycurl got HTTP {code} for {url}, falling back...")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"pycurl fetch failed for {url}: {e}, falling back...")

    # 2. Try curl_cffi if installed
    try:
        from curl_cffi import requests as cffi_requests
        session = create_resilient_session(impersonate="chrome124")
        req_headers = dict(headers or {})
        if user_agent:
            req_headers['User-Agent'] = user_agent
        if post_data is not None:
            resp = session.post(url, data=post_data, headers=req_headers, timeout=timeout)
        else:
            resp = session.get(url, headers=req_headers, timeout=timeout)
        if resp.status_code not in (403, 429, 202):
            return resp.status_code, resp.text
        logger.info(f"curl_cffi got HTTP {resp.status_code} for {url}, falling back...")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"curl_cffi fetch failed for {url}: {e}, falling back...")

    # 3. Fallback to standard requests
    try:
        import requests
        session = requests.Session()
        session.headers['User-Agent'] = user_agent or DEFAULT_HEADERS['User-Agent']
        session.verify = False
        req_headers = dict(headers or {})
        if user_agent:
            req_headers['User-Agent'] = user_agent
        if post_data is not None:
            resp = session.post(url, data=post_data, headers=req_headers, timeout=timeout)
        else:
            resp = session.get(url, headers=req_headers, timeout=timeout)
        return resp.status_code, resp.text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return 0, ""


# Signatures of JavaScript bot-challenge interstitials that only a real browser clears.
_CHALLENGE_MARKERS = (
    "sgcaptcha",
    "robot challenge",
    "just a moment",
    "attention required",
    "checking your browser",
    "cf-chl",
)


def is_bot_challenge(status: int, body: str) -> bool:
    """True when a response is a bot-challenge/block page rather than real content.

    Covers the SiteGround/Sucuri handshake (HTTP 202 plus a meta-refresh pointing at
    /.well-known/sgcaptcha/) and Cloudflare interstitials (403 "Attention Required!" or
    "Just a moment...").

    Verified 2026-09-12 against a challenged IP: the Sucuri challenge URL sets no cookie,
    so replaying it still returns 202; curl_cffi Chrome impersonation (chrome124/131/136)
    returns 202 while an un-impersonated client gets a hard 403; per-IP proxies and
    Crawlbase (Normal and JavaScript tokens) also fail.  Only JS execution clears these —
    see fetch_rendered_url.
    """
    if status == 202:  # SiteGround/Sucuri challenge handshake
        return True
    text = (body or "")[:6000].lower()
    return any(marker in text for marker in _CHALLENGE_MARKERS)


def _looks_like_challenge(body: str) -> bool:
    """True when a rendered body is still an unsolved bot-challenge interstitial."""
    return is_bot_challenge(200, body)


def _browser_proxy_config(proxy: str) -> Dict[str, str]:
    """Converts a proxy URL (possibly with inline credentials) into Playwright's format."""
    parsed = urllib.parse.urlsplit(proxy)
    if not parsed.hostname:
        return {"server": proxy}

    server = f"{parsed.scheme or 'http'}://{parsed.hostname}"
    if parsed.port:
        server = f"{server}:{parsed.port}"

    config = {"server": server}
    if parsed.username:
        config["username"] = urllib.parse.unquote(parsed.username)
    if parsed.password:
        config["password"] = urllib.parse.unquote(parsed.password)
    return config


def fetch_rendered_url(
    url: str,
    timeout: int = 45,
    user_agent: Optional[str] = None,
    wait_until: str = "domcontentloaded",
) -> Optional[str]:
    """
    Fetches a URL through headless Chromium (Playwright) so JavaScript bot-challenges can
    execute and clear themselves, then returns the settled page body.

    Playwright is an OPTIONAL dependency: when it (or its Chromium binary) is unavailable
    this returns None instead of raising, leaving plain HTTP fetching as the fallback.
    Enable with `pip install playwright && playwright install chromium`; force off with
    SCRAPER_DISABLE_BROWSER=1, or run headed for debugging with SCRAPER_BROWSER_HEADLESS=0.

    Returns page HTML, or the plain-text body for JSON endpoints (Chromium wraps JSON in
    a <pre>, so the inner text is the useful payload there).
    """
    if os.environ.get("SCRAPER_DISABLE_BROWSER"):
        logger.info(f"Browser fallback disabled via SCRAPER_DISABLE_BROWSER for {url}")
        return None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.info(
            f"Playwright not installed — browser fallback unavailable for {url} "
            "(pip install playwright && playwright install chromium)"
        )
        return None

    headless = os.environ.get("SCRAPER_BROWSER_HEADLESS", "1") not in ("0", "false", "no")
    proxy = get_proxy_config()
    timeout = max(timeout, 5)
    deadline = time.time() + timeout

    launch_kwargs: Dict[str, Any] = {"headless": headless}
    if proxy:
        launch_kwargs["proxy"] = _browser_proxy_config(proxy)

    # WAFs often answer a cleared challenge with a 403 page; track the last document status
    # so an error page is never handed back as if it were real content.
    document_status: Dict[str, Optional[int]] = {"code": None}

    def _record_document_status(response: Any) -> None:
        try:
            if response.request.resource_type == "document":
                document_status["code"] = response.status
        except Exception:
            pass

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(**launch_kwargs)
            try:
                context = browser.new_context(
                    user_agent=user_agent or DEFAULT_HEADERS['User-Agent'],
                    locale="he-IL",
                    extra_http_headers={
                        key: value for key, value in DEFAULT_HEADERS.items() if key != 'User-Agent'
                    },
                )
                page = context.new_page()
                page.on("response", _record_document_status)
                page.goto(url, timeout=timeout * 1000, wait_until=wait_until)

                # A solved challenge reloads the original URL, so poll until the body settles.
                # content() raises while a navigation is in flight (the challenge reload does
                # exactly that), so treat those reads as "not settled yet" and retry.
                body = ""
                while time.time() < deadline:
                    try:
                        body = page.content()
                    except Exception:
                        body = ""
                    if body and not _looks_like_challenge(body):
                        break
                    page.wait_for_timeout(1000)

                if not body or _looks_like_challenge(body):
                    logger.warning(f"Browser fallback still challenge-blocked for {url}")
                    return None

                status_code = document_status["code"]
                if status_code is not None and status_code >= 400:
                    logger.warning(
                        f"Browser fallback cleared the challenge but the site answered HTTP {status_code} "
                        f"for {url} — this IP is likely WAF-blocked, so no content is usable."
                    )
                    return None

                try:
                    text = (page.evaluate("document.body ? document.body.innerText : ''") or "").strip()
                except Exception:
                    text = ""
                if text[:1] in ("[", "{"):
                    logger.info(f"Browser fallback rendered JSON endpoint {url} ({len(text)} bytes)")
                    return text

                logger.info(f"Browser fallback rendered {url} ({len(body)} bytes)")
                return body
            finally:
                browser.close()
    except Exception as e:
        logger.warning(f"Browser fallback failed for {url}: {e}")
        return None


