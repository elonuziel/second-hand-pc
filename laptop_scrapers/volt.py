"""VOLT Green Computing scraper."""
from __future__ import annotations
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier

logger = logging.getLogger("VoltScraper")

# --- Store 11: VOLT (וולט מחשוב ירוק) Scraper ---
class VoltScraper:
    STORE_NAME = "Volt"
    CATALOG_URL = "https://www.volt.co.il/23409-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D"

    def __init__(self, session: Any = None):
        self.session = session

    def _fetch_detail_specs(self, url: str) -> str:
        try:
            status, html_page = fetch_resilient_url(url)
            if status == 200 and html_page:
                sub_m = re.search(r'id=[\"\']item_current_sub_title[\"\'][^>]*>([\s\S]*?)</div>', html_page)
                attr_m = re.search(r'id=[\"\']item_attributes[\"\'][^>]*>([\s\S]*?)</div>\s*<!--\s*show_html_in_tabs', html_page)
                if not attr_m:
                    attr_m = re.search(r'class=[\"\'][^\"\']*item_attributes[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', html_page)
                desc_m = re.search(r'class=[\"\'][^\"\']*page_item_description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', html_page)

                parts = []
                if sub_m:
                    parts.append(sub_m.group(1))
                if attr_m:
                    parts.append(attr_m.group(1))
                if desc_m:
                    parts.append(desc_m.group(1))
                if parts:
                    return html.unescape(re.sub(r'<[^>]+>', ' ', ' '.join(parts))).strip()
        except Exception:
            pass
        return ""

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping VOLT Green Computing...")
        items: List[LaptopItem] = []
        parsed_cards = []
        page = 1
        seen_urls = set()
        try:
            while page <= 15:
                url = f"{self.CATALOG_URL}?page={page}" if page > 1 else self.CATALOG_URL
                status, text = fetch_resilient_url(url)
                if status != 200 or not text:
                    break

                cards = re.findall(
                    r'<div id=[\"\']item_id_(\d+)[\"\'][^>]*class=[\"\'][^\"\']*layout_list_item[^\"\']*[\"\'][^>]*>([\s\S]*?)<!-- end layout_list_item -->',
                    text
                )
                if not cards:
                    break

                for item_id, card_body in cards:
                    title_m = re.search(
                        r'<div class=[\"\']list_item_title_with_brand[\"\']>\s*<h3><a href=[\"\']([^\"\']+)[\"\']>([\s\S]*?)</a></h3>',
                        card_body
                    )
                    if not title_m:
                        continue

                    rel_url = title_m.group(1).strip()
                    full_url = f"https://www.volt.co.il{rel_url}" if rel_url.startswith('/') else rel_url
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    raw_title = html.unescape(re.sub(r'<[^>]+>', ' ', title_m.group(2))).strip()
                    t_low = raw_title.lower()
                    if any(x in t_low for x in ['נייח', 'tiny', 'mini pc', 'desktop', 'optiplex', 'prodesk', 'elitedesk', 'tower', 'sff', 'all in one', 'aio', 'שולחני']):
                        continue

                    price_m = re.search(r'<strong>\s*([0-9,]+)\s*₪\s*</strong>', card_body)
                    if not price_m:
                        price_m = re.search(r'([0-9,]+)\s*₪', card_body)
                    price = int(price_m.group(1).replace(',', '')) if price_m else 0
                    if price <= 0:
                        continue

                    img_m = re.search(
                        r'<div class=[\"\']list_item_image[\"\']>[\s\S]*?<img[^>]*src=[\"\']([^\"\']+)[\"\']',
                        card_body
                    )
                    img = img_m.group(1).strip() if img_m else ""

                    desc_m = re.search(
                        r'<div class=[\"\']list_item_current_list_item_content[\"\']>[\s\S]*?<p>([\s\S]*?)</p>',
                        card_body
                    )
                    desc_text = re.sub(r'<[^>]+>', ' ', desc_m.group(1)).strip() if desc_m else ""

                    parsed_cards.append((raw_title, price, full_url, img, desc_text))

                if 'class="next_page"' not in text and "class='next_page'" not in text:
                    break
                page += 1

            # Fetch detailed product specifications concurrently
            urls_to_fetch = [c[2] for c in parsed_cards]
            details_map = {}
            with ThreadPoolExecutor(max_workers=6) as executor:
                desc_results = executor.map(self._fetch_detail_specs, urls_to_fetch)
                for u, d in zip(urls_to_fetch, desc_results):
                    details_map[u] = d

            for raw_title, price, full_url, img, desc_text in parsed_cards:
                detail_specs = details_map.get(full_url, "")
                analysis = f"{raw_title} {desc_text} {detail_specs}".strip()

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
            logger.error(f"Error scraping VOLT: {e}")
        return items
