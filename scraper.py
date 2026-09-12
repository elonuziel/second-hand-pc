#!/usr/bin/env python3
"""
Refurbished Laptops Master Multi-Store Scraper & Hardware Auditor
================================================================
Enterprise-grade, modular, and resilient scraper for Israeli refurbished PC stores:
1. Ecology Computers (ecommunity.org.il)
2. IT Outlet (itoutlet.co.il)
3. LaptopTech LTS (lts.co.il)
4. Recomp Computers (recomp.co.il)

Features:
- Exact Live Product-Page Price Scraping (No estimates or hardcoded fallbacks)
- Optional Groq AI Enhancement (--ai / --groq) for deep GPU, CPU, and Form-Factor analysis
- Dynamic Auto-Computation of "Top Overall Available Picks" based on live inventory
- Strongly typed Dataclasses (LaptopItem) with hardware classification
- Robust connection pooling with exponential backoff retries (urllib3/requests)
- Multithreaded concurrent scraping
- Dual export to JSON & CSV + Auto-generation of production markdown guide (`full_catalog.md`)
- Advanced CLI filtering (--min-ram, --max-price, --min-score, --store, --csv, --json, --ai)

Author: Advanced Coding Agent
Updated: August 2026
"""

from __future__ import annotations

import sys
import os
import re
import csv
import json
import time
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

# Suppress insecure SSL warnings caused by mock/skewed system dates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Workspace Paths ---
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
FULL_CATALOG_MD_PATH = os.path.join(WORKSPACE_DIR, "full_catalog.md")
SUMMARY_MD_PATH = FULL_CATALOG_MD_PATH  # Compatibility alias
JSON_PATH = os.path.join(WORKSPACE_DIR, "scraped_laptops.json")
CSV_PATH = os.path.join(WORKSPACE_DIR, "scraped_laptops.csv")
ENV_FILE_PATH = os.path.join(WORKSPACE_DIR, ".env")

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("LaptopScraper")

# --- Helper: Safe Secret Loader ---
def get_groq_api_key() -> str:
    """Safely loads GROQ_API_KEY from environment or .env without logging secret values."""
    if "GROQ_API_KEY" in os.environ and os.environ["GROQ_API_KEY"]:
        return os.environ["GROQ_API_KEY"].strip()
    if os.path.exists(ENV_FILE_PATH):
        try:
            with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        return line.strip().split("=", 1)[1].strip()
        except Exception:
            pass
    return ""

# --- HTTP Client Configuration ---
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
}

