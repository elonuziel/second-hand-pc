#!/usr/bin/env python3
"""
Refurbished Phones & Tablets Scraper & Auditor
================================================
Scraper and hardware spec auditor for Israeli refurbished mobile stores:
1. IT Outlet Phones & Tablets (itoutlet.co.il)
2. GoMobile Outlet (gomobile.co.il)
3. Partner Plus Renewed (partnerplus.partner.co.il)

Features:
- Dynamic extraction of mobile phone & tablet models, RAM, storage, prices, and brands.
- Accessory filter guard (filters out covers, cases, screen protectors, chargers, cables, etc.).
- Dual JSON & CSV export + Markdown catalog report generation (`full_mobile_catalog.md`).
"""

from __future__ import annotations

import os
import re
import csv
import json
import logging
import argparse
import datetime
import urllib.parse
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
FULL_MOBILE_CATALOG_MD_PATH = os.path.join(WORKSPACE_DIR, "full_mobile_catalog.md")
JSON_PATH = os.path.join(WORKSPACE_DIR, "scraped_mobile.json")
CSV_PATH = os.path.join(WORKSPACE_DIR, "scraped_mobile.csv")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("MobileScraper")

try:
    from http_session import create_resilient_session, fetch_resilient_url, DEFAULT_HEADERS
except ImportError:
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }

    def create_resilient_session(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        session.verify = False
        retry_strategy = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=15, pool_maxsize=30)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def fetch_resilient_url(url: str, timeout: int = 25, **_) -> tuple:
        """Fallback when http_session is unavailable — plain requests."""
        try:
            r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, verify=False)
            return r.status_code, r.text
        except Exception:
            return 0, ""



