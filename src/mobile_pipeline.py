"""Master mobile scraper runner and pipeline orchestrator."""
from __future__ import annotations

import argparse
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Type

from mobile_domain import MobileItem
from mobile_reports import MobileReportGenerator
from mobile_scrapers import DEFAULT_MOBILE_SCRAPER_CLASSES
from scraper_progress import ScrapeProgressTracker

try:
    from http_session import create_resilient_session
except ImportError:
    import requests
    def create_resilient_session(**_) -> requests.Session:
        return requests.Session()

logger = logging.getLogger("MobileAuditor")

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
FULL_MOBILE_CATALOG_MD_PATH = os.path.join(DATA_DIR, "full_mobile_catalog.md")
JSON_PATH = os.path.join(DATA_DIR, "scraped_mobile.json")
CSV_PATH = os.path.join(DATA_DIR, "scraped_mobile.csv")


class MasterMobileAuditor:
    def __init__(self, session: Optional[Any] = None):
        self.session = session or create_resilient_session()
        self.scraper_classes = dict(DEFAULT_MOBILE_SCRAPER_CLASSES)

    def run(self, store_filter: Optional[str] = None, max_workers: int = 4) -> Dict[str, List[MobileItem]]:
        results: Dict[str, List[MobileItem]] = {}
        target_scrapers = {}

        if store_filter and store_filter.lower() in self.scraper_classes:
            target_scrapers[store_filter.lower()] = self.scraper_classes[store_filter.lower()]
        else:
            target_scrapers = self.scraper_classes

        worker_count = max(1, min(max_workers, len(target_scrapers) or 1))
        progress_file = os.path.join(DATA_DIR, "scraper_mobile_progress.json")
        status_log = os.path.join(DATA_DIR, "scraper_status.log")

        tracker = ScrapeProgressTracker(
            total_stores=len(target_scrapers),
            store_names=list(target_scrapers.keys()),
            worker_count=worker_count,
            category="mobile",
            logger=logger,
            progress_json_path=progress_file,
            status_log_path=status_log,
        )
        tracker.start()

        def _scrape_worker(name: str, cls: Type[Any]) -> List[MobileItem]:
            display = getattr(cls, "STORE_NAME", name)
            tracker.on_store_start(name, display_name=display)
            try:
                items = cls(self.session).scrape()
                tracker.on_store_finish(name, len(items), display_name=display)
                return items
            except Exception as ex:
                tracker.on_store_finish(name, 0, error=ex, display_name=display)
                raise

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_scrape_worker, name, cls): name
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

        tracker.finish()
        return results


def run_mobile_pipeline(
    store: str = "all",
    csv: bool = False,
    json_dump: bool = False,
    no_md: bool = False,
    workers: int = 4,
) -> Dict[str, List[MobileItem]]:
    auditor = MasterMobileAuditor()
    results = auditor.run(
        store_filter=None if store == 'all' else store,
        max_workers=workers
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
            if store != 'all':
                for _k, _v in _prev_raw.items():
                    if _k not in results and isinstance(_v, list):
                        results[_k] = [
                            MobileItem(**{k: v for k, v in _d.items() if k in _fields})
                            for _d in _v if isinstance(_d, dict)
                        ]
            all_items = []
            for store_name, items in results.items():
                all_items.extend(items)
        except Exception as _e:
            logger.warning("Could not load previous mobile catalog for fallback: %s", _e)

    ReportGenerator_export = MobileReportGenerator
    ReportGenerator_export.export_json(results, JSON_PATH)

    if csv:
        ReportGenerator_export.export_csv(all_items, CSV_PATH)

    if not no_md:
        ReportGenerator_export.update_summary_markdown(results, FULL_MOBILE_CATALOG_MD_PATH)

    ReportGenerator_export.update_scraper_status(results, fresh_counts, preserved_counts)

    print("\n" + "=" * 65)
    print(f"📊 MOBILE LIVE AUDIT COMPLETE: {len(all_items)} total devices parsed across {len(results)} stores.")
    print("=" * 65)
    for name, items in results.items():
        print(f"  • {name:18}: {len(items):2d} mobile devices found")

    if json_dump:
        print("\n" + json.dumps({k: [i.to_dict() for i in v] for k, v in results.items()}, ensure_ascii=False, indent=2))

    return results


def main():
    parser = argparse.ArgumentParser(description="Master Multi-Store Refurbished Mobile Device Scraper & Auditor")
    parser.add_argument("--store", choices=list(DEFAULT_MOBILE_SCRAPER_CLASSES.keys()) + ['all'], default='all', help="Specific store to scrape")
    parser.add_argument("--csv", action="store_true", help="Also export devices to CSV")
    parser.add_argument("--json", action="store_true", help="Dump JSON output to stdout")
    parser.add_argument("--no-md", action="store_true", help="Disable automatic full_mobile_catalog.md update")
    parser.add_argument("--workers", type=int, default=4, help="Max concurrent store threads")

    args = parser.parse_args()
    run_mobile_pipeline(
        store=args.store,
        csv=args.csv,
        json_dump=args.json,
        no_md=args.no_md,
        workers=args.workers,
    )


if __name__ == "__main__":
    main()
