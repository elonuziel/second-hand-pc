"""Ofek PC scraper."""
from __future__ import annotations
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier

logger = logging.getLogger("OfekPCScraper")

# --- Store 12: Ofek PC (אופק פי סי) Scraper ---
class OfekPCScraper:
    STORE_NAME = "Ofek PC"
    CATALOG_URL = "https://ofekpc.co.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D"

    def __init__(self, session: Any = None):
        self.session = session

    def _fetch_detail_specs(self, url: str) -> str:
        try:
            status, html_page = fetch_resilient_url(url)
            if status == 200 and html_page:
                full_desc_m = re.search(r'class=[\"\'][^\"\']*full-description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', html_page)
                specs_m = re.search(r'class=[\"\'][^\"\']*product-specs-box[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', html_page)
                parts = []
                if full_desc_m:
                    parts.append(full_desc_m.group(1))
                if specs_m:
                    parts.append(specs_m.group(1))
                if parts:
                    return html.unescape(re.sub(r'<[^>]+>', ' ', ' '.join(parts))).strip()
        except Exception:
            pass
        return ""

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Ofek PC (אופק פי סי)...")
        items: List[LaptopItem] = []
        parsed_items = []
        page = 1
        seen_urls = set()
        try:
            while page <= 10:
                url = f"{self.CATALOG_URL}?pagesize=100&pagenumber={page}" if page > 1 else f"{self.CATALOG_URL}?pagesize=100"
                status, text = fetch_resilient_url(url)
                if status != 200 or not text:
                    break

                boxes = text.split('class="item-box"')[1:]
                if not boxes:
                    break

                new_on_page = 0
                for box in boxes:
                    title_m = re.search(r'<h2 class=[\"\']product-title[\"\']>\s*<a href=[\"\']([^\"\']+)[\"\']>([\s\S]*?)</a>', box)
                    if not title_m:
                        continue

                    rel_url = title_m.group(1).strip()
                    full_url = f"https://ofekpc.co.il{rel_url}" if rel_url.startswith('/') else rel_url
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)
                    new_on_page += 1

                    raw_title = html.unescape(re.sub(r'<[^>]+>', ' ', title_m.group(2))).strip()
                    t_low = raw_title.lower()
                    if any(x in t_low for x in ['נייח', 'tiny', 'mini pc', 'desktop', 'optiplex', 'prodesk', 'elitedesk', 'tower', 'sff', 'all in one', 'aio', 'שולחני']):
                        continue

                    price_m = re.search(r'<span class=[\"\']price actual-price[\"\']>([\s\S]*?)</span>', box)
                    price_str = html.unescape(price_m.group(1)) if price_m else ''
                    num_m = re.search(r'([0-9,]+)', price_str)
                    price = int(num_m.group(1).replace(',', '')) if num_m else 0
                    if price <= 0:
                        continue

                    desc_m = re.search(r'<div class=[\"\']description[\"\'][^>]*>([\s\S]*?)</div>', box)
                    desc = html.unescape(re.sub(r'<[^>]+>', ' ', desc_m.group(1))).strip() if desc_m else ''

                    img_m = re.search(r'data-lazyloadsrc=[\"\']([^\"\']+)[\"\']', box)
                    if not img_m:
                        img_m = re.search(r'<img[^>]*src=[\"\']([^\"\']+)[\"\']', box)
                    img = img_m.group(1).strip() if img_m else ''

                    parsed_items.append((raw_title, price, full_url, desc, img))

                if new_on_page == 0:
                    break
                page += 1

            # Fetch detailed product specifications concurrently
            urls_to_fetch = [pi[2] for pi in parsed_items]
            details_map = {}
            with ThreadPoolExecutor(max_workers=6) as executor:
                desc_results = executor.map(self._fetch_detail_specs, urls_to_fetch)
                for u, d in zip(urls_to_fetch, desc_results):
                    details_map[u] = d

            for raw_title, price, full_url, desc, img in parsed_items:
                detail_specs = details_map.get(full_url, "")
                analysis = f"{raw_title} {desc} {detail_specs}".strip()

                warranty = 12
                if any(k in analysis for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש"]):
                    warranty = 36
                elif any(k in analysis for k in ["שנתיים אחריות", "שנתיים", "24 חודש"]):
                    warranty = 24

                items.append(HardwareClassifier.build_laptop(
                    store=self.STORE_NAME,
                    title=raw_title,
                    price_ils=price,
                    url=full_url,
                    analysis_text=analysis,
                    warranty_months=warranty,
                    stock_status="🟢 In Stock",
                    image_url=img
                ))

        except Exception as e:
            logger.error(f"Error scraping Ofek PC: {e}")
        return items
