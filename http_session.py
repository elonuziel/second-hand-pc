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
import threading
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


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Reads a float env var, falling back to `default` when absent or unparseable."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(minimum, float(raw))
    except ValueError:
        logger.warning(f"Invalid {name}={raw!r}; using {default}")
        return default


def host_of(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc.lower()


# --- Per-host politeness -------------------------------------------------------
# WAFs escalate on request bursts, so keep a minimum gap between requests to the same
# host.  Serialising per host also caps its effective concurrency at one, which is what
# the Cloudflare/Sucuri walls actually react to.  Each store scrapes a single host, so
# SCRAPER_HOST_DELAYS lets the WAF-heavy stores run slower than the rest.
DEFAULT_HOST_DELAY = 1.0
_host_delay_lock = threading.Lock()
_host_locks: Dict[str, threading.Lock] = {}
_last_request_at: Dict[str, float] = {}


def get_host_delays() -> Dict[str, float]:
    """Per-host overrides from SCRAPER_HOST_DELAYS, e.g. 'payngo.co.il=3,cwc.co.il=2'."""
    overrides: Dict[str, float] = {}
    raw = (os.environ.get("SCRAPER_HOST_DELAYS") or "").strip()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        host, _, value = chunk.partition("=")
        host = host.strip().lower()
        try:
            overrides[host] = max(0.0, float(value))
        except ValueError:
            logger.warning(f"Ignoring invalid SCRAPER_HOST_DELAYS entry {chunk!r}")
    return overrides


def get_host_delay(host: str = "") -> float:
    """Seconds to wait between same-host requests.

    A host listed in SCRAPER_HOST_DELAYS wins; otherwise SCRAPER_HOST_DELAY (default 1.0s),
    and 0 disables throttling entirely.
    """
    host = (host or "").lower()
    if host:
        for suffix, seconds in get_host_delays().items():
            if host == suffix or host.endswith("." + suffix):
                return seconds
    return _env_float("SCRAPER_HOST_DELAY", DEFAULT_HOST_DELAY)


def respect_host_delay(url: str) -> float:
    """Blocks until `url`'s host may be contacted again; returns the seconds waited."""
    host = host_of(url)
    delay = get_host_delay(host)
    if delay <= 0 or not host:
        return 0.0

    with _host_delay_lock:
        host_lock = _host_locks.setdefault(host, threading.Lock())

    with host_lock:
        waited = 0.0
        last = _last_request_at.get(host)
        if last is not None:
            remaining = delay - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
                waited = remaining
        _last_request_at[host] = time.monotonic()
    return waited


def reset_host_delay_state() -> None:
    """Clears the throttle bookkeeping (used by tests and explicit rate-limit resets)."""
    with _host_delay_lock:
        _last_request_at.clear()


# --- Backoff on rate-limit / challenge responses --------------------------------
# These walls apply short-lived per-IP penalty windows (seconds to a minute), so one
# cooldown-then-retry recovers most transient blocks.  A host that stays blocked has its
# budget spent once and is then parked, so the rest of that store's URLs fail fast
# instead of each idling for the full cooldown.
# Off by default: measured on payngo (2026-09-12), a 30s/URL cooldown-retry tripled run
# time (10s -> 61-127s) and still produced no more items, because retrying *adds* request
# volume — the exact thing these walls penalise.  Raise SCRAPER_BACKOFF_BUDGET only when a
# store's catalog is transiently blocked and you can afford ~a minute of waiting per store.
DEFAULT_BACKOFF_BUDGET = 0.0    # seconds spent waiting per URL (0 = single attempt)
DEFAULT_BACKOFF_WAIT = 30.0     # seconds to wait before each retry
DEFAULT_HOST_PENALTY = 300.0    # seconds a host is parked after exhausting its budget
# 429 is deliberately absent: the pycurl -> curl_cffi -> requests chain inside one attempt
# already absorbs per-request throttling.  503 has no such fallback and is worth a retry.
RETRYABLE_STATUSES = (503,)

_backoff_lock = threading.Lock()
_penalized_hosts: Dict[str, float] = {}


def get_backoff_budget() -> float:
    return _env_float("SCRAPER_BACKOFF_BUDGET", DEFAULT_BACKOFF_BUDGET)


def get_backoff_wait() -> float:
    return _env_float("SCRAPER_BACKOFF_WAIT", DEFAULT_BACKOFF_WAIT)


def get_host_penalty() -> float:
    return _env_float("SCRAPER_HOST_PENALTY", DEFAULT_HOST_PENALTY)


def _is_retryable_block(status: int, body: str) -> bool:
    """Rate-limit/challenge responses are worth one cooldown-and-retry; hard errors are not."""
    return status in RETRYABLE_STATUSES or is_bot_challenge(status, body)


def _penalize_host(host: str, seconds: float) -> None:
    if not host or seconds <= 0:
        return
    with _backoff_lock:
        _penalized_hosts[host] = time.monotonic() + seconds


def is_host_penalized(host: str) -> bool:
    """True while a host is parked after burning its retry budget."""
    host = (host or "").lower()
    if not host:
        return False
    with _backoff_lock:
        until = _penalized_hosts.get(host)
        if until is None:
            return False
        if time.monotonic() >= until:
            _penalized_hosts.pop(host, None)
            return False
        return True


def reset_backoff_state() -> None:
    """Clears parked hosts and retry bookkeeping (used by tests)."""
    with _backoff_lock:
        _penalized_hosts.clear()


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


def _attempt_fetch(
    url: str,
    post_data: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
    timeout: int = 25,
) -> tuple[int, str]:
    """
    One pass through the client chain: pycurl (HTTP/2) -> curl_cffi -> plain requests.
    Returns (status_code, body_string), or (0, "") when every client failed.
    """
    respect_host_delay(url)

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


def fetch_resilient_url(
    url: str,
    post_data: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    user_agent: Optional[str] = None,
    timeout: int = 25,
) -> tuple[int, str]:
    """
    Fetches a URL using HTTP/2 and browser TLS fingerprinting (pycurl / curl_cffi),
    paced per host and retried through short-lived rate-limit blocks.
    Returns (status_code, body_string).

    A challenged response (or `503`) is retried after a cooldown when
    SCRAPER_BACKOFF_BUDGET > 0, waiting SCRAPER_BACKOFF_WAIT between attempts; a host that
    stays blocked after spending its budget is parked for SCRAPER_HOST_PENALTY seconds so
    the remaining URLs for that store fail fast.  Retries are off by default — see the
    note on DEFAULT_BACKOFF_BUDGET for the measurements behind that choice.
    """
    host = host_of(url)
    attempts = 0
    waited = 0.0

    while True:
        attempts += 1
        status, body = _attempt_fetch(url, post_data, headers, user_agent, timeout)
        if not _is_retryable_block(status, body):
            if attempts > 1:
                logger.info(f"Recovered after {attempts} attempts: {url}")
            return status, body

        budget, wait = get_backoff_budget(), get_backoff_wait()
        if budget <= 0 or wait <= 0:
            return status, body  # cooldown retries disabled (the default)

        if is_host_penalized(host):
            logger.info(f"Host {host} is parked after an earlier block; skipping retries for {url}")
            return status, body

        if waited + wait > budget:
            logger.warning(
                f"Still blocked (HTTP {status}) after {attempts} attempt(s): {url} — "
                f"parking {host} for {get_host_penalty():.0f}s"
            )
            _penalize_host(host, get_host_penalty())
            return status, body

        logger.warning(
            f"HTTP {status} looks like a challenge for {url}; "
            f"cooling down {wait:.0f}s before attempt {attempts + 1}"
        )
        time.sleep(wait)
        waited += wait


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

    respect_host_delay(url)

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