@dataclass
class MobileItem:
    store: str
    title: str
    brand: str
    model: str
    device_type: str  # 'phone' or 'tablet'
    ram_gb: int
    storage_gb: int
    price_ils: int
    deal_price_ils: int
    deal_label: str
    warranty_months: int
    stock_status: str
    url: str
    screen_size_in: float = 6.1
    image_url: str = ""
    confidence_level: str = "verified"
    scraped_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MobileClassifier:
    ACCESSORY_KEYWORDS = (
        'כיסוי', 'מגן', 'מטען', 'סוללה', 'זכוכית', 'כבל', 'נרתיק', 'מעמד', 'תושבת',
        'case', 'cover', 'charger', 'cable', 'protector', 'holder', 'strap', 'רצועה',
        'אוזניות', 'headset', 'airpods', 'buds'
    )

    _RAM_PATTERN = re.compile(r'(?:^|[^\d])(3|4|6|8|12|16)\s*(?:gb|ג"ב|גיגה)?\s*(?:ram|זכרון|זיכרון)(?:[^\d]|$)', re.IGNORECASE)
    _STORAGE_PATTERN = re.compile(r'(?:^|[^\d])(32|64|128|256|512|1000|1tb|1000gb|1 טרה)(?:gb|g|ג"ב|גיגה)?(?:[^\d]|$)', re.IGNORECASE)
    _SCREEN_PATTERN = re.compile(r'(?:^|[^\d])(5\.\d|6\.\d|7\.\d|8\.\d|10\.\d|11\.\d|12\.\d|13\.\d)\s*(?:"|\'|inch|אינץ)?(?:[^\d]|$)', re.IGNORECASE)

    @classmethod
    def is_mobile_device(cls, title: str) -> bool:
        t = title.lower()
        if any(k in t for k in cls.ACCESSORY_KEYWORDS):
            return False
        return any(k in t for k in [
            'iphone', 'galaxy', 'samsung', 'xiaomi', 'ipad', 'tab', 'pixel', 'redmi',
            'poco', 'motorola', 'realme', 'טלפון', 'סלולרי', 'סמארטפון', 'טאבלט', 'סלולר',
            'oneplus', 'asus', 'oppo', 'vivo', 'z flip', 'z fold', 'razr'
        ])

    @classmethod
    def detect_brand(cls, title: str) -> str:
        t = title.lower()
        if 'iphone' in t or 'ipad' in t or 'apple' in t: return "Apple"
        if 'galaxy' in t or 'samsung' in t or 'סמסונג' in t: return "Samsung"
        if 'xiaomi' in t or 'redmi' in t or 'poco' in t or 'שיאומי' in t: return "Xiaomi"
        if 'motorola' in t or 'razr' in t or 'מוטורולה' in t: return "Motorola"
        if 'pixel' in t or 'google' in t: return "Google"
        if 'realme' in t: return "Realme"
        if 'oneplus' in t: return "OnePlus"
        return "Mobile"

    @classmethod
    def detect_device_type(cls, title: str) -> str:
        t = title.lower()
        if any(k in t for k in ['ipad', 'tab', 'טאבלט', 'tablet']):
            return "tablet"
        return "phone"

    @classmethod
    def detect_storage(cls, title: str) -> int:
        t = title.lower()
        if '1tb' in t or '1 טרה' in t or '1000gb' in t:
            return 1000
        matches = cls._STORAGE_PATTERN.findall(t)
        if matches:
            for val in matches:
                v_str = val.lower()
                if v_str == '1tb': return 1000
                try:
                    num = int(v_str)
                    if num in [32, 64, 128, 256, 512, 1000]:
                        return num
                except ValueError:
                    pass
        return 128

    @classmethod
    def detect_ram(cls, title: str, brand: str, device_type: str, storage_gb: int) -> int:
        t = title.lower()
        m = cls._RAM_PATTERN.search(t)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass

        # Smart defaults by model/storage
        if brand == "Apple":
            if 'pro max' in t or '15 pro' in t or '16 pro' in t: return 8
            if '14 pro' in t or '13 pro' in t or '12 pro' in t or '15' in t or '16' in t: return 6
            return 4
        if brand == "Samsung":
            if 'ultra' in t or 'fold' in t or 's24' in t or 's23' in t: return 12
            if 'plus' in t or 'fe' in t or 's22' in t or 's21' in t: return 8
            return 6
        if brand == "Xiaomi":
            if storage_gb >= 512: return 12
            if storage_gb >= 256: return 8
            return 6

        return 6 if device_type == "phone" else 4

    @classmethod
    def detect_screen_size(cls, title: str, device_type: str) -> float:
        t = title.lower()
        m = cls._SCREEN_PATTERN.search(t)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

        if device_type == "tablet":
            if '12.9' in t: return 12.9
            if '11' in t: return 11.0
            if '10.5' in t or '10.4' in t or '10.1' in t: return 10.4
            return 10.5

        if 'ultra' in t or 'pro max' in t or 'plus' in t: return 6.7
        if 'mini' in t or 'se' in t or 's9' in t: return 5.8
        return 6.1

    @classmethod
    def build_item(
        cls,
        store: str,
        title: str,
        price_ils: int,
        url: str,
        deal_price_ils: Optional[int] = None,
        deal_label: Optional[str] = None,
        warranty_months: int = 12,
        stock_status: str = "🟢 In Stock",
        image_url: str = "",
        scraped_at: Optional[str] = None,
    ) -> MobileItem:
        clean_title = ' '.join(re.sub(r'<[^>]+>', ' ', title).split())
        brand = cls.detect_brand(clean_title)
        device_type = cls.detect_device_type(clean_title)
        storage_gb = cls.detect_storage(clean_title)
        ram_gb = cls.detect_ram(clean_title, brand, device_type, storage_gb)
        screen_size = cls.detect_screen_size(clean_title, device_type)

        resolved_deal_price = deal_price_ils if deal_price_ils is not None else price_ils
        resolved_deal_label = deal_label or f"{resolved_deal_price:,} ₪"
        resolved_scraped_at = scraped_at or datetime.date.today().isoformat()

        return MobileItem(
            store=store,
            title=clean_title,
            brand=brand,
            model=clean_title,
            device_type=device_type,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            price_ils=price_ils,
            deal_price_ils=resolved_deal_price,
            deal_label=resolved_deal_label,
            warranty_months=warranty_months,
            stock_status=stock_status,
            url=url,
            screen_size_in=screen_size,
            image_url=image_url,
            scraped_at=resolved_scraped_at,
        )


