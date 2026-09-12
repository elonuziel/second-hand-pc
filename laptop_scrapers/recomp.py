"""Recomp Computers scraper."""
from __future__ import annotations
import html
import logging
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional
import requests
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import last_valid_price

logger = logging.getLogger("RecompScraper")

# Try the Hebrew-slug catalog page first, fall back to decoded equivalents
# and the root site (which may route differently from datacenter IPs).
CATALOG_URLS = [
    "https://recomp.co.il/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%d7%95%d7%93%d7%a9%d7%99%d7%9d-%d7%91%d7%9e%d7%91%d7%a6%d7%a2/",
    "https://recomp.co.il/מחשבים-מחודשים-במבצע/",
    "https://recomp.co.il/product-category/laptops/",
    "https://recomp.co.il/",
]

# --- Store 4: Recomp Computers Scraper ---
class RecompScraper:
    STORE_NAME = "Recomp Computers"

    def __init__(self, session: requests.Session):
        self.session = session
        # Import resilient fetcher — prefer the shared engine over bare session
        try:
            from http_session import fetch_resilient_url as _fetch
            self._fetch = _fetch
        except ImportError:
            self._fetch = None

    def _get(self, url: str, timeout: int = 35) -> Optional[requests.Response]:
        """Fetch url via resilient engine or fall back to session.get()."""
        if self._fetch is not None:
            try:
                status, text = self._fetch(url, timeout=timeout)
                if status == 200 and text:
                    # Wrap in a mock response-like object
                    class _R:
                        def __init__(self, t, s):
                            self.text = t
                            self.status_code = s
                    return _R(text, status)
            except Exception as ex:
                logger.debug("Resilient fetch failed for %s: %s", url, ex)
        # Fallback: plain session
        return self.session.get(url, timeout=timeout)

    def _parse_recomp_price(self, page_html: str) -> Optional[int]:
        cleaned = page_html.replace('&#8362;', '₪').replace('&nbsp;', ' ')
        ins = re.findall(r'<ins[^>]*>.*?([0-9]{1,2},[0-9]{3}|[0-9]{3,5}).*?</ins>', cleaned, re.DOTALL)
        if ins:
            return last_valid_price(ins)
        nums = re.findall(r'₪\s*([\d,]+)|([\d,]+)\s*₪', cleaned)
        values = [value for pair in nums for value in pair if value]
        return last_valid_price((value for value in values if value.replace(',', '') != '8362'), minimum=501)

    def _parse_recomp_image(self, page_html: str) -> str:
        og_m = re.search(r'<meta\s+property=[\"\']og:image[\"\']\s+content=[\"\']([^\"\']+)[\"\']', page_html, re.I)
        if og_m:
            return og_m.group(1).strip()
        img_m = re.search(r'<img[^>]*src=[\"\']([^\"\']+(?:uploads|product)[^\"\']+)[\"\']', page_html, re.I)
        if img_m:
            return img_m.group(1).strip()
        return ""

    def _parse_recomp_desc(self, page_html: str) -> str:
        short_m = re.search(r'class=[\"\'][^\"\']*woocommerce-product-details__short-description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        tab_m = re.search(r'id=[\"\'](tab-description)[\"\']\s*[^>]*>([\s\S]*?)</div>', page_html)
        if not tab_m:
            tab_m = re.search(r'class=[\"\'][^\"\']*woocommerce-Tabs-panel--description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        parts = []
        if short_m:
            parts.append(short_m.group(1))
        if tab_m:
            # group(1) is the id attr, group(2) is content if the second pattern matched
            g = tab_m.group(2) if tab_m.lastindex and tab_m.lastindex >= 2 else tab_m.group(1)
            parts.append(g)
        if parts:
            return html.unescape(re.sub(r'<[^>]+>', ' ', ' '.join(parts))).strip()
        return ""

    def _fetch_catalog(self) -> Optional[str]:
        """Try each catalog URL in order; return HTML text of first successful one."""
        for url in CATALOG_URLS:
            for attempt in range(3):
                try:
                    r = self._get(url, timeout=35)
                    if r and r.status_code == 200 and r.text:
                        # Sanity check: must look like a product listing page
                        if 'recomp.co.il' in r.text or 'product' in r.text:
                            logger.info("Recomp catalog fetched from %s (attempt %d)", url, attempt + 1)
                            return r.text
                except Exception as ex:
                    logger.warning("Recomp catalog fetch %s attempt %d failed: %s", url, attempt + 1, ex)
            logger.warning("All attempts failed for Recomp catalog URL: %s", url)
        return None

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Recomp Computers...")
        items: List[LaptopItem] = []
        try:
            catalog_html = self._fetch_catalog()
            if not catalog_html:
                logger.error("Recomp: could not fetch any catalog URL — giving up.")
                return items

            links = re.findall(
                r'<a[^>]+href=[\"\']\\s*(https://recomp\\.co\\.il/(?:product/|מוצר/|פריט/)[^\"\']+)[\"\'][^>]*>(.*?)</a>',
                catalog_html, re.DOTALL
            )
            # Also try percent-encoded product paths
            if not links:
                links = re.findall(
                    r'href=["\']( https?://recomp\.co\.il/[^"\']*(?:product|%d7%9e%d7%95%d7%a6%d7%a8)[^"\']+)["\']',
                    catalog_html, re.IGNORECASE | re.DOTALL
                )
                links = [(l.strip(), "") for l in links]

            seen = set()
            valid_links = []
            for link, text in links:
                link = link.strip()
                if link in seen:
                    continue
                seen.add(link)
                title = HardwareClassifier.clean_text(text)
                if len(title) < 4:
                    slug = link.rstrip('/').split('/')[-1]
                    title = HardwareClassifier.clean_text(urllib.parse.unquote(slug).replace('-', ' '))
                if not HardwareClassifier.is_laptop(title):
                    continue
                valid_links.append((link, title))

            logger.info("Recomp: found %d product links to fetch.", len(valid_links))

            # Fetch exact prices and descriptions concurrently
            def fetch_recomp_item(item_tuple):
                link, title = item_tuple
                for attempt in range(2):
                    try:
                        res = self._get(link, timeout=20)
                        if res and res.status_code == 200:
                            p = self._parse_recomp_price(res.text)
                            img = self._parse_recomp_image(res.text)
                            desc = self._parse_recomp_desc(res.text)
                            return link, title, p, img, desc
                    except Exception as ex:
                        logger.debug("Recomp item fetch attempt %d failed for %s: %s", attempt + 1, link, ex)
                return link, title, None, "", ""

            with ThreadPoolExecutor(max_workers=6) as executor:
                fetched_results = list(executor.map(fetch_recomp_item, valid_links))

            for link, title, price, img, desc in fetched_results:
                if price is None:
                    logger.warning("Skipping Recomp listing without a valid price: %s", link)
                    continue
                analysis = f"{title} {desc}".strip()

                warranty = 12
                if any(k in analysis for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש"]):
                    warranty = 36
                elif any(k in analysis for k in ["שנתיים אחריות", "שנתיים", "24 חודש"]):
                    warranty = 24

                items.append(HardwareClassifier.build_laptop(
                    store=self.STORE_NAME,
                    title=title,
                    price_ils=price,
                    url=link,
                    analysis_text=analysis,
                    warranty_months=warranty,
                    stock_status="🟢 In Stock",
                    image_url=img,
                ))
        except Exception as e:
            logger.error("Error scraping Recomp: %s", e)
        return items
