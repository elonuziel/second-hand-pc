"""iStore CPO (Apple) scraper."""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Any

import requests
from mobile_classification import MobileClassifier
from mobile_domain import MobileItem

logger = logging.getLogger("IStoreMobileScraper")

try:
    from http_session import create_resilient_session, fetch_resilient_url
except ImportError:
    def create_resilient_session(**_) -> requests.Session:
        return requests.Session()

    def fetch_resilient_url(url: str, timeout: int = 25, **_) -> tuple:
        try:
            r = requests.get(url, timeout=timeout, verify=False)
            return r.status_code, r.text
        except Exception:
            return 0, ""


class IStoreMobileScraper:
    STORE_NAME = "iStore CPO"
    CATALOG_URLS = [
        "https://www.istoreil.co.il/refurbish/iphone",
        "https://www.istoreil.co.il/refurbish/ipad",
    ]

    def __init__(self, session: Optional[Any] = None):
        self.session = session or create_resilient_session()

    def _fetch(self, url: str, timeout: int = 20) -> str:
        if self.session:
            try:
                r = self.session.get(url, timeout=timeout)
                if r.status_code == 200 and r.text:
                    return r.text
            except Exception as ex:
                logger.debug("Session.get failed for %s: %s", url, ex)
        try:
            status, text = fetch_resilient_url(url, timeout=timeout)
            if status == 200 and text:
                return text
        except Exception as ex:
            logger.debug("Resilient fetch failed for %s: %s", url, ex)
        return ""

    def scrape(self) -> List[MobileItem]:
        logger.info("Scraping iStore CPO (Apple)...")
        items: List[MobileItem] = []
        seen = set()

        for cat_url in self.CATALOG_URLS:
            try:
                html_text = self._fetch(cat_url)
                if not html_text:
                    continue

                cat_prods = html_text[html_text.find('class="category-products"'):] if 'class="category-products"' in html_text else ""
                raw_blocks = [it for it in cat_prods.split('product-description') if 'category-main-price' in it]

                for b in raw_blocks:
                    link_m = re.search(r'href=[\"\'](https://www.istoreil.co.il/[^\"\']+)[\"\']', b)
                    price_m = re.search(r'category-main-price[\"\'][^>]*>\s*([0-9,\.]+)\s*₪', b)
                    if not link_m or not price_m:
                        continue
                    p_url = link_m.group(1).strip()
                    if p_url in seen:
                        continue
                    seen.add(p_url)

                    try:
                        price = int(round(float(price_m.group(1).replace(',', ''))))
                    except Exception:
                        continue
                    if price <= 0:
                        continue

                    slug = p_url.rstrip('/').split('/')[-1]
                    raw_title = slug.replace('-', ' ').title()
                    raw_title = re.sub(r'^(Refurbished|Ref|Demo)\s+', '', raw_title, flags=re.IGNORECASE)
                    raw_title = re.sub(r'\s+(Demo|Refurbished)$', '', raw_title, flags=re.IGNORECASE)

                    img_m = re.search(r'<img[^>]*src=[\"\']([^\"\']+)[\"\']', b)
                    img_url = img_m.group(1) if img_m else ""

                    items.append(MobileClassifier.build_item(
                        store=self.STORE_NAME,
                        title=raw_title,
                        price_ils=price,
                        url=p_url,
                        image_url=img_url,
                        warranty_months=12
                    ))
            except Exception as e:
                logger.error("Error scraping iStore from %s: %s", cat_url, e)

        logger.info("iStore CPO: scraped %d mobile items.", len(items))
        return items

