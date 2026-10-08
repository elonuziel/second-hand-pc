"""LaptopTech LTS scraper."""
from __future__ import annotations
import html
import json
import logging
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional, Set
import requests

from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title, last_valid_price
from laptop_scrapers.base import fetch_resilient_url

logger = logging.getLogger("LTSScraper")


class LTSScraper:
    STORE_NAME = "LaptopTech LTS"
    API_URL = "https://lts.co.il/wp-json/wc/store/v1/products?category=559&per_page=100"
    CATALOG_URL = "https://lts.co.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%99%D7%93-2/"

    def __init__(self, session: Optional[requests.Session] = None, include_legacy: Optional[bool] = None):
        self.session = session or requests.Session()
        if include_legacy is None:
            import os
            include_legacy = os.environ.get("SCRAPER_INCLUDE_LEGACY", "").lower() in ("1", "true", "yes")
        self.include_legacy = include_legacy

    @staticmethod
    def _is_modern_cpu(cpu_str: str) -> bool:
        """Filter strictly for modern laptops: 8th Gen+, AMD Ryzen, Apple Silicon M-series, Core Ultra."""
        if not cpu_str:
            return False
        modern_gens = ["8th Gen", "9th Gen", "10th Gen", "11th Gen", "12th Gen", "13th Gen", "14th Gen"]
        if any(g in cpu_str for g in modern_gens):
            return True
        if any(k in cpu_str for k in ["Ryzen", "Apple M", "Core Ultra"]):
            return True
        return False

    def _items_from_api_payload(self, data: list) -> List[LaptopItem]:
        """Parse WooCommerce Store API products filtering for active, in-stock modern refurbished laptops."""
        items: List[LaptopItem] = []
        for p in data:
            if not isinstance(p, dict):
                continue

            name = html.unescape(p.get("name", "")).strip()
            if not name or not HardwareClassifier.is_laptop(name) or not is_laptop_title(name):
                continue

            if not p.get("is_in_stock", True):
                continue

            # Sold check: LTS store owners frequently append / prepend "נמכר" instead of marking out-of-stock
            short_desc = html.unescape(re.sub(r'<[^>]+>', ' ', p.get("short_description", ""))).strip()
            desc = html.unescape(re.sub(r'<[^>]+>', ' ', p.get("description", ""))).strip()
            if "נמכר" in name or "נמכר" in short_desc or "נמכר" in desc:
                continue

            prices = p.get("prices", {})
            raw_price = prices.get("price") or prices.get("regular_price")
            minor = prices.get("currency_minor_unit", 0)
            try:
                price_val = int(round(float(raw_price) / (10 ** minor)))
            except Exception:
                price_val = 0

            if price_val < 601:
                continue

            url = p.get("permalink", "")
            images = p.get("images", [])
            img_url = images[0].get("src", "") if images else ""

            # Deal price calculation (if on sale)
            sale_price_raw = prices.get("sale_price")
            deal_price = price_val
            deal_label = f"{price_val:,} ₪"
            if sale_price_raw and str(sale_price_raw).isdigit():
                try:
                    sale_val = int(round(float(sale_price_raw) / (10 ** minor)))
                    if 601 <= sale_val < price_val:
                        deal_price = sale_val
                        deal_label = f"{sale_val:,} ₪ (Sale)"
                except Exception:
                    pass

            # Attributes & description
            attr_parts = []
            warranty_terms = []
            for a in p.get("attributes", []):
                aname = a.get("name", "")
                terms = [t.get("name", "") for t in a.get("terms", [])]
                attr_parts.append(f"{aname}: {', '.join(terms)}")
                if aname in ["אחריות", "Warranty", "warranty"]:
                    warranty_terms.extend(terms)

            analysis = f"{name} {' '.join(attr_parts)} {short_desc} {desc}".strip()

            warranty = 12
            all_warr_text = f"{' '.join(warranty_terms)} {analysis}"
            if any(k in all_warr_text for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש", "3 years", "3y"]):
                warranty = 36
            elif any(k in all_warr_text for k in ["שנתיים אחריות", "שנתיים", "24 חודש", "2 years", "2y"]):
                warranty = 24

            item = HardwareClassifier.build_laptop(
                store=self.STORE_NAME,
                title=name,
                price_ils=price_val,
                url=url,
                deal_price_ils=deal_price,
                deal_label=deal_label,
                analysis_text=analysis,
                warranty_months=warranty,
                stock_status="🟢 In Stock",
                image_url=img_url,
            )

            # Filter for modern laptops (8th Gen Intel or newer, AMD Ryzen, Apple Silicon) unless include_legacy is set
            if not self.include_legacy and not self._is_modern_cpu(item.cpu):
                continue

            items.append(item)

        return items

    def _parse_product_page_price(self, html_text: str) -> Optional[int]:
        cleaned = html_text.replace('&#8362;', '₪').replace('&nbsp;', ' ')
        widget = re.findall(r'elementor-widget-woocommerce-product-price(.*?)</div>\s*</div>', cleaned, re.DOTALL)
        if widget:
            ins = re.findall(r'<ins[^>]*>.*?([0-9]{1,2},[0-9]{3}|[0-9]{3,5}).*?</ins>', widget[0], re.DOTALL)
            if ins:
                return last_valid_price(ins)
            nums = re.findall(r'([0-9]{1,2},[0-9]{3}|[0-9]{3,5})', widget[0])
            price = last_valid_price((n for n in nums if n.replace(',', '') != '8362'))
            if price is not None:
                return price

        cur_match = re.findall(r'המחיר הנוכחי הוא:[^\d]*([\d,]+)', cleaned)
        if cur_match:
            return last_valid_price(cur_match)

        single = re.findall(r'<p class=\"price\">(.*?)</p>', cleaned, re.DOTALL)
        if single:
            nums = re.findall(r'([0-9]{1,2},[0-9]{3}|[0-9]{3,5})', single[-1])
            price = last_valid_price((n for n in nums if n.replace(',', '') != '8362'))
            if price is not None:
                return price

        schema = re.findall(r'\"price\"\s*:\s*\"?(\d+)\"?', cleaned)
        if schema:
            return int(schema[-1])
        return None

    def _parse_product_page_image(self, html_text: str) -> str:
        og_m = re.search(r'<meta\s+property=[\"\']og:image[\"\']\s+content=[\"\']([^\"\']+)[\"\']', html_text, re.I)
        if og_m:
            return og_m.group(1).strip()
        img_m = re.search(r'<img[^>]*src=[\"\']([^\"\']+(?:uploads|product)[^\"\']+)[\"\']', html_text, re.I)
        if img_m:
            return img_m.group(1).strip()
        return ""

    def _parse_product_page_desc(self, page_html: str) -> str:
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
        logger.info("Scraping LaptopTech LTS...")
        items: List[LaptopItem] = []
        seen_urls: Set[str] = set()

        # 1. Primary: WooCommerce Store API
        for page in range(1, 5):
            url = f"{self.API_URL}&page={page}"
            try:
                status, text = fetch_resilient_url(url, headers={"Accept": "application/json"})
                if status == 200 and text:
                    data = json.loads(text)
                    if not isinstance(data, list) or len(data) == 0:
                        break
                    page_items = self._items_from_api_payload(data)
                    for item in page_items:
                        if item.url not in seen_urls:
                            seen_urls.add(item.url)
                            items.append(item)
                    if len(data) < 100:
                        break
                else:
                    break
            except Exception as e:
                logger.warning("Error fetching LTS API page %d: %s", page, e)
                break

        if items:
            logger.info("LTS: successfully scraped %d modern refurbished laptops via Store API", len(items))
            return items

        # 2. Fallback: HTML Catalog
        logger.info("LTS: Store API returned 0 items; falling back to HTML catalog scraping...")
        try:
            r = self.session.get(self.CATALOG_URL, timeout=12)
            if r.status_code == 200:
                raw_links = set(re.findall(r'href=[\"\']\s*(https://lts\.co\.il/(?:פריט|product)/[^\"\']+)[\"\']', r.text))
                valid_links = []
                for link in sorted(raw_links):
                    slug = link.rstrip('/').split('/')[-1]
                    slug_clean = urllib.parse.unquote(slug).replace('-', ' ')
                    if HardwareClassifier.is_laptop(slug_clean) and is_laptop_title(slug_clean):
                        valid_links.append((link, slug_clean))

                def fetch_item_details(item_tuple):
                    link, slug_clean = item_tuple
                    try:
                        res = self.session.get(link, timeout=8)
                        p = self._parse_product_page_price(res.text)
                        img = self._parse_product_page_image(res.text)
                        desc = self._parse_product_page_desc(res.text)
                        return link, slug_clean, p, img, desc
                    except Exception:
                        return link, slug_clean, None, "", ""

                with ThreadPoolExecutor(max_workers=10) as executor:
                    fetched_results = list(executor.map(fetch_item_details, valid_links))

                for link, slug_clean, price, img, desc in fetched_results:
                    if price is None or price < 601:
                        continue
                    if "נמכר" in slug_clean or "נמכר" in desc:
                        continue
                    words = slug_clean.split()
                    title = ' '.join(w.capitalize() if not any(c.isdigit() for c in w) else w.upper() for w in words)
                    analysis = f"{title} {slug_clean} {desc}".strip()

                    warranty = 12
                    if any(k in analysis for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש"]):
                        warranty = 36
                    elif any(k in analysis for k in ["שנתיים אחריות", "שנתיים", "24 חודש"]):
                        warranty = 24

                    item = HardwareClassifier.build_laptop(
                        store=self.STORE_NAME,
                        title=title,
                        price_ils=price,
                        url=link,
                        analysis_text=analysis,
                        warranty_months=warranty,
                        stock_status="🟢 In Stock",
                        image_url=img,
                    )
                    if not self.include_legacy and not self._is_modern_cpu(item.cpu):
                        continue
                    if item.url not in seen_urls:
                        seen_urls.add(item.url)
                        items.append(item)
        except Exception as e:
            logger.error(f"Error scraping LTS HTML fallback: {e}")

        return items
