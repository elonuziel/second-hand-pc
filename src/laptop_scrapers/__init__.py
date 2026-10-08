"""Collection of all 12 refurbished laptop store scrapers."""

from __future__ import annotations

from typing import Dict, Type

from laptop_scrapers.itoutlet import ITOutletScraper
from laptop_scrapers.ecology import EcologyScraper
from laptop_scrapers.lts import LTSScraper
from laptop_scrapers.recomp import RecompScraper
from laptop_scrapers.cwc import CWCScraper
from laptop_scrapers.payngo import PayngoScraper
from laptop_scrapers.alm import ALMScraper
from laptop_scrapers.shufersal import ShufersalScraper
from laptop_scrapers.p1000 import P1000Scraper
from laptop_scrapers.lastprice import LastPriceScraper
from laptop_scrapers.volt import VoltScraper
from laptop_scrapers.ofekpc import OfekPCScraper

DEFAULT_SCRAPER_CLASSES: Dict[str, Type] = {
    'itoutlet': ITOutletScraper,
    'ecology': EcologyScraper,
    'lts': LTSScraper,
    'recomp': RecompScraper,
    'cwc': CWCScraper,
    'payngo': PayngoScraper,
    'alm': ALMScraper,
    'shufersal': ShufersalScraper,
    'p1000': P1000Scraper,
    'lastprice': LastPriceScraper,
    'volt': VoltScraper,
    'ofekpc': OfekPCScraper,
}

__all__ = [
    'ITOutletScraper',
    'EcologyScraper',
    'LTSScraper',
    'RecompScraper',
    'CWCScraper',
    'PayngoScraper',
    'ALMScraper',
    'ShufersalScraper',
    'P1000Scraper',
    'LastPriceScraper',
    'VoltScraper',
    'OfekPCScraper',
    'DEFAULT_SCRAPER_CLASSES',
]

