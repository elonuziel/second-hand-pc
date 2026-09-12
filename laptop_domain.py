"""Domain models for the laptop catalog pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class LaptopItem:
    """Normalized laptop listing shared by scrapers, reports, and consumers."""

    store: str
    title: str
    brand: str
    series: str
    model: str
    cpu: str
    ram_gb: int
    storage_gb: int
    price_ils: int
    deal_price_ils: int
    deal_label: str
    storage_type: str
    ram_type: str
    upgradability_score: float
    warranty_months: int
    stock_status: str
    url: str
    gpu: str = "Integrated"
    is_touch: bool = False
    is_2in1: bool = False
    image_url: str = ""
    screen_size_in: float = 14.0
    weight_kg: float = 1.5
    battery_wh: int = 50
    ram_gen: str = "DDR4"
    ram_source: str = "chassis_decoder"
    screen_source: str = "chassis_decoder"
    weight_source: str = "chassis_decoder"
    battery_source: str = "chassis_decoder"
    confidence_level: str = "verified"
    weight_warning: str = ""
    battery_warning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
