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
from typing import Dict, List, Tuple, Any, Optional, Union
from scraper import HardwareClassifier, LaptopItem, ReportGenerator, GroqSpecEnhancer

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(WORKSPACE_DIR, "scraped_laptops.json")
CSV_PATH = os.path.join(WORKSPACE_DIR, "scraped_laptops.csv")
FULL_CATALOG_MD_PATH = os.path.join(WORKSPACE_DIR, "full_catalog.md")
SUMMARY_MD_PATH = FULL_CATALOG_MD_PATH  # Compatibility alias

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SpecEnricher")


class SpecEnricher:
    """Heuristic and AI specification enrichment engine for laptops."""

    detect_screen_size = HardwareClassifier.detect_screen_size
    detect_weight_kg = HardwareClassifier.detect_weight_kg
    detect_battery_wh = HardwareClassifier.detect_battery_wh

    @classmethod
    def enrich_item_dict(cls, laptop: Dict[str, Any]) -> Dict[str, Any]:
        title = laptop.get("title") or laptop.get("model") or ""

        # Accurately compute screen_size_in, weight_kg, and battery_wh based on verified heuristics
        screen_size, screen_src = cls.detect_screen_size(title, return_source=True)
        weight_kg, weight_src = cls.detect_weight_kg(title, screen_size, return_source=True)
        battery_wh, battery_src = cls.detect_battery_wh(title, weight_kg, return_source=True)

        laptop["screen_size_in"] = round(screen_size, 1)
        laptop["weight_kg"] = round(weight_kg, 2)
        laptop["battery_wh"] = battery_wh
        laptop["screen_source"] = screen_src
        laptop["weight_source"] = weight_src
        laptop["battery_source"] = battery_src
        laptop["confidence_level"] = "estimated" if (screen_src == "fallback_estimate" or weight_src == "fallback_estimate") else "verified"

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

    store_map: Dict[str, List[LaptopItem]] = {"itoutlet": [], "ecology": [], "lts": [], "recomp": []}
    if isinstance(data, dict):
        for k, v in data.items():
            laptop_items = []
            for itm in v:
                fields = {f: itm[f] for f in itm if f in LaptopItem.__dataclass_fields__}
                laptop_items.append(LaptopItem(**fields))
            store_map[k] = laptop_items
    elif isinstance(data, list):
        for itm in data:
            st = itm.get("store", "").lower().replace(" ", "")
            key = "itoutlet" if "itoutlet" in st else ("ecology" if "eco" in st else ("lts" if "lts" in st else "recomp"))
            fields = {f: itm[f] for f in itm if f in LaptopItem.__dataclass_fields__}
            if key in store_map:
                store_map[key].append(LaptopItem(**fields))

    ReportGenerator.update_summary_markdown(store_map, md_file)
    logger.info(f"Summary markdown updated at {md_file}")


def enrich_dataset(json_file: str = JSON_PATH, csv_file: str = CSV_PATH, use_ai: bool = False):
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

    if use_ai:
        enhancer = GroqSpecEnhancer()
        if enhancer.enabled:
            logger.info(f"🤖 Running Groq AI spec audit on {len(all_items_flat)} laptops...")
            items_to_audit = []
            for item in all_items_flat:
                fields = {f: item[f] for f in item if f in LaptopItem.__dataclass_fields__}
                items_to_audit.append(LaptopItem(**fields))
            audited = enhancer.enhance_batch(items_to_audit)
            for raw_item, audited_item in zip(all_items_flat, audited):
                raw_item["screen_size_in"] = audited_item.screen_size_in
                raw_item["weight_kg"] = audited_item.weight_kg
                raw_item["battery_wh"] = audited_item.battery_wh
                raw_item["gpu"] = audited_item.gpu
                raw_item["is_touch"] = audited_item.is_touch
                raw_item["is_2in1"] = audited_item.is_2in1
                raw_item["upgradability_score"] = audited_item.upgradability_score
                raw_item["screen_source"] = audited_item.screen_source
                raw_item["weight_source"] = audited_item.weight_source
                raw_item["battery_source"] = audited_item.battery_source
                raw_item["confidence_level"] = audited_item.confidence_level
        else:
            logger.warning("Groq API key not found. Skipping AI audit.")

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
    parser.add_argument("--ai", action="store_true", help="Enable Groq AI hardware spec audit")
    args = parser.parse_args()

    enrich_dataset(args.json, args.csv, use_ai=args.ai)

if __name__ == "__main__":
    main()
