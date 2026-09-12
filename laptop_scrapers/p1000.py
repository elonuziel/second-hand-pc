"""P1000 scraper."""
from __future__ import annotations
import html
import logging
import re
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier

logger = logging.getLogger("P1000Scraper")

# --- Store 9: P1000 Scraper ---
class P1000Scraper:
    STORE_NAME = "P1000"
    CATALOG_URL = "https://www.p1000.co.il/categories/category.aspx?categoryname=laptopoutlet"

    def __init__(self, session: Any = None):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping P1000...")
        items: List[LaptopItem] = []
        try:
            status, text = fetch_resilient_url(self.CATALOG_URL)
            if status != 200 or not text:
                logger.warning(f"P1000 returned HTTP {status}")
                return items

            cards = re.findall(r'<li[^>]*data-sku=[\"\'](\d+)[\"\'][^>]*data-title=[\"\']([^\"\']+)[\"\'][^>]*>([\s\S]*?)</li>', text)
            for sku, raw_title, card_body in cards:
                title = html.unescape(raw_title).strip()
                t_low = title.lower()
                if any(k in t_low for k in ["נייח", "mini", "tiny", "desktop"]):
                    continue

                link_m = re.search(r'href=[\"\']([^\"\']+)[\"\']', card_body)
                rel_url = link_m.group(1) if link_m else f"/sales/saledetails.aspx?productid={sku}"
                url = f"https://www.p1000.co.il{rel_url}" if rel_url.startswith('/') else rel_url

                price_m = re.search(r'categoryResults_itemBuy[\"\']>\s*[^0-9]*([0-9,]+)', card_body)
                if not price_m:
                    price_m = re.search(r'([0-9,]+)\s*(?:₪|ש\"ח)', card_body)
                price = int(price_m.group(1).replace(',', '')) if price_m else 0
                if price <= 0:
                    continue

                img_m = re.search(r'<img\s+src=[\"\']([^\"\']+)[\"\']', card_body)
                img = ""
                if img_m:
                    img_src = img_m.group(1)
                    img = f"https://www.p1000.co.il{img_src}" if img_src.startswith('/') else img_src

                spans = re.findall(r'<span>([^<]+)</span>', card_body)
                specs_summary = ' '.join(spans)
                analysis = f"{title} {specs_summary}"

                warranty = 24 if any(k in card_body for k in ["שנתיים אחריות", "שנתיים"]) else 12

                items.append(HardwareClassifier.build_laptop(
                    store=self.STORE_NAME,
                    title=title,
                    price_ils=price,
                    url=url,
                    analysis_text=analysis,
                    warranty_months=warranty,
                    stock_status="🟢 In Stock",
                    image_url=img
                ))
        except Exception as e:
            logger.error(f"Error scraping P1000: {e}")
        return items
