"""BuyMobile (WooCommerce display/renewed) scraper."""
from __future__ import annotations

import html
import json
import logging
from typing import List, Optional, Any

import requests
from mobile_classification import MobileClassifier
from mobile_domain import MobileItem

logger = logging.getLogger("BuyMobileScraper")

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


class BuyMobileScraper:
    STORE_NAME = "BuyMobile"
    CATALOG_URL = "https://buy-mobile.co.il/wp-json/wc/store/v1/products?category=19&per_page=50"

    def __init__(self, session: Optional[Any] = None):
        self.session = session or create_resilient_session()

    def scrape(self) -> List[MobileItem]:
        logger.info("Scraping BuyMobile (תצוגה / מחודש)...")
        items: List[MobileItem] = []
        try:
            resp = None
            if self.session:
                try:
                    resp = self.session.get(self.CATALOG_URL, timeout=15)
                except Exception as ex:
                    logger.debug("BuyMobile session.get failed: %s", ex)

            if not resp or getattr(resp, "status_code", 0) != 200:
                try:
                    status, text = fetch_resilient_url(self.CATALOG_URL, timeout=15)
                    if status == 200 and text:
                        class _MockResp:
                            def __init__(self, t):
                                self.text = t
                                self.status_code = 200
                            def json(self):
                                return json.loads(self.text)
                        resp = _MockResp(text)
                except Exception as ex:
                    logger.debug("BuyMobile resilient fetch failed: %s", ex)

            if resp and getattr(resp, "status_code", 0) == 200:
                data = resp.json()
                for p in data:
                    if not isinstance(p, dict):
                        continue
                    name = html.unescape(p.get("name", "")).strip()
                    if not MobileClassifier.is_mobile_device(name):
                        continue
                    if not p.get("is_in_stock", True):
                        continue

                    prices = p.get("prices", {})
                    minor = prices.get("currency_minor_unit", 2)
                    raw_price = prices.get("price") or prices.get("regular_price")
                    try:
                        price_val = int(round(float(raw_price) / (10 ** minor)))
                    except Exception:
                        continue
                    if price_val < 200:
                        continue

                    # Sale price check
                    sale_price_raw = prices.get("sale_price")
                    deal_price = price_val
                    deal_label = f"{price_val:,} ₪"
                    if sale_price_raw and str(sale_price_raw).isdigit():
                        try:
                            sale_val = int(round(float(sale_price_raw) / (10 ** minor)))
                            if 200 <= sale_val < price_val:
                                deal_price = sale_val
                                deal_label = f"{sale_val:,} ₪ (Sale)"
                        except Exception:
                            pass

                    url = p.get("permalink", "")
                    images = p.get("images", [])
                    img_url = images[0].get("src", "") if images else ""

                    items.append(MobileClassifier.build_item(
                        store=self.STORE_NAME,
                        title=name,
                        price_ils=price_val,
                        url=url,
                        deal_price_ils=deal_price,
                        deal_label=deal_label,
                        image_url=img_url,
                        warranty_months=12
                    ))
        except Exception as e:
            logger.error(f"Error scraping BuyMobile: {e}")

        logger.info("BuyMobile: scraped %d mobile items.", len(items))
        return items

