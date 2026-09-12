"""VOLT Green Computing scraper."""
from __future__ import annotations
import html
import logging
import re
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

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping VOLT Green Computing...")
        items: List[LaptopItem] = []
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
                    analysis = f"{raw_title} {desc_text}"

                    warranty = 12
                    if "שנתיים" in analysis or "24 חודש" in analysis:
                        warranty = 24
                    elif "3 שנים" in analysis or "36 חודש" in analysis:
                        warranty = 36

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

                if 'class="next_page"' not in text and "class='next_page'" not in text:
                    break
                page += 1

        except Exception as e:
            logger.error(f"Error scraping VOLT: {e}")
        return items
