"""Recomp Computers scraper."""
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
from laptop_pipeline import report_store_block
from laptop_scrapers.base import fetch_resilient_url

logger = logging.getLogger("RecompScraper")

# Try the Hebrew-slug catalog page first, fall back to decoded equivalents
# and the root site (which may route differently from datacenter IPs).
CATALOG_URLS = [
    "https://recomp.co.il/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%d7%95%d7%93%d7%a9%d7%99%d7%9d-%d7%91%d7%9e%d7%91%d7%a6%d7%a2/",
    "https://recomp.co.il/מחשבים-מחודשים-במבצע/",
    "https://recomp.co.il/product-category/laptops/",
    "https://recomp.co.il/",
]


class RecompScraper:
    STORE_NAME = "Recomp Computers"
    API_URL = "https://recomp.co.il/wp-json/wc/store/v1/products?category=24&per_page=50"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        # Import resilient fetcher — prefer the shared engine over bare session
        try:
            from http_session import fetch_resilient_url as _fetch
            self._fetch = _fetch
        except ImportError:
            self._fetch = None

    def _get(self, url: str, timeout: int = 35) -> Optional[requests.Response]:
        """Fetch url via resilient engine or fall back to session.get()."""
        if self._fetch is not None:
            try:
                status, text = self._fetch(url, timeout=timeout)
                if status == 200 and text:
                    # Wrap in a mock response-like object
                    class _R:
                        def __init__(self, t, s):
                            self.text = t
                            self.status_code = s
                    return _R(text, status)
            except Exception as ex:
                logger.debug("Resilient fetch failed for %s: %s", url, ex)
        # Fallback: plain session
        return self.session.get(url, timeout=timeout)

    def _items_from_api_payload(self, data: list) -> List[LaptopItem]:
        """Parse WooCommerce Store API products adding all active, in-stock refurbished laptops."""
        items: List[LaptopItem] = []
        for p in data:
            if not isinstance(p, dict):
                continue

            name = html.unescape(p.get("name", "")).strip()
            if not name or not HardwareClassifier.is_laptop(name) or not is_laptop_title(name):
                continue

            if not p.get("is_in_stock", True):
                continue

            short_desc = html.unescape(re.sub(r'<[^>]+>', ' ', p.get("short_description", ""))).strip()
            desc = html.unescape(re.sub(r'<[^>]+>', ' ', p.get("description", ""))).strip()

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

    def _parse_recomp_price(self, page_html: str) -> Optional[int]:
        cleaned = page_html.replace('&#8362;', '₪').replace('&nbsp;', ' ')
        ins = re.findall(r'<ins[^>]*>.*?([0-9]{1,2},[0-9]{3}|[0-9]{3,5}).*?</ins>', cleaned, re.DOTALL)
        if ins:
            return last_valid_price(ins)
        nums = re.findall(r'₪\s*([\d,]+)|([\d,]+)\s*₪', cleaned)
        values = [value for pair in nums for value in pair if value]
        return last_valid_price((value for value in values if value.replace(',', '') != '8362'), minimum=501)

    def _parse_recomp_image(self, page_html: str) -> str:
        og_m = re.search(r'<meta\s+property=[\"\']og:image[\"\']\s+content=[\"\']([^\"\']+)[\"\']', page_html, re.I)
        if og_m:
            return og_m.group(1).strip()
        img_m = re.search(r'<img[^>]*src=[\"\']([^\"\']+(?:uploads|product)[^\"\']+)[\"\']', page_html, re.I)
        if img_m:
            return img_m.group(1).strip()
        return ""

    def _parse_recomp_desc(self, page_html: str) -> str:
        short_m = re.search(r'class=[\"\'][^\"\']*woocommerce-product-details__short-description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        tab_m = re.search(r'id=[\"\'](tab-description)[\"\']\s*[^>]*>([\s\S]*?)</div>', page_html)
        if not tab_m:
            tab_m = re.search(r'class=[\"\'][^\"\']*woocommerce-Tabs-panel--description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        parts = []
        if short_m:
            parts.append(short_m.group(1))
        if tab_m:
            # group(1) is the id attr, group(2) is content if the second pattern matched
            g = tab_m.group(2) if tab_m.lastindex and tab_m.lastindex >= 2 else tab_m.group(1)
            parts.append(g)
        if parts:
            return html.unescape(re.sub(r'<[^>]+>', ' ', ' '.join(parts))).strip()
        return ""

    def _extract_product_links(self, catalog_html: str) -> List[tuple]:
        """Extract (url, anchor_text) pairs for product pages from catalog HTML."""
        links = re.findall(
            r'<a[^>]+href=[\"\']\s*(https?://recomp\.co\.il/product/[^\"\']+)[\"\'][^>]*>(.*?)</a>',
            catalog_html, re.DOTALL | re.IGNORECASE
        )
        if not links:
            # Fallback: simpler href-only extraction, then we fetch each page for the title
            raw_hrefs = re.findall(
                r'href=[\"\']\s*(https?://recomp\.co\.il/product/[^\"\']+)[\"\']',
                catalog_html, re.IGNORECASE
            )
            links = [(h, "") for h in raw_hrefs]
        return [(url.strip(), text) for url, text in links]

    def _fetch_catalog(self) -> Optional[str]:
        """Try each catalog URL in order; return HTML text of first successful one."""
        for url in CATALOG_URLS:
            for attempt in range(3):
                try:
                    r = self._get(url, timeout=35)
                    if r and r.status_code == 200 and r.text:
                        # Sanity check: must look like a product listing page
                        if 'recomp.co.il' in r.text or 'product' in r.text:
                            logger.info("Recomp catalog fetched from %s (attempt %d)", url, attempt + 1)
                            return r.text
                except Exception as ex:
                    logger.warning("Recomp catalog fetch %s attempt %d failed: %s", url, attempt + 1, ex)
            logger.warning("All attempts failed for Recomp catalog URL: %s", url)
        return None

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Recomp Computers...")
        items: List[LaptopItem] = []
        seen_urls: Set[str] = set()

        # 1. Primary: WooCommerce Store API
        for page in range(1, 3):
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
                logger.warning("Error fetching Recomp API page %d: %s", page, e)
                break

        if items:
            logger.info("Recomp: successfully scraped %d in-stock laptops via Store API", len(items))
            return items

        # 2. Fallback: HTML Catalog
        logger.info("Recomp: Store API returned 0 items; falling back to HTML catalog scraping...")
        try:
            catalog_html = self._fetch_catalog()
            if not catalog_html:
                logger.error("Recomp: could not fetch any catalog URL — giving up.")
                report_store_block(
                    self.STORE_NAME, "catalog unreachable from this IP (every URL attempt failed)"
                )
                return items

            links = self._extract_product_links(catalog_html)

            valid_links = []
            for link, text in links:
                link = link.strip()
                if link in seen_urls:
                    continue
                title = HardwareClassifier.clean_text(text)
                if len(title) < 4:
                    slug = link.rstrip('/').split('/')[-1]
                    title = HardwareClassifier.clean_text(urllib.parse.unquote(slug).replace('-', ' '))
                if not HardwareClassifier.is_laptop(title) or not is_laptop_title(title):
                    continue
                valid_links.append((link, title))

            logger.info("Recomp: found %d product links to fetch in HTML fallback.", len(valid_links))

            def fetch_recomp_item(item_tuple):
                link, title = item_tuple
                for attempt in range(2):
                    try:
                        res = self._get(link, timeout=20)
                        if res and res.status_code == 200:
                            # Skip out-of-stock items in fallback
                            if any(k in res.text for k in ["class=\"out-of-stock\"", "class='out-of-stock'", "חסר במלאי", "אזל מהמלאי"]):
                                return link, title, None, "", ""
                            p = self._parse_recomp_price(res.text)
                            img = self._parse_recomp_image(res.text)
                            desc = self._parse_recomp_desc(res.text)
                            return link, title, p, img, desc
                    except Exception as ex:
                        logger.debug("Recomp item fetch attempt %d failed for %s: %s", attempt + 1, link, ex)
                return link, title, None, "", ""

            with ThreadPoolExecutor(max_workers=6) as executor:
                fetched_results = list(executor.map(fetch_recomp_item, valid_links))

            for link, title, price, img, desc in fetched_results:
                if price is None or price < 601:
                    continue
                analysis = f"{title} {desc}".strip()

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
                if item.url not in seen_urls:
                    seen_urls.add(item.url)
                    items.append(item)
        except Exception as e:
            logger.error("Error scraping Recomp HTML fallback: %s", e)
        return items
