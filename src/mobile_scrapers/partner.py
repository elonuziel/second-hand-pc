"""Partner Plus Renewed scraper."""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Any

import requests
from mobile_classification import MobileClassifier
from mobile_domain import MobileItem

logger = logging.getLogger("PartnerPlusScraper")


class PartnerPlusScraper:
    STORE_NAME = "Partner Plus"
    CATALOG_URL = "https://partnerplus.partner.co.il/renewed"
    _LD_JSON_PATTERN = re.compile(r"<script[^>]*type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>", re.DOTALL)

    def __init__(self, session: Optional[Any] = None):
        self.session = session or requests.Session()

    def scrape(self) -> List[MobileItem]:
        logger.info("Scraping Partner Plus Renewed...")
        items: List[MobileItem] = []
        try:
            r = self.session.get(self.CATALOG_URL, timeout=12)
            if r.status_code == 200:
                items_element = re.search(r'\"itemListElement\":(\[.*?\])', r.text)
                if not items_element:
                    return items
                parsed_items = json.loads(items_element.group(1))

                def fetch_partner_item(prod_entry):
                    title = prod_entry.get('name', '')
                    url = prod_entry.get('url', '')
                    if not MobileClassifier.is_mobile_device(title):
                        return None
                    try:
                        r_p = self.session.get(url, timeout=6)
                        p_json = self._LD_JSON_PATTERN.search(r_p.text)
                        price = 0
                        if p_json:
                            data = json.loads(p_json.group(1))
                            if isinstance(data, list):
                                for d in data:
                                    if d.get('@type') == 'Product':
                                        price = int(d.get('offers', {}).get('price', 0))
                            elif isinstance(data, dict) and data.get('@type') == 'Product':
                                price = int(data.get('offers', {}).get('price', 0))
                        if price > 0:
                            return MobileClassifier.build_item(
                                store=self.STORE_NAME,
                                title=title,
                                price_ils=price,
                                url=url,
                                warranty_months=12
                            )
                    except Exception:
                        pass
                    return None

                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [executor.submit(fetch_partner_item, entry) for entry in parsed_items]
                    for f in as_completed(futures):
                        res = f.result()
                        if res:
                            items.append(res)
        except Exception as e:
            logger.error(f"Error scraping Partner Plus: {e}")
        return items