class ITOutletMobileScraper:
    STORE_NAME = "IT Outlet"
    CATALOG_URL = "https://www.itoutlet.co.il/173553-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8-%D7%95%D7%98%D7%90%D7%91%D7%9C%D7%98%D7%99%D7%9D"

    def __init__(self, session: requests.Session):
        self.session = session

    def scrape(self) -> List[MobileItem]:
        logger.info("Scraping IT Outlet Mobile Devices...")
        items: List[MobileItem] = []
        seen = set()

        for page in range(1, 4):
            url = f"{self.CATALOG_URL}&page={page}"
            try:
                r = self.session.get(url, timeout=12)
                if r.status_code != 200:
                    break

                blocks = re.findall(r'<div[^>]*class=[\"\'][^\"\']*layout_list_item[^\"\']*[\"\'][^>]*>(.*?)(?=<div[^>]*class=[\"\'][^\"\']*layout_list_item|$)', r.text, re.DOTALL)
                for b in blocks:
                    title_m = re.findall(r'alt=[\"\']([^\"\']+)[\"\']|<h[234][^>]*>(.*?)</h[234]>', b)
                    raw_title = title_m[0][0] or title_m[0][1] if title_m else ""
                    if not MobileClassifier.is_mobile_device(raw_title):
                        continue

                    link_m = re.findall(r'href=[\"\']\s*(/items/\d+-[^\"\']+)[\"\']', b)
                    if not link_m:
                        continue
                    full_link = f"https://www.itoutlet.co.il{link_m[0].strip()}"
                    if full_link in seen:
                        continue
                    seen.add(full_link)

                    raw_prices = [int(p.replace(',', '')) for p in re.findall(r'(\d[\d,]*)\s*₪', b)]
                    valid_prices = [p for p in raw_prices if 150 <= p < 30000]
                    price = valid_prices[-1] if valid_prices else 0
                    if price <= 0:
                        continue

                    items.append(MobileClassifier.build_item(
                        store=self.STORE_NAME,
                        title=raw_title,
                        price_ils=price,
                        url=full_link,
                        warranty_months=12
                    ))
            except Exception as e:
                logger.error(f"Error scraping IT Outlet Mobile page {page}: {e}")

        return items


class GoMobileScraper:
    STORE_NAME = "GoMobile Outlet"
    CATALOG_URL = "https://www.gomobile.co.il/category/%D7%A1%D7%9E%D7%90%D7%A8%D7%98%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%AA%D7%A6%D7%95%D7%92%D7%94/"

    def __init__(self, session: requests.Session):
        self.session = session

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


class PartnerPlusScraper:
    STORE_NAME = "Partner Plus"
    CATALOG_URL = "https://partnerplus.partner.co.il/renewed"

    def __init__(self, session: requests.Session):
        self.session = session

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
                        p_json = re.search(r'<script[^>]*type=[\"\']application/ld\+json[\"\'][^>]*>(.*?)</script>', r_p.text, re.DOTALL)
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


