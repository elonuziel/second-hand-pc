"""Pure parsing and validation helpers for laptop store adapters."""

from __future__ import annotations

import re
from typing import Iterable, Optional


DESKTOP_KEYWORDS = (
    "נייח",
    "שולחני",
    "tiny",
    "mini",
    "micro",
    "desktop",
    "optiplex",
    "desk",
    "prodesk",
    "elitedesk",
    "tower",
    "sff",
    "all in one",
    "aio",
)

LAPTOP_KEYWORDS = (
    "נייד",
    "laptop",
    "thinkpad",
    "latitude",
    "elitebook",
    "macbook",
)


def is_desktop_title(title: str) -> bool:
    """Return whether a product title identifies a desktop computer."""
    lowered = (title or "").lower()
    return any(keyword in lowered for keyword in DESKTOP_KEYWORDS)


def is_laptop_title(title: str) -> bool:
    """Return whether a title contains a known laptop marker."""
    lowered = (title or "").lower()
    return any(keyword in lowered for keyword in LAPTOP_KEYWORDS) and not is_desktop_title(title)


def parse_price_value(value: object, *, minimum: int = 1, maximum: int = 30000) -> Optional[int]:
    """Parse a currency-like value and reject values outside catalog bounds."""
    if value is None:
        return None
    text = str(value).replace(",", "").replace("₪", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        price = int(round(float(match.group(0))))
    except (TypeError, ValueError):
        return None
    return price if minimum <= price <= maximum else None


def last_valid_price(values: Iterable[object], *, minimum: int = 1, maximum: int = 30000) -> Optional[int]:
    """Return the last valid price from source candidates."""
    parsed = [parse_price_value(value, minimum=minimum, maximum=maximum) for value in values]
    valid = [price for price in parsed if price is not None]
    return valid[-1] if valid else None
