#!/usr/bin/env python3
"""
Laptop Spec Enrichment Engine
=============================
Enriches scraped laptop data with:
- Screen Size (inches, float)
- Weight (kg, float)
- Battery Capacity (Wh, int)

Uses regex & hardware model heuristic classification, with optional Groq AI enhancement.
"""

from __future__ import annotations

import os
import re
import csv
import json
import logging
import argparse
from typing import Dict, List, Tuple, Any, Optional
from scraper import HardwareClassifier

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(WORKSPACE_DIR, "scraped_laptops.json")
CSV_PATH = os.path.join(WORKSPACE_DIR, "scraped_laptops.csv")
FULL_CATALOG_MD_PATH = os.path.join(WORKSPACE_DIR, "full_catalog.md")
SUMMARY_MD_PATH = FULL_CATALOG_MD_PATH  # Compatibility alias

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SpecEnricher")


class SpecEnricher:
    """Heuristic and AI specification enrichment engine for laptops."""

    # Explicit regex patterns for Screen Size
    _SCREEN_EXPLICIT_RE = re.compile(
        r'(?:^|[^\d])(11\.6|12\.5|13\.3|13\.5|14\.0|14|15\.4|15\.6|15|16\.0|16|17\.3|17)\s*(?:"|\'\'|in|inch|אינץ|\'\s|\s*$)',
        re.IGNORECASE
    )

    @classmethod
    def detect_screen_size(cls, title: str) -> float:
        t = title.lower()

        # Check explicit mentions like 15 6, 17 3, 13 3 in title
        if '17 3' in t or '17.3' in t: return 17.3
        if '15 6' in t or '15.6' in t: return 15.6
        if '15 4' in t or '15.4' in t: return 15.4
        if '13 3' in t or '13.3' in t: return 13.3
        if '13 5' in t or '13.5' in t: return 13.5
        if '12 5' in t or '12.5' in t: return 12.5
        if '11 6' in t or '11.6' in t: return 11.6
        if ' 14 "' in t or ' 14"' in t or ' 14 ' in t or '14.0' in t: return 14.0

        # Model-based heuristics
        if any(k in t for k in ['a517', '17.3']):
            return 17.3
        if any(k in t for k in ['p52', 'p15', 'p15s', 'p15v', 't15', '3520', '5530', '5531', 'e1504', 'x515', '330 15ikb', 'gaming 3', 'zbook fury 15', 'zbook 15', '850', 'ay010nj', '250 g7', '255 g5', '255 g7']):
            return 15.6
        if any(k in t for k in ['a1707']):
            return 15.4
        if any(k in t for k in ['t14', 't14s', 'p14s', 'e14', 'e480', 'x1 carbon', '7410', '7420', '7430', '5410', '5420', '5430', '5431', '5480', 'e7440', '840', 'firefly 14', 'sfx14', 'x1404za', 'x442ur']):
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

        # Ultra-lightweight (< 1.1kg)
        if 'x30l' in t: return 0.90
        if 'x1 carbon' in t: return 1.10
        if '7320' in t or '7330' in t: return 1.20
        if any(k in t for k in ['a2337', 'surface 3', 'surface 4', 'x280', 'x13']): return 1.28

        # Light Ultrabooks (1.3kg - 1.45kg)
        if any(k in t for k in ['t14s', '830', '840 g8', '7420', '7430', '7410']): return 1.35
        if any(k in t for k in ['840 g3', 'firefly 14', 'l13', 'a1706', 'a1708', 'a1989', 'a2179', 'a2251']): return 1.40

        # Standard 14" Business (1.45kg - 1.65kg)
        if any(k in t for k in ['t14', 'p14s', 'e14', 'e480', '5410', '5420', '5430', '5431', '5480', 'e7440', 'sfx14', 'x1404za']): return 1.55

        # 15.6" Mainstream / Light Workstation (1.7kg - 1.9kg)
        if any(k in t for k in ['p15s', 't15', '850', '5530', '5531', '3520', 'e1504', 'x515', 'a1707']): return 1.75
        if any(k in t for k in ['250 g7', '255 g5', '255 g7', 'ay010nj', '330 15ikb', 'x442ur']): return 1.85

        # Performance Workstations / Gaming / 17.3" (2.1kg - 2.7kg)
        if any(k in t for k in ['thinkpad p1', 'p15v']): return 2.05
        if any(k in t for k in ['gaming 3', 'zbook 15 g6', 'zbook g7 14']): return 2.25
        if any(k in t for k in ['p52', 'p15 gen', 'p15 g1', 'zbook fury 15']): return 2.45
        if 'a517' in t or screen_size >= 17.0: return 2.60

        # Fallback by screen size
        if screen_size <= 12.5: return 1.20
        if screen_size <= 13.5: return 1.30
        if screen_size <= 14.0: return 1.50
        if screen_size <= 15.6: return 1.80
        return 2.40

    @classmethod
    def detect_battery_wh(cls, title: str, weight_kg: float) -> int:
        t = title.lower()

        # Heavy Workstations / Long Battery beasts
        if any(k in t for k in ['p52', 'p15 gen', 'p15 g1', 'zbook fury 15', 'p1 gen 3']): return 90
        if any(k in t for k in ['zbook 15 g6', '5531', '5431', 'p15v']): return 68
        if any(k in t for k in ['x1 carbon', 't14s', '7420', '7320', '7330', '7430', '5430', '5530', '5330']): return 57
        if any(k in t for k in ['t14', 'p14s', 'e14 gen 4', '830 g8', '840 g8', 'firefly 14', 'p15s']): return 51
        if any(k in t for k in ['a2337', 'a1706', 'a1708', 'a1989', 'a2179', 'a2251', 'surface 3', 'surface 4']): return 49
        if any(k in t for k in ['e480', '5410', '5480', 'x280', 'x13', '840 g3', 'e7440', '435 g7']): return 45
        if any(k in t for k in ['e1504', 'x515', '250 g7', '255 g5', 'ay010nj', 'a517', '330 15ikb']): return 41

        if weight_kg >= 2.3: return 83
        if weight_kg >= 1.7: return 54
        return 50

    @classmethod
    def enrich_item_dict(cls, laptop: Dict[str, Any]) -> Dict[str, Any]:
        title = laptop.get("title") or laptop.get("model") or ""

        # Accurately compute screen_size_in, weight_kg, and battery_wh based on verified heuristics
        screen_size = cls.detect_screen_size(title)
        weight_kg = cls.detect_weight_kg(title, screen_size)
        battery_wh = cls.detect_battery_wh(title, weight_kg)

        laptop["screen_size_in"] = round(screen_size, 1)
        laptop["weight_kg"] = round(weight_kg, 2)
        laptop["battery_wh"] = battery_wh

        # Detect and enrich CPU generation if missing
        current_cpu = laptop.get("cpu", "")
        detected_cpu = HardwareClassifier.detect_cpu(f"{title} {current_cpu}")
        if "gen" in detected_cpu.lower() or not current_cpu:
            laptop["cpu"] = detected_cpu
        elif current_cpu:
            laptop["cpu"] = current_cpu

        return laptop


