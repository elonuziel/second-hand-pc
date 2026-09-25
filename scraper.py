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
from laptop_pipeline import get_store_blocks, run_store_scrapers
from http_session import create_resilient_session, fetch_rendered_url, fetch_resilient_url, DEFAULT_HEADERS

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


def _print_store_status(results, fresh_counts, preserved_counts) -> None:
    """Prints which stores produced nothing fresh, why, and whether preserved data covered it."""
    status_lines = ReportGenerator.build_store_status_lines(
        list(results.keys()), fresh_counts, preserved_counts, get_store_blocks()
    )
    if status_lines:
        print("-" * 65)
        print("⚠️  STORES WITH NO FRESH DATA (blocked or empty):")
        for line in status_lines:
            print(line)


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

    # Snapshot who produced fresh data before any fallback replaces empty results, so the
    # summary can tell a healthy store apart from a blocked one running on preserved data.
    fresh_counts: Dict[str, int] = {_name: len(_items) for _name, _items in results.items()}
    preserved_counts: Dict[str, int] = {}

    # --- Preserve previously scraped data for any stores that returned 0 items ---
    # Handles stores (e.g. Recomp) that timeout/block from CI datacenter IPs.
    # If a store returned nothing new, fall back to its last known scraped items.
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, encoding="utf-8") as _f:
                _prev_raw = json.load(_f)
            # Previous JSON may be a flat list (after enrich_specs) or dict-by-store
            if isinstance(_prev_raw, dict):
                _prev_by_store: Dict[str, list] = _prev_raw
            else:
                _prev_by_store = {}
                for _itm in _prev_raw:
                    _k = _itm.get("store", "")
                    _prev_by_store.setdefault(_k, []).append(_itm)
            _fields = set(LaptopItem.__dataclass_fields__.keys())
            for _key in list(results.keys()):
                if len(results[_key]) == 0:
                    _prev_items = _prev_by_store.get(_key)
                    if not _prev_items:
                        for _pk, _pv in _prev_by_store.items():
                            if _key.lower().replace(" ", "") in _pk.lower().replace(" ", ""):
                                _prev_items = _pv
                                break
                    if _prev_items:
                        logger.warning(
                            "⚠️  Store '%s' returned 0 laptops — preserving %d previously scraped items.",
                            _key, len(_prev_items)
                        )
                        preserved_counts[_key] = len(_prev_items)
                        results[_key] = [
                            LaptopItem(**{k: v for k, v in _d.items() if k in _fields})
                            for _d in _prev_items
                            if isinstance(_d, dict)
                        ]
        except Exception as _e:
            logger.warning("Could not load previous catalog for fallback: %s", _e)

    # Flatten items for filtering & statistics
    all_items: List[LaptopItem] = []
    for store_name, items in results.items():
        all_items.extend(items)

    if not all_items:
        logger.warning("⚠️ No laptops were scraped across any store (network error or sites unreachable). Preserving existing catalog.")
        print("\n" + "=" * 65)
        print("⚠️  SCRAPE INCOMPLETE: 0 laptops parsed. Existing files preserved.")
        print("=" * 65)
        _print_store_status(results, fresh_counts, preserved_counts)
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

    # Update scraper status metadata
    ReportGenerator.update_scraper_status(results, fresh_counts, preserved_counts, get_store_blocks())

    # CLI Terminal Summary
    print("\n" + "=" * 65)
    print(f"📊 LIVE AUDIT COMPLETE: {len(all_items)} total laptops parsed across {len(results)} stores.")
    print("=" * 65)
    for name, items in results.items():
        print(f"  • {name:18}: {len(items):2d} laptops found")

    # Name the stores that produced nothing fresh, why, and whether preserved data covered it.
    _print_store_status(results, fresh_counts, preserved_counts)

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
