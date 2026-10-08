"""Execution helpers for concurrent laptop store scraping."""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Mapping, Optional, Type

from laptop_domain import LaptopItem
from scraper_progress import ScrapeProgressTracker

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

# Scrapers report WHY they collected nothing (bot challenge, WAF block, unreachable site)
# so the run summary can name blocked stores instead of only showing a zero count.
# Scrapers report under their display name; run_store_scrapers resolves those onto the
# scraper keys used for results (e.g. "Olam HaKolnoa" -> "cwc").
_reported_reasons: Dict[str, str] = {}
_resolved_reasons: Dict[str, str] = {}
_reason_lock = threading.Lock()


def report_store_block(store: str, reason: str) -> None:
    """Records that `store` produced no data, and why. Safe to call from scraper threads."""
    with _reason_lock:
        _reported_reasons[store] = reason


def clear_store_blocks() -> None:
    with _reason_lock:
        _reported_reasons.clear()
        _resolved_reasons.clear()


def get_store_blocks() -> Dict[str, str]:
    """Block/no-data reasons keyed by scraper key (e.g. 'cwc'), for the run summary."""
    with _reason_lock:
        return dict(_resolved_reasons)


def _normalize(name: Any) -> str:
    return str(name).lower().replace(" ", "").replace("_", "")


def _resolve_reasons(scraper_classes: Mapping[str, Type[Any]]) -> None:
    """Maps reasons reported under display names onto the configured scraper keys."""
    with _reason_lock:
        for name, scraper_class in scraper_classes.items():
            display = getattr(scraper_class, "STORE_NAME", name)
            for reported_name, reason in _reported_reasons.items():
                if _normalize(reported_name) == _normalize(display) or _normalize(reported_name) == _normalize(name):
                    _resolved_reasons[name] = reason
                    break


def run_store_scrapers(
    scraper_classes: Mapping[str, Type[Any]],
    session: Any,
    store_filter: Optional[str] = None,
    max_workers: int = 6,
    logger: Optional[logging.Logger] = None,
) -> Dict[str, List[LaptopItem]]:
    """Run selected store adapters and return results in configured order."""
    log = logger or logging.getLogger(__name__)
    normalized_filter = store_filter.lower() if store_filter else None
    if normalized_filter and normalized_filter in scraper_classes:
        target_scrapers = {normalized_filter: scraper_classes[normalized_filter]}
    else:
        target_scrapers = dict(scraper_classes)

    clear_store_blocks()

    results: Dict[str, List[LaptopItem]] = {}
    worker_count = max(1, min(max_workers, len(target_scrapers) or 1))

    progress_file = os.path.join(DATA_DIR, "scraper_progress.json")
    status_log = os.path.join(DATA_DIR, "scraper_status.log")

    tracker = ScrapeProgressTracker(
        total_stores=len(target_scrapers),
        store_names=list(target_scrapers.keys()),
        worker_count=worker_count,
        category="laptops",
        logger=log,
        progress_json_path=progress_file,
        status_log_path=status_log,
    )
    tracker.start()

    def _scrape_worker(name: str, scraper_cls: Type[Any]) -> List[LaptopItem]:
        display = getattr(scraper_cls, "STORE_NAME", name)
        tracker.on_store_start(name, display_name=display)
        try:
            items = scraper_cls(session).scrape()
            tracker.on_store_finish(name, len(items), display_name=display)
            return items
        except Exception as ex:
            tracker.on_store_finish(name, 0, error=ex, display_name=display)
            raise

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(_scrape_worker, name, scraper_class): name
            for name, scraper_class in target_scrapers.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as error:
                log.error("Scraper '%s' encountered a critical error: %s", name, error)
                results[name] = []
                display = getattr(target_scrapers[name], "STORE_NAME", name)
                report_store_block(display, f"scraper raised {type(error).__name__}: {error}")

    tracker.finish()
    _resolve_reasons(target_scrapers)
    return {name: results.get(name, []) for name in target_scrapers}
