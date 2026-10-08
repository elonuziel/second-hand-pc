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
from typing import Dict, List, Optional, Tuple, Any

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
    KTWOScraper,
    SuperPriceScraper,
    PCILScraper,
    IvoryScraper,
    EspirScraper,
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


MOBILE_STORE_KEYS = [
    'itoutlet', 'gomobile', 'partner', 'dynamica', 'vmobile', 'lastprice', 'istore', 'buymobile'
]


def prompt_user_mode() -> str:
    """Displays an interactive selection menu offering scraping options."""
    print("\n" + "=" * 65)
    print("🤖 Second-Hand & Refurbished Hardware Scraper Suite")
    print("=================================================================")
    print("What would you like to scrape?")
    print("  [1] 🌐 All Catalogs (Laptops + Mobile phones & Tablets)")
    print("  [2] 💻 Laptops Only (17 stores: ThinkPads, MacBooks, Dell, Asus...)")
    print("  [3] 📱 Phones & Tablets Only (8 stores: iPhones, Galaxy, iPads...)")
    print("  [4] 🎯 Specific Store (choose from 25 stores)")
    print("  [0] ❌ Exit")
    print("-" * 65)
    try:
        raw = input("Enter choice [1-4, default: 1]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nOperation cancelled.")
        sys.exit(0)

    if not raw or raw in ("1", "all"):
        return "all"
    elif raw in ("2", "laptops", "laptop"):
        return "laptops"
    elif raw in ("3", "phones", "phone", "mobile"):
        return "mobile"
    elif raw in ("4", "store", "specific"):
        return "store"
    elif raw in ("0", "q", "exit", "quit"):
        print("Scraper aborted by user.")
        sys.exit(0)
    else:
        print(f"Unknown choice '{raw}'. Defaulting to All Catalogs.")
        return "all"


def prompt_specific_store() -> Tuple[str, str]:
    """Interactively prompts the user to pick a specific store. Returns (category, store_key)."""
    laptop_keys = list(DEFAULT_SCRAPER_CLASSES.keys())
    mobile_keys = MOBILE_STORE_KEYS

    print("\nSelect a specific store to scrape:")
    print("--- 💻 Laptop Stores (17) ---")
    for idx, key in enumerate(laptop_keys, 1):
        cls = DEFAULT_SCRAPER_CLASSES[key]
        display = getattr(cls, "STORE_NAME", key)
        print(f"  [{idx:2d}] {display} ({key})")

    print("\n--- 📱 Mobile Stores (8) ---")
    offset = len(laptop_keys)
    mobile_display_names = {
        'itoutlet': 'IT Outlet Mobile',
        'gomobile': 'GoMobile Outlet',
        'partner': 'Partner Plus Renewed',
        'dynamica': 'Dynamica Outlet',
        'vmobile': 'VMobile',
        'lastprice': 'LastPrice Mobile',
        'istore': 'iStore CPO',
        'buymobile': 'BuyMobile',
    }
    for idx, key in enumerate(mobile_keys, offset + 1):
        dname = mobile_display_names.get(key, key)
        print(f"  [{idx:2d}] {dname} ({key})")

    try:
        val = input(f"\nEnter store number or name [1-{offset + len(mobile_keys)}, 0 to cancel]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nOperation cancelled.")
        sys.exit(0)

    if not val or val in ("0", "q", "exit", "quit", "cancel"):
        print("Selection cancelled.")
        sys.exit(0)

    if val.isdigit():
        num = int(val)
        if 1 <= num <= offset:
            return "laptops", laptop_keys[num - 1]
        elif offset < num <= offset + len(mobile_keys):
            return "mobile", mobile_keys[num - offset - 1]

    # Name matching
    for key in laptop_keys:
        cls = DEFAULT_SCRAPER_CLASSES[key]
        display = getattr(cls, "STORE_NAME", key).lower()
        if val in key.lower() or val in display:
            return "laptops", key

    for key in mobile_keys:
        dname = mobile_display_names.get(key, key).lower()
        if val in key.lower() or val in dname:
            return "mobile", key

    print(f"Store '{val}' not recognized. Defaulting to all laptops.")
    return "laptops", "all"