class MobileReportGenerator:
    SCRAPER_STATUS_PATH = os.path.join(WORKSPACE_DIR, "scraper_status.json")

    @staticmethod
    def update_scraper_status(
        results: Dict[str, List[MobileItem]],
        fresh_counts: Dict[str, int],
        preserved_counts: Dict[str, int],
        filepath: str = SCRAPER_STATUS_PATH,
    ):
        status_data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    status_data = json.load(f)
            except Exception:
                pass

        today = datetime.date.today()
        store_map = {}
        total_items = 0
        for name, items in results.items():
            count = len(items)
            total_items += count
            fresh = fresh_counts.get(name, 0)
            scraped_at = items[0].scraped_at if items and hasattr(items[0], "scraped_at") and items[0].scraped_at else today.isoformat()
            days_ago = 0
            try:
                s_dt = datetime.date.fromisoformat(scraped_at)
                days_ago = (today - s_dt).days
            except Exception:
                pass

            display_name = getattr(items[0], "store", name) if items else name
            if fresh > 0:
                st = "fresh"
                note = "Successfully scraped fresh catalog"
            else:
                st = "preserved"
                note = "Preserved stock (anti-bot challenge or unreachable in CI)"

            store_map[name] = {
                "display_name": display_name,
                "count": count,
                "scraped_at": scraped_at,
                "status": st,
                "days_ago": days_ago,
                "note": note
            }

        status_data["last_updated"] = datetime.datetime.now().isoformat()
        status_data["mobile"] = {
            "total_items": total_items,
            "stores": store_map
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Updated scraper status JSON (mobile): {filepath}")
        except Exception as e:
            logger.warning(f"Could not write mobile scraper status: {e}")

    @staticmethod
    def export_json(data: Dict[str, List[MobileItem]], filepath: str):
        serializable = {k: [item.to_dict() for item in v] for k, v in data.items()}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        logger.info(f"Mobile JSON export saved to: {filepath}")

    @staticmethod
    def export_csv(all_items: List[MobileItem], filepath: str):
        if not all_items:
            return
        fieldnames = list(all_items[0].to_dict().keys())
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in all_items:
                writer.writerow(item.to_dict())
        logger.info(f"Mobile CSV export saved to: {filepath}")

    @staticmethod
    def update_summary_markdown(all_results: Dict[str, List[MobileItem]], filepath: str):
        now_str = datetime.datetime.now().strftime("%B %d, %Y (%H:%M)")
        all_devices: List[MobileItem] = []
        for v in all_results.values():
            all_devices.extend(v)

        md_parts = [
            "# 📱 Refurbished Phones & Tablets Market Research Guide\n",
            "**Stores Audited & Researched:**\n",
            "1. 🏬 **IT Outlet (איי טי אאוטלט):** [itoutlet.co.il/סלולר-וטאבלטים](https://www.itoutlet.co.il/173553-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8-%D7%95%D7%98%D7%90%D7%91%D7%9C%D7%98%D7%99%D7%9D)\n",
            "2. 🏬 **GoMobile Outlet (גו מוביל):** [gomobile.co.il/category/סמארטפונים-מחודשים-תצוגה](https://www.gomobile.co.il/category/%D7%A1%D7%9E%D7%90%D7%A8%D7%98%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%AA%D7%A6%D7%95%D7%92%D7%94/)\n",
            "3. 🏬 **Partner Plus Renewed (פרטנר פלוס):** [partnerplus.partner.co.il/renewed](https://partnerplus.partner.co.il/renewed)\n",
            "4. 🏬 **Dynamica Outlet (דינמיקה אאוטלט):** [dynamica.co.il/325880-Outlet](https://www.dynamica.co.il/325880-Outlet)\n",
            "5. 🏬 **VMobile (וי מובייל):** [vmobile.co.il/361324-מחודשים](https://www.vmobile.co.il/361324-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D)\n",
            "6. 🏬 **LastPrice (לאסטפרייס):** [lastprice.co.il/טלפונים-סלולרים-מחודשים](https://www.lastprice.co.il/c/531/%D7%9E%D7%97%D7%A9%D7%95%D7%91-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%98%D7%9C%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D?filter1=20710526,20670485)\n\n",
            f"*Last Automated Live Audit: {now_str}*\n\n",
            "---\n\n",
            "## 📱 Live Mobile Devices Catalog & Stock Audit\n\n",
            "| # | Model / Device Title | Brand | Type | RAM & Storage | Screen | Deal Price | Store | Warranty | Scraped | Direct Link |\n",
            "| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
        ]

        today = datetime.date.today()
        for i, dev in enumerate(all_devices, 1):
            type_badge = "📱 Phone" if dev.device_type == "phone" else "📱 Tablet"
            scraped_str = getattr(dev, 'scraped_at', '') or today.isoformat()
            stale_badge = ""
            try:
                s_dt = datetime.date.fromisoformat(scraped_str)
                days_old = (today - s_dt).days
                if days_old > 30:
                    stale_badge = f" ⚠️ *({days_old}d ago - Stale)*"
                elif days_old > 1:
                    stale_badge = f" *({days_old}d ago)*"
            except Exception:
                pass
            scraped_cell = f"{scraped_str}{stale_badge}"
            md_parts.append(
                f"| {i} | **{dev.title}** | {dev.brand} | {type_badge} | {dev.ram_gb}GB / {dev.storage_gb}GB | {dev.screen_size_in}\" | **{dev.deal_label}** | {dev.store} | {dev.warranty_months}M | {scraped_cell} | [View Product]({dev.url}) |\n"
            )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("".join(md_parts).strip() + "\n")
        logger.info(f"Mobile Markdown catalog saved to: {filepath}")


class DynamicaScraper:
    STORE_NAME = "Dynamica Outlet"
    CATALOG_URL = "https://www.dynamica.co.il/325880-Outlet"

    def __init__(self, session: requests.Session):
        self.session = session

    def scrape(self) -> List[MobileItem]:
        logger.info("Scraping Dynamica Outlet...")
        items: List[MobileItem] = []
        seen = set()

        for page in range(1, 4):
            url = f"{self.CATALOG_URL}?page={page}"
            try:
                r = self.session.get(url, timeout=12)
                if r.status_code != 200:
                    break

                blocks = re.findall(r'<div[^>]*class=[\"\'][^\"\']*layout_list_item[^\"\']*[\"\'][^>]*>(.*?)(?=<div[^>]*class=[\"\'][^\"\']*layout_list_item|$)', r.text, re.DOTALL)
                for b in blocks:
                    title_m = re.findall(r'alt=[\"\']([^\"\']+)[\"\']|<h[234][^>]*>(.*?)</h[234]>', b)
                    raw_title = title_m[0][0] or title_m[0][1] if title_m else ""
                    if not MobileClassifier.is_mobile_device(raw_title):
                        continue

                    link_m = re.findall(r'href=[\"\']\s*(/items/\d+-[^\"\']+)[\"\']', b)
                    if not link_m:
                        continue
                    full_link = f"https://www.dynamica.co.il{link_m[0].strip()}"
                    if full_link in seen:
                        continue
                    seen.add(full_link)

                    raw_prices = [int(p.replace(',', '')) for p in re.findall(r'(\d[\d,]*)\s*₪', b)]
                    valid_prices = [p for p in raw_prices if 150 <= p < 30000]
                    price = valid_prices[-1] if valid_prices else 0
                    if price <= 0:
                        continue

                    items.append(MobileClassifier.build_item(
                        store=self.STORE_NAME,
                        title=raw_title,
                        price_ils=price,
                        url=full_link,
                        warranty_months=12
                    ))
            except Exception as e:
                logger.error(f"Error scraping Dynamica Outlet page {page}: {e}")

        return items


class VMobileScraper:
    STORE_NAME = "VMobile"
    CATALOG_URL = "https://www.vmobile.co.il/361324-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D"

    def __init__(self, session: requests.Session):
        self.session = session

    def scrape(self) -> List[MobileItem]:
        logger.info("Scraping VMobile...")
        items: List[MobileItem] = []
        seen = set()

        for page in range(1, 4):
            url = f"{self.CATALOG_URL}?page={page}"
            try:
                r = self.session.get(url, timeout=12)
                if r.status_code != 200:
                    break

                blocks = re.findall(r'<div[^>]*class=[\"\'][^\"\']*layout_list_item[^\"\']*[\"\'][^>]*>(.*?)(?=<div[^>]*class=[\"\'][^\"\']*layout_list_item|$)', r.text, re.DOTALL)
                for b in blocks:
                    title_m = re.findall(r'alt=[\"\']([^\"\']+)[\"\']|<h[234][^>]*>(.*?)</h[234]>', b)
                    raw_title = title_m[0][0] or title_m[0][1] if title_m else ""
                    if not MobileClassifier.is_mobile_device(raw_title):
                        continue

                    link_m = re.findall(r'href=[\"\']\s*(/items/\d+-[^\"\']+)[\"\']', b)
                    if not link_m:
                        continue
                    full_link = f"https://www.vmobile.co.il{link_m[0].strip()}"
                    if full_link in seen:
                        continue
                    seen.add(full_link)

                    raw_prices = [int(p.replace(',', '')) for p in re.findall(r'(\d[\d,]*)\s*₪', b)]
                    valid_prices = [p for p in raw_prices if 150 <= p < 30000]
                    price = valid_prices[-1] if valid_prices else 0
                    if price <= 0:
                        continue

                    items.append(MobileClassifier.build_item(
                        store=self.STORE_NAME,
                        title=raw_title,
                        price_ils=price,
                        url=full_link,
                        warranty_months=12
                    ))
            except Exception as e:
                logger.error(f"Error scraping VMobile page {page}: {e}")

        return items


class LastPriceMobileScraper:
    STORE_NAME = "LastPrice"
    # Try the filtered URL first, then without filters, then the broader category
    CATALOG_URLS = [
        "https://www.lastprice.co.il/c/531/%D7%9E%D7%97%D7%A9%D7%95%D7%91-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%98%D7%9C%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D?filter1=20710526,20670485",
        "https://www.lastprice.co.il/c/531/%D7%9E%D7%97%D7%A9%D7%95%D7%91-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%98%D7%9C%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D",
        "https://www.lastprice.co.il/c/531/%D7%9E%D7%97%D7%A9%D7%95%D7%91-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%A1%D7%9C%D7%95%D7%9C%D7%A8",
    ]

    def __init__(self, session: Any):
        self.session = session

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




class MasterMobileAuditor:
    def __init__(self, session: Optional[Any] = None):
        self.session = session or create_resilient_session()
        self.scraper_classes = {
            'itoutlet': ITOutletMobileScraper,
            'gomobile': GoMobileScraper,
            'partner': PartnerPlusScraper,
            'dynamica': DynamicaScraper,
            'vmobile': VMobileScraper,
            'lastprice': LastPriceMobileScraper
        }

    def run(self, store_filter: Optional[str] = None, max_workers: int = 4) -> Dict[str, List[MobileItem]]:
        results: Dict[str, List[MobileItem]] = {}
        target_scrapers = {}

        if store_filter and store_filter.lower() in self.scraper_classes:
            target_scrapers[store_filter.lower()] = self.scraper_classes[store_filter.lower()]
        else:
            target_scrapers = self.scraper_classes

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(cls(self.session).scrape): name
                for name, cls in target_scrapers.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    items = future.result()
                    results[name] = items
                except Exception as e:
                    logger.error(f"Mobile scraper '{name}' encountered a critical error: {e}")
                    results[name] = []

        return results


def main():
    parser = argparse.ArgumentParser(description="Master Multi-Store Refurbished Mobile Device Scraper & Auditor")
    parser.add_argument("--store", choices=['itoutlet', 'gomobile', 'partner', 'dynamica', 'vmobile', 'lastprice', 'all'], default='all', help="Specific store to scrape")
    parser.add_argument("--csv", action="store_true", help="Also export devices to CSV")
    parser.add_argument("--json", action="store_true", help="Dump JSON output to stdout")
    parser.add_argument("--no-md", action="store_true", help="Disable automatic full_mobile_catalog.md update")
    parser.add_argument("--workers", type=int, default=4, help="Max concurrent store threads")

    args = parser.parse_args()

    auditor = MasterMobileAuditor()
    results = auditor.run(
        store_filter=None if args.store == 'all' else args.store,
        max_workers=args.workers
    )

    fresh_counts: Dict[str, int] = {_name: len(_items) for _name, _items in results.items()}
    preserved_counts: Dict[str, int] = {}

    all_items: List[MobileItem] = []
    for store_name, items in results.items():
        all_items.extend(items)

    # --- Preserve previously scraped data for any stores that returned 0 items ---
    # This prevents blocked/timeout stores from wiping their section from the JSON.
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, encoding="utf-8") as _f:
                _prev_raw = json.load(_f)
            _fields = set(MobileItem.__dataclass_fields__.keys())
            for _key in list(results.keys()):
                if len(results[_key]) == 0 and _key in _prev_raw and isinstance(_prev_raw[_key], list) and _prev_raw[_key]:
                    logger.warning(
                        "⚠️  Mobile store '%s' returned 0 items — preserving %d previously scraped items.",
                        _key, len(_prev_raw[_key])
                    )
                    preserved_counts[_key] = len(_prev_raw[_key])
                    results[_key] = [
                        MobileItem(**{k: v for k, v in _d.items() if k in _fields})
                        for _d in _prev_raw[_key]
                        if isinstance(_d, dict)
                    ]
                    # Rebuild all_items to include re-instated items
            all_items = []
            for store_name, items in results.items():
                all_items.extend(items)
        except Exception as _e:
            logger.warning("Could not load previous mobile catalog for fallback: %s", _e)

    ReportGenerator_export = MobileReportGenerator
    ReportGenerator_export.export_json(results, JSON_PATH)

    if args.csv:
        ReportGenerator_export.export_csv(all_items, CSV_PATH)

    if not args.no_md:
        ReportGenerator_export.update_summary_markdown(results, FULL_MOBILE_CATALOG_MD_PATH)

    ReportGenerator_export.update_scraper_status(results, fresh_counts, preserved_counts)

    print("\n" + "=" * 65)
    print(f"📊 MOBILE LIVE AUDIT COMPLETE: {len(all_items)} total devices parsed across {len(results)} stores.")
    print("=" * 65)
    for name, items in results.items():
        print(f"  • {name:18}: {len(items):2d} mobile devices found")

    if args.json:
        print("\n" + json.dumps({k: [i.to_dict() for i in v] for k, v in results.items()}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