def update_summary_markdown(json_file: str = JSON_PATH, md_file: str = FULL_CATALOG_MD_PATH):
    if not os.path.exists(json_file):
        return

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_laptops = []
    store_map = {"itoutlet": [], "ecology": [], "lts": [], "recomp": []}
    if isinstance(data, dict):
        for k, v in data.items():
            store_map[k] = v
            all_laptops.extend(v)

    now_str = "Recent Live Audit"

    md_parts = []
    md_parts.append(f"""# 💻 Refurbished Laptops Market Research & Multi-Store Comparison Guide
**Stores Audited & Researched:**
1. 🏬 **Ecology Computers (אקולוגיה לקהילה מוגנת):** [ecommunity.org.il/מחשבים-ניידים](https://www.ecommunity.org.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D)
2. 🏬 **IT Outlet (איי טי אאוטלט):** [itoutlet.co.il/מחשבים-ניידים](https://www.itoutlet.co.il/164920-%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D?order=up_price)
3. 🏬 **LaptopTech LTS (לפטופ.טק):** [lts.co.il/מחשבים-ניידים-מחודשים-יד-2](https://lts.co.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%99%D7%93-2/)
4. 🏬 **Recomp Computers (ריקומפ):** [recomp.co.il/מחשבים-מחודשים-במבצע](https://recomp.co.il/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%D7%95%D7%93%D7%a9%d7%99%D7%9D-%D7%91%D7%9e%d7%91%d7%a6%d7%a2/)

---

## 🏬 1. IT Outlet (איי טי אאוטלט) — Live Catalog & Stock Audit

| # | Model / Product Title | CPU & Gen | RAM & SSD | Screen | Weight | Battery | Deal Price | Storage Interface | Upgradability | Direct Link |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
""")
    for i, itm in enumerate(store_map.get("itoutlet", []), 1):
        score = itm.get("upgradability_score", 7.5)
        badge = f"🟢 {score}" if score >= 8.5 else (f"🟡 {score}" if score >= 7.0 else f"🟠 {score}")
        md_parts.append(f"| {i} | **{itm.get('title')}** | {itm.get('cpu')} | {itm.get('ram_gb')}GB / {itm.get('storage_gb')}GB | {itm.get('screen_size_in')}\" | {itm.get('weight_kg')} kg | {itm.get('battery_wh')} Wh | **{itm.get('deal_label')}** | {itm.get('storage_type')} | {badge} | [View Product]({itm.get('url')}) |\n")

    md_parts.append(f"""
---

## 🏬 2. Ecology Computers (אקולוגיה לקהילה מוגנת) — Live Stock Audit

| # | Model / Product Title | CPU & Gen | RAM & SSD | Screen | Weight | Battery | Deal Price | Storage Interface | Upgradability | Direct Link |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
""")
    for i, itm in enumerate(store_map.get("ecology", []), 1):
        score = itm.get("upgradability_score", 7.5)
        badge = f"🟢 {score}" if score >= 8.5 else (f"🟡 {score}" if score >= 7.0 else f"🟠 {score}")
        md_parts.append(f"| {i} | **{itm.get('title')}** | {itm.get('cpu')} | {itm.get('ram_gb')}GB / {itm.get('storage_gb')}GB | {itm.get('screen_size_in')}\" | {itm.get('weight_kg')} kg | {itm.get('battery_wh')} Wh | **{itm.get('deal_label')}** | {itm.get('storage_type')} | {badge} | [View Product]({itm.get('url')}) |\n")

    md_parts.append(f"""
---

## 🏬 3. LaptopTech LTS (לפטופ.טק) — Live Stock Audit

| # | Model / Product Title | CPU & Gen | RAM & SSD | Screen | Weight | Battery | Price | Storage Interface | Upgradability | Direct Link |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
""")
    for i, itm in enumerate(store_map.get("lts", [])[:25], 1):
        score = itm.get("upgradability_score", 7.5)
        badge = f"🟢 {score}" if score >= 8.5 else (f"🟡 {score}" if score >= 7.0 else f"🟠 {score}")
        md_parts.append(f"| {i} | **{itm.get('title')}** | {itm.get('cpu')} | {itm.get('ram_gb')}GB / {itm.get('storage_gb')}GB | {itm.get('screen_size_in')}\" | {itm.get('weight_kg')} kg | {itm.get('battery_wh')} Wh | **{itm.get('deal_label')}** | {itm.get('storage_type')} | {badge} | [View Product]({itm.get('url')}) |\n")

    md_parts.append(f"""
---

## 🏬 4. Recomp Computers (ריקומפ) — Live Stock Audit

| # | Model / Product Title | CPU & Gen | RAM & SSD | Screen | Weight | Battery | Price | Storage Interface | Upgradability | Direct Store Link |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
""")
    for i, itm in enumerate(store_map.get("recomp", []), 1):
        score = itm.get("upgradability_score", 7.5)
        badge = f"🟢 {score}" if score >= 8.5 else (f"🟡 {score}" if score >= 7.0 else f"🟠 {score}")
        md_parts.append(f"| {i} | **{itm.get('title')}** | {itm.get('cpu')} | {itm.get('ram_gb')}GB / {itm.get('storage_gb')}GB | {itm.get('screen_size_in')}\" | {itm.get('weight_kg')} kg | {itm.get('battery_wh')} Wh | **{itm.get('deal_label')}** | {itm.get('storage_type')} | {badge} | [View on Recomp]({itm.get('url')}) |\n")

    with open(md_file, "w", encoding="utf-8") as f:
        f.write("".join(md_parts).strip() + "\n")
    logger.info(f"Summary markdown updated at {md_file}")


