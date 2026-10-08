"""Ivory Computers Outlet / Metziaon scraper."""
from __future__ import annotations
import html
import logging
import re
import urllib.parse
from typing import Any, List, Optional
import requests

from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title
from laptop_scrapers.base import fetch_resilient_url

logger = logging.getLogger("IvoryScraper")

OUTLET_URL = "https://www.ivory.co.il/catalog.php?act=cat&q=%D7%9E%D7%95%D7%97%D7%93%D7%A9"

_NON_LAPTOP_IVORY = (
    'ראוטר', 'מודם', 'דיסק', 'כונן', 'מטען', 'כרטיס', 'מתאם', 'סוללה', 'מקלדת',
    'עכבר', 'אוזניות', 'router', 'modem', 'charger', 'cable'
)


class IvoryScraper:
    STORE_NAME = "Ivory Outlet"

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
        logger.info("Scraping Ivory Outlet (מוחדשים / מציאון)...")
        html_text = self._get_html(OUTLET_URL)
        if not html_text:
            logger.warning("Ivory: empty response")
            return []

        blocks = html_text.split('title_product_catalog')
        items: List[LaptopItem] = []
        seen = set()

        for b in blocks[1:]:
            title_m = re.search(r'title=[\"\']([^\"\']+)[\"\']', b)
            if not title_m:
                title_m = re.search(r'>([^<]*(?:מציאון|מוחדש|עודפים|נייד|thinkpad|latitude|elitebook)[^<]*)<', b, re.IGNORECASE)
            if not title_m:
                continue

            raw_title = html.unescape(title_m.group(1)).strip()
            # Clean title prefixes and suffixes
            clean_title = re.sub(r'^(?:מציאון|מוחדש|עודפים)\s*-\s*', '', raw_title).strip()
            clean_title = re.sub(r'\s*-\s*(?:מוחדש|מציאון|עודפים)$', '', clean_title).strip()

            if any(k in clean_title.lower() for k in _NON_LAPTOP_IVORY):
                continue
            if not is_laptop_title(clean_title) and not any(k in clean_title.lower() for k in ['asus tuf', 'omnibook', 'slim 3i', 'aspire go', 'onyx book', 'v15 gen', 'thinkpad', 'latitude', 'elitebook']):
                continue

            # Price
            price_m = re.search(r'class=[\"\']price\s*[\"\']>([0-9,]+)<', b)
            if not price_m:
                continue
            try:
                price = int(price_m.group(1).replace(',', ''))
            except Exception:
                continue
            if price < 500:
                continue

            # URL & Product ID
            id_m = re.search(r'(?:catalog\.php\?id=|\/catalog\.php\?id=)(\d+)', b)
            if not id_m:
                id_m = re.search(r'location\.href=[\"\'](?:catalog\.php\?id=)?(\d+)[\"\']', b)
            prod_id = id_m.group(1) if id_m else ""
            if not prod_id:
                continue
            prod_url = f"https://www.ivory.co.il/catalog.php?id={prod_id}"

            if prod_url in seen:
                continue
            seen.add(prod_url)

            # Image
            img_m = re.search(r'data-src=[\"\'](files/catalog/[^\"\']+)[\"\']', b)
            img_url = f"https://www.ivory.co.il/{img_m.group(1)}" if img_m else ""

            items.append(HardwareClassifier.build_laptop(
                store=self.STORE_NAME,
                title=clean_title,
                price_ils=price,
                url=prod_url,
                deal_price_ils=price,
                deal_label=f"{price:,} ₪",
                analysis_text=f"{clean_title} מוחדש מציאון",
                warranty_months=12,
                stock_status="🟢 In Stock",
                image_url=img_url
            ))

        logger.info("Ivory Outlet: scraped %d renewed laptops", len(items))
        return items
