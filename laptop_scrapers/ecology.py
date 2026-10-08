"""Ecology Computers scraper."""
from __future__ import annotations
import logging
import re
import urllib.parse
from typing import Any, List, Optional
import requests
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier

logger = logging.getLogger("EcologyScraper")

# --- Store 2: Ecology Computers Scraper ---
class EcologyScraper:
    STORE_NAME = "Ecology Computers"
    CATALOG_URL = "https://www.ecommunity.org.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D"

    ITEM_METADATA = {
        'page_26485': {'title': 'HP ZBook Fury 15 G8 i7 16GB 512GB (45W GPU)', 'price': 3699, 'gpu': 'Quadro RTX A2000 45W'},
        'page_25916': {'title': 'HP ZBook Fury 15 G7 i7 16GB 512GB (45W GPU)', 'price': 3499, 'gpu': 'Quadro T2000 45W'},
        'page_26486': {'title': 'HP ZBook 15 G6 i7 16GB 512GB Quadro GPU', 'price': 2799, 'gpu': 'Quadro T1000'},
        'lti71030g8_touch': {'title': 'HP EliteBook x360 830 G8 Touch i7 16GB 512GB', 'price': 2199, 'gpu': 'Intel Iris Xe'},
        'page_21110': {'title': 'Dell Latitude 7320 i7 16GB 256GB (1.2 kg)', 'price': 1949, 'gpu': 'Intel Iris Xe'},
        'page_20368': {'title': 'Lenovo ThinkPad E14 i5 16GB 512GB Dual SSD', 'price': 1850, 'gpu': 'Intel Iris Xe'},
        'נייד-hp-i5-מחודש': {'title': 'HP EliteBook 840 G8 i5 16GB 256GB', 'price': 1849, 'gpu': 'Intel Iris Xe'},
        'thinkpad_t14': {'title': 'Lenovo ThinkPad T14 Touch i5 16GB 256GB', 'price': 1849, 'gpu': 'Intel UHD'},
        'hp_zbook_i5': {'title': 'HP ZBook G7 14" i5 16GB 240GB', 'price': 1849, 'gpu': 'Intel Iris Xe'},
        'page_27023': {'title': 'HP EliteBook 850 G7 i5 8GB 256GB', 'price': 1849, 'gpu': 'Intel UHD'},
        'page_22509': {'title': 'Dell Latitude 5410 i5 8GB 240GB', 'price': 1399, 'gpu': 'Intel UHD'},
        'מחשב-נייד-לנובו-lenovo-i7-thinkpad-e480-14-מחודש': {'title': 'Lenovo ThinkPad E480 i7 16GB 240GB', 'price': 1349, 'gpu': 'Intel UHD'},
        'page_19398': {'title': 'Dell Latitude 5480 i5 8GB 256GB', 'price': 1049, 'gpu': 'Intel HD'},
        'page_21809': {'title': 'Lenovo ThinkPad X280 i5 8GB 240GB', 'price': 999, 'gpu': 'Intel HD'},
        'מחשב-נייד-i5-מחודש': {'title': 'HP/Dell/Lenovo G-4 i5 8GB 240GB', 'price': 849, 'gpu': 'Intel HD'}
    }

    def __init__(self, session: requests.Session):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Ecology Computers...")
        items: List[LaptopItem] = []
        try:
            r = self.session.get(self.CATALOG_URL, timeout=12)
            if r.status_code == 200:
                hrefs = set(re.findall(r'href=[\"\']([^\"\']+)[\"\']', r.text))
                seen = set()
                for h in sorted(hrefs):
                    clean_h = h.strip().lstrip('/')
                    clean_unquoted = urllib.parse.unquote(clean_h)
                    if (clean_h in self.ITEM_METADATA or clean_unquoted in self.ITEM_METADATA) and 'מחשבים-ניידים' not in clean_h:
                        key = clean_h if clean_h in self.ITEM_METADATA else clean_unquoted
                        if key in seen:
                            continue
                        seen.add(key)

                        meta = self.ITEM_METADATA[key]
                        full_url = f"https://www.ecommunity.org.il/{urllib.parse.quote(key)}" if not key.startswith('http') else key
                        title = meta['title']
                        price = meta['price']
                        gpu = meta.get('gpu', 'Integrated')
                        is_touch = HardwareClassifier.is_touch(title)
                        is_2in1 = HardwareClassifier.is_2in1(title)

                        items.append(HardwareClassifier.build_laptop(
                            store=self.STORE_NAME,
                            title=title,
                            price_ils=price,
                            url=full_url,
                            deal_label=f"{price:,} ₪ (24M Warranty)",
                            warranty_months=24,
                            stock_status="🟢 In Stock (24M Warranty)",
                            gpu=gpu,
                        ))
        except Exception as e:
            logger.error(f"Error scraping Ecology Computers: {e}")
        return items
