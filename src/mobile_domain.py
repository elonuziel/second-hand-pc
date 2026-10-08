"""Data structures for refurbished mobile phones and tablets."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class MobileItem:
    store: str
    title: str
    brand: str
    model: str
    device_type: str  # 'phone' or 'tablet'
    ram_gb: int
    storage_gb: int
    price_ils: int
    deal_price_ils: int
    deal_label: str
    warranty_months: int
    stock_status: str
    url: str
    screen_size_in: float = 6.1
    image_url: str = ""
    confidence_level: str = "verified"
    scraped_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
