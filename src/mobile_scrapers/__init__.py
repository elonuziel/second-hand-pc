"""Collection of all 8 refurbished mobile phone & tablet store scrapers."""
from __future__ import annotations

from typing import Dict, Type

from mobile_scrapers.itoutlet import ITOutletMobileScraper
from mobile_scrapers.gomobile import GoMobileScraper
from mobile_scrapers.partner import PartnerPlusScraper
from mobile_scrapers.dynamica import DynamicaScraper
from mobile_scrapers.vmobile import VMobileScraper
from mobile_scrapers.lastprice import LastPriceMobileScraper
from mobile_scrapers.istore import IStoreMobileScraper
from mobile_scrapers.buymobile import BuyMobileScraper

DEFAULT_MOBILE_SCRAPER_CLASSES: Dict[str, Type] = {
    'itoutlet': ITOutletMobileScraper,
    'gomobile': GoMobileScraper,
    'partner': PartnerPlusScraper,
    'dynamica': DynamicaScraper,
    'vmobile': VMobileScraper,
    'lastprice': LastPriceMobileScraper,
    'istore': IStoreMobileScraper,
    'buymobile': BuyMobileScraper,
}

__all__ = [
    'ITOutletMobileScraper',
    'GoMobileScraper',
    'PartnerPlusScraper',
    'DynamicaScraper',
    'VMobileScraper',
    'LastPriceMobileScraper',
    'IStoreMobileScraper',
    'BuyMobileScraper',
    'DEFAULT_MOBILE_SCRAPER_CLASSES',
]
