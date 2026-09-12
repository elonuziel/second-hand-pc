"""Olam HaKolnoa (CWC) scraper."""
from __future__ import annotations
import html
import json
import logging
import re
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title

logger = logging.getLogger("CWCScraper")

# --- Store 5: Olam HaKolnoa (CWC) Scraper ---
class CWCScraper:
    STORE_NAME = "Olam HaKolnoa"
    API_URL = "https://www.cwc.co.il/wp-json/wc/store/v1/products?category=817&per_page=100"
    CATEGORY_URLS = [
        "https://www.cwc.co.il/product-category/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%95%d7%a6%d7%99%d7%95%d7%93-%d7%a0%d7%9c%d7%95%d7%95%d7%94-1/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%d7%95%d7%93%d7%a9%d7%99%d7%9d/",
        "https://www.cwc.co.il/product-category/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%95%d7%a6%d7%99%d7%95%d7%93-%d7%a0%d7%9c%d7%95%d7%95%d7%94-1/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%d7%95%d7%93%d7%a9%d7%99%d7%9d/page/2/",
    ]
    MOBILE_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    def __init__(self, session: Any = None):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Olam HaKolnoa (CWC)...")
        items: List[LaptopItem] = []

        # 1. Try WP REST API first
        try:
            status, text = fetch_resilient_url(
                self.API_URL,
                user_agent=self.MOBILE_UA,
                headers={"Accept": "application/json"}
            )
            if status == 200 and text and text.strip().startswith("["):
                data = json.loads(text)
                if isinstance(data, list) and len(data) > 0:
                    for p in data:
                        name = html.unescape(p.get("name", "")).strip()
                        if not name or not is_laptop_title(name):
                            continue

                        prices = p.get("prices", {})
                        raw_price = prices.get("price") or prices.get("regular_price")
                        price_val = 0
                        if raw_price:
                            try:
                                minor = prices.get("currency_minor_unit", 2)
                                price_val = int(round(float(raw_price) / (10 ** minor))) if str(raw_price).isdigit() else int(round(float(raw_price)))
                            except Exception:
                                pass
                        if price_val <= 0:
                            continue

                        url = p.get("permalink", "")
                        images = p.get("images", [])
                        img_url = images[0].get("src", "") if images else ""

                        desc = p.get("short_description", "") + " " + p.get("description", "")
                        clean_desc = html.unescape(re.sub(r'<[^>]+>', ' ', desc)).strip()
                        analysis = f"{name} {clean_desc}".strip()

                        warranty = 12
                        if any(k in analysis for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש"]):
                            warranty = 36
                        elif any(k in analysis for k in ["שנתיים אחריות", "שנתיים", "24 חודש"]):
                            warranty = 24

                        items.append(HardwareClassifier.build_laptop(
                            store=self.STORE_NAME,
                            title=name,
                            price_ils=price_val,
                            url=url,
                            analysis_text=analysis,
                            warranty_months=warranty,
                            stock_status="🟢 In Stock",
                            image_url=img_url
                        ))
                    if items:
                        return items
        except Exception as e:
            logger.warning(f"CWC REST API fetch failed: {e}")

        # 2. Resilient fallback to HTML category pages (when API is blocked or 403)
        logger.info("Falling back to CWC HTML category pages...")
        seen_urls = set()
        for cat_url in self.CATEGORY_URLS:
            try:
                status, page_text = fetch_resilient_url(cat_url, user_agent=self.MOBILE_UA)
                if status != 200 or not page_text:
                    continue

                matches = list(re.finditer(
                    r'<div[^>]*class=[\"\'][^\"\']*woocommerce-loop-product__title[^\"\']*[\"\'][^>]*>\s*<a[^>]*href=[\"\']([^\"\']+)[\"\'][^>]*>([\s\S]*?)</a>([\s\S]*?)(?=<div[^>]*class=[\"\'][^\"\']*woocommerce-loop-product__title|\Z)',
                    page_text
                ))
                for m in matches:
                    link = m.group(1)
                    if link in seen_urls:
                        continue
                    raw_title = html.unescape(re.sub(r'<[^>]+>', '', m.group(2))).strip()
                    if not is_laptop_title(raw_title):
                        continue

                    after_html = m.group(3)
                    price_m = re.search(r'class=[\"\']price[\"\']>[\s\S]*?<bdi>([0-9,]+)', after_html)
                    if not price_m:
                        price_m = re.search(r'<bdi>([0-9,]+)', after_html)
                    price_val = int(price_m.group(1).replace(',', '')) if price_m else 0
                    if price_val <= 0:
                        continue

                    seen_urls.add(link)
                    img_m = re.search(r'<img[^>]*src=[\"\']([^\"\']+)[\"\']', after_html)
                    img_url = img_m.group(1) if img_m else ""

                    clean_card = html.unescape(re.sub(r'<[^>]+>', ' ', after_html)).strip()
                    analysis = f"{raw_title} {clean_card}".strip()

                    warranty = 36 if any(k in clean_card for k in ["3 שנים", "36 חודש", "שלוש שנים", "אחריות מורחבת 3"]) else 12

                    items.append(HardwareClassifier.build_laptop(
                        store=self.STORE_NAME,
                        title=raw_title,
                        price_ils=price_val,
                        url=link,
                        analysis_text=analysis,
                        warranty_months=warranty,
                        stock_status="🟢 In Stock",
                        image_url=img_url
                    ))
            except Exception as e:
                logger.error(f"Error scraping CWC HTML category {cat_url}: {e}")

        return items
