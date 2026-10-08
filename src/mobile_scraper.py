"""Refurbished Phones & Tablets Scraper facade and backward-compatible re-exports."""
from __future__ import annotations

import logging
from mobile_domain import MobileItem
from mobile_classification import MobileClassifier
from mobile_scrapers import (
    ITOutletMobileScraper,
    GoMobileScraper,
    PartnerPlusScraper,
    DynamicaScraper,
    VMobileScraper,
    LastPriceMobileScraper,
    IStoreMobileScraper,
    BuyMobileScraper,
    DEFAULT_MOBILE_SCRAPER_CLASSES,
)
from mobile_reports import MobileReportGenerator
from mobile_pipeline import MasterMobileAuditor, run_mobile_pipeline, main

logger = logging.getLogger("MobileScraper")

__all__ = [
    'MobileItem',
    'MobileClassifier',
    'ITOutletMobileScraper',
    'GoMobileScraper',
    'PartnerPlusScraper',
    'DynamicaScraper',
    'VMobileScraper',
    'LastPriceMobileScraper',
    'IStoreMobileScraper',
    'BuyMobileScraper',
    'DEFAULT_MOBILE_SCRAPER_CLASSES',
    'MobileReportGenerator',
    'MasterMobileAuditor',
    'run_mobile_pipeline',
    'main',
]

if __name__ == "__main__":
    main()