def run_laptop_pipeline(
    store: str = "all",
    min_ram: int = 0,
    max_price: int = 99999,
    min_score: float = 0.0,
    ai: bool = False,
    csv: bool = False,
    json_dump: bool = False,
    no_md: bool = False,
    include_legacy: bool = False,
    workers: int = 8,
) -> Dict[str, List[LaptopItem]]:
    """Runs the full refurbished laptop scraping and auditing pipeline."""
    if include_legacy:
        os.environ["SCRAPER_INCLUDE_LEGACY"] = "1"

    auditor = MasterLaptopAuditor()
    results = auditor.run(
        store_filter=None if store == 'all' else store,
        max_workers=workers,
        use_ai=ai
    )

    fresh_counts: Dict[str, int] = {_name: len(_items) for _name, _items in results.items()}
    preserved_counts: Dict[str, int] = {}

    # Preserve previously scraped data for stores that returned 0 items
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, encoding="utf-8") as _f:
                _prev_raw = json.load(_f)
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
            if store != 'all':
                for _k, _v in _prev_by_store.items():
                    if _k not in results and isinstance(_v, list):
                        results[_k] = [
                            LaptopItem(**{k: v for k, v in _d.items() if k in _fields})
                            for _d in _v if isinstance(_d, dict)
                        ]
        except Exception as _e:
            logger.warning("Could not load previous catalog for fallback: %s", _e)

    all_items: List[LaptopItem] = []
    for store_name, items in results.items():
        all_items.extend(items)

    if not all_items:
        logger.warning("⚠️ No laptops were scraped across any store. Preserving existing catalog.")
        print("\n" + "=" * 65)
        print("⚠️  SCRAPE INCOMPLETE: 0 laptops parsed. Existing files preserved.")
        print("=" * 65)
        _print_store_status(results, fresh_counts, preserved_counts)
        return results

    filtered_items = [
        item for item in all_items
        if item.ram_gb >= min_ram
        and item.deal_price_ils <= max_price
        and item.upgradability_score >= min_score
    ]

    ReportGenerator.export_json(results, JSON_PATH)

    if csv:
        ReportGenerator.export_csv(all_items, CSV_PATH)

    if not no_md:
        ReportGenerator.update_summary_markdown(results, FULL_CATALOG_MD_PATH)

    ReportGenerator.update_scraper_status(results, fresh_counts, preserved_counts, get_store_blocks())

    print("\n" + "=" * 65)
    print(f"📊 LIVE AUDIT COMPLETE: {len(all_items)} total laptops parsed across {len(results)} stores.")
    print("=" * 65)
    for name, items in results.items():
        print(f"  • {name:18}: {len(items):2d} laptops found")

    _print_store_status(results, fresh_counts, preserved_counts)

    if min_ram > 0 or max_price < 99999 or min_score > 0.0:
        print("\n" + "-" * 65)
        print(f"🎯 Filtered Matches (RAM >= {min_ram}GB, Price <= {max_price} ₪, Score >= {min_score}): {len(filtered_items)} items")
        print("-" * 65)
        for itm in filtered_items[:10]:
            print(f"  [{itm.store:12}] {itm.title[:35]:35} | {itm.cpu:16} | {itm.ram_gb:2d}GB RAM | {itm.deal_label:20} | GPU: {itm.gpu}")

    if json_dump:
        print("\n" + json.dumps({k: [i.to_dict() for i in v] for k, v in results.items()}, ensure_ascii=False, indent=2))

    return results


def run_all_pipeline(
    ai: bool = False,
    csv: bool = False,
    json_dump: bool = False,
    no_md: bool = False,
    include_legacy: bool = False,
    workers: int = 8,
) -> Dict[str, Any]:
    """Runs scraping across BOTH laptops (17 stores) and mobile phones/tablets (8 stores)."""
    print("\n" + "=" * 65)
    print("🚀 [1/2] RUNNING LAPTOPS & WORKSTATIONS AUDIT (17 STORES)")
    print("=" * 65)
    laptop_results = run_laptop_pipeline(
        store="all",
        ai=ai,
        csv=csv,
        json_dump=False,
        no_md=no_md,
        include_legacy=include_legacy,
        workers=workers,
    )

    print("\n" + "=" * 65)
    print("🚀 [2/2] RUNNING MOBILE PHONES & TABLETS AUDIT (8 STORES)")
    print("=" * 65)
    from mobile_scraper import run_mobile_pipeline
    mobile_results = run_mobile_pipeline(
        store="all",
        csv=csv,
        json_dump=False,
        no_md=no_md,
        workers=min(workers, 4),
    )

    total_laptops = sum(len(v) for v in laptop_results.values())
    total_mobile = sum(len(v) for v in mobile_results.values())

    print("\n" + "=" * 65)
    print("🏆 GRAND MULTI-MARKETPLACE AUDIT SUMMARY")
    print("=" * 65)
    print(f"  • 💻 Laptops: {total_laptops:3d} devices across {len(laptop_results)} stores")
    print(f"  • 📱 Mobile:  {total_mobile:3d} devices across {len(mobile_results)} stores")
    print(f"  • 🌟 Total:   {total_laptops + total_mobile:3d} refurbished devices audited & cataloged")
    print("=" * 65 + "\n")

    if json_dump:
        combined = {
            "laptops": {k: [i.to_dict() for i in v] for k, v in laptop_results.items()},
            "mobile": {k: [i.to_dict() for i in v] for k, v in mobile_results.items()},
        }
        print(json.dumps(combined, ensure_ascii=False, indent=2))

    return {"laptops": laptop_results, "mobile": mobile_results}


