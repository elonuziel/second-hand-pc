"""KTWO scraper."""
from __future__ import annotations
import html
import json
import logging
import re
from typing import Any, List, Optional, Set
import requests

from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title
from laptop_scrapers.base import fetch_resilient_url

logger = logging.getLogger("KTWOScraper")


class KTWOScraper:
    STORE_NAME = "KTWO"
    API_URL = "https://www.ktwo.co.il/wp-json/wc/store/v1/products?category=283&per_page=50"
    CATALOG_URL = "https://www.ktwo.co.il/category/laptop/"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        if hasattr(self.session, "headers") and hasattr(self.session.headers, "setdefault"):
            self.session.headers.setdefault(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            )

    @staticmethod
    def _is_refurbished_product(p: dict) -> bool:
        """Determines if a KTWO product is refurbished based on condition attribute, tags, and title."""
        name = p.get("name", "")
        if "NEW!" in name:
            return False

        cond_terms = []
        for a in p.get("attributes", []):
            if a.get("name") in ["מצב", "Condition", "condition"]:
                cond_terms.extend([t.get("name", "") for t in a.get("terms", [])])

        # If explicitly marked new
        if any(c == "חדש" for c in cond_terms):
            return False

        # Condition attribute explicitly refurbished
        if any("מחודש" in c or "מוחדש" in c or "refurb" in c.lower() for c in cond_terms):
            return True

        # Tagged as refurbished (e.g. מחודשים - חיסכון)
        tags = [t.get("name", "") for t in p.get("tags", [])]
        if any("מחודש" in t or "מוחדש" in t or "refurb" in t.lower() for t in tags):
            return True

        # Title keyword
        refurb_patterns = [r"מחודש", r"מחודשת", r"מוחדש", r"מוחדשת", r"refurbished", r"\brenew\b", r"עודפי מלאי"]
        return any(re.search(pat, name, re.IGNORECASE) for pat in refurb_patterns)

    def _items_from_api_payload(self, data: list) -> List[LaptopItem]:
        """Parses the WooCommerce Store API JSON payload for refurbished laptops."""
        items: List[LaptopItem] = []
        for p in data:
            if not isinstance(p, dict):
                continue

            name = html.unescape(p.get("name", "")).strip()
            if not name or not is_laptop_title(name):
                continue

            if not self._is_refurbished_product(p):
                continue

            if not p.get("is_in_stock", True):
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

            # Attributes & description for hardware classifier
            attr_parts = []
            warranty_terms = []
            for a in p.get("attributes", []):
                aname = a.get("name", "")
                terms = [t.get("name", "") for t in a.get("terms", [])]
                attr_parts.append(f"{aname}: {', '.join(terms)}")
                if aname in ["אחריות", "Warranty", "warranty"]:
                    warranty_terms.extend(terms)

            short_desc = html.unescape(re.sub(r'<[^>]+>', ' ', p.get("short_description", ""))).strip()
            desc = html.unescape(re.sub(r'<[^>]+>', ' ', p.get("description", ""))).strip()
            analysis = f"{name} {' '.join(attr_parts)} {short_desc} {desc}".strip()

            warranty = 12
            all_warr_text = f"{' '.join(warranty_terms)} {analysis}"
            if any(k in all_warr_text for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש", "3 years", "3y"]):
                warranty = 36
            elif any(k in all_warr_text for k in ["שנתיים אחריות", "שנתיים", "24 חודש", "2 years", "2y"]):
                warranty = 24

            items.append(HardwareClassifier.build_laptop(
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
            ))

        return items

    def _items_from_html(self, page_html: str, seen_urls: Set[str]) -> List[LaptopItem]:
        """Fallback parser for KTWO catalog HTML pages."""
        items: List[LaptopItem] = []
        cards = re.findall(
            r'<li[^>]*class=[\"\'][^\"\']*product[^\"\']*[\"\'][^>]*>(.*?)</li>',
            page_html,
            re.DOTALL,
        )
        for card in cards:
            link_m = re.search(r'href=[\"\'](https://www.ktwo.co.il/product/[^\"\']+)[\"\']', card)
            if not link_m:
                continue
            link = link_m.group(1)
            if link in seen_urls:
                continue

            title_m = re.search(r'<h[23][^>]*class=[\"\'][^\"\']*woocommerce-loop-product__title[^\"\']*[\"\'][^>]*>(.*?)</h[23]>', card, re.DOTALL)
            if not title_m:
                title_m = re.search(r'alt=[\"\']([^\"\']+)[\"\']', card)
            raw_title = html.unescape(re.sub(r'<[^>]+>', '', title_m.group(1))).strip() if title_m else ""
            if not raw_title or not is_laptop_title(raw_title):
                continue

            # Must be refurbished
            if "NEW!" in raw_title or not any(k in raw_title.lower() for k in ["מחודש", "מחודשת", "מוחדש", "מוחדשת", "refurb", "renew"]):
                continue

            price_m = re.search(r'<bdi>([0-9,]+)', card)
            if not price_m:
                price_m = re.search(r'(\d[\d,]*)\s*₪', card)
            if not price_m:
                continue
            price_val = int(price_m.group(1).replace(',', ''))
            if price_val < 601:
                continue

            seen_urls.add(link)
            img_m = re.search(r'<img[^>]*src=[\"\']([^\"\']+)[\"\']', card)
            img_url = img_m.group(1) if img_m else ""

            warranty = 24 if any(k in card for k in ["שנתיים", "24 חודש", "2 years"]) else 12

            items.append(HardwareClassifier.build_laptop(
                store=self.STORE_NAME,
                title=raw_title,
                price_ils=price_val,
                url=link,
                deal_price_ils=price_val,
                deal_label=f"{price_val:,} ₪",
                analysis_text=f"{raw_title} {card}",
                warranty_months=warranty,
                stock_status="🟢 In Stock",
                image_url=img_url,
            ))

        return items

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping KTWO...")
        items: List[LaptopItem] = []
        seen_urls: Set[str] = set()

        # 1. Primary: WooCommerce Store API
        for page in range(1, 4):
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
                    if len(data) < 50:
                        break
                else:
                    break
            except Exception as e:
                logger.warning("Error fetching KTWO API page %d: %s", page, e)
                break

        if items:
            return items

        # 2. Fallback: Category HTML
        for page in range(1, 3):
            page_url = f"{self.CATALOG_URL}page/{page}/" if page > 1 else self.CATALOG_URL
            try:
                status, text = fetch_resilient_url(page_url)
                if status == 200 and text:
                    page_items = self._items_from_html(text, seen_urls)
                    items.extend(page_items)
            except Exception as e:
                logger.warning("Error fetching KTWO HTML page %d: %s", page, e)

        return items

