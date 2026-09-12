"""Machsanei Hashmal (Payngo) scraper."""
from __future__ import annotations
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional
from http_session import is_bot_challenge
from laptop_scrapers.base import fetch_rendered_url, fetch_resilient_url
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

    def _fetch_detail_specs(self, url: str) -> str:
        try:
            status, html_page = fetch_resilient_url(url)
            if status == 200 and html_page:
                desc_m = re.search(r'class=[\"\'][^\"\']*product\s+attribute\s+description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', html_page)
                if not desc_m:
                    desc_m = re.search(r'id=[\"\']description[\"\'][^>]*>([\s\S]*?)</div>', html_page)
                if not desc_m:
                    desc_m = re.search(r'class=[\"\'][^\"\']*additional-attributes-wrapper[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', html_page)
                if desc_m:
                    return html.unescape(re.sub(r'<[^>]+>', ' ', desc_m.group(1))).strip()
        except Exception:
            pass
        return ""

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Machsanei Hashmal (Payngo)...")
        items: List[LaptopItem] = []
        parsed_cards = []
        try:
            status, text = fetch_resilient_url(self.CATALOG_URL)
            if status != 200 or not text:
                if is_bot_challenge(status, text):
                    logger.warning(
                        "Payngo catalog is behind a bot challenge (HTTP %s) — trying the optional browser fallback.",
                        status,
                    )
                else:
                    logger.warning("Payngo returned HTTP %s — trying the optional browser fallback.", status)

                # Only the catalog is worth a browser: detail pages degrade to empty specs
                # rather than launching one browser per product.
                text = fetch_rendered_url(self.CATALOG_URL) or ""
                if not text:
                    logger.error(
                        "Payngo: no usable catalog content (HTTP %s, browser fallback unavailable or blocked). "
                        "Previously scraped data will be preserved by the pipeline.",
                        status,
                    )
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

                parsed_cards.append((title, price, url, img, card_body))

            # Fetch detailed product specifications concurrently
            urls_to_fetch = [c[2] for c in parsed_cards]
            details_map = {}
            with ThreadPoolExecutor(max_workers=4) as executor:
                desc_results = executor.map(self._fetch_detail_specs, urls_to_fetch)
                for url, desc in zip(urls_to_fetch, desc_results):
                    details_map[url] = desc

            for title, price, url, img, card_body in parsed_cards:
                detail_specs = details_map.get(url, "")
                analysis = f"{title} {detail_specs}".strip()

                warranty = 12
                if any(k in analysis for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש"]):
                    warranty = 36
                elif any(k in analysis for k in ["שנתיים אחריות", "שנתיים", "24 חודש"]) or 'שנתיים' in card_body:
                    warranty = 24

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
            logger.error(f"Error scraping Payngo: {e}")
        return items
