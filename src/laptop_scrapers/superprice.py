"""SuperPrice scraper (WooCommerce Store REST API)."""
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

logger = logging.getLogger("SuperPriceScraper")

CATALOG_API_URL = "https://superprice.co.il/wp-json/wc/store/v1/products?category=149&per_page=100"


class SuperPriceScraper:
    STORE_NAME = "SuperPrice"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        try:
            from http_session import fetch_resilient_url as _fetch
            self._fetch = _fetch
        except ImportError:
            self._fetch = None

    def _get(self, url: str, timeout: int = 25) -> Optional[requests.Response]:
        if self._fetch is not None:
            try:
                status, text = self._fetch(url, timeout=timeout)
                if status == 200 and text:
                    class _R:
                        def __init__(self, t, s):
                            self.text = t
                            self.status_code = s
                        def json(self):
                            return json.loads(self.text)
                    return _R(text, status)
            except Exception as ex:
                logger.debug("Resilient fetch failed for %s: %s", url, ex)
        return self.session.get(url, timeout=timeout)

    def _items_from_api_payload(self, data: list) -> List[LaptopItem]:
        items: List[LaptopItem] = []
        for p in data:
            if not isinstance(p, dict):
                continue

            name = html.unescape(p.get("name", "")).strip()
            if not name or not HardwareClassifier.is_laptop(name) or not is_laptop_title(name):
                continue

            if not p.get("is_in_stock", True):
                continue

            prices = p.get("prices", {})
            raw_price = prices.get("price") or prices.get("regular_price")
            minor = prices.get("currency_minor_unit", 2)
            try:
                price_val = int(round(float(raw_price) / (10 ** minor)))
            except Exception:
                price_val = 0

            if price_val < 500:
                continue

            # Sale / deal price
            sale_price_raw = prices.get("sale_price")
            deal_price = price_val
            deal_label = f"{price_val:,} ₪"
            if sale_price_raw and str(sale_price_raw).isdigit():
                try:
                    sale_val = int(round(float(sale_price_raw) / (10 ** minor)))
                    if 500 <= sale_val < price_val:
                        deal_price = sale_val
                        deal_label = f"{sale_val:,} ₪ (Sale)"
                except Exception:
                    pass

            # Parse attributes
            attr_parts = []
            condition = "מחודש"
            warranty = 12
            for a in p.get("attributes", []):
                aname = a.get("name", "")
                terms = [t.get("name", "") for t in a.get("terms", [])]
                attr_parts.append(f"{aname}: {', '.join(terms)}")
                if aname == "מצב" and terms:
                    condition = terms[0]
                if any(w in aname.lower() for w in ["אחריות", "warranty"]):
                    w_text = " ".join(terms)
                    if any(k in w_text for k in ["3", "שלוש"]):
                        warranty = 36
                    elif any(k in w_text for k in ["2", "שנתיים"]):
                        warranty = 24

            short_desc = html.unescape(re.sub(r'<[^>]+>', ' ', p.get("short_description", ""))).strip()
            desc = html.unescape(re.sub(r'<[^>]+>', ' ', p.get("description", ""))).strip()
            analysis = f"{name} [{' '.join(attr_parts)}] {short_desc} {desc}".strip()

            images = p.get("images", [])
            img_url = images[0].get("src", "") if images else ""

            # Check warranty in text
            if any(k in analysis for k in ["3 שנות אחריות", "3 שנים אחריות", "36 חודש"]):
                warranty = 36
            elif any(k in analysis for k in ["שנתיים אחריות", "2 שנות אחריות", "24 חודש"]):
                warranty = 24

            items.append(HardwareClassifier.build_laptop(
                store=self.STORE_NAME,
                title=name,
                price_ils=price_val,
                url=p.get("permalink", ""),
                deal_price_ils=deal_price,
                deal_label=deal_label,
                analysis_text=analysis,
                warranty_months=warranty,
                stock_status="🟢 In Stock",
                image_url=img_url,
            ))

        return items

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping SuperPrice via WooCommerce Store API...")
        try:
            resp = self._get(CATALOG_API_URL, timeout=20)
            if resp and resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    items = self._items_from_api_payload(data)
                    logger.info("SuperPrice: scraped %d in-stock laptops from WooCommerce API", len(items))
                    return items
        except Exception as e:
            logger.error("Error scraping SuperPrice: %s", e)

        return []
