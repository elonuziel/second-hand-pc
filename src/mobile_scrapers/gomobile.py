"""GoMobile Outlet scraper."""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Any

import requests
from mobile_classification import MobileClassifier
from mobile_domain import MobileItem

logger = logging.getLogger("GoMobileScraper")


class GoMobileScraper:
    STORE_NAME = "GoMobile Outlet"
    CATALOG_URL = "https://www.gomobile.co.il/category/%D7%A1%D7%9E%D7%90%D7%A8%D7%98%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%AA%D7%A6%D7%95%D7%92%D7%94/"

    def __init__(self, session: Optional[Any] = None):
        self.session = session or requests.Session()

    def scrape(self) -> List[MobileItem]:
        logger.info("Scraping GoMobile Outlet...")
        items: List[MobileItem] = []
        try:
            r = self.session.get(self.CATALOG_URL, timeout=12)
            if r.status_code == 200:
                cards = re.findall(r'<a[^>]+href=[\"\']([^\"\']+)[\"\'][^>]*class=[\"\'][^\"\']*category-product[^\"\']*[\"\'][^>]*>(.*?)</a>', r.text, re.DOTALL)
                seen = set()
                for link, inner in cards:
                    full_url = link if link.startswith('http') else f"https://www.gomobile.co.il{link}"
                    if full_url in seen:
                        continue
                    seen.add(full_url)

                    title_m = re.findall(r'class=[\"\'][^\"\']*min-product-title[^\"\']*[\"\'][^>]*>(.*?)</h2>|title=[\"\']([^\"\']+)[\"\']|alt=[\"\']([^\"\']+)[\"\']', inner, re.DOTALL)
                    raw_title = ""
                    if title_m:
                        raw_title = title_m[0][0] or title_m[0][1] or title_m[0][2]
                    if not MobileClassifier.is_mobile_device(raw_title):
                        continue

                    valid_prices = []
                    for p_tuple in re.findall(r'class=[\"\']price-normal[\"\'][^>]*>(\d[\d,]*)</span>|(\d[\d,]*)\s*₪', inner):
                        val_str = p_tuple[0] or p_tuple[1]
                        if val_str:
                            valid_prices.append(int(val_str.replace(',', '')))
                    price = valid_prices[0] if valid_prices else 0
                    if price <= 0:
                        continue

                    warranty = 3
                    if '12' in inner or 'שנה' in inner or 'חודשים' in inner:
                        if '12 חודשי' in inner or 'שנה' in inner:
                            warranty = 12

                    items.append(MobileClassifier.build_item(
                        store=self.STORE_NAME,
                        title=raw_title,
                        price_ils=price,
                        url=full_url,
                        warranty_months=warranty
                    ))
        except Exception as e:
            logger.error(f"Error scraping GoMobile: {e}")
        return items
