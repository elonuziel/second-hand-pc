"""Olam HaKolnoa (CWC) scraper."""
from __future__ import annotations
import html
import json
import logging
import re
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title

logger = logging.getLogger("CWCScraper")

# --- Store 5: Olam HaKolnoa (CWC) Scraper ---
class CWCScraper:
    STORE_NAME = "Olam HaKolnoa"
    API_URL = "https://www.cwc.co.il/wp-json/wc/store/v1/products?category=817&per_page=100"
    MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"

    def __init__(self, session: Any = None):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Olam HaKolnoa (CWC)...")
        items: List[LaptopItem] = []
        try:
            status, text = fetch_resilient_url(
                self.API_URL,
                user_agent=self.MOBILE_UA,
                headers={"Accept": "application/json"}
            )
            if status != 200 or not text:
                logger.warning(f"CWC API returned HTTP {status}")
                return items

            data = json.loads(text)
            if not isinstance(data, list):
                return items

            for p in data:
                name = html.unescape(p.get("name", "")).strip()
                if not name:
                    continue

                if not is_laptop_title(name):
                    continue

                prices = p.get("prices", {})
                raw_price = prices.get("price") or prices.get("regular_price")
                price_val = 0
                if raw_price:
                    try:
                        minor = prices.get("currency_minor_unit", 2)
                        price_val = int(round(float(raw_price) / (10 ** minor))) if str(raw_price).isdigit() else int(round(float(raw_price)))
                    except Exception:
                        pass
                if price_val <= 0:
                    continue

                url = p.get("permalink", "")
                images = p.get("images", [])
                img_url = images[0].get("src", "") if images else ""

                desc = p.get("short_description", "") + " " + p.get("description", "")
                warranty = 36 if ("3 שנות אחריות" in desc or "3 שנים" in desc or "שלוש שנים" in desc) else 12

                items.append(HardwareClassifier.build_laptop(
                    store=self.STORE_NAME,
                    title=name,
                    price_ils=price_val,
                    url=url,
                    warranty_months=warranty,
                    stock_status="🟢 In Stock",
                    image_url=img_url
                ))
        except Exception as e:
            logger.error(f"Error scraping CWC: {e}")
        return items
