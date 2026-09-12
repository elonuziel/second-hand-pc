"""LastPrice scraper."""
from __future__ import annotations
import html
import logging
import re
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier

logger = logging.getLogger("LastPriceScraper")

# --- Store 10: LastPrice Laptops Scraper ---
class LastPriceScraper:
    STORE_NAME = "LastPrice"
    CATALOG_URL = "https://www.lastprice.co.il/c/85/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%95%D7%92%D7%99%D7%99%D7%9E%D7%99%D7%A0%D7%92/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%95%D7%A2%D7%95%D7%93%D7%A4%D7%99-%D7%9E%D7%9C%D7%90%D7%99"

    def __init__(self, session: Any = None):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping LastPrice Laptops...")
        items: List[LaptopItem] = []
        seen = set()
        try:
            status, text = fetch_resilient_url(self.CATALOG_URL)
            if status != 200 or not text:
                logger.warning(f"LastPrice returned HTTP {status}")
                return items

            blocks = re.findall(
                r'<div[^>]*class=[\"\'][^\"\']*infinite-item[^\"\']*[\"\'][^>]*>(.*?)(?=<div[^>]*class=[\"\'][^\"\']*infinite-item|$)',
                text,
                re.DOTALL
            )

            for b in blocks:
                title_m = re.findall(r'<h3[^>]*>(.*?)</h3>', b)
                price_m = re.findall(r'₪([0-9,]+)', b)
                link_m = re.findall(r'href=[\"\'](https://www.lastprice.co.il/p/[^\"\']+)[\"\']', b)
                img_m = re.findall(r'<img[^>]*class=[\"\'][^\"\']*prodimg[^\"\']*[\"\'][^>]*src=[\"\']([^\"\']+)[\"\']', b)
                if not (title_m and price_m and link_m):
                    continue

                raw_title = html.unescape(title_m[0].strip())
                full_link = link_m[0].strip()
                if full_link in seen:
                    continue
                seen.add(full_link)

                price = int(price_m[0].replace(',', ''))
                if price <= 0:
                    continue

                img_url = ''
                if img_m:
                    src = img_m[0].strip()
                    img_url = src if src.startswith('http') else f"https://www.lastprice.co.il{src}"

                warranty = 12
                if 'שנתיים' in raw_title or '36 חודשים' in raw_title or '3 שנים' in raw_title:
                    warranty = 24 if 'שנתיים' in raw_title else 36

                items.append(HardwareClassifier.build_laptop(
                    store=self.STORE_NAME,
                    title=raw_title,
                    price_ils=price,
                    url=full_link,
                    image_url=img_url,
                    warranty_months=warranty,
                    stock_status="🟢 In Stock"
                ))
        except Exception as e:
            logger.error(f"Error scraping LastPrice Laptops: {e}")
        return items