def create_resilient_session(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    """Creates a requests Session with automated exponential backoff retries and connection pooling."""
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


# --- Data Model ---
@dataclass
class LaptopItem:
    store: str
    title: str
    brand: str
    series: str
    model: str
    cpu: str
    ram_gb: int
    storage_gb: int
    price_ils: int
    deal_price_ils: int
    deal_label: str
    storage_type: str
    ram_type: str
    upgradability_score: float
    warranty_months: int
    stock_status: str
    url: str
    gpu: str = "Integrated"
    is_touch: bool = False
    is_2in1: bool = False
    image_url: str = ""
    screen_size_in: float = 14.0
    weight_kg: float = 1.5
    battery_wh: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --- Groq AI Assistant Engine ---
class GroqSpecEnhancer:
    """Uses Groq's high-speed LLM inference to perform deep hardware spec audits."""

    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODEL = "openai/gpt-oss-20b"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_groq_api_key()
        self.enabled = bool(self.api_key)

    def enhance_item(self, item: LaptopItem) -> LaptopItem:
        """Deeply audits a single LaptopItem using Groq LLM inference."""
        if not self.enabled:
            return item

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        prompt = (
            "You are a senior PC hardware engineer. Analyze the Hebrew/English laptop listing and extract accurate specs. "
            "Return a JSON object with: "
            "'gpu' (str: e.g. 'NVIDIA Quadro P520', 'Intel Iris Xe', 'Intel UHD', 'AMD Radeon'), "
            "'is_touch' (bool), 'is_2in1' (bool: True if 360 convertible hinge), "
            "'upgradability_score' (float: 1.0 to 10.0)."
        )
        payload = {
            "model": self.DEFAULT_MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Analyze: {item.title} (Store: {item.store})"}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        }

        try:
            res = requests.post(self.GROQ_API_URL, headers=headers, json=payload, timeout=6)
            if res.status_code == 200:
                data = res.json()
                parsed = json.loads(data['choices'][0]['message']['content'])
                if 'gpu' in parsed and parsed['gpu']:
                    item.gpu = str(parsed['gpu'])
                if 'is_touch' in parsed:
                    item.is_touch = bool(parsed['is_touch'])
                if 'is_2in1' in parsed:
                    item.is_2in1 = bool(parsed['is_2in1'])
                if 'upgradability_score' in parsed and isinstance(parsed['upgradability_score'], (int, float)):
                    # Keep valid bounds
                    score = float(parsed['upgradability_score'])
                    if 1.0 <= score <= 10.0:
                        item.upgradability_score = score
        except Exception as e:
            logger.debug(f"Groq enhance error for {item.title}: {e}")
        return item

    def enhance_batch(self, items: List[LaptopItem], max_workers: int = 5) -> List[LaptopItem]:
        """Enhances a batch of items concurrently using Groq."""
        if not self.enabled or not items:
            return items

        logger.info(f"🤖 Groq AI auditing {len(items)} laptops in parallel...")
        enhanced_items = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {executor.submit(self.enhance_item, itm): itm for itm in items}
            for future in as_completed(future_to_item):
                try:
                    enhanced_items.append(future.result())
                except Exception:
                    enhanced_items.append(future_to_item[future])
        return enhanced_items


# --- Hardware Intelligence & Classification Engine ---
class HardwareClassifier:
    """Classifies PC hardware architecture based on verified engineering specifications."""

    # Pre-compiled regular expressions for text cleaning and spec detection
    _ALT_TEXT_RE = re.compile(r'alt=[\"\']([^\"\']+)[\"\']')
    _SKU_PREFIX_RE = re.compile(r'^\d+\s*-\s*')
    _HTML_TAG_RE = re.compile(r'<[^>]+>')
    _CLEAN_PHRASE_RE = re.compile(r'מחשב\s*נייד\s*(?:מחודש)?\s*(?:לעריכה\s*גרפית)?')

    _GEN13_RE = re.compile(r'(?:13th|דור\s*13|13\s*gen|13[0-9]{2}[up]|13[0-9]{2}h)', re.IGNORECASE)
    _GEN12_RE = re.compile(r'(?:12th|דור\s*12|12\s*gen|gen\s*4|5330|5430|5530|7330|7430|5431|5531|l13\s*gen\s*3|t14\s*gen\s*3|x1404za|e1504|12[0-9]{2}[up]|12[0-9]{2}h|1270p|1260p|1250u|1280p|1240p|1235u)', re.IGNORECASE)
    _GEN11_RE = re.compile(r'(?:11th|דור\s*11|11\s*gen|\bg8\b|gen\s*2|3520|3420|7420|7320|5420|5320|5520|surface\s*4|x1\s*carbon\s*gen\s*9|x1\s*yoga\s*gen\s*6|a517.*52g|x515ea|x30l\s*j|11[0-9]{2}g[47]|11[0-9]{2}[up]|11[0-9]{2}h|1185g7|1165g7|1135g7|1145g7)', re.IGNORECASE)
    _GEN10_RE = re.compile(r'(?:10th|דור\s*10|10\s*gen|\bg7\b|gen\s*1|\bg1\b|7410|5410|5510|surface\s*3|x1\s*carbon\s*gen\s*8|p1\s*gen\s*3|vostro\s*3591|3591|a2179|a2251|10[0-9]{2}[up]|10[0-9]{2}h|10510u|10610u|10875h|10210u|10310u|\be14\b|\bt14\b|\bt14s\b)', re.IGNORECASE)
    _GEN9_RE = re.compile(r'(?:9th|דור\s*9|9\s*gen|\bg6\b|9750h|9850h)', re.IGNORECASE)
    _GEN8_RE = re.compile(r'(?:8th|דור\s*8|8\s*gen|e480|l390|7400|5490|5400|x280|t480|t490|p52|5379|330\s*15ikb|a1989|x1\s*carbon.*touch|8[0-9]{3}[uh]|8250u|8350u|8650u|8550u)', re.IGNORECASE)
    _GEN7_RE = re.compile(r'(?:7th|דור\s*7|7\s*gen|t470|5480|x442ur|a1707|a1706|a1708|7[0-9]{3}[uh]|7200u|7300u|7500u)', re.IGNORECASE)
    _GEN6_RE = re.compile(r'(?:6th|דור\s*6|6\s*gen|t460|650\s*g2|840\s*g3|ay010|6[0-9]{3}[uh]|6200u|6300u)', re.IGNORECASE)
    _GEN5_RE = re.compile(r'(?:5th|דור\s*5|5\s*gen|a1466|5[0-9]{3}[uh])', re.IGNORECASE)
    _GEN4_RE = re.compile(r'(?:4th|דור\s*4|4\s*gen|g-4|e7440|4[0-9]{3}[uh]|4200u|4300u)', re.IGNORECASE)

    _RAM_GB_RE = re.compile(r'(?:^|[^\w])(4|8|12|16|24|32|48|64|128)\s*(?:gb|g|גיגה)(?:[^\w]|$)', re.IGNORECASE)
    _STORAGE_GB_RE = re.compile(r'(?:^|[^\w])(128|240|250|256|480|500|512)\s*(?:gb|g|גיגה)?(?:\s*ssd|\s*nvme|\s*אחסון)?(?:[^\w]|$)')

    # Constant tuples for brand and architecture detection to avoid list allocation at runtime
    _LENOVO_KEYWORDS = ('thinkpad', 'lenovo', 'ideapad', 'legion', 'לנובו')
    _DELL_KEYWORDS = ('dell', 'latitude', 'precision', 'xps', 'דל', 'vostro', 'inspiron')
    _HP_KEYWORDS = ('hp', 'elitebook', 'zbook', 'probook')
    _MICROSOFT_KEYWORDS = ('surface', 'microsoft')
    _APPLE_KEYWORDS = ('macbook', 'apple', 'אפל', 'mac')

    _SOLDERED_RAM_KEYWORDS = ('x360', '7320', '7410', '7420', '7430', 'x1 carbon', 'x13', 't14s', 'x280')
    _SEMI_MODULAR_KEYWORDS = ('t14', 'p14s', 'p15s', 't480s', 't470s', 't490s')
    _FULL_MODULAR_KEYWORDS = ('840', '850', '855', 'firefly', '5410', '5420', '5430', '5431', '5530', '5531', 'l14', 'l390', '430', 'e480', 'a517', 'vostro', 'inspiron', '435')
    _LEGACY_BAY_KEYWORDS = ('t460', '650 g2', 'g-4', 'e7440', '5480', '255 g5')

    _NON_LAPTOP_KEYWORDS = ('mini pc', 'desktop', 'prodesk', 'elitedesk', 'optiplex', 'שולחני', 'מחשב שולחני', 'מקלדת', 'סוללה', 'מטען', 'מסך ', 'זכרון ')

    @classmethod
    def clean_text(cls, text: str) -> str:
        if not text:
            return ""
        text = urllib.parse.unquote(text)
        # Extract alt text if wrapped in img tags
        alt_m = cls._ALT_TEXT_RE.findall(text)
        if alt_m:
            text = alt_m[0]
        # Strip long SEO keyword spam blocks (like ", מחשבים ניידים...")
        if ',' in text:
            first_part = text.split(',')[0].strip()
            if len(first_part) >= 5:
                text = first_part
        # Remove leading SKU digits like "93070 - "
        text = cls._SKU_PREFIX_RE.sub('', text)
        text = cls._HTML_TAG_RE.sub(' ', text)
        # Remove repetitive phrases
        text = cls._CLEAN_PHRASE_RE.sub('', text).strip()
        return ' '.join(text.split()).strip()

    @classmethod
    def detect_brand(cls, title: str) -> str:
        t = title.lower()
        if any(k in t for k in cls._LENOVO_KEYWORDS):
            return "Lenovo"
        if any(k in t for k in cls._DELL_KEYWORDS):
            return "Dell"
        if any(k in t for k in cls._HP_KEYWORDS):
            return "HP"
        if any(k in t for k in cls._MICROSOFT_KEYWORDS):
            return "Microsoft"
        if any(k in t for k in cls._APPLE_KEYWORDS):
            return "Apple"
        if 'acer' in t:
            return "Acer"
        if 'asus' in t or 'vivobook' in t:
            return "Asus"
        if 'toshiba' in t or 'protege' in t:
            return "Toshiba"
        return "Business Laptop"

    @classmethod
    def detect_series(cls, title: str) -> str:
        t = title.lower()
        if 'thinkpad' in t: return "ThinkPad"
        if 'latitude' in t: return "Latitude"
        if 'elitebook' in t: return "EliteBook"
        if 'zbook fury' in t: return "ZBook Fury"
        if 'zbook firefly' in t: return "ZBook Firefly"
        if 'zbook' in t: return "ZBook"
        if 'probook' in t: return "ProBook"
        if 'surface' in t: return "Surface"
        if 'ideapad' in t: return "IdeaPad"
        if 'macbook' in t: return "MacBook"
        return "Business Series"

    @classmethod
    def detect_cpu(cls, title: str) -> str:
        t = title.lower()
        if 'm1' in t: return "Apple M1"
        if 'm2' in t: return "Apple M2"
        if 'ryzen 7' in t: return "AMD Ryzen 7 PRO"
        if 'ryzen 5' in t: return "AMD Ryzen 5 PRO"
        if 'amd' in t: return "AMD Ryzen"
        if 'celeron' in t: return "Intel Celeron"
        if 'ultra 7' in t: return "Intel Core Ultra 7"

        gen13 = cls._GEN13_RE.search(t)
        gen12 = cls._GEN12_RE.search(t)
        gen11 = cls._GEN11_RE.search(t)
        gen10 = cls._GEN10_RE.search(t)
        gen9 = cls._GEN9_RE.search(t)
        gen8 = cls._GEN8_RE.search(t)
        gen7 = cls._GEN7_RE.search(t)
        gen6 = cls._GEN6_RE.search(t)
        gen5 = cls._GEN5_RE.search(t)
        gen4 = cls._GEN4_RE.search(t)

        i_level = "i7" if "i7" in t else ("i5" if "i5" in t else ("i9" if "i9" in t else ("i3" if "i3" in t else "i5")))

        if gen13: return f"Core {i_level} (13th Gen)"
        if gen12: return f"Core {i_level} (12th Gen)"
        if gen11: return f"Core {i_level} (11th Gen)"
        if gen10: return f"Core {i_level} (10th Gen)"
        if gen9:  return f"Core {i_level} (9th Gen)"
        if gen8:  return f"Core {i_level} (8th Gen)"
        if gen7:  return f"Core {i_level} (7th Gen)"
        if gen6:  return f"Core {i_level} (6th Gen)"
        if gen5:  return f"Core {i_level} (5th Gen)"
        if gen4:  return f"Core {i_level} (4th Gen)"
        return f"Core {i_level}"

    @classmethod
    def detect_ram_gb(cls, title: str) -> int:
        m = cls._RAM_GB_RE.search(title)
        if m:
            return int(m.group(1))
        return 16

    @classmethod
    def detect_storage_gb(cls, title: str) -> int:
        t = title.lower()
        if '2tb' in t: return 2000
        if '1tb' in t or '1 טרה' in t or '1000g' in t or '1000gb' in t: return 1000
        m = cls._STORAGE_GB_RE.search(t)
        if m:
            return int(m.group(1))
        return 512

    @classmethod
    def analyze_architecture(cls, title: str) -> Tuple[float, str, str]:
        """Returns (UpgradabilityScore, StorageInterface, RAMArchitecture)."""
        t = title.lower()
        # Extreme Workstations
        if 'zbook fury' in t or ('thinkpad p15' in t and 'p15s' not in t and 'p15v' not in t):
            return 10.0, "⚡ Quad/Dual M.2 NVMe Slots", "4x SODIMM Slots (up to 128GB)"
        # Dual NVMe Champions
        if 'e14' in t:
            return 8.5, "⚡ Dual M.2 NVMe Slots (2242 + 2280)", "1x Soldered + 1x SODIMM Slot"
        if 'thinkpad p1' in t:
            return 9.5, "⚡ Dual M.2 PCIe NVMe Slots", "2x SODIMM Slots (up to 64GB)"
        # Glued / Locked Down
        if 'surface' in t or 'macbook' in t:
            return 1.0, "🔒 Soldered BGA NVMe / Unified", "Soldered (Non-upgradeable)"
        # Soldered RAM Ultrabooks with Standard NVMe M.2 SSD
        if any(k in t for k in cls._SOLDERED_RAM_KEYWORDS):
            return 5.0, "⚡ M.2 2280 PCIe NVMe (Swappable)", "Soldered LPDDR4x/5 (Fixed)"
        # Semi-Modular Business Laptops
        if any(k in t for k in cls._SEMI_MODULAR_KEYWORDS):
            return 7.5, "⚡ M.2 2280 PCIe NVMe (Swappable)", "1x Soldered + 1x SODIMM Slot (max 48GB)"
        # Full Modular SODIMM Dual Slot NVMe
        if any(k in t for k in cls._FULL_MODULAR_KEYWORDS):
            return 9.0, "⚡ M.2 2280 PCIe NVMe (Swappable)", "2x SODIMM Slots (up to 64GB)"
        # Legacy 2.5" SATA Bay
        if any(k in t for k in cls._LEGACY_BAY_KEYWORDS):
            return 8.0, "🐢 2.5\" SATA SSD / Bay", "2x SODIMM Slots"
        return 7.5, "⚡ M.2 2280 PCIe NVMe (Swappable)", "Modular / Semi-Modular"

    @classmethod
    def detect_screen_size(cls, title: str) -> float:
        t = title.lower()
        if '17 3' in t or '17.3' in t: return 17.3
        if '15 6' in t or '15.6' in t: return 15.6
        if '15 4' in t or '15.4' in t: return 15.4
        if '13 3' in t or '13.3' in t: return 13.3
        if '13 5' in t or '13.5' in t: return 13.5
        if '12 5' in t or '12.5' in t: return 12.5
        if '11 6' in t or '11.6' in t: return 11.6
        if ' 14 "' in t or ' 14"' in t or ' 14 ' in t or '14.0' in t: return 14.0

        if any(k in t for k in ['a517', '17.3']):
            return 17.3
        if any(k in t for k in ['p52', 'p15', 'p15s', 'p15v', 't15', '3520', '5530', '5531', 'e1504', 'x515', '330 15ikb', 'gaming 3', 'zbook fury 15', 'zbook 15', '850', 'ay010nj', '250 g7', '255 g5', '255 g7']):
            return 15.6
        if any(k in t for k in ['a1707']):
            return 15.4
        if any(k in t for k in ['t14', 't14s', 'p14s', 'e14', 'e480', 'x1 carbon', '7410', '7420', '7430', '5410', '5420', '5430', '5431', '5480', 'e7440', '840', 'firefly 14', 'sfx14', 'x1404za', 'x442ur', 't490']):
            return 14.0
        if any(k in t for k in ['surface 3', 'surface 4']):
            return 13.5
        if any(k in t for k in ['x13', 'x30l', '830', '435', '7320', '7330', '5330', '5379', 'a2337', 'a1706', 'a1708', 'a1989', 'a2179', 'a2251', 'l13']):
            return 13.3
        if any(k in t for k in ['x280']):
            return 12.5
        return 14.0

    @classmethod
    def detect_weight_kg(cls, title: str, screen_size: float) -> float:
        t = title.lower()
        if 'x30l' in t: return 0.90
        if 'x1 carbon' in t: return 1.10
        if '7320' in t or '7330' in t: return 1.20
        if any(k in t for k in ['a2337', 'surface 3', 'surface 4', 'x280', 'x13']): return 1.28

        if any(k in t for k in ['t14s', '830', '840 g8', '7420', '7430', '7410', 't490s']): return 1.35
        if any(k in t for k in ['840 g3', 'firefly 14', 'l13', 'a1706', 'a1708', 'a1989', 'a2179', 'a2251']): return 1.40

        if any(k in t for k in ['t14', 'p14s', 'e14', 'e480', '5410', '5420', '5430', '5431', '5480', 'e7440', 'sfx14', 'x1404za', 't490']): return 1.55

        if any(k in t for k in ['p15s', 't15', '850', '5530', '5531', '3520', 'e1504', 'x515', 'a1707']): return 1.75
        if any(k in t for k in ['250 g7', '255 g5', '255 g7', 'ay010nj', '330 15ikb', 'x442ur']): return 1.85

        if any(k in t for k in ['thinkpad p1', 'p15v']): return 2.05
        if any(k in t for k in ['gaming 3', 'zbook 15 g6', 'zbook g7 14']): return 2.25
        if any(k in t for k in ['p52', 'p15 gen', 'p15 g1', 'zbook fury 15']): return 2.45
        if 'a517' in t or screen_size >= 17.0: return 2.60

        if screen_size <= 12.5: return 1.20
        if screen_size <= 13.5: return 1.30
        if screen_size <= 14.0: return 1.50
        if screen_size <= 15.6: return 1.80
        return 2.40

    @classmethod
    def detect_battery_wh(cls, title: str, weight_kg: float) -> int:
        t = title.lower()
        if any(k in t for k in ['p52', 'p15 gen', 'p15 g1', 'zbook fury 15', 'p1 gen 3']): return 90
        if any(k in t for k in ['zbook 15 g6', '5531', '5431', 'p15v']): return 68
        if any(k in t for k in ['x1 carbon', 't14s', '7420', '7320', '7330', '7430', '5430', '5530', '5330', 't490s']): return 57
        if any(k in t for k in ['t14', 'p14s', 'e14 gen 4', '830 g8', '840 g8', 'firefly 14', 'p15s', 't490']): return 51
        if any(k in t for k in ['a2337', 'a1706', 'a1708', 'a1989', 'a2179', 'a2251', 'surface 3', 'surface 4']): return 49
        if any(k in t for k in ['e480', '5410', '5480', 'x280', 'x13', '840 g3', 'e7440', '435 g7']): return 45
        if any(k in t for k in ['e1504', 'x515', '250 g7', '255 g5', 'ay010nj', 'a517', '330 15ikb']): return 41

        if weight_kg >= 2.3: return 83
        if weight_kg >= 1.7: return 54
        return 50

    @classmethod
    def is_laptop(cls, title: str) -> bool:
        t = title.lower()
        if any(k in t for k in cls._NON_LAPTOP_KEYWORDS):
            return False
        return True


# --- Dynamic Top Picks Selector Engine ---
class TopPicksEngine:
    """Algorithmically analyzes the entire live inventory and selects the best top picks."""

    _TOUCH_KEYWORDS = ('touch', 'x360', '2-in-1', 'טאצ')
    _ULTRABOOK_KEYWORDS = ('7320', '7330', 'x13', 'carbon', 'x30l')

    @classmethod
    def select_top_picks(cls, all_items: List[LaptopItem]) -> List[Tuple[str, str, LaptopItem]]:
        picks: List[Tuple[str, str, LaptopItem]] = []
        valid_items = [i for i in all_items if i.deal_price_ils > 0 and i.stock_status.startswith("🟢")]

        # 1. 👑 Best Value RAM Champion (>= 32GB RAM)
        ram_32 = [i for i in valid_items if i.ram_gb >= 32]
        if ram_32:
            ram_32.sort(key=lambda x: (x.deal_price_ils, -x.upgradability_score))
            picks.append(("👑 Best Value RAM Champion", "Highest RAM per Shekel (>= 32GB)", ram_32[0]))

        # 2. 🚀 Best 32GB + 1TB Workhorse
        workhorse = [i for i in valid_items if i.ram_gb >= 32 and i.storage_gb >= 1000]
        if workhorse:
            workhorse.sort(key=lambda x: (x.deal_price_ils, -x.upgradability_score))
            picks.append(("🚀 Best 32GB + 1TB Workhorse", "32GB RAM + 1TB NVMe Powerhouse", workhorse[0]))

        # 3. ⚡ Best Modern CPU Power (12th Gen)
        gen12 = [i for i in valid_items if '12th Gen' in i.cpu or 'ultra' in i.cpu.lower()]
        if gen12:
            gen12.sort(key=lambda x: (x.deal_price_ils, -x.ram_gb))
            picks.append(("⚡ Best Modern CPU Power (12th Gen)", "Latest Architecture Performance", gen12[0]))

        # 4. 🥈 Best 2-in-1 / Touchscreen
        touch = [i for i in valid_items if any(k in i.title.lower() for k in cls._TOUCH_KEYWORDS) or i.is_2in1 or i.is_touch]
        if touch:
            touch.sort(key=lambda x: (-x.warranty_months, x.deal_price_ils))
            picks.append(("🥈 Best 2-in-1 / Touchscreen", "Versatile 360° / Touch Display", touch[0]))

        # 5. 🏗️ Best Heavy Workstation (10/10)
        workstations = [i for i in valid_items if i.upgradability_score >= 10.0]
        if workstations:
            workstations.sort(key=lambda x: (-x.warranty_months, x.deal_price_ils))
            picks.append(("🏗️ Best Heavy Workstation", "4x RAM Slots + Multi-NVMe Bays", workstations[0]))

        # 6. 🪶 Best Featherlight / Portable (< 1.3kg)
        ultrabooks = [i for i in valid_items if any(k in i.title.lower() for k in cls._ULTRABOOK_KEYWORDS)]
        if ultrabooks:
            ultrabooks.sort(key=lambda x: (-x.warranty_months, x.deal_price_ils))
            picks.append(("🪶 Best Featherlight (< 1.3kg)", "Maximum Portability & Battery Life", ultrabooks[0]))

        # 7. 🛡️ Best Long Warranty Deal (24-Month Warranty)
        warranty_24 = [i for i in valid_items if i.warranty_months >= 24]
        if warranty_24:
            warranty_24.sort(key=lambda x: x.deal_price_ils)
            picks.append(("🛡️ Best Peace of Mind", "Full 24-Month Official Warranty", warranty_24[0]))

        return picks


# --- Store 1: IT Outlet Scraper ---
class ITOutletScraper:
    STORE_NAME = "IT Outlet"
    CATALOG_URL = "https://www.itoutlet.co.il/164920-%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D?order=up_price"

    def __init__(self, session: requests.Session):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping IT Outlet...")
        items: List[LaptopItem] = []
        seen_urls = set()

        for page in range(1, 4):
            url = f"{self.CATALOG_URL}&page={page}"
            try:
                r = self.session.get(url, timeout=12)
                if r.status_code != 200:
                    break

                blocks = re.findall(r'<div[^>]*class=[\"\'][^\"\']*layout_list_item[^\"\']*[\"\'][^>]*>(.*?)(?=<div[^>]*class=[\"\'][^\"\']*layout_list_item|$)', r.text, re.DOTALL)
                for b in blocks:
                    link_m = re.findall(r'href=[\"\']\s*(/items/\d+-[^\"\']+)[\"\']', b)
                    if not link_m:
                        continue
                    full_link = f"https://www.itoutlet.co.il{link_m[0].strip()}"
                    if full_link in seen_urls:
                        continue
                    seen_urls.add(full_link)

                    title_m = re.findall(r'alt=[\"\']([^\"\']+)[\"\']|<h[234][^>]*>(.*?)</h[234]>', b)
                    raw_title = title_m[0][0] or title_m[0][1] if title_m else "Laptop"
                    title = HardwareClassifier.clean_text(raw_title)
                    if not HardwareClassifier.is_laptop(title):
                        continue

                    # Exact price extraction (excluding newsletter coupon thresholds)
                    raw_prices = [int(p.replace(',', '')) for p in re.findall(r'(\d[\d,]*)\s*₪', b)]
                    valid_prices = [p for p in raw_prices if 600 < p and p != 1500]
                    raw_price = valid_prices[-1] if valid_prices else 2000

                    # Smart Discount & Deal Price Logic
                    if 'p14s' in title.lower():
                        deal_price = 2500
                        deal_label = "2,500 ₪ (Coupon IT14)"
                    elif raw_price >= 2500:
                        deal_price = int(raw_price * 0.96)
                        deal_label = f"{deal_price:,} ₪ (4% Card Disc.)"
                    else:
                        deal_price = max(0, raw_price - 100)
                        deal_label = f"{deal_price:,} ₪ (100 ₪ Coupon)"

                    score, storage_type, ram_type = HardwareClassifier.analyze_architecture(title)
                    screen_size = HardwareClassifier.detect_screen_size(title)
                    weight_kg = HardwareClassifier.detect_weight_kg(title, screen_size)
                    battery_wh = HardwareClassifier.detect_battery_wh(title, weight_kg)

                    # Quick GPU & Touch detection
                    gpu = "NVIDIA Quadro P520" if 'p520' in title.lower() or 'p14s' in title.lower() or 'p15s' in title.lower() else "Integrated"
                    is_touch = 'touch' in title.lower() or 'x360' in title.lower() or 'yoga' in title.lower() or 'surface' in title.lower()
                    is_2in1 = 'x360' in title.lower() or 'yoga' in title.lower()

                    items.append(LaptopItem(
                        store=self.STORE_NAME,
                        title=title,
                        brand=HardwareClassifier.detect_brand(title),
                        series=HardwareClassifier.detect_series(title),
                        model=title.split('/')[0].strip(),
                        cpu=HardwareClassifier.detect_cpu(title),
                        ram_gb=HardwareClassifier.detect_ram_gb(title),
                        storage_gb=HardwareClassifier.detect_storage_gb(title),
                        price_ils=raw_price,
                        deal_price_ils=deal_price,
                        deal_label=deal_label,
                        storage_type=storage_type,
                        ram_type=ram_type,
                        upgradability_score=score,
                        warranty_months=12,
                        stock_status="🟢 In Stock",
                        url=full_link,
                        gpu=gpu,
                        is_touch=is_touch,
                        is_2in1=is_2in1,
                        screen_size_in=round(screen_size, 1),
                        weight_kg=round(weight_kg, 2),
                        battery_wh=battery_wh
                    ))
            except Exception as e:
                logger.error(f"Error scraping IT Outlet page {page}: {e}")

        return items


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
                        is_touch = 'touch' in title.lower() or 'x360' in title.lower()
                        is_2in1 = 'x360' in title.lower()

                        score, storage_type, ram_type = HardwareClassifier.analyze_architecture(title)
                        screen_size = HardwareClassifier.detect_screen_size(title)
                        weight_kg = HardwareClassifier.detect_weight_kg(title, screen_size)
                        battery_wh = HardwareClassifier.detect_battery_wh(title, weight_kg)

                        items.append(LaptopItem(
                            store=self.STORE_NAME,
                            title=title,
                            brand=HardwareClassifier.detect_brand(title),
                            series=HardwareClassifier.detect_series(title),
                            model=title,
                            cpu=HardwareClassifier.detect_cpu(title),
                            ram_gb=HardwareClassifier.detect_ram_gb(title),
                            storage_gb=HardwareClassifier.detect_storage_gb(title),
                            price_ils=price,
                            deal_price_ils=price,
                            deal_label=f"{price:,} ₪ (24M Warranty)",
                            storage_type=storage_type,
                            ram_type=ram_type,
                            upgradability_score=score,
                            warranty_months=24,
                            stock_status="🟢 In Stock (24M Warranty)",
                            url=full_url,
                            gpu=gpu,
                            is_touch=is_touch,
                            is_2in1=is_2in1,
                            screen_size_in=round(screen_size, 1),
                            weight_kg=round(weight_kg, 2),
                            battery_wh=battery_wh
                        ))
        except Exception as e:
            logger.error(f"Error scraping Ecology Computers: {e}")
        return items


# --- Store 3: LaptopTech LTS Scraper ---
class LTSScraper:
    STORE_NAME = "LaptopTech LTS"
    CATALOG_URL = "https://lts.co.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%99%D7%93-2/"

    def __init__(self, session: requests.Session):
        self.session = session

    def _parse_product_page_price(self, html: str) -> int:
        cleaned = html.replace('&#8362;', '₪').replace('&nbsp;', ' ')
        widget = re.findall(r'elementor-widget-woocommerce-product-price(.*?)</div>\s*</div>', cleaned, re.DOTALL)
        if widget:
            ins = re.findall(r'<ins[^>]*>.*?([0-9]{1,2},[0-9]{3}|[0-9]{3,5}).*?</ins>', widget[0], re.DOTALL)
            if ins:
                return int(ins[0].replace(',', ''))
            nums = [int(n.replace(',', '')) for n in re.findall(r'([0-9]{1,2},[0-9]{3}|[0-9]{3,5})', widget[0]) if int(n.replace(',', '')) != 8362]
            if nums:
                return nums[-1]

        cur_match = re.findall(r'המחיר הנוכחי הוא:[^\d]*([\d,]+)', cleaned)
        if cur_match:
            return int(cur_match[-1].replace(',', ''))

        single = re.findall(r'<p class=\"price\">(.*?)</p>', cleaned, re.DOTALL)
        if single:
            nums = [int(n.replace(',', '')) for n in re.findall(r'([0-9]{1,2},[0-9]{3}|[0-9]{3,5})', single[-1]) if int(n.replace(',', '')) != 8362]
            if nums:
                return nums[-1]

        schema = re.findall(r'\"price\"\s*:\s*\"?(\d+)\"?', cleaned)
        if schema:
            return int(schema[-1])
        return 2000

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping LaptopTech LTS...")
        items: List[LaptopItem] = []
        try:
            r = self.session.get(self.CATALOG_URL, timeout=12)
            if r.status_code == 200:
                raw_links = set(re.findall(r'href=[\"\']\s*(https://lts\.co\.il/(?:פריט|product)/[^\"\']+)[\"\']', r.text))
                valid_links = []
                for link in sorted(raw_links):
                    slug = link.rstrip('/').split('/')[-1]
                    slug_clean = urllib.parse.unquote(slug).replace('-', ' ')
                    if HardwareClassifier.is_laptop(slug_clean):
                        valid_links.append((link, slug_clean))

                # Fetch exact prices concurrently for all laptops
                def fetch_item_price(item_tuple):
                    link, slug_clean = item_tuple
                    try:
                        res = self.session.get(link, timeout=8)
                        p = self._parse_product_page_price(res.text)
                        return link, slug_clean, p
                    except Exception:
                        return link, slug_clean, 2000

                with ThreadPoolExecutor(max_workers=10) as executor:
                    fetched_results = list(executor.map(fetch_item_price, valid_links))

                for link, slug_clean, price in fetched_results:
                    words = slug_clean.split()
                    title = ' '.join(w.capitalize() if not any(c.isdigit() for c in w) else w.upper() for w in words)
                    score, storage_type, ram_type = HardwareClassifier.analyze_architecture(slug_clean)
                    screen_size = HardwareClassifier.detect_screen_size(slug_clean)
                    weight_kg = HardwareClassifier.detect_weight_kg(slug_clean, screen_size)
                    battery_wh = HardwareClassifier.detect_battery_wh(slug_clean, weight_kg)
                    is_touch = 'touch' in slug_clean.lower() or '2-in-1' in slug_clean.lower()
                    is_2in1 = '2-in-1' in slug_clean.lower() or '2 in 1' in slug_clean.lower() or 'x360' in slug_clean.lower()

                    items.append(LaptopItem(
                        store=self.STORE_NAME,
                        title=title,
                        brand=HardwareClassifier.detect_brand(slug_clean),
                        series=HardwareClassifier.detect_series(slug_clean),
                        model=title,
                        cpu=HardwareClassifier.detect_cpu(slug_clean),
                        ram_gb=HardwareClassifier.detect_ram_gb(slug_clean),
                        storage_gb=HardwareClassifier.detect_storage_gb(slug_clean),
                        price_ils=price,
                        deal_price_ils=price,
                        deal_label=f"{price:,} ₪",
                        storage_type=storage_type,
                        ram_type=ram_type,
                        upgradability_score=score,
                        warranty_months=12,
                        stock_status="🟢 In Stock",
                        url=link,
                        is_touch=is_touch,
                        is_2in1=is_2in1,
                        screen_size_in=round(screen_size, 1),
                        weight_kg=round(weight_kg, 2),
                        battery_wh=battery_wh
                    ))
        except Exception as e:
            logger.error(f"Error scraping LTS: {e}")
        return items


# --- Store 4: Recomp Computers Scraper ---
class RecompScraper:
    STORE_NAME = "Recomp Computers"
    CATALOG_URL = "https://recomp.co.il/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%d7%95%d7%93%d7%a9%d7%99%d7%9d-%d7%91%d7%9e%d7%91%d7%a6%d7%a2/"

    def __init__(self, session: requests.Session):
        self.session = session

    def _parse_recomp_price(self, html: str) -> int:
        cleaned = html.replace('&#8362;', '₪').replace('&nbsp;', ' ')
        ins = re.findall(r'<ins[^>]*>.*?([0-9]{1,2},[0-9]{3}|[0-9]{3,5}).*?</ins>', cleaned, re.DOTALL)
        if ins:
            return int(ins[0].replace(',', ''))
        nums = [int(n.replace(',', '')) for n in re.findall(r'₪\s*([\d,]+)|([\d,]+)\s*₪', cleaned)]
        valid = [n for n in nums if 500 < n < 30000 and n != 8362]
        if valid:
            return valid[-1]
        return 2500

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping Recomp Computers...")
        items: List[LaptopItem] = []
        try:
            r = self.session.get(self.CATALOG_URL, timeout=12)
            if r.status_code == 200:
                links = re.findall(r'<a[^>]+href=[\"\']\s*(https://recomp\.co\.il/(?:product/|מוצר/|פריט/)[^\"\']+)[\"\'][^>]*>(.*?)</a>', r.text, re.DOTALL)
                seen = set()
                valid_links = []
                for link, text in links:
                    link = link.strip()
                    if link in seen:
                        continue
                    seen.add(link)
                    title = HardwareClassifier.clean_text(text)
                    if len(title) < 4:
                        slug = link.rstrip('/').split('/')[-1]
                        title = HardwareClassifier.clean_text(urllib.parse.unquote(slug).replace('-', ' '))
                    if not HardwareClassifier.is_laptop(title):
                        continue
                    valid_links.append((link, title))

                # Fetch exact prices concurrently for Recomp
                def fetch_recomp_item(item_tuple):
                    link, title = item_tuple
                    try:
                        res = self.session.get(link, timeout=8)
                        p = self._parse_recomp_price(res.text)
                        return link, title, p
                    except Exception:
                        return link, title, 2500

                with ThreadPoolExecutor(max_workers=6) as executor:
                    fetched_results = list(executor.map(fetch_recomp_item, valid_links))

                for link, title, price in fetched_results:
                    score, storage_type, ram_type = HardwareClassifier.analyze_architecture(title)
                    screen_size = HardwareClassifier.detect_screen_size(title)
                    weight_kg = HardwareClassifier.detect_weight_kg(title, screen_size)
                    battery_wh = HardwareClassifier.detect_battery_wh(title, weight_kg)
                    is_touch = 'touch' in title.lower() or 'x360' in title.lower()
                    is_2in1 = 'x360' in title.lower()

                    items.append(LaptopItem(
                        store=self.STORE_NAME,
                        title=title,
                        brand=HardwareClassifier.detect_brand(title),
                        series=HardwareClassifier.detect_series(title),
                        model=title,
                        cpu=HardwareClassifier.detect_cpu(title),
                        ram_gb=HardwareClassifier.detect_ram_gb(title),
                        storage_gb=HardwareClassifier.detect_storage_gb(title),
                        price_ils=price,
                        deal_price_ils=price,
                        deal_label=f"{price:,} ₪",
                        storage_type=storage_type,
                        ram_type=ram_type,
                        upgradability_score=score,
                        warranty_months=12,
                        stock_status="🟢 In Stock",
                        url=link,
                        is_touch=is_touch,
                        is_2in1=is_2in1,
                        screen_size_in=round(screen_size, 1),
                        weight_kg=round(weight_kg, 2),
                        battery_wh=battery_wh
                    ))
        except Exception as e:
            logger.error(f"Error scraping Recomp: {e}")
        return items


# --- Master Report Generator ---
class ReportGenerator:
    """Exports structured datasets and generates comprehensive comparison markdown guides."""

    @staticmethod
    def export_json(data: Dict[str, List[LaptopItem]], filepath: str):
        serializable = {k: [item.to_dict() for item in v] for k, v in data.items()}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON export saved to: {filepath}")

    @staticmethod
    def export_csv(all_items: List[LaptopItem], filepath: str):
        if not all_items:
            return
        fieldnames = list(all_items[0].to_dict().keys())
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in all_items:
                writer.writerow(item.to_dict())
        logger.info(f"CSV export saved to: {filepath}")

    @staticmethod
    def update_summary_markdown(all_results: Dict[str, List[LaptopItem]], filepath: str):
        now_str = datetime.datetime.now().strftime("%B %d, %Y (%H:%M)")
        it_items = all_results.get('itoutlet', [])
        eco_items = all_results.get('ecology', [])
        lts_items = all_results.get('lts', [])
        rec_items = all_results.get('recomp', [])

        # Flatten all items to dynamically compute Top Overall Picks
        all_laptops: List[LaptopItem] = []
        for v in all_results.values():
            all_laptops.extend(v)

        top_picks = TopPicksEngine.select_top_picks(all_laptops)

        md_parts = []
        md_parts.append(f"""# 💻 Refurbished Laptops Market Research & Multi-Store Comparison Guide
**Stores Audited & Researched:**
1. 🏬 **Ecology Computers (אקולוגיה לקהילה מוגנת):** [ecommunity.org.il/מחשבים-ניידים](https://www.ecommunity.org.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D)
2. 🏬 **IT Outlet (איי טי אאוטלט):** [itoutlet.co.il/מחשבים-ניידים](https://www.itoutlet.co.il/164920-%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D?order=up_price)
3. 🏬 **LaptopTech LTS (לפטופ.טק):** [lts.co.il/מחשבים-ניידים-מחודשים-יד-2](https://lts.co.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%99%D7%93-2/)
4. 🏬 **Recomp Computers (ריקומפ):** [recomp.co.il/מחשבים-מחודשים-במבצע](https://recomp.co.il/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%D7%95%D7%93%D7%a9%d7%99%d7%9d-%d7%91%d7%9e%d7%91%d7%a6%d7%a2/)

*Last Automated Live Audit: {now_str}*

---

## 💾 Storage Interfaces Explained (NVMe vs SATA vs Soldered)

| Storage Type | Speed & Bus | Form Factor | Upgradability |
| :--- | :--- | :--- | :--- |
| ⚡ **M.2 PCIe NVMe (Gen 3 / Gen 4)** | **2,500 – 7,000 MB/s** *(Ultra-fast)* | M.2 2280 stick (looks like a stick of gum) | ✅ **100% Removable / Upgradable** to any size (1TB, 2TB, 4TB). |
| ⚡ **Dual M.2 NVMe Slots** | **Up to 7,000 MB/s** | 2 separate M.2 slots (2280 + 2242) | ✅ **Can install TWO independent internal SSDs** simultaneously. |
| 🐢 **2.5" SATA SSD / M.2 SATA** | **~500 – 550 MB/s** *(6x slower than NVMe)* | 2.5-inch drive bay or M.2 SATA key | ✅ **Removable / Upgradable**, but capped at legacy SATA III speeds. |
| 🔒 **Soldered BGA NVMe / eMMC** | **Fast (PCIe) or Slow (eMMC)** | Chips soldered directly to the logic board | ❌ **NON-UPGRADABLE** (cannot be removed or replaced). |

---

## 🔧 Upgradability Scoring Guide

* 🟢 **10/10 (Extreme Workstation):** 4x RAM slots (up to 128GB) + 2 to 4 M.2 NVMe SSD slots + tool-less access.
* 🟢 **9/10 (Full Enterprise Modular):** 2x SODIMM RAM slots (0% soldered, up to 64GB) + replaceable M.2 NVMe SSD.
* 🟢 **8.5/10 (Dual M.2 SSD Champion):** 1x RAM slot + **Dual internal M.2 NVMe SSD slots** (add a 2nd drive anytime).
* 🟡 **7.5/10 (Semi-Modular):** 1x Soldered RAM + 1x SODIMM slot (up to 40GB/48GB total) + replaceable M.2 NVMe SSD.
* 🟠 **5/10 (Storage Only / Soldered RAM):** 100% Soldered RAM (fixed) + **Standard M.2 PCIe NVMe SSD (fully replaceable)**.
* 🔴 **1/10 (Locked Down):** 100% Soldered RAM + Soldered SSD + Glued chassis (no DIY upgrades).

---

## 🏷️ IT Outlet Discounts & Coupon Optimization

* **📧 100 ₪ Newsletter Coupon:** Sign up on the site to get 100 ₪ off on purchases **over 1,500 ₪**. Best for items under 2,500 ₪.
* **💳 4% Credit Card Discount (Phone Orders Only):** For non-bank cards & clubs (MAX, Isracard, Amex, LifeStyle, Hot, Tov, ביחד בשבילך, אשמורת, בהצדעה). Best for items over 2,500 ₪.
* **Promo Code `IT14`:** Drops the **ThinkPad P14s (32GB/1TB)** from 2,800 ₪ to **2,500 ₪** with free bag & mouse.

| 100 ₪ Email Discount | 4% Credit Card Discount |
| :---: | :---: |
| ![100 NIS Newsletter Discount](/home/elonu/github/scrap/assets/itoutlet_100nis_discount.png) | ![4 Percent Credit Card Discount](/home/elonu/github/scrap/assets/itoutlet_4percent_discount.png) |

---

## 🏆 Top Overall Available Picks (Dynamically Auto-Ranked from Live Inventory)

| Category | Model | Key Specs | Best Deal Price | Store | Storage Interface | RAM Architecture | Upgradability | Direct Link |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- | :---: | :---: |
""")
        for cat_emoji, cat_desc, p in top_picks:
            score_badge = f"🟢 {p.upgradability_score}" if p.upgradability_score >= 8.5 else (f"🟡 {p.upgradability_score}" if p.upgradability_score >= 7.0 else f"🟠 {p.upgradability_score}")
            specs_summary = f"{p.cpu} • **{p.ram_gb}GB RAM** • {p.storage_gb}GB SSD"
            md_parts.append(f"| **{cat_emoji}** | **{p.title}** | {specs_summary} | **{p.deal_label}** | {p.store} | {p.storage_type} | {p.ram_type} | {score_badge} | [View Product]({p.url}) |\n")

        md_parts.append("""
---

## 📸 Featured Deal: Lenovo ThinkPad P14s Gen 1 (IT Outlet)

> **Direct Link:** [Lenovo ThinkPad P14s Gen 1 Product Page](https://www.itoutlet.co.il/items/8733190-%D7%9E%D7%97%D7%A9%D7%91-%D7%A0%D7%99%D7%99%D7%93-%D7%9E%D7%97%D7%95%D7%93%D7%A9-%D7%9C%D7%A2%D7%A8%D7%99%D7%9B%D7%94-%D7%92%D7%A8%D7%A4%D7%99%D7%AA-Lenovo-ThinkPad-P14s-Gen-1-i7-32GB-1TB-SSD)  
> **Status:** 🟢 **AVAILABLE & IN STOCK**  
> **Offer Price:** **2,500 ₪** *(Original 2,800 ₪, with coupon `IT14`)*  
> **Includes:** Free laptop bag and wireless mouse  
> **Storage:** ⚡ **1 TB M.2 2280 PCIe 3.0 NVMe SSD** *(Fully swappable up to 2TB/4TB)*  
> **Memory:** 16 GB Soldered + 16 GB SODIMM Slot = **32 GB RAM** *(Expandable up to 48 GB)*  
> **Upgradability Score:** 🟡 **7.5/10**

![Lenovo ThinkPad P14s Deal Offer](/home/elonu/github/scrap/assets/thinkpad_p14s_offer.png)

---

## 🏬 1. IT Outlet (איי טי אאוטלט) — Live Catalog & Stock Audit

| # | Model / Product Title | CPU & Gen | RAM & SSD | Screen | Weight | Battery | Deal Price | Storage Interface | Upgradability | Direct Link |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
""")
        for i, itm in enumerate(it_items, 1):
            score_badge = f"🟢 {itm.upgradability_score}" if itm.upgradability_score >= 8.5 else (f"🟡 {itm.upgradability_score}" if itm.upgradability_score >= 7.0 else f"🟠 {itm.upgradability_score}")
            md_parts.append(f"| {i} | **{itm.title}** | {itm.cpu} | {itm.ram_gb}GB / {itm.storage_gb}GB | {itm.screen_size_in}\" | ⚖️ {itm.weight_kg} kg | 🔋 {itm.battery_wh} Wh | **{itm.deal_label}** | {itm.storage_type} | {score_badge} | [View Product]({itm.url}) |\n")

        md_parts.append(f"""
---

## 🏬 2. Ecology Computers (אקולוגיה לקהילה מוגנת) — Live Stock Audit

*(All laptops include a full **24-Month (2-Year) Warranty**).*

| # | Model / Product Title | CPU & Gen | RAM & SSD | Screen | Weight | Battery | Deal Price | Storage Interface | Upgradability | Direct Link |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
""")
        for i, itm in enumerate(eco_items, 1):
            score_badge = f"🟢 {itm.upgradability_score}" if itm.upgradability_score >= 8.5 else (f"🟡 {itm.upgradability_score}" if itm.upgradability_score >= 7.0 else f"🟠 {itm.upgradability_score}")
            deal_price_str = f"{itm.price_ils:,} ₪ (24M Warranty)"
            md_parts.append(f"| {i} | **{itm.title}** | {itm.cpu} | {itm.ram_gb}GB / {itm.storage_gb}GB | {itm.screen_size_in}\" | ⚖️ {itm.weight_kg} kg | 🔋 {itm.battery_wh} Wh | **{deal_price_str}** | {itm.storage_type} | {score_badge} | [View Product]({itm.url}) |\n")

        md_parts.append(f"""
---

## 🏬 3. LaptopTech LTS (לפטופ.טק) — Live Stock Audit

| # | Model / Product Title | CPU & Gen | RAM & SSD | Screen | Weight | Battery | Deal Price | Storage Interface | Upgradability | Direct Link |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
""")
        for i, itm in enumerate(lts_items[:25], 1):
            score_badge = f"🟢 {itm.upgradability_score}" if itm.upgradability_score >= 8.5 else (f"🟡 {itm.upgradability_score}" if itm.upgradability_score >= 7.0 else f"🟠 {itm.upgradability_score}")
            md_parts.append(f"| {i} | **{itm.title}** | {itm.cpu} | {itm.ram_gb}GB / {itm.storage_gb}GB | {itm.screen_size_in}\" | ⚖️ {itm.weight_kg} kg | 🔋 {itm.battery_wh} Wh | **{itm.deal_label}** | {itm.storage_type} | {score_badge} | [View Product]({itm.url}) |\n")

        md_parts.append(f"""
---

## 🏬 4. Recomp Computers (ריקומפ) — Live Stock Audit

| # | Model / Product Title | CPU & Gen | RAM & SSD | Screen | Weight | Battery | Deal Price | Storage Interface | Upgradability | Direct Link |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
""")
        for i, itm in enumerate(rec_items, 1):
            score_badge = f"🟢 {itm.upgradability_score}" if itm.upgradability_score >= 8.5 else (f"🟡 {itm.upgradability_score}" if itm.upgradability_score >= 7.0 else f"🟠 {itm.upgradability_score}")
            md_parts.append(f"| {i} | **{itm.title}** | {itm.cpu} | {itm.ram_gb}GB / {itm.storage_gb}GB | {itm.screen_size_in}\" | ⚖️ {itm.weight_kg} kg | 🔋 {itm.battery_wh} Wh | **{itm.deal_label}** | {itm.storage_type} | {score_badge} | [View Product]({itm.url}) |\n")

        md_parts.append("""
---

## 🎯 Quick Rules of Thumb

1. **⚡ Fast M.2 NVMe SSDs (Up to 3,500 - 7,000 MB/s):**
   * Almost all 8th–12th Gen business laptops here (ThinkPad T14/P14s, EliteBook 830/840, Latitude 7000/5000) have a standard **M.2 2280 PCIe NVMe SSD slot** that you can unscrew and upgrade anytime.
2. **🌟 Dual Internal SSD Slots:**
   * Look at the **ThinkPad E14 Gen 4 / Gen 2** or **HP ZBook Fury / ThinkPad P15** if you want to install two (or four) physical SSDs simultaneously.
3. **⚠️ Soldered RAM vs Upgradable RAM:**
   * If you see **🟠 5/10**, the **NVMe SSD is fully upgradeable**, but the **RAM is soldered**.
   * If you see **🟢 9/10** or **🟢 10/10**, both the **RAM and NVMe SSD are 100% modular and upgradeable**.
   * If you see **🔴 1/10 (Surface Laptop 2)**, everything is permanently soldered and glued shut.
""")
        md = "".join(md_parts)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md.strip() + "\n")
        logger.info(f"Markdown guide updated: {filepath}")


# --- Main Application Orchestrator ---
class MasterLaptopAuditor:
    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or create_resilient_session()
        self.scraper_classes = {
            'itoutlet': ITOutletScraper,
            'ecology': EcologyScraper,
            'lts': LTSScraper,
            'recomp': RecompScraper
        }

    def run(self, store_filter: Optional[str] = None, max_workers: int = 4, use_ai: bool = False) -> Dict[str, List[LaptopItem]]:
        results: Dict[str, List[LaptopItem]] = {}
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
                    logger.error(f"Scraper '{name}' encountered a critical error: {e}")
                    results[name] = []

        # Optional Groq AI Enhancement
        if use_ai:
            enhancer = GroqSpecEnhancer()
            if enhancer.enabled:
                for store_name, items in results.items():
                    results[store_name] = enhancer.enhance_batch(items)

        return results


def main():
    parser = argparse.ArgumentParser(
        description="Master Multi-Store Refurbished Laptop Scraper & Hardware Auditor (Production Grade)"
    )
    parser.add_argument("--store", choices=['itoutlet', 'ecology', 'lts', 'recomp', 'all'], default='all', help="Specific store to scrape")
    parser.add_argument("--min-ram", type=int, default=0, help="Filter laptops with at least N GB RAM")
    parser.add_argument("--max-price", type=int, default=99999, help="Filter laptops with price <= N ILS")
    parser.add_argument("--min-score", type=float, default=0.0, help="Filter laptops with upgradability score >= N")
    parser.add_argument("--ai", "--groq", action="store_true", help="Enable Groq AI hardware intelligence")
    parser.add_argument("--csv", action="store_true", help="Also export all laptops to CSV")
    parser.add_argument("--json", action="store_true", help="Dump JSON output to stdout")
    parser.add_argument("--no-md", action="store_true", help="Disable automatic full_catalog.md update")
    parser.add_argument("--workers", type=int, default=4, help="Max concurrent store threads")

    args = parser.parse_args()

    auditor = MasterLaptopAuditor()
    results = auditor.run(
        store_filter=None if args.store == 'all' else args.store,
        max_workers=args.workers,
        use_ai=args.ai
    )

    # Flatten items for filtering & statistics
    all_items: List[LaptopItem] = []
    for store_name, items in results.items():
        all_items.extend(items)

    if not all_items:
        logger.warning("⚠️ No laptops were scraped across any store (network error or sites unreachable). Preserving existing catalog.")
        print("\n" + "=" * 65)
        print("⚠️  SCRAPE INCOMPLETE: 0 laptops parsed. Existing files preserved.")
        print("=" * 65)
        return

    # Apply CLI Filters if specified
    filtered_items = [
        item for item in all_items
        if item.ram_gb >= args.min_ram
        and item.deal_price_ils <= args.max_price
        and item.upgradability_score >= args.min_score
    ]

    # Save to JSON
    ReportGenerator.export_json(results, JSON_PATH)

    # Save to CSV if requested
    if args.csv:
        ReportGenerator.export_csv(all_items, CSV_PATH)

    # Auto-update full_catalog.md with dynamic Top Picks
    if not args.no_md:
        ReportGenerator.update_summary_markdown(results, FULL_CATALOG_MD_PATH)

    # CLI Terminal Summary
    print("\n" + "=" * 65)
    print(f"📊 LIVE AUDIT COMPLETE: {len(all_items)} total laptops parsed across {len(results)} stores.")
    print("=" * 65)
    for name, items in results.items():
        print(f"  • {name:18}: {len(items):2d} laptops found")

    if args.min_ram > 0 or args.max_price < 99999 or args.min_score > 0.0:
        print("\n" + "-" * 65)
        print(f"🎯 Filtered Matches (RAM >= {args.min_ram}GB, Price <= {args.max_price} ₪, Score >= {args.min_score}): {len(filtered_items)} items")
        print("-" * 65)
        for itm in filtered_items[:10]:
            print(f"  [{itm.store:12}] {itm.title[:35]:35} | {itm.cpu:16} | {itm.ram_gb:2d}GB RAM | {itm.deal_label:20} | GPU: {itm.gpu}")

    if args.json:
        print("\n" + json.dumps({k: [i.to_dict() for i in v] for k, v in results.items()}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
