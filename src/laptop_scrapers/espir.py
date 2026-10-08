"""Espircom Systems scraper."""
from __future__ import annotations
import html
import logging
import re
from typing import Any, List, Optional
import requests

from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title
from laptop_scrapers.base import fetch_resilient_url

logger = logging.getLogger("EspirScraper")

CATALOG_URLS = [
    "https://www.espir.co.il/category/apple-mac",
    "https://www.espir.co.il/category/dell-pro-3",
    "https://www.espir.co.il/category/dell-pro-5",
]


class EspirScraper:
    STORE_NAME = "Espircom"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        try:
            from http_session import fetch_resilient_url as _fetch
            self._fetch = _fetch
        except ImportError:
            self._fetch = None

    def _get_html(self, url: str, timeout: int = 25) -> str:
        if self._fetch is not None:
            try:
                status, text = self._fetch(url, timeout=timeout)
                if status == 200 and text:
                    return text
            except Exception as ex:
                logger.debug("Resilient fetch failed for %s: %s", url, ex)
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
        except Exception as ex:
            logger.debug("Session get failed for %s: %s", url, ex)
        return ""

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Espircom Systems...")
        items: List[LaptopItem] = []
        seen = set()

        for cat_url in CATALOG_URLS:
            try:
                html_text = self._get_html(cat_url)
                if not html_text:
                    continue

                for m in re.finditer(r'<a\b[^>]*\bhref=[\"\'](/product/[^\"\']+)[\"\'][^>]*>', html_text, re.IGNORECASE):
                    tag = m.group(0)
                    u = m.group(1)
                    full_url = f"https://www.espir.co.il{u}"
                    if full_url in seen:
                        continue

                    price_m = re.search(r'ee_list_itemprice=[\"\']([0-9,]+)[\"\']', tag)
                    name_m = re.search(r'ee_list_itemname=[\"\']([^\"\']+)[\"\']', tag)
                    if not price_m or not name_m:
                        continue

                    title = html.unescape(name_m.group(1)).strip()
                    if not HardwareClassifier.is_laptop(title) or not is_laptop_title(title):
                        continue

                    try:
                        price = int(price_m.group(1).replace(',', ''))
                    except Exception:
                        continue
                    if price < 500:
                        continue

                    seen.add(full_url)
                    warranty = 36 if any(k in title for k in ['3Y', '3 years', '3 שנים', '36 חודש']) else 12

                    items.append(HardwareClassifier.build_laptop(
                        store=self.STORE_NAME,
                        title=title,
                        price_ils=price,
                        url=full_url,
                        deal_price_ils=price,
                        deal_label=f"{price:,} ₪",
                        analysis_text=title,
                        warranty_months=warranty,
                        stock_status="🟢 In Stock"
                    ))
            except Exception as e:
                logger.error("Error scraping Espircom from %s: %s", cat_url, e)

        logger.info("Espircom: scraped %d laptops", len(items))
        return items