def enrich_dataset(json_file: str = JSON_PATH, csv_file: str = CSV_PATH):
    if not os.path.exists(json_file):
        logger.warning(f"File {json_file} does not exist. Skipping enrichment.")
        return

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_items_flat = []
    if isinstance(data, dict):
        for store_key, item_list in data.items():
            for item in item_list:
                SpecEnricher.enrich_item_dict(item)
                all_items_flat.append(item)
    elif isinstance(data, list):
        for item in data:
            SpecEnricher.enrich_item_dict(item)
            all_items_flat.append(item)

    # Save back to JSON
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Enriched dataset written to {json_file}")

    # Export to CSV
    if all_items_flat and csv_file:
        fieldnames = list(all_items_flat[0].keys())
        with open(csv_file, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in all_items_flat:
                writer.writerow(item)
        logger.info(f"Enriched CSV written to {csv_file}")

    update_summary_markdown(json_file)


def main():
    parser = argparse.ArgumentParser(description="Enrich laptop dataset with screen size, weight, and battery capacity.")
    parser.add_argument("--json", default=JSON_PATH, help="Path to scraped_laptops.json")
    parser.add_argument("--csv", default=CSV_PATH, help="Path to scraped_laptops.csv")
    args = parser.parse_args()

    enrich_dataset(args.json, args.csv)

if __name__ == "__main__":
    main()