def main():
    parser = argparse.ArgumentParser(
        description="Master Multi-Store Refurbished Laptop & Mobile Hardware Scraper & Auditor"
    )
    store_choices = list(DEFAULT_SCRAPER_CLASSES.keys()) + MOBILE_STORE_KEYS + ['all']
    parser.add_argument(
        "--store",
        choices=store_choices,
        default='all',
        help="Specific store to scrape"
    )
    parser.add_argument(
        "--category", "-c",
        choices=['all', 'laptops', 'mobile', 'phones'],
        default=None,
        help="Category to scrape: 'all', 'laptops', or 'mobile'/'phones'"
    )
    parser.add_argument("--all", action="store_true", help="Scrape all categories (laptops + mobile)")
    parser.add_argument("--laptops", action="store_true", help="Scrape laptops only (17 stores)")
    parser.add_argument("--mobile", "--phones", action="store_true", dest="mobile", help="Scrape phones and tablets only (8 stores)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Force interactive options menu")
    parser.add_argument("-y", "--non-interactive", action="store_true", help="Force non-interactive execution with defaults")

    parser.add_argument("--min-ram", type=int, default=0, help="Filter laptops with at least N GB RAM")
    parser.add_argument("--max-price", type=int, default=99999, help="Filter laptops with price <= N ILS")
    parser.add_argument("--min-score", type=float, default=0.0, help="Filter laptops with upgradability score >= N")
    parser.add_argument("--ai", "--groq", action="store_true", help="Enable Groq AI hardware intelligence")
    parser.add_argument("--csv", action="store_true", help="Also export items to CSV")
    parser.add_argument("--json", action="store_true", help="Dump JSON output to stdout")
    parser.add_argument("--no-md", action="store_true", help="Disable automatic catalog Markdown updates")
    parser.add_argument("--include-legacy", action="store_true", help="Include older/legacy CPUs (<8th Gen Intel) in stores with legacy inventory")
    parser.add_argument("--workers", type=int, default=8, help="Max concurrent store threads")

    args = parser.parse_args()

    # Determine target category
    target_category = args.category
    if args.all:
        target_category = "all"
    elif args.laptops:
        target_category = "laptops"
    elif args.mobile:
        target_category = "mobile"

    # Normalize 'phones' -> 'mobile'
    if target_category == "phones":
        target_category = "mobile"

    # Should we prompt interactively?
    # Prompt if explicitly asked (-i) OR if running in an interactive terminal with no explicit category and store='all'
    should_prompt = args.interactive or (
        target_category is None
        and args.store == 'all'
        and not args.non_interactive
        and sys.stdin.isatty()
        and not any([args.ai, args.csv, args.json, args.min_ram > 0, args.max_price < 99999, args.min_score > 0.0])
    )

    selected_store = args.store
    if should_prompt:
        choice = prompt_user_mode()
        if choice == "store":
            cat_choice, store_choice = prompt_specific_store()
            target_category = cat_choice
            selected_store = store_choice
        else:
            target_category = choice
    elif target_category is None:
        # Non-interactive default:
        # If a store was specified that belongs only to mobile, select mobile; otherwise default to laptops
        if selected_store != 'all' and selected_store in MOBILE_STORE_KEYS and selected_store not in DEFAULT_SCRAPER_CLASSES:
            target_category = "mobile"
        else:
            target_category = "laptops"

    # Dispatch to appropriate pipeline
    if target_category == "all":
        run_all_pipeline(
            ai=args.ai,
            csv=args.csv,
            json_dump=args.json,
            no_md=args.no_md,
            include_legacy=args.include_legacy,
            workers=args.workers,
        )
    elif target_category in ("mobile", "phones"):
        from mobile_scraper import run_mobile_pipeline
        run_mobile_pipeline(
            store=selected_store,
            csv=args.csv,
            json_dump=args.json,
            no_md=args.no_md,
            workers=min(args.workers, 4),
        )
    else:  # "laptops"
        run_laptop_pipeline(
            store=selected_store,
            min_ram=args.min_ram,
            max_price=args.max_price,
            min_score=args.min_score,
            ai=args.ai,
            csv=args.csv,
            json_dump=args.json,
            no_md=args.no_md,
            include_legacy=args.include_legacy,
            workers=args.workers,
        )


if __name__ == "__main__":
    main()

