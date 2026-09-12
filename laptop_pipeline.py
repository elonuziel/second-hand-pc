"""Execution helpers for concurrent laptop store scraping."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Mapping, Optional, Type

from laptop_domain import LaptopItem


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

    results: Dict[str, List[LaptopItem]] = {}
    worker_count = max(1, min(max_workers, len(target_scrapers) or 1))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {
            executor.submit(scraper_class(session).scrape): name
            for name, scraper_class in target_scrapers.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as error:
                log.error("Scraper '%s' encountered a critical error: %s", name, error)
                results[name] = []

    return {name: results.get(name, []) for name in target_scrapers}
