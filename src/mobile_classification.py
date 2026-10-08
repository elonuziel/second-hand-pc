"""Classification, heuristics, and item builder for mobile devices."""
from __future__ import annotations

import datetime
import re
from typing import Optional

from mobile_domain import MobileItem


class MobileClassifier:
    ACCESSORY_KEYWORDS = (
        'כיסוי', 'מגן', 'מטען', 'סוללה', 'זכוכית', 'כבל', 'נרתיק', 'מעמד', 'תושבת',
        'case', 'cover', 'charger', 'cable', 'protector', 'holder', 'strap', 'רצועה',
        'אוזניות', 'headset', 'airpods', 'buds'
    )
    TABLET_KEYWORDS = ('ipad', 'tab', 'טאבלט', 'tablet')

    _RAM_PATTERN = re.compile(r'(?:^|[^\d])(3|4|6|8|12|16)\s*(?:gb|ג"ב|גיגה)?\s*(?:ram|זכרון|זיכרון)(?:[^\d]|$)', re.IGNORECASE)
    _STORAGE_PATTERN = re.compile(r'(?:^|[^\d])(32|64|128|256|512|1000|1tb|1000gb|1 טרה)(?:gb|g|ג"ב|גיגה)?(?:[^\d]|$)', re.IGNORECASE)
    _SCREEN_PATTERN = re.compile(r'(?:^|[^\d])(5\.\d|6\.\d|7\.\d|8\.\d|10\.\d|11\.\d|12\.\d|13\.\d)\s*(?:"|\'|inch|אינץ)?(?:[^\d]|$)', re.IGNORECASE)

    @classmethod
    def is_mobile_device(cls, title: str) -> bool:
        t = title.lower()
        if any(k in t for k in cls.ACCESSORY_KEYWORDS):
            return False
        return any(k in t for k in [
            'iphone', 'galaxy', 'samsung', 'xiaomi', 'ipad', 'tab', 'pixel', 'redmi',
            'poco', 'motorola', 'realme', 'טלפון', 'סלולרי', 'סמארטפון', 'טאבלט', 'סלולר',
            'oneplus', 'asus', 'oppo', 'vivo', 'z flip', 'z fold', 'razr'
        ])

    @classmethod
    def detect_brand(cls, title: str) -> str:
        t = title.lower()
        if 'iphone' in t or 'ipad' in t or 'apple' in t: return "Apple"
        if 'galaxy' in t or 'samsung' in t or 'סמסונג' in t: return "Samsung"
        if 'xiaomi' in t or 'redmi' in t or 'poco' in t or 'שיאומי' in t: return "Xiaomi"
        if 'motorola' in t or 'razr' in t or 'מוטורולה' in t: return "Motorola"
        if 'pixel' in t or 'google' in t: return "Google"
        if 'realme' in t: return "Realme"
        if 'oneplus' in t: return "OnePlus"
        return "Mobile"

    @classmethod
    def detect_device_type(cls, title: str) -> str:
        t = title.lower()
        if any(k in t for k in cls.TABLET_KEYWORDS):
            return "tablet"
        return "phone"

    @classmethod
    def detect_storage(cls, title: str) -> int:
        t = title.lower()
        if '1tb' in t or '1 טרה' in t or '1000gb' in t:
            return 1000
        matches = cls._STORAGE_PATTERN.findall(t)
        if matches:
            for val in matches:
                v_str = val.lower()
                if v_str == '1tb': return 1000
                try:
                    num = int(v_str)
                    if num in [32, 64, 128, 256, 512, 1000]:
                        return num
                except ValueError:
                    pass
        return 128

    @classmethod
    def detect_ram(cls, title: str, brand: str, device_type: str, storage_gb: int) -> int:
        t = title.lower()
        m = cls._RAM_PATTERN.search(t)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass

        # Smart defaults by model/storage
        if brand == "Apple":
            if 'pro max' in t or '15 pro' in t or '16 pro' in t: return 8
            if '14 pro' in t or '13 pro' in t or '12 pro' in t or '15' in t or '16' in t: return 6
            return 4
        if brand == "Samsung":
            if 'ultra' in t or 'fold' in t or 's24' in t or 's23' in t: return 12
            if 'plus' in t or 'fe' in t or 's22' in t or 's21' in t: return 8
            return 6
        if brand == "Xiaomi":
            if storage_gb >= 512: return 12
            if storage_gb >= 256: return 8
            return 6

        return 6 if device_type == "phone" else 4

    @classmethod
    def detect_screen_size(cls, title: str, device_type: str) -> float:
        t = title.lower()
        m = cls._SCREEN_PATTERN.search(t)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass

        if device_type == "tablet":
            if '12.9' in t: return 12.9
            if '11' in t: return 11.0
            if '10.5' in t or '10.4' in t or '10.1' in t: return 10.4
            return 10.5

        if 'ultra' in t or 'pro max' in t or 'plus' in t: return 6.7
        if 'mini' in t or 'se' in t or 's9' in t: return 5.8
        return 6.1

    @classmethod
    def build_item(
        cls,
        store: str,
        title: str,
        price_ils: int,
        url: str,
        deal_price_ils: Optional[int] = None,
        deal_label: Optional[str] = None,
        warranty_months: int = 12,
        stock_status: str = "🟢 In Stock",
        image_url: str = "",
        scraped_at: Optional[str] = None,
    ) -> MobileItem:
        clean_title = ' '.join(re.sub(r'<[^>]+>', ' ', title).split())
        brand = cls.detect_brand(clean_title)
        device_type = cls.detect_device_type(clean_title)
        storage_gb = cls.detect_storage(clean_title)
        ram_gb = cls.detect_ram(clean_title, brand, device_type, storage_gb)
        screen_size = cls.detect_screen_size(clean_title, device_type)

        resolved_deal_price = deal_price_ils if deal_price_ils is not None else price_ils
        resolved_deal_label = deal_label or f"{resolved_deal_price:,} ₪"
        resolved_scraped_at = scraped_at or datetime.date.today().isoformat()

        return MobileItem(
            store=store,
            title=clean_title,
            brand=brand,
            model=clean_title,
            device_type=device_type,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            price_ils=price_ils,
            deal_price_ils=resolved_deal_price,
            deal_label=resolved_deal_label,
            warranty_months=warranty_months,
            stock_status=stock_status,
            url=url,
            screen_size_in=screen_size,
            image_url=image_url,
            scraped_at=resolved_scraped_at,
        )
