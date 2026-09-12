"""Machsanei Hashmal (Payngo) scraper."""
from __future__ import annotations
import html
import logging
import re
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title

logger = logging.getLogger("PayngoScraper")

# --- Store 6: Machsanei Hashmal (Payngo) Scraper ---
class PayngoScraper:
    STORE_NAME = "Payngo"
    CATALOG_URL = "https://www.payngo.co.il/computers-pcs/computing-gaming/direct-imports-tech.html"

    def __init__(self, session: Any = None):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Machsanei Hashmal (Payngo)...")
        items: List[LaptopItem] = []
        try:
            status, text = fetch_resilient_url(self.CATALOG_URL)
            if status != 200 or not text:
                logger.warning(f"Payngo returned HTTP {status}")
                return items

            cards = re.findall(r'<form\s+method="post"[^>]*action="[^"]*product/(\d+)/"[^>]*>([\s\S]*?)</form>', text)
            for pid, card_body in cards:
                title_m = re.search(r'<a\s+class="product-item-link"\s+href="([^"]+)"[^>]*>([\s\S]*?)</a>', card_body)
                if not title_m:
                    continue

                url = title_m.group(1).strip()
                title = html.unescape(re.sub(r'\s+', ' ', title_m.group(2)).strip())

                if not is_laptop_title(title):
                    continue

                price_m = re.search(r'data-price-amount="([0-9.]+)"', card_body)
                if not price_m:
                    price_m = re.search(r'<span\s+class="price">\s*‏?([0-9,]+)', card_body)
                price = int(round(float(price_m.group(1).replace(',', '')))) if price_m else 0
                if price <= 0:
                    continue

                img_m = re.search(r'<img[^>]*class="[^"]*product-image-photo[^"]*"[^>]*src="([^"]+)"', card_body)
                img = img_m.group(1) if img_m else ""

                warranty = 24 if ('שנתיים אחריות' in card_body or 'שנתיים' in title) else 12

                items.append(HardwareClassifier.build_laptop(
                    store=self.STORE_NAME,
                    title=title,
                    price_ils=price,
                    url=url,
                    warranty_months=warranty,
                    stock_status="🟢 In Stock",
                    image_url=img
                ))
        except Exception as e:
            logger.error(f"Error scraping Payngo: {e}")
        return items
