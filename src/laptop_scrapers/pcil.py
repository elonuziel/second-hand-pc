"""PC-Online / PCIL clearance and renewed laptops scraper."""
from __future__ import annotations
import html
import json
import logging
import re
from typing import Any, List, Optional
import requests

from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title
from laptop_scrapers.base import fetch_resilient_url

logger = logging.getLogger("PCILScraper")

CLEARANCE_URL = "https://pcil.co.il/categories/clearance"


class PCILScraper:
    STORE_NAME = "PC-Online (PCIL)"

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
        logger.info("Scraping PC-Online (PCIL) clearance...")
        html_text = self._get_html(CLEARANCE_URL)
        if not html_text:
            logger.warning("PCIL: failed to fetch clearance page")
            return []

        items: List[LaptopItem] = []
        json_ld_matches = re.findall(r'<script type=[\"\']application/ld\+json[\"\']>(.*?)</script>', html_text, re.DOTALL)
        for block in json_ld_matches:
            try:
                data = json.loads(block)
                if data.get('@type') == 'ItemList':
                    for el in data.get('itemListElement', []):
                        it = el.get('item', {})
                        name = html.unescape(it.get('name', '')).strip()
                        if not name or not HardwareClassifier.is_laptop(name) or not is_laptop_title(name):
                            continue
                        url = it.get('url', '')
                        price = float(it.get('offers', {}).get('price', 0))
                        price_val = int(round(price))
                        if price_val < 500:
                            continue
                        image = it.get('image', '')

                        warranty = 12
                        if any(k in name for k in ["3Y", "3 years", "3 שנים", "36 חודש"]):
                            warranty = 36
                        elif any(k in name for k in ["2Y", "2 years", "שנתיים", "24 חודש"]):
                            warranty = 24

                        item = HardwareClassifier.build_laptop(
                            store=self.STORE_NAME,
                            title=name,
                            price_ils=price_val,
                            url=url,
                            deal_price_ils=price_val,
                            deal_label=f"{price_val:,} ₪",
                            analysis_text=name,
                            warranty_months=warranty,
                            stock_status="🟢 In Stock",
                            image_url=image
                        )
                        items.append(item)
            except Exception as e:
                logger.debug("PCIL: JSON-LD parse error: %s", e)

        logger.info("PCIL: scraped %d clearance laptops", len(items))
        return items
