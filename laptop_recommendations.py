"""Recommendation selection for normalized laptop inventory."""

from __future__ import annotations

from typing import List, Tuple

from laptop_domain import LaptopItem


class TopPicksEngine:
    """Select category winners from available laptop inventory."""

    _TOUCH_KEYWORDS = ("touch", "x360", "2-in-1", "טאצ")
    _ULTRABOOK_KEYWORDS = ("7320", "7330", "x13", "carbon", "x30l")

    @classmethod
    def select_top_picks(cls, all_items: List[LaptopItem]) -> List[Tuple[str, str, LaptopItem]]:
        picks: List[Tuple[str, str, LaptopItem]] = []
        valid_items = [item for item in all_items if item.deal_price_ils > 0 and item.stock_status.startswith("🟢")]

        ram_32 = [item for item in valid_items if item.ram_gb >= 32]
        if ram_32:
            ram_32.sort(key=lambda item: (item.deal_price_ils, -item.upgradability_score))
            picks.append(("👑 Best Value RAM Champion", "Highest RAM per Shekel (>= 32GB)", ram_32[0]))

        workhorse = [item for item in valid_items if item.ram_gb >= 32 and item.storage_gb >= 1000]
        if workhorse:
            workhorse.sort(key=lambda item: (item.deal_price_ils, -item.upgradability_score))
            picks.append(("🚀 Best 32GB + 1TB Workhorse", "32GB RAM + 1TB NVMe Powerhouse", workhorse[0]))

        gen12 = [item for item in valid_items if "12th Gen" in item.cpu or "ultra" in item.cpu.lower()]
        if gen12:
            gen12.sort(key=lambda item: (item.deal_price_ils, -item.ram_gb))
            picks.append(("⚡ Best Modern CPU Power (12th Gen)", "Latest Architecture Performance", gen12[0]))

        touch = [
            item for item in valid_items
            if any(keyword in item.title.lower() for keyword in cls._TOUCH_KEYWORDS)
            or item.is_2in1
            or item.is_touch
        ]
        if touch:
            touch.sort(key=lambda item: (-item.warranty_months, item.deal_price_ils))
            picks.append(("🥈 Best 2-in-1 / Touchscreen", "Versatile 360° / Touch Display", touch[0]))

        workstations = [item for item in valid_items if item.upgradability_score >= 10.0]
        if workstations:
            workstations.sort(key=lambda item: (-item.warranty_months, item.deal_price_ils))
            picks.append(("🏗️ Best Heavy Workstation", "4x RAM Slots + Multi-NVMe Bays", workstations[0]))

        ultrabooks = [
            item for item in valid_items
            if any(keyword in item.title.lower() for keyword in cls._ULTRABOOK_KEYWORDS)
        ]
        if ultrabooks:
            ultrabooks.sort(key=lambda item: (-item.warranty_months, item.deal_price_ils))
            picks.append(("🪶 Best Featherlight (< 1.3kg)", "Maximum Portability & Battery Life", ultrabooks[0]))

        warranty_24 = [item for item in valid_items if item.warranty_months >= 24]
        if warranty_24:
            warranty_24.sort(key=lambda item: item.deal_price_ils)
            picks.append(("🛡️ Best Peace of Mind", "Full 24-Month Official Warranty", warranty_24[0]))

        return picks
