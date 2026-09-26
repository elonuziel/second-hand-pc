"""P1000 scraper."""
from __future__ import annotations
import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier

logger = logging.getLogger("P1000Scraper")

# Pre-compiled regex patterns for P1000 parsing
RE_DETAIL_PRODUCT_DETAILS = re.compile(r'id=[\"\'][^\"\']*productDetails[\"\'][^>]*>([\s\S]*?)</li>')
RE_DETAIL_MAIN_CONTENT = re.compile(r'id=[\"\']MainContent_Properties[^\"]*[\"\'][^>]*>([\s\S]*?)</ul>')
RE_DETAIL_SPECS_CLASS = re.compile(r'<div[^>]*class=[\"\'][^\"\']*specs[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', re.I)
RE_HTML_TAGS = re.compile(r'<[^>]+>')

RE_CARDS = re.compile(r'<li[^>]*data-sku=[\"\'](\d+)[\"\'][^>]*data-title=(?:\"([^\"]+)\"|\'([^\']+)\')[^>]*>([\s\S]*?)</li>')
RE_HREF = re.compile(r'href=[\"\']([^\"\']+)[\"\']')
RE_PRICE_CATEGORY = re.compile(r'categoryResults_itemBuy[\"\']>\s*[^0-9]*([0-9,]+)')
RE_PRICE_FALLBACK = re.compile(r'([0-9,]+)\s*(?:₪|ש\"ח)')
RE_IMG_SRC = re.compile(r'<img\s+[^>]*src=[\"\']([^\"\']+)[\"\']')
RE_SPANS = re.compile(r'<span>([^<]+)</span>')


# --- Store 9: P1000 Scraper ---
class P1000Scraper:
    STORE_NAME = "P1000"
    CATALOG_URL = "https://www.p1000.co.il/categories/category.aspx?categoryname=laptopoutlet"

    def __init__(self, session: Any = None):
        self.session = session

    def _fetch_detail_specs(self, url: str) -> str:
        try:
            status, html_page = fetch_resilient_url(url)
            if status == 200 and html_page:
                m = RE_DETAIL_PRODUCT_DETAILS.search(html_page)
                if not m:
                    m = RE_DETAIL_MAIN_CONTENT.search(html_page)
                if m:
                    return html.unescape(RE_HTML_TAGS.sub(' ', m.group(1))).strip()
                m2 = RE_DETAIL_SPECS_CLASS.search(html_page)
                if m2:
                    return html.unescape(RE_HTML_TAGS.sub(' ', m2.group(1))).strip()
        except Exception:
            pass
        return ""

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping P1000...")
        items: List[LaptopItem] = []
        try:
            status, text = fetch_resilient_url(self.CATALOG_URL)
            if status != 200 or not text:
                logger.warning(f"P1000 returned HTTP {status}")
                return items

            cards = RE_CARDS.findall(text)
            parsed_cards = []
            for sku, raw_title_dq, raw_title_sq, card_body in cards:
                raw_title = raw_title_dq or raw_title_sq or ""
                title = html.unescape(raw_title).strip()
                t_low = title.lower()
                if any(k in t_low for k in ["נייח", "mini", "tiny", "desktop"]):
                    continue

                link_m = RE_HREF.search(card_body)
                rel_url = link_m.group(1) if link_m else f"/sales/saledetails.aspx?productid={sku}"
                url = f"https://www.p1000.co.il{rel_url}" if rel_url.startswith('/') else rel_url

                price_m = RE_PRICE_CATEGORY.search(card_body)
                if not price_m:
                    price_m = RE_PRICE_FALLBACK.search(card_body)
                price = int(price_m.group(1).replace(',', '')) if price_m else 0
                if price <= 0:
                    continue

                img_matches = RE_IMG_SRC.findall(card_body)
                img = ""
                for src in img_matches:
                    src_low = src.lower()
                    if "brand" not in src_low and "logo" not in src_low and "icon" not in src_low:
                        img = f"https://www.p1000.co.il{src}" if src.startswith('/') else src
                        break
                if not img and img_matches:
                    img = f"https://www.p1000.co.il{img_matches[0]}" if img_matches[0].startswith('/') else img_matches[0]

                spans = RE_SPANS.findall(card_body)
                specs_summary = ' '.join(spans)

                parsed_cards.append((sku, title, price, url, img, specs_summary, card_body))

            # Fetch detailed product specifications concurrently
            urls_to_fetch = [c[3] for c in parsed_cards]
            details_map = {}
            with ThreadPoolExecutor(max_workers=6) as executor:
                desc_results = executor.map(self._fetch_detail_specs, urls_to_fetch)
                for url, desc in zip(urls_to_fetch, desc_results):
                    details_map[url] = desc

            for sku, title, price, url, img, specs_summary, card_body in parsed_cards:
                detail_specs = details_map.get(url, "")
                analysis = f"{title} {specs_summary} {detail_specs}".strip()

                warranty = 12
                if any(k in analysis for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש"]):
                    warranty = 36
                elif any(k in analysis for k in ["שנתיים אחריות", "שנתיים", "24 חודש"]):
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
            logger.error(f"Error scraping P1000: {e}")
        return items
