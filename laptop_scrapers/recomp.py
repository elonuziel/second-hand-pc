"""Recomp Computers scraper."""
from __future__ import annotations
import html
import logging
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional
import requests
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import last_valid_price

logger = logging.getLogger("RecompScraper")

# --- Store 4: Recomp Computers Scraper ---
class RecompScraper:
    STORE_NAME = "Recomp Computers"
    CATALOG_URL = "https://recomp.co.il/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%d7%95%d7%93%d7%a9%d7%99%d7%9d-%d7%91%d7%9e%d7%91%d7%a6%d7%a2/"

    def __init__(self, session: requests.Session):
        self.session = session

    def _parse_recomp_price(self, html: str) -> Optional[int]:
        cleaned = html.replace('&#8362;', '₪').replace('&nbsp;', ' ')
        ins = re.findall(r'<ins[^>]*>.*?([0-9]{1,2},[0-9]{3}|[0-9]{3,5}).*?</ins>', cleaned, re.DOTALL)
        if ins:
            return last_valid_price(ins)
        nums = re.findall(r'₪\s*([\d,]+)|([\d,]+)\s*₪', cleaned)
        values = [value for pair in nums for value in pair if value]
        return last_valid_price((value for value in values if value.replace(',', '') != '8362'), minimum=501)

    def _parse_recomp_image(self, html: str) -> str:
        og_m = re.search(r'<meta\s+property=[\"\']og:image[\"\']\s+content=[\"\']([^\"\']+)[\"\']', html, re.I)
        if og_m:
            return og_m.group(1).strip()
        img_m = re.search(r'<img[^>]*src=[\"\']([^\"\']+(?:uploads|product)[^\"\']+)[\"\']', html, re.I)
        if img_m:
            return img_m.group(1).strip()
        return ""

    def _parse_recomp_desc(self, page_html: str) -> str:
        short_m = re.search(r'class=[\"\'][^\"\']*woocommerce-product-details__short-description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        tab_m = re.search(r'id=[\"\']tab-description[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        if not tab_m:
            tab_m = re.search(r'class=[\"\'][^\"\']*woocommerce-Tabs-panel--description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        parts = []
        if short_m:
            parts.append(short_m.group(1))
        if tab_m:
            parts.append(tab_m.group(1))
        if parts:
            return html.unescape(re.sub(r'<[^>]+>', ' ', ' '.join(parts))).strip()
        return ""

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Recomp Computers...")
        items: List[LaptopItem] = []
        try:
            r = self.session.get(self.CATALOG_URL, timeout=12)
            if r.status_code == 200:
                links = re.findall(r'<a[^>]+href=[\"\']\s*(https://recomp\.co\.il/(?:product/|מוצר/|פריט/)[^\"\']+)[\"\'][^>]*>(.*?)</a>', r.text, re.DOTALL)
                seen = set()
                valid_links = []
                for link, text in links:
                    link = link.strip()
                    if link in seen:
                        continue
                    seen.add(link)
                    title = HardwareClassifier.clean_text(text)
                    if len(title) < 4:
                        slug = link.rstrip('/').split('/')[-1]
                        title = HardwareClassifier.clean_text(urllib.parse.unquote(slug).replace('-', ' '))
                    if not HardwareClassifier.is_laptop(title):
                        continue
                    valid_links.append((link, title))

                # Fetch exact prices and descriptions concurrently for Recomp
                def fetch_recomp_item(item_tuple):
                    link, title = item_tuple
                    try:
                        res = self.session.get(link, timeout=8)
                        p = self._parse_recomp_price(res.text)
                        img = self._parse_recomp_image(res.text)
                        desc = self._parse_recomp_desc(res.text)
                        return link, title, p, img, desc
                    except Exception:
                        return link, title, None, "", ""

                with ThreadPoolExecutor(max_workers=6) as executor:
                    fetched_results = list(executor.map(fetch_recomp_item, valid_links))

                for link, title, price, img, desc in fetched_results:
                    if price is None:
                        logger.warning("Skipping Recomp listing without a valid price: %s", link)
                        continue
                    analysis = f"{title} {desc}".strip()

                    warranty = 12
                    if any(k in analysis for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש"]):
                        warranty = 36
                    elif any(k in analysis for k in ["שנתיים אחריות", "שנתיים", "24 חודש"]):
                        warranty = 24

                    items.append(HardwareClassifier.build_laptop(
                        store=self.STORE_NAME,
                        title=title,
                        price_ils=price,
                        url=link,
                        analysis_text=analysis,
                        warranty_months=warranty,
                        stock_status="🟢 In Stock",
                        image_url=img,
                    ))
        except Exception as e:
            logger.error(f"Error scraping Recomp: {e}")
        return items
