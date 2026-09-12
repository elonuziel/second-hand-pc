"""IT Outlet scraper."""
from __future__ import annotations
import logging
import re
import urllib.parse
from typing import Any, List, Optional
import requests
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import last_valid_price

logger = logging.getLogger("ITOutletScraper")

# --- Store 1: IT Outlet Scraper ---
class ITOutletScraper:
    STORE_NAME = "IT Outlet"
    CATALOG_URL = "https://www.itoutlet.co.il/164920-%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D?order=up_price"

    def __init__(self, session: requests.Session):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping IT Outlet...")
        items: List[LaptopItem] = []
        seen_urls = set()

        for page in range(1, 4):
            url = f"{self.CATALOG_URL}&page={page}"
            try:
                r = self.session.get(url, timeout=12)
                if r.status_code != 200:
                    break

                blocks = re.findall(r'<div[^>]*class=[\"\'][^\"\']*layout_list_item[^\"\']*[\"\'][^>]*>(.*?)(?=<div[^>]*class=[\"\'][^\"\']*layout_list_item|$)', r.text, re.DOTALL)
                for b in blocks:
                    link_m = re.findall(r'href=[\"\']\s*(/items/\d+-[^\"\']+)[\"\']', b)
                    if not link_m:
                        continue
                    full_link = f"https://www.itoutlet.co.il{link_m[0].strip()}"
                    if full_link in seen_urls:
                        continue
                    seen_urls.add(full_link)

                    title_m = re.findall(r'alt=[\"\']([^\"\']+)[\"\']|<h[234][^>]*>(.*?)</h[234]>', b)
                    raw_title = title_m[0][0] or title_m[0][1] if title_m else "Laptop"
                    title = HardwareClassifier.clean_text(raw_title)
                    if not HardwareClassifier.is_laptop(title):
                        continue

                    # Exact price extraction (excluding newsletter coupon thresholds)
                    raw_prices = [int(p.replace(',', '')) for p in re.findall(r'(\d[\d,]*)\s*₪', b)]
                    raw_price = last_valid_price(
                        (price for price in raw_prices if price != 1500),
                        minimum=601,
                    )
                    if raw_price is None:
                        logger.warning("Skipping IT Outlet listing without a valid price: %s", title)
                        continue

                    # Smart Discount & Deal Price Logic
                    if 'p14s' in title.lower():
                        deal_price = 2500
                        deal_label = "2,500 ₪ (Coupon IT14)"
                    elif raw_price >= 2500:
                        deal_price = int(raw_price * 0.96)
                        deal_label = f"{deal_price:,} ₪ (4% Card Disc.)"
                    else:
                        deal_price = max(0, raw_price - 100)
                        deal_label = f"{deal_price:,} ₪ (100 ₪ Coupon)"

                    items.append(HardwareClassifier.build_laptop(
                        store=self.STORE_NAME,
                        title=title,
                        price_ils=raw_price,
                        url=full_link,
                        deal_price_ils=deal_price,
                        deal_label=deal_label,
                        warranty_months=12,
                        stock_status="🟢 In Stock",
                    ))
            except Exception as e:
                logger.error(f"Error scraping IT Outlet page {page}: {e}")

        return items
