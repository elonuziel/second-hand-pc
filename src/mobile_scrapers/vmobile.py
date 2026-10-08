"""VMobile refurbished scraper."""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Any

import requests
from mobile_classification import MobileClassifier
from mobile_domain import MobileItem

logger = logging.getLogger("VMobileScraper")


class VMobileScraper:
    STORE_NAME = "VMobile"
    CATALOG_URL = "https://www.vmobile.co.il/361324-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D"

    def __init__(self, session: Optional[Any] = None):
        self.session = session or requests.Session()

    def scrape(self) -> List[MobileItem]:
        logger.info("Scraping VMobile...")
        items: List[MobileItem] = []
        seen = set()

        for page in range(1, 4):
            url = f"{self.CATALOG_URL}?page={page}"
            try:
                r = self.session.get(url, timeout=12)
                if r.status_code != 200:
                    break

                blocks = re.findall(r'<div[^>]*class=[\"\'][^\"\']*layout_list_item[^\"\']*[\"\'][^>]*>(.*?)(?=<div[^>]*class=[\"\'][^\"\']*layout_list_item|$)', r.text, re.DOTALL)
                for b in blocks:
                    title_m = re.findall(r'alt=[\"\']([^\"\']+)[\"\']|<h[234][^>]*>(.*?)</h[234]>', b)
                    raw_title = title_m[0][0] or title_m[0][1] if title_m else ""
                    if not MobileClassifier.is_mobile_device(raw_title):
                        continue

                    link_m = re.findall(r'href=[\"\']\s*(/items/\d+-[^\"\']+)[\"\']', b)
                    if not link_m:
                        continue
                    full_link = f"https://www.vmobile.co.il{link_m[0].strip()}"
                    if full_link in seen:
                        continue
                    seen.add(full_link)

                    raw_prices = [int(p.replace(',', '')) for p in re.findall(r'(\d[\d,]*)\s*₪', b)]
                    valid_prices = [p for p in raw_prices if 150 <= p < 30000]
                    price = valid_prices[-1] if valid_prices else 0
                    if price <= 0:
                        continue

                    items.append(MobileClassifier.build_item(
                        store=self.STORE_NAME,
                        title=raw_title,
                        price_ils=price,
                        url=full_link,
                        warranty_months=12
                    ))
            except Exception as e:
                logger.error(f"Error scraping VMobile page {page}: {e}")

        return items
