"""LastPrice Mobile refurbished scraper."""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Any

import requests
from mobile_classification import MobileClassifier
from mobile_domain import MobileItem

logger = logging.getLogger("LastPriceMobileScraper")

try:
    from http_session import fetch_resilient_url
except ImportError:
    def fetch_resilient_url(url: str, timeout: int = 25, **_) -> tuple:
        try:
            r = requests.get(url, timeout=timeout, verify=False)
            return r.status_code, r.text
        except Exception:
            return 0, ""


class LastPriceMobileScraper:
    STORE_NAME = "LastPrice"
    # Try the filtered URL first, then without filters, then the broader category
    CATALOG_URLS = [
        "https://www.lastprice.co.il/c/531/%D7%9E%D7%97%D7%A9%D7%95%D7%91-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%98%D7%9C%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D?filter1=20710526,20670485",
        "https://www.lastprice.co.il/c/531/%D7%9E%D7%97%D7%A9%D7%95%D7%91-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%98%D7%9C%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D",
        "https://www.lastprice.co.il/c/531/%D7%9E%D7%97%D7%A9%D7%95%D7%91-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%A1%D7%9C%D7%95%D7%9C%D7%A8",
    ]

    def __init__(self, session: Optional[Any] = None):
        self.session = session or requests.Session()

    def _fetch(self, url: str, timeout: int = 20) -> str:
        """Try session.get() first; if it returns non-200 or fails, try resilient engine."""
        try:
            r = self.session.get(url, timeout=timeout)
            if r.status_code == 200 and r.text:
                return r.text
            logger.debug("Session returned %s for %s, trying resilient engine.", r.status_code, url)
        except Exception as ex:
            logger.debug("Session.get failed for %s: %s", url, ex)
        # Fallback: pycurl → curl_cffi → requests engine chain
        try:
            status, text = fetch_resilient_url(url, timeout=timeout)
            if status == 200 and text:
                return text
        except Exception as ex:
            logger.debug("Resilient fetch also failed for %s: %s", url, ex)
        return ""

    def scrape(self) -> List[MobileItem]:
        logger.info("Scraping LastPrice Mobile...")
        items: List[MobileItem] = []
        seen: set = set()

        for catalog_url in self.CATALOG_URLS:
            try:
                html_text = self._fetch(catalog_url)
                if not html_text:
                    logger.warning("LastPrice: empty response for %s", catalog_url)
                    continue

                blocks = re.findall(
                    r'<div[^>]*class=[\"\'][^\"\']*infinite-item[^\"\']*[\"\'][^>]*>(.*?)(?=<div[^>]*class=[\"\'][^\"\']*infinite-item|$)',
                    html_text,
                    re.DOTALL
                )

                if not blocks:
                    logger.warning("LastPrice: no infinite-item blocks found in %s", catalog_url)
                    continue

                logger.info("LastPrice: found %d blocks in %s", len(blocks), catalog_url)

                for b in blocks:
                    title_m = re.findall(r'<h3[^>]*>(.*?)</h3>', b)
                    if not title_m:
                        continue
                    raw_title = title_m[0].strip()
                    if not MobileClassifier.is_mobile_device(raw_title):
                        continue

                    link_m = re.findall(r'href=["\']([^"\']*lastprice\.co\.il/p/[^"\']+)["\']', b)
                    if not link_m:
                        continue
                    full_link = link_m[0].strip()
                    if full_link in seen:
                        continue
                    seen.add(full_link)

                    price_m = re.findall(r'₪([0-9,]+)', b)
                    price = int(price_m[0].replace(',', '')) if price_m else 0
                    if price <= 0:
                        continue

                    img_m = re.findall(r'<img[^>]*class=[\"\'][^\"\']*prodimg[^\"\']*[\"\'][^>]*src=[\"\']([^\"\']+)[\"\']', b)
                    img_url = ''
                    if img_m:
                        src = img_m[0].strip()
                        img_url = src if src.startswith('http') else f"https://www.lastprice.co.il{src}"

                    items.append(MobileClassifier.build_item(
                        store=self.STORE_NAME,
                        title=raw_title,
                        price_ils=price,
                        url=full_link,
                        image_url=img_url,
                        warranty_months=12
                    ))

                if items:
                    logger.info("LastPrice: scraped %d mobile items.", len(items))
                    return items  # success — no need to try more URLs

            except Exception as e:
                logger.error("Error scraping LastPrice from %s: %s", catalog_url, e)

        if not items:
            logger.warning("LastPrice: all catalog URLs exhausted, returning 0 items.")
        return items
