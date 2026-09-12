#!/usr/bin/env python3
"""
Refurbished Laptops Master Multi-Store Scraper & Hardware Auditor
================================================================
Enterprise-grade, modular, and resilient scraper for Israeli refurbished PC stores.
Orchestrates concurrent store scrapers, hardware classification, AI enrichment,
and catalog reporting.

Re-exports core domain models and adapters for full backwards compatibility.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Optional

import requests
import urllib3

# Suppress insecure SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Core Domain & Utility Imports (Re-exported for backwards compatibility) ---
from laptop_domain import LaptopItem
from laptop_parsing import is_desktop_title, is_laptop_title, last_valid_price, parse_price_value
from laptop_classification import HardwareClassifier
from laptop_ai import GroqSpecEnhancer, get_groq_api_key
from laptop_recommendations import TopPicksEngine
from laptop_reports import (
    ReportGenerator,
    WORKSPACE_DIR,
    FULL_CATALOG_MD_PATH,
    SUMMARY_MD_PATH,
    JSON_PATH,
    CSV_PATH,
    ENV_FILE_PATH,
)
from laptop_pipeline import run_store_scrapers
from http_session import create_resilient_session, fetch_resilient_url, DEFAULT_HEADERS

# --- Store Scrapers ---
from laptop_scrapers import (
    ITOutletScraper,
    EcologyScraper,
    LTSScraper,
    RecompScraper,
    CWCScraper,
    PayngoScraper,
    ALMScraper,
    ShufersalScraper,
    P1000Scraper,
    LastPriceScraper,
    VoltScraper,
    OfekPCScraper,
    DEFAULT_SCRAPER_CLASSES,
)

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("LaptopAuditor")


# --- Main Application Orchestrator ---
class MasterLaptopAuditor:
    """Orchestrates store scraping, concurrent execution, and AI spec enhancement."""

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or create_resilient_session()
        self.scraper_classes = dict(DEFAULT_SCRAPER_CLASSES)

    def run(self, store_filter: Optional[str] = None, max_workers: int = 6, use_ai: bool = False) -> Dict[str, List[LaptopItem]]:
        results = run_store_scrapers(
            scraper_classes=self.scraper_classes,
            session=self.session,
            store_filter=store_filter,
            max_workers=max_workers,
            logger=logger,
        )

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
    store_choices = list(DEFAULT_SCRAPER_CLASSES.keys()) + ['all']
    parser.add_argument(
        "--store",
        choices=store_choices,
        default='all',
        help="Specific store to scrape"
    )
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
