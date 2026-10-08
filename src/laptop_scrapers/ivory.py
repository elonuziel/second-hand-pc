"""Ivory Computers Outlet / Metziaon scraper."""
from __future__ import annotations

import html
import logging
import re
from typing import Any, List, Optional
import requests

from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title, is_desktop_title

logger = logging.getLogger("IvoryScraper")

OUTLET_URL = "https://www.ivory.co.il/catalog.php?act=cat&q=%D7%9E%D7%95%D7%97%D7%93%D7%A9"

_NON_LAPTOP_PREFIXES = (
    'מסך ', 'מטען ', 'מגן ', 'כיסוי ', 'סוללה ', 'כבל ', 'מעמד ', 'עכבר ', 'אוזניות ',
    'דיסק קשיח ', 'כונן חיצוני', 'זכרון נייד', 'כרטיס זכרון'
)

_STANDALONE_MONITOR_KEYWORDS = (
    'מסך גיימינג', 'מסך קעור', 'מסך מחשב', 'מסך oled', 'מסך ips', 'מסך 2', 'מסך 3', 'מסך 4'
)


def _is_ivory_non_laptop(title: str) -> bool:
    t = title.lower()
    # Check if it is a standalone monitor/screen
    if any(k in t for k in _STANDALONE_MONITOR_KEYWORDS) and not any(k in t for k in ['מחשב נייד', 'גיימינג נייד', 'מסך מגע']):
        return True
    # Check prefix exclusions
    if any(t.startswith(prefix) for prefix in _NON_LAPTOP_PREFIXES):
        return True
    # If explicitly recognized as a laptop model
    if any(k in t for k in ['מחשב נייד', 'מחשב גיימינג נייד', 'מקבוק', 'macbook', 'thinkpad', 'latitude', 'elitebook', 'zenbook', 'vivobook', 'loq', 'legion']):
        return False
    # General accessory items
    return any(k in t for k in ('ראוטר', 'מודם', 'עכבר', 'אוזניות', 'כרטיס זכרון', 'כרטיס רשת', 'דיסק קשיח', 'מקלדת'))


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

        # Split product boxes by border container or fallback markers
        boxes: List[str] = []
        if 'border: 1px solid #dddddd;' in html_text:
            boxes = html_text.split('border: 1px solid #dddddd;')[1:]
        elif 'product-anchor' in html_text:
            boxes = re.findall(
                r'(<a[^>]+class=[\"\'][^\"\']*product-anchor.*?)(?=<a[^>]+class=[\"\'][^\"\']*product-anchor|$)',
                html_text,
                re.DOTALL
            )
        elif 'title_product_catalog' in html_text:
            boxes = html_text.split('title_product_catalog')[1:]

        items: List[LaptopItem] = []
        seen = set()

        for box in boxes:
            # Product ID
            id_m = re.search(r'data-product-id=[\"\'](\d+)[\"\']|catalog\.php\?id=(\d+)', box)
            if not id_m:
                continue
            prod_id = id_m.group(1) or id_m.group(2)
            prod_url = f"https://www.ivory.co.il/catalog.php?id={prod_id}"
            if prod_url in seen:
                continue

            # Extract title: image title attribute, anchor title attribute, or main-text-area
            title_m = re.search(r'<img[^>]+class=[\"\'][^\"\']*img-fluid[^\"\']*[\"\'][^>]+title=[\"\']([^\"\']+)[\"\']', box)
            if not title_m:
                title_m = re.search(r'<img[^>]+title=[\"\']([^\"\']+)[\"\'][^>]+class=[\"\'][^\"\']*img-fluid[^\"\']*[\"\']', box)
            if not title_m:
                all_titles = re.findall(r'title=[\"\']([^\"\']+)[\"\']', box)
                for t in all_titles:
                    if t not in ('קיים במלאי', 'לא קיים במלאי') and not t.startswith('הוסף') and len(t) > 5:
                        title_m = re.match(r'^(.*)$', t)
                        break
            if not title_m:
                text_m = re.search(r'class=[\"\'][^\"\']*main-text-area[^\"\']*[\"\'][^>]*>(.*?)</div>', box, re.DOTALL)
                if text_m:
                    title_m = text_m

            if not title_m:
                continue

            raw_title = html.unescape(title_m.group(1)).strip()
            # Clean prefixes/suffixes including standard hyphens and unicode en/em dashes
            clean_title = re.sub(r'^(?:מציאון|מוחדש|עודפים)\s*[-–—]\s*', '', raw_title).strip()
            clean_title = re.sub(r'\s*[-–—]\s*(?:מוחדש|מציאון|עודפים)$', '', clean_title).strip()

            # Filter out desktops, accessories, and monitors
            if is_desktop_title(clean_title) or _is_ivory_non_laptop(clean_title):
                continue
            if not is_laptop_title(clean_title) and not any(k in clean_title.lower() for k in [
                'asus tuf', 'omnibook', 'slim 3i', 'aspire go', 'onyx book', 'v15 gen', 'thinkpad',
                'latitude', 'elitebook', 'zenbook', 'vivobook', 'loq', 'legion', 'macbook'
            ]):
                continue

            # Price
            price_m = re.search(r'class=[\"\']price\s*[\"\']>([0-9,]+)<', box)
            if not price_m:
                continue
            try:
                price = int(price_m.group(1).replace(',', ''))
            except Exception:
                continue
            if price < 500:
                continue

            seen.add(prod_url)

            # Image
            img_m = re.search(r'data-src=[\"\'](files/catalog/[^\"\']+)[\"\']', box)
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
