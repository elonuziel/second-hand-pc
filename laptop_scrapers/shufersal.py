"""Shufersal Online scraper."""
from __future__ import annotations
import html
import json
import logging
import re
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier

logger = logging.getLogger("ShufersalScraper")

# --- Store 8: Shufersal Online Scraper ---
class ShufersalScraper:
    STORE_NAME = "Shufersal"
    CATALOG_URL = "https://www.shufersal.co.il/online/he/%D7%A7%D7%98%D7%92%D7%95%D7%A8%D7%99%D7%95%D7%AA/%D7%94%D7%A7%D7%A0%D7%99%D7%95%D7%9F-%D7%94%D7%9B%D7%9C-%D7%9C%D7%91%D7%99%D7%AA/%D7%90%D7%9C%D7%A7%D7%98%D7%A8%D7%95%D7%A0%D7%99%D7%A7%D7%94-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%95%D7%92%D7%99%D7%99%D7%9E%D7%99%D7%A0%D7%92/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%95%D7%A0%D7%99%D7%99%D7%97%D7%99%D7%9D/c/G030401"

    def __init__(self, session: Any = None):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Shufersal Online...")
        items: List[LaptopItem] = []
        try:
            status, text = fetch_resilient_url(self.CATALOG_URL)
            if status != 200 or not text:
                logger.warning(f"Shufersal returned HTTP {status}")
                return items

            tiles = re.findall(r'<li[^>]*class="[^"]*miglog-prod[^"]*"[^>]*>([\s\S]*?)</li>', text)
            for tile in tiles:
                link_m = re.search(r'<div\s+class="text description"[^>]*>\s*<a\s+href="([^"]+)"[^>]*>([\s\S]*?)</a>', tile)
                if not link_m:
                    continue

                rel_url = link_m.group(1).strip()
                full_url = f"https://www.shufersal.co.il{rel_url}" if rel_url.startswith('/') else rel_url
                raw_title = re.sub(r'<[^>]+>', ' ', link_m.group(2))
                title = html.unescape(re.sub(r'\s+', ' ', raw_title)).strip()

                t_low = title.lower()
                if any(k in t_low for k in ["שולחן", "מארז", "עכבר", "מקלדת", "אוזניות", "נייח", "all in one"]):
                    continue
                if not any(k in t_low for k in ["נייד", "laptop", "macbook", "thinkpad", "latitude"]):
                    continue

                price_m = re.search(r'<span\s+class="number">\s*([\d,]+)', tile)
                price = int(price_m.group(1).replace(',', '')) if price_m else 0
                if price < 400:
                    continue

                img_m = re.search(r'<img\s+src="([^"]+)"[^>]*class="pic"', tile)
                img = img_m.group(1) if img_m else ""

                small_m = re.search(r'<div\s+class="smallText">([\s\S]*?)</div>', tile)
                extra_text = re.sub(r'<[^>]+>', ' ', small_m.group(1)).strip() if small_m else ""
                analysis = f"{title} {extra_text}"

                items.append(HardwareClassifier.build_laptop(
                    store=self.STORE_NAME,
                    title=title,
                    price_ils=price,
                    url=full_url,
                    analysis_text=analysis,
                    warranty_months=12,
                    stock_status="🟢 In Stock",
                    image_url=img
                ))
        except Exception as e:
            logger.error(f"Error scraping Shufersal: {e}")
        return items
