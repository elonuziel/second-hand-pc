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
    detect_ram_generation = HardwareClassifier.detect_ram_generation

    @classmethod
    def enrich_item_dict(cls, laptop: Dict[str, Any]) -> Dict[str, Any]:
        title = laptop.get("title") or laptop.get("model") or ""

        # Clean brand & series if title provides exact detection
        current_brand = laptop.get("brand", "")
        detected_brand = HardwareClassifier.detect_brand(title)
        if detected_brand != "Business Laptop" or not current_brand:
            laptop["brand"] = detected_brand

        current_series = laptop.get("series", "")
        detected_series = HardwareClassifier.detect_series(title)
        if detected_series != "Business Series" or not current_series:
            laptop["series"] = detected_series

        # Detect and enrich CPU specification
        current_cpu = laptop.get("cpu", "")
        detected_cpu = HardwareClassifier.detect_cpu(title)
        if detected_cpu in ("Intel Core", "Core i5", "Core i7", "Core i3", "AMD Ryzen") and current_cpu and current_cpu != detected_cpu:
            combined_detected = HardwareClassifier.detect_cpu(f"{title} {current_cpu}")
            if "gen" in combined_detected.lower():
                detected_cpu = combined_detected
        laptop["cpu"] = detected_cpu or current_cpu

        # Enrich storage if misdetected or defaulted to 512
        current_storage = laptop.get("storage_gb")
        detected_storage = HardwareClassifier.detect_storage_gb(title)
        if not current_storage or (current_storage == 512 and detected_storage in (32, 64, 120, 128, 160, 180, 240, 250, 256, 320, 480, 1000, 2000)):
            laptop["storage_gb"] = detected_storage

        # Architectural analysis for ram_type if missing or needs update
        score, storage_type, ram_type = HardwareClassifier.analyze_architecture(title)
        if not laptop.get("ram_type") or "LPDDR4x/5" in laptop.get("ram_type", "") or "435" in title:
            laptop["ram_type"] = ram_type
            laptop["upgradability_score"] = score
            laptop["storage_type"] = storage_type
        current_ram_type = laptop.get("ram_type", ram_type)

        # Accurately compute screen_size_in, weight_kg, battery_wh, and ram_gen based on verified heuristics
        if laptop.get("screen_source") == "listing_explicit" and laptop.get("screen_size_in"):
            screen_size = laptop["screen_size_in"]
            screen_src = "listing_explicit"
        else:
            screen_size, screen_src = cls.detect_screen_size(title, return_source=True)

        if laptop.get("weight_source") == "listing_explicit" and laptop.get("weight_kg"):
            weight_kg = laptop["weight_kg"]
            weight_src = "listing_explicit"
        else:
            weight_kg, weight_src = cls.detect_weight_kg(title, screen_size, return_source=True)

        if laptop.get("battery_source") == "listing_explicit" and laptop.get("battery_wh"):
            battery_wh = laptop["battery_wh"]
            battery_src = "listing_explicit"
        else:
            battery_wh, battery_src = cls.detect_battery_wh(title, weight_kg, return_source=True)

        ram_gen, ram_src = cls.detect_ram_generation(title, cpu=laptop.get("cpu", ""), ram_type=current_ram_type, return_source=True)

        laptop["screen_size_in"] = round(screen_size, 1)
        laptop["weight_kg"] = round(weight_kg, 2)
        laptop["battery_wh"] = battery_wh
        laptop["ram_gen"] = ram_gen
        laptop["ram_source"] = ram_src
        laptop["screen_source"] = screen_src
        laptop["weight_source"] = weight_src
        laptop["battery_source"] = battery_src

        is_2in1 = laptop.get("is_2in1") or HardwareClassifier.is_2in1(title)
        weight_warn, battery_warn = HardwareClassifier.validate_hardware_sanity(
            title=title,
            screen_size=screen_size,
            weight_kg=weight_kg,
            battery_wh=battery_wh,
            is_2in1=is_2in1,
        )
        laptop["weight_warning"] = weight_warn
        laptop["battery_warning"] = battery_warn
        if weight_warn or battery_warn:
            laptop["confidence_level"] = "warning"
        else:
            laptop["confidence_level"] = "estimated" if (screen_src == "fallback_estimate" or weight_src == "fallback_estimate" or ram_src == "fallback_estimate") else "verified"

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
                raw_item["ram_gen"] = audited_item.ram_gen
                raw_item["ram_source"] = audited_item.ram_source
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
