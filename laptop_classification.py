"""Hardware Intelligence & Classification Engine for PC hardware specifications."""

from __future__ import annotations

import datetime
import re
import urllib.parse
from typing import Optional, Tuple, Union

from laptop_domain import LaptopItem


class HardwareClassifier:
    """Classifies PC hardware architecture based on verified engineering specifications."""

    # Pre-compiled regular expressions for text cleaning and spec detection
    _ALT_TEXT_RE = re.compile(r'alt=[\"\']([^\"\']+)[\"\']')
    _SKU_PREFIX_RE = re.compile(r'^\d+\s*-\s*')
    _HTML_TAG_RE = re.compile(r'<[^>]+>')
    _CLEAN_PHRASE_RE = re.compile(r'מחשב\s*נייד\s*(?:מחודש)?\s*(?:לעריכה\s*גרפית)?')

    _GEN13_RE = re.compile(r'(?:13th|דור\s*13|(?<![a-z0-9])13\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?13\b|\bgen\s*13(?!\d)|13[0-9]{2}[up]|13[0-9]{3}h|13[0-9]{2}h)', re.IGNORECASE)
    _GEN12_RE = re.compile(r'(?:12th|דור\s*12|(?<![a-z0-9])12\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?12\b|\bgen\s*12(?!\d)|(?:t14|t14s|x13|l13|l14|l15|p14s|p15s|e14|e15)\s*gen\s*4|\bg9\b|5330|5430|5530|7330|7430|5431|5531|l13\s*gen\s*3|t14\s*gen\s*3|x1404za|e1504|12[0-9]{2}[up]|12[0-9]{3}h|12[0-9]{2}h|1270p|1260p|1250u|1280p|1240p|1235u)', re.IGNORECASE)
    _GEN11_RE = re.compile(r'(?:11th|דור\s*11|(?<![a-z0-9])11\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?11\b|\bg8\b|(?:t14|t14s|x13|l13|l14|l15|p14s|p15s|e14|e15)\s*gen\s*2|3520|3420|7420|7320|5420|5320|5520|surface\s*4|x1\s*carbon\s*gen\s*9|x1\s*yoga\s*gen\s*6|a517.*52g|x515ea|x30l\s*j|11[0-9]{2}g[47]|11[0-9]{2}[up]|11[0-9]{3}h|11[0-9]{2}h|1185g7|1165g7|1135g7|1145g7|11500h|11800h)', re.IGNORECASE)
    _GEN10_RE = re.compile(r'(?:10th|דור\s*10|(?<![a-z0-9])10\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?10\b|\bgen\s*10(?!\d)|\bg7\b|(?:t14|t14s|x13|l13|l14|l15|p14s|p15s|e14|e15)\s*(?:gen\s*1|\bg1\b)|7410|5410|5510|surface\s*3|x1\s*carbon\s*gen\s*8|p1\s*gen\s*3|vostro\s*3591|3591|a2179|a2251|10[0-9]{2}[up]|10[0-9]{3}h|10[0-9]{2}h|10510u|10610u|10875h|10850h|10210u|10310u)', re.IGNORECASE)
    _GEN9_RE = re.compile(r'(?:9th|דור\s*9|(?<![a-z0-9])9\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?9\b|\bgen\s*9(?!\d)|\bg6\b|a2141|9750h|9850h|9[0-9]{3}[uh])', re.IGNORECASE)
    _GEN8_RE = re.compile(r'(?:8th|דור\s*8|(?<![a-z0-9])8\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?8\b|\bgen\s*8(?!\d)|e480|l390|l480|7400|5490|5400|5500|x280|t480|t490|p52|5379|330\s*15ikb|a1989|a1990|x380|x1\s*carbon.*touch|8[0-9]{3}[uh]|8250u|8350u|8650u|8550u|8750h|8850h)', re.IGNORECASE)
    _GEN7_RE = re.compile(r'(?:7th|דור\s*7|(?<![a-z0-9])7\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?7\b|\bgen\s*7(?!\d)|t470|l470|5480|x442ur|a1707|a1706|a1708|7[0-9]{3}[uh]|7200u|7300u|7500u)', re.IGNORECASE)
    _GEN6_RE = re.compile(r'(?:6th|דור\s*6|(?<![a-z0-9])6\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?6\b|\bgen\s*6(?!\d)|t460|650\s*g2|840\s*g3|e5470|e7470|ay010|6[0-9]{3}[uh]|6200u|6300u)', re.IGNORECASE)
    _GEN5_RE = re.compile(r'(?:5th|דור\s*5|(?<![a-z0-9])5\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?5\b|\bgen\s*5(?!\d)|t450|x250|a1466|5[0-9]{3}[uh]|5200u|5300u)', re.IGNORECASE)
    _GEN4_RE = re.compile(r'(?:4th|דור\s*4|(?<![a-z0-9])4\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?4\b|\bgen\s*4(?!\d)|g-4|e7440|t440|x240|4[0-9]{3}[uh]|4200u|4300u)', re.IGNORECASE)
    _GEN3_RE = re.compile(r'(?:3rd|דור\s*3|(?<![a-z0-9])3\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?3\b|\bgen\s*3(?!\d)|t430|x230|e6530|e6230|9470m|3[0-9]{3}[uhm]|3687u|3210m|3320m|3340m)', re.IGNORECASE)
    _GEN2_RE = re.compile(r'(?:2nd|דור\s*2|(?<![a-z0-9])2\s*gen(?!\s*[0-9])|\bi[3579]-(?:gen\s*)?2\b|\bgen\s*2(?!\d)|t420|x220|e6420|n5110|2[0-9]{3}[uhm]|2410m|2520m|2540m)', re.IGNORECASE)

    _RAM_GB_RE = re.compile(r'(?:^|[^\w])(4|8|12|16|24|32|48|64)\s*(?:gb|g|גיגה)(?:[^\w]|$)', re.IGNORECASE)
    _EXPLICIT_RAM_RE = re.compile(
        r'(?:(?:ram|זכרון|זיכרון|memory)\s*(?:של\s*)?(4|8|12|16|24|32|48|64|128)\s*(?:gb|g|גיגה)?'
        r'|(?<!דור\s)(?<!דור)(?:^|[^\w])(4|8|12|16|24|32|48|64|128)\s*(?:gb|g|גיגה)\s*(?:ram|זכרון|זיכרון|memory)'
        r'|(?<!דור\s)(?<!דור)(?:^|[^\w])(4|8|12|16|24|32|48|64|128)\s*(?:ram|memory))',
        re.IGNORECASE
    )
    _GPU_VRAM_RE = re.compile(r'(?:gtx|rtx|quadro|geforce|radeon|iris|t500|t600|t1000|t1200|t2000)\s*(?:[0-9]{3,4})?\s*(?:\d+\s*(?:gb|g))?|(?:\d+\s*(?:gb|g|גיגה)?\s*(?:graphics|vram|כרטיס מסך|כרטיס גרפי|גרפיקה))', re.IGNORECASE)
    _STORAGE_PREFIX_RE = re.compile(
        r'(?:ssd|nvme|אחסון|דיסק|storage|hdd|emmc|hard\s*drive|drive)\s*(?:של\s*)?(64|120|128|160|180|240|250|256|320|480|500|512|1000|1024|2000|2048)\s*(?:gb|g|גיגה)?',
        re.IGNORECASE
    )
    _STORAGE_POSTFIX_RE = re.compile(
        r'(?:^|[^\w])(64|120|128|160|180|240|250|256|320|480|500|512|1000|1024|2000|2048)\s*(?:gb|g|גיגה)?\s*(?:ssd|nvme|אחסון|דיסק|storage|hdd|emmc)',
        re.IGNORECASE
    )
    _STORAGE_STANDALONE_RE = re.compile(
        r'(?:^|[^\w])(120|128|160|180|240|250|256|320|480|500|512)\s*(?:gb|g|גיגה)(?!\s*(?:ram|זכרון|זיכרון|memory))',
        re.IGNORECASE
    )
    _TB_STORAGE_RE = re.compile(r'\b(?:1|2)\s*(?:tb|טרה)\b', re.IGNORECASE)
    _RAM_GEN_EXPLICIT_RE = re.compile(r'\b(lpddr5x|lpddr5|ddr5|lpddr4x|lpddr4|ddr4|ddr3l|ddr3)\b', re.IGNORECASE)

    _APPLE_SILICON_RE = re.compile(r'\b(?:apple\s*m[123]|m[123]\s*(?:pro|max|ultra))\b', re.IGNORECASE)
    _M3_RE = re.compile(r'\bm3\b', re.IGNORECASE)
    _M2_RE = re.compile(r'\bm2\b', re.IGNORECASE)
    _M2_DISCARD_RE = re.compile(r'\bm\.?2\s*(?:ssd|nvme|pcie|דיסק)', re.IGNORECASE)
    _M1_RE = re.compile(r'\bm1\b', re.IGNORECASE)
    _CORE_ULTRA_RE = re.compile(r'\b(?:core\s*ultra|ultra)\s*([3579])\b', re.IGNORECASE)
    _AMD_ATHLON_RE = re.compile(r'\b(?:athlon|3020e|4020e)\b', re.IGNORECASE)
    _AMD_A_SERIES_1_RE = re.compile(r'\b(?:a[468]|a10)\b', re.IGNORECASE)
    _AMD_A_SERIES_2_RE = re.compile(r'amd.*(?:a4|a6|a8|a10)', re.IGNORECASE)
    _ATOM_RE = re.compile(r'\b(?:atom|n270|n450|z[0-9]{3}|10v|nb100)\b', re.IGNORECASE)
    _CORE_2_DUO_RE = re.compile(r'\b(?:c2d|core\s*2\s*duo|su[0-9]{4}|l[0-9]{4}|t[0-9]{4}|p[0-9]{4}|x60|x61|x61s|x301)\b', re.IGNORECASE)
    _PENTIUM_RE = re.compile(r'\b(?:pentium|centrino|t43|r40)\b', re.IGNORECASE)
    _INTEL_I_LEVEL_RE = re.compile(r'\b(i[3579])\b', re.IGNORECASE)

    _RYZEN_6K_RE = re.compile(r'ryzen\s*[3579]?\s*(?:pro\s*)?[678]\d{3}', re.IGNORECASE)

    _DELL_MODEL_RE = re.compile(r'\b(?:latitude|precision)?\s*([3579])([34567])([0-9])([05])?\b', re.IGNORECASE)
    _DELL_MODEL_SIMPLE_RE = re.compile(r'\b(?:latitude)?\s*([3579])([34567])([0-9])([05])?\b', re.IGNORECASE)
    _TP_MODEL_RE = re.compile(r'\b(?:thinkpad\s*)?([txple])(13|14|15|16)(s)?\b', re.IGNORECASE)
    _HP_MODEL_RE = re.compile(r'\b(?:elitebook|probook)?\s*([468])([3456])([05])\b', re.IGNORECASE)

    _WEIGHT_HEBREW_RE = re.compile(r'(?:משקל\s*[:\-]?\s*)?(\d+(?:\.\d+)?)\s*(?:kg|ק["\'״]*ג|קג)\b', re.IGNORECASE)
    _WEIGHT_ENGLISH_RE = re.compile(r'\bweight\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:kg)?\b', re.IGNORECASE)

    _BATTERY_HEBREW_RE = re.compile(r'(\d{2,3})\s*(?:whr?|w/h|watt|וואט(?:-שעה)?)\b', re.IGNORECASE)
    _BATTERY_ENGLISH_RE = re.compile(r'\bbattery\s*[:\-]?\s*(\d{2,3})\s*(?:whr?|w/h)?\b', re.IGNORECASE)

    # Constant tuples for brand and architecture detection to avoid list allocation at runtime
    _LENOVO_KEYWORDS = ('thinkpad', 'lenovo', 'ideapad', 'legion', 'לנובו')
    _DELL_KEYWORDS = ('dell', 'latitude', 'precision', 'xps', 'דל', 'vostro', 'inspiron')
    _HP_KEYWORDS = ('hp', 'elitebook', 'zbook', 'probook')
    _MICROSOFT_KEYWORDS = ('surface', 'microsoft')
    _APPLE_KEYWORDS = ('macbook', 'apple', 'אפל', 'mac')

    _SOLDERED_RAM_KEYWORDS = ('x360', '7320', '7410', '7420', '7430', 'x1 carbon', 'x13', 't14s', 'x280')
    _SEMI_MODULAR_KEYWORDS = ('t14', 'p14s', 'p15s', 't480s', 't470s', 't490s')
    _FULL_MODULAR_KEYWORDS = ('840', '850', '855', 'firefly', '5410', '5420', '5430', '5431', '5530', '5531', 'l14', 'l390', '430', 'e480', 'a517', 'vostro', 'inspiron', '435')
    _LEGACY_BAY_KEYWORDS = ('t460', '650 g2', 'g-4', 'e7440', '5480', '255 g5')

    _NON_LAPTOP_KEYWORDS = ('mini pc', 'desktop', 'prodesk', 'elitedesk', 'optiplex', 'שולחני', 'מחשב שולחני', 'מקלדת', 'סוללה', 'מטען', 'מסך ', 'זכרון ')

    @classmethod
    def clean_text(cls, text: str) -> str:
        if not text:
            return ""
        text = urllib.parse.unquote(text)
        # Extract alt text if wrapped in img tags
        alt_m = cls._ALT_TEXT_RE.findall(text)
        if alt_m:
            text = alt_m[0]
        # Strip long SEO keyword spam blocks (like ", מחשבים ניידים...")
        if ',' in text:
            first_part = text.split(',')[0].strip()
            if len(first_part) >= 5:
                text = first_part
        # Remove leading SKU digits like "93070 - "
        text = cls._SKU_PREFIX_RE.sub('', text)
        text = cls._HTML_TAG_RE.sub(' ', text)
        # Remove repetitive phrases
        text = cls._CLEAN_PHRASE_RE.sub('', text).strip()
        return ' '.join(text.split()).strip()

    @classmethod
    def detect_brand(cls, title: str) -> str:
        t = title.lower()
        if any(k in t for k in cls._LENOVO_KEYWORDS):
            return "Lenovo"
        if any(k in t for k in cls._DELL_KEYWORDS):
            return "Dell"
        if any(k in t for k in cls._HP_KEYWORDS):
            return "HP"
        if any(k in t for k in cls._MICROSOFT_KEYWORDS):
            return "Microsoft"
        if any(k in t for k in cls._APPLE_KEYWORDS):
            return "Apple"
        if 'acer' in t:
            return "Acer"
        if 'asus' in t or 'vivobook' in t or 'zenbook' in t:
            return "Asus"
        if 'toshiba' in t or 'protege' in t:
            return "Toshiba"
        return "Business Laptop"

    @classmethod
    def detect_series(cls, title: str) -> str:
        t = title.lower()
        if 'thinkpad' in t: return "ThinkPad"
        if 'latitude' in t: return "Latitude"
        if 'precision' in t: return "Precision"
        if 'elitebook' in t: return "EliteBook"
        if 'zbook fury' in t: return "ZBook Fury"
        if 'zbook firefly' in t: return "ZBook Firefly"
        if 'zbook' in t: return "ZBook"
        if 'probook' in t: return "ProBook"
        if 'surface' in t: return "Surface"
        if 'ideapad' in t: return "IdeaPad"
        if 'macbook' in t: return "MacBook"
        return "Business Series"

    @classmethod
    def is_touch(cls, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in ['touch', 'טאץ', 'טאצ', 'מסך מגע', 'מגע', 'x360', 'yoga', '2-in-1', '2 in 1', '2in1', 'surface', 'flip'])

    @classmethod
    def is_2in1(cls, text: str) -> bool:
        t = text.lower()
        return any(k in t for k in ['x360', 'yoga', '2-in-1', '2 in 1', '2in1', 'convertible', 'flip', '360'])

    @classmethod
    def detect_cpu(cls, title: str) -> str:
        t = title.lower()
        # Apple Silicon (must be Apple/MacBook or explicit Apple M-series, not M.2 NVMe SSD)
        if any(k in t for k in ['apple', 'macbook', 'mac']) or cls._APPLE_SILICON_RE.search(t):
            if cls._M3_RE.search(t): return "Apple M3"
            if cls._M2_RE.search(t) and not cls._M2_DISCARD_RE.search(t): return "Apple M2"
            if cls._M1_RE.search(t): return "Apple M1"

        # Modern Intel Core Ultra (Meteor Lake)
        ultra_m = cls._CORE_ULTRA_RE.search(t)
        if ultra_m:
            return f"Intel Core Ultra {ultra_m.group(1)}"
        if 'core ultra' in t or 'meteor lake' in t:
            return "Intel Core Ultra"

        # AMD Processors
        if 'ryzen 7' in t: return "AMD Ryzen 7 PRO"
        if 'ryzen 5' in t: return "AMD Ryzen 5 PRO"
        if 'ryzen 3' in t: return "AMD Ryzen 3 PRO"
        if 'ryzen' in t: return "AMD Ryzen"
        if cls._AMD_ATHLON_RE.search(t): return "AMD Athlon"
        if cls._AMD_A_SERIES_1_RE.search(t) or cls._AMD_A_SERIES_2_RE.search(t): return "AMD A-Series"
        if 'amd' in t: return "AMD Ryzen"

        # Legacy Intel Architectures & Low-Power CPUs
        if cls._ATOM_RE.search(t) or 'נטבוק' in t or (('מיני' in t or 'mini' in t) and any(k in t for k in ['atom', '10v', 'nb100'])):
            return "Intel Atom"
        if cls._CORE_2_DUO_RE.search(t):
            return "Intel Core 2 Duo"
        if cls._PENTIUM_RE.search(t):
            return "Intel Pentium"
        if 'celeron' in t: return "Intel Celeron"
        if 'xeon' in t: return "Intel Xeon"

        gen13 = cls._GEN13_RE.search(t)
        gen12 = cls._GEN12_RE.search(t)
        gen11 = cls._GEN11_RE.search(t)
        gen10 = cls._GEN10_RE.search(t)
        gen9 = cls._GEN9_RE.search(t)
        gen8 = cls._GEN8_RE.search(t)
        gen7 = cls._GEN7_RE.search(t)
        gen6 = cls._GEN6_RE.search(t)
        gen5 = cls._GEN5_RE.search(t)
        gen4 = cls._GEN4_RE.search(t)
        gen3 = cls._GEN3_RE.search(t)
        gen2 = cls._GEN2_RE.search(t)

        has_i_explicit = cls._INTEL_I_LEVEL_RE.search(t)
        if has_i_explicit:
            i_level = has_i_explicit.group(1).lower()
        else:
            i_level = "i7" if "i7" in t else ("i5" if "i5" in t else ("i9" if "i9" in t else ("i3" if "i3" in t else "i5")))

        if gen13: return f"Core {i_level} (13th Gen)"
        if gen12: return f"Core {i_level} (12th Gen)"
        if gen11: return f"Core {i_level} (11th Gen)"
        if gen10: return f"Core {i_level} (10th Gen)"
        if gen9:  return f"Core {i_level} (9th Gen)"
        if gen8:  return f"Core {i_level} (8th Gen)"
        if gen7:  return f"Core {i_level} (7th Gen)"
        if gen6:  return f"Core {i_level} (6th Gen)"
        if gen5:  return f"Core {i_level} (5th Gen)"
        if gen4:  return f"Core {i_level} (4th Gen)"
        if gen3:  return f"Core {i_level} (3rd Gen)"
        if gen2:  return f"Core {i_level} (2nd Gen)"

        if any(k in t for k in ["core", "i3", "i5", "i7", "i9", "intel"]):
            return f"Core {i_level}"
        return "Intel Core"

    @classmethod
    def detect_ram_gb(cls, title: str) -> int:
        # 1. Mask out GPU VRAM and graphics memory strings so they don't corrupt system RAM
        cleaned = cls._GPU_VRAM_RE.sub(" ", title)

        # 2. Mask out storage indicators (e.g. 128GB SSD, דיסק 256GB, 1TB) so SSD sizes aren't mistaken for RAM
        cleaned = cls._STORAGE_PREFIX_RE.sub(" ", cleaned)
        cleaned = cls._STORAGE_POSTFIX_RE.sub(" ", cleaned)
        cleaned = cls._TB_STORAGE_RE.sub(" ", cleaned)

        # 3. First priority: explicit RAM keyword in cleaned title
        m_exp = cls._EXPLICIT_RAM_RE.search(cleaned)
        if m_exp:
            val = m_exp.group(1) or m_exp.group(2) or m_exp.group(3)
            if val:
                return int(val)

        # 4. Search for RAM in cleaned title
        m = cls._RAM_GB_RE.search(cleaned)
        if m:
            return int(m.group(1))
        return 16

    @classmethod
    def detect_storage_gb(cls, title: str) -> int:
        t = title.lower()
        if '2tb' in t or '2 טרה' in t or '2000gb' in t: return 2000
        if '1tb' in t or '1 טרה' in t or '1000g' in t or '1000gb' in t: return 1000

        # 1. First priority: explicit storage prefix like 'דיסק 256' or 'ssd 512'
        m = cls._STORAGE_PREFIX_RE.search(t)
        if m:
            val = m.group(1)
            if val:
                return int(val)

        # 2. Mask out explicit RAM patterns so 'זיכרון 32GB' won't be matched as storage
        cleaned = cls._EXPLICIT_RAM_RE.sub(' ', t)

        # 3. Check postfix storage like '256GB SSD'
        m = cls._STORAGE_POSTFIX_RE.search(cleaned)
        if m:
            val = m.group(1)
            if val:
                return int(val)

        # 4. Check standalone storage like '256GB'
        m = cls._STORAGE_STANDALONE_RE.search(cleaned)
        if m:
            val = m.group(1)
            if val:
                return int(val)

        return 512

    @classmethod
    def analyze_architecture(cls, title: str) -> Tuple[float, str, str]:
        """Returns (UpgradabilityScore, StorageInterface, RAMArchitecture)."""
        t = title.lower()
        # Extreme Workstations
        if 'zbook fury' in t or ('thinkpad p15' in t and 'p15s' not in t and 'p15v' not in t):
            return 10.0, "⚡ Quad/Dual M.2 NVMe Slots", "4x SODIMM Slots (up to 128GB)"
        # Dual NVMe Champions
        if 'e14' in t:
            return 8.5, "⚡ Dual M.2 NVMe Slots (2242 + 2280)", "1x Soldered + 1x SODIMM Slot"
        if 'thinkpad p1' in t:
            return 9.5, "⚡ Dual M.2 PCIe NVMe Slots", "2x SODIMM Slots (up to 64GB)"
        # Glued / Locked Down
        if 'surface' in t or 'macbook' in t:
            return 1.0, "🔒 Soldered BGA NVMe / Unified", "Soldered (Non-upgradeable)"
        # Full Modular override for specific models like ProBook 435 x360 before checking soldered x360
        if '435' in t:
            return 9.0, "⚡ M.2 2280 PCIe NVMe (Swappable)", "2x SODIMM Slots (up to 64GB)"
        # Soldered RAM Ultrabooks with Standard NVMe M.2 SSD
        if any(k in t for k in cls._SOLDERED_RAM_KEYWORDS):
            return 5.0, "⚡ M.2 2280 PCIe NVMe (Swappable)", "Soldered (Fixed)"
        # Semi-Modular Business Laptops
        if any(k in t for k in cls._SEMI_MODULAR_KEYWORDS):
            return 7.5, "⚡ M.2 2280 PCIe NVMe (Swappable)", "1x Soldered + 1x SODIMM Slot (max 48GB)"
        # Full Modular SODIMM Dual Slot NVMe
        if any(k in t for k in cls._FULL_MODULAR_KEYWORDS):
            return 9.0, "⚡ M.2 2280 PCIe NVMe (Swappable)", "2x SODIMM Slots (up to 64GB)"
        # Legacy 2.5" SATA Bay
        if any(k in t for k in cls._LEGACY_BAY_KEYWORDS):
            return 8.0, "🐢 2.5\" SATA SSD / Bay", "2x SODIMM Slots"
        return 7.5, "⚡ M.2 2280 PCIe NVMe (Swappable)", "Modular / Semi-Modular"

    @classmethod
    def detect_ram_generation(cls, title: str, cpu: str = "", ram_type: str = "", return_source: bool = False) -> Union[str, Tuple[str, str]]:
        """Detects RAM generation (DDR3L, DDR4, LPDDR4x, DDR5, LPDDR5, Unified LPDDR4x) with provenance tag."""
        t = title.lower()
        cpu_low = (cpu or "").lower()

        # 1. Check explicit mention first
        m = cls._RAM_GEN_EXPLICIT_RE.search(t)
        if m:
            raw_val = m.group(1).upper()
            if raw_val == "DDR3" and (any(k in cpu_low for k in ["4th gen", "5th gen", "3rd gen", "2nd gen"]) or any(k in t for k in ["e7440", "t440", "840 g1", "840 g2"])):
                val = "DDR3L"
            elif raw_val == "LPDDR4X":
                val = "LPDDR4x"
            elif raw_val == "LPDDR5X":
                val = "LPDDR5x"
            else:
                val = raw_val
            return (val, "listing_explicit") if return_source else val

        is_soldered = "soldered" in ram_type.lower() and "sodimm" not in ram_type.lower()
        if "435" in t:
            is_soldered = False

        # 2. Apple Silicon
        if "apple" in cpu_low or "m1" in cpu_low or "a2337" in t:
            return ("Unified LPDDR4x", "chassis_decoder") if return_source else "Unified LPDDR4x"
        if any(k in cpu_low for k in ["m2", "m3"]):
            return ("Unified LPDDR5", "chassis_decoder") if return_source else "Unified LPDDR5"

        # 3. Modern DDR5 era (Core Ultra, 13th Gen, Ryzen 6000+)
        ryzen_6k_plus = bool(cls._RYZEN_6K_RE.search(t + " " + cpu_low))
        if "core ultra" in cpu_low or "13th gen" in cpu_low or ryzen_6k_plus:
            val = "LPDDR5" if is_soldered else "DDR5"
            return (val, "chassis_decoder") if return_source else val

        # 4. Intel 12th Gen Alder Lake transition
        if "12th gen" in cpu_low:
            if is_soldered or any(k in t for k in ["7430", "7330", "x1 carbon"]):
                return ("LPDDR5", "chassis_decoder") if return_source else "LPDDR5"
            return ("DDR4", "chassis_decoder") if return_source else "DDR4"

        # 5. Legacy DDR3L era (4th & 5th Gen)
        if any(k in cpu_low for k in ["4th gen", "5th gen", "3rd gen", "2nd gen"]) or any(k in t for k in ["e7440", "t440", "a1466", "840 g1", "840 g2"]):
            return ("DDR3L", "chassis_decoder") if return_source else "DDR3L"

        # 6. Intel 6th - 11th Gen, AMD 3000-5000
        if is_soldered:
            if any(k in cpu_low for k in ["11th gen", "10th gen"]) or any(k in t for k in ["7420", "7320", "x1 carbon"]):
                return ("LPDDR4x", "chassis_decoder") if return_source else "LPDDR4x"
            return ("LPDDR4", "chassis_decoder") if return_source else "LPDDR4"

        return ("DDR4", "chassis_decoder") if return_source else "DDR4"


    _SCREEN_EXPLICIT_RE = re.compile(
        r'(?:^|[^\d])(11\.6|12\.5|13\.3|13\.5|14\.0|15\.4|15\.6|16\.0|17\.3)\b'
        r'|(?:^|[^\d])(11\.6|12\.5|13\.3|13\.5|14\.0|14|15\.4|15\.6|15|16\.0|16|17\.3|17)\s*(?:"|\'\'|in\b|inch|אינץ|\')',
        re.IGNORECASE
    )

    @classmethod
    def detect_screen_size(cls, title: str, return_source: bool = False) -> Union[float, Tuple[float, str]]:
        t = title.lower()

        # Check explicit mentions like 15 6, 17 3, 13 3 in title
        if '17 3' in t or '17.3' in t: return (17.3, "listing_explicit") if return_source else 17.3
        if '15 6' in t or '15.6' in t: return (15.6, "listing_explicit") if return_source else 15.6
        if '15 4' in t or '15.4' in t: return (15.4, "listing_explicit") if return_source else 15.4
        if '13 3' in t or '13.3' in t: return (13.3, "listing_explicit") if return_source else 13.3
        if '13 5' in t or '13.5' in t: return (13.5, "listing_explicit") if return_source else 13.5
        if '12 5' in t or '12.5' in t: return (12.5, "listing_explicit") if return_source else 12.5
        if '11 6' in t or '11.6' in t: return (11.6, "listing_explicit") if return_source else 11.6
        if ' 14 "' in t or ' 14"' in t or ' 14 אינץ' in t or '14.0' in t: return (14.0, "listing_explicit") if return_source else 14.0

        explicit_m = cls._SCREEN_EXPLICIT_RE.search(t)
        if explicit_m:
            try:
                val_str = explicit_m.group(1) or explicit_m.group(2)
                val = float(val_str)
                return (val, "listing_explicit") if return_source else val
            except (ValueError, TypeError):
                pass

        # Model-based heuristics (chassis decoder)
        if any(k in t for k in ['a517', '17.3']):
            return (17.3, "chassis_decoder") if return_source else 17.3
        if any(k in t for k in ['p52', 'p15', 'p15s', 'p15v', 't15', '3520', '5530', '5531', 'e1504', 'x515', '330 15ikb', 'gaming 3', 'zbook fury 15', 'zbook 15', '850', 'ay010nj', '250 g7', '255 g5', '255 g7']):
            return (15.6, "chassis_decoder") if return_source else 15.6
        if any(k in t for k in ['a1707']):
            return (15.4, "chassis_decoder") if return_source else 15.4
        if any(k in t for k in ['t14', 't14s', 'p14s', 'e14', 'e480', 'x1 carbon', '7410', '7420', '7430', '5410', '5420', '5430', '5431', '5480', 'e7440', '840', 'firefly 14', 'sfx14', 'x1404za', 'x442ur', 't490']):
            return (14.0, "chassis_decoder") if return_source else 14.0
        if any(k in t for k in ['surface 3', 'surface 4']):
            return (13.5, "chassis_decoder") if return_source else 13.5
        if any(k in t for k in ['x13', 'x30l', '830', '435', '7320', '7330', '5330', '5379', 'a2337', 'a1706', 'a1708', 'a1989', 'a2179', 'a2251', 'l13']):
            return (13.3, "chassis_decoder") if return_source else 13.3
        if any(k in t for k in ['x280']):
            return (12.5, "chassis_decoder") if return_source else 12.5

        # Generative algorithmic syntax decoders (Dell, ThinkPad, HP)
        dell_m = cls._DELL_MODEL_RE.search(t)
        if dell_m and ('dell' in t or 'latitude' in t or 'precision' in t):
            s_digit = dell_m.group(2)
            if s_digit == '3': return (13.3, "chassis_decoder") if return_source else 13.3
            if s_digit == '4': return (14.0, "chassis_decoder") if return_source else 14.0
            if s_digit == '5': return (15.6, "chassis_decoder") if return_source else 15.6
            if s_digit == '6': return (16.0, "chassis_decoder") if return_source else 16.0
            if s_digit == '7': return (17.3, "chassis_decoder") if return_source else 17.3

        tp_m = cls._TP_MODEL_RE.search(t)
        if tp_m:
            tp_screen = tp_m.group(2)
            if tp_screen == '13': return (13.3, "chassis_decoder") if return_source else 13.3
            if tp_screen == '14': return (14.0, "chassis_decoder") if return_source else 14.0
            if tp_screen == '15': return (15.6, "chassis_decoder") if return_source else 15.6
            if tp_screen == '16': return (16.0, "chassis_decoder") if return_source else 16.0

        hp_m = cls._HP_MODEL_RE.search(t)
        if hp_m and ('hp' in t or 'elitebook' in t or 'probook' in t):
            hp_screen = hp_m.group(2)
            if hp_screen == '3': return (13.3, "chassis_decoder") if return_source else 13.3
            if hp_screen == '4': return (14.0, "chassis_decoder") if return_source else 14.0
            if hp_screen == '5': return (15.6, "chassis_decoder") if return_source else 15.6
            if hp_screen == '6': return (16.0, "chassis_decoder") if return_source else 16.0

        return (14.0, "fallback_estimate") if return_source else 14.0

    @classmethod
    def detect_weight_kg(cls, title: str, screen_size: float, return_source: bool = False) -> Union[float, Tuple[float, str]]:
        t = title.lower()

        # Check explicit weight in text
        wt_m = cls._WEIGHT_HEBREW_RE.search(t)
        if not wt_m:
            wt_m = cls._WEIGHT_ENGLISH_RE.search(t)
        if wt_m:
            try:
                w_str = wt_m.group(1)
                if w_str:
                    w = float(w_str)
                    if 0.7 <= w <= 5.0:
                        return (w, "listing_explicit") if return_source else w
            except (ValueError, TypeError):
                pass

        # Ultra-lightweight (< 1.1kg)
        if 'x30l' in t: return (0.90, "chassis_decoder") if return_source else 0.90
        if 'x1 carbon' in t: return (1.10, "chassis_decoder") if return_source else 1.10
        if '7320' in t or '7330' in t: return (1.20, "chassis_decoder") if return_source else 1.20
        if any(k in t for k in ['a2337', 'surface 3', 'surface 4', 'x280', 'x13']): return (1.28, "chassis_decoder") if return_source else 1.28

        # Dell Latitude 7420 / 7430 (2-in-1 is ~1.36kg with touch glass & 360 hinges; Clamshell is ~1.22kg)
        if '7420' in t or '7430' in t:
            is_convertible = any(k in t for k in ['2in1', '2-in-1', '2 in 1', 'מגע', 'touch', 'convertible', 'flip'])
            w = 1.36 if is_convertible else 1.22
            return (w, "chassis_decoder") if return_source else w

        # Light Ultrabooks (1.3kg - 1.45kg)
        if any(k in t for k in ['t14s', '830', '840 g8', '7410', 't490s']): return (1.35, "chassis_decoder") if return_source else 1.35
        if any(k in t for k in ['840 g3', 'firefly 14', 'l13', 'a1706', 'a1708', 'a1989', 'a2179', 'a2251']): return (1.40, "chassis_decoder") if return_source else 1.40

        # Standard 14" Business (1.45kg - 1.65kg)
        if any(k in t for k in ['t14', 'p14s', 'e14', 'e480', '5410', '5420', '5430', '5431', '5480', 'e7440', 'sfx14', 'x1404za', 't490']): return (1.55, "chassis_decoder") if return_source else 1.55

        # 15.6" Mainstream / Light Workstation (1.7kg - 1.9kg)
        if any(k in t for k in ['p15s', 't15', '850', '5530', '5531', '3520', 'e1504', 'x515', 'a1707']): return (1.75, "chassis_decoder") if return_source else 1.75
        if any(k in t for k in ['250 g7', '255 g5', '255 g7', 'ay010nj', '330 15ikb', 'x442ur']): return (1.85, "chassis_decoder") if return_source else 1.85

        # Performance Workstations / Gaming / 17.3" (2.1kg - 2.7kg)
        if any(k in t for k in ['thinkpad p1', 'p15v']): return (2.05, "chassis_decoder") if return_source else 2.05
        if any(k in t for k in ['gaming 3', 'zbook 15 g6', 'zbook g7 14']): return (2.25, "chassis_decoder") if return_source else 2.25
        if any(k in t for k in ['p50', 'p51', 'p52', 'p53', 'p70', 'p71', 'p72', 'p73', 'p16', 'p15 gen', 'p15 g1', 'zbook fury 15']): return (2.45, "chassis_decoder") if return_source else 2.45
        if 'a517' in t or screen_size >= 17.0: return (2.60, "chassis_decoder") if return_source else 2.60

        # Precision Mobile Workstations (Heavy desktop replacements)
        if 'precision' in t or 'workstation' in t:
            if screen_size >= 17.0 or any(k in t for k in ['77', '7750', '7760', '7770', '7780']): return (3.10, "chassis_decoder") if return_source else 3.10
            if any(k in t for k in ['75', '76', '7550', '7560', '7540', '7530', '7520', '7510', '3571', '3581']): return (2.45, "chassis_decoder") if return_source else 2.45
            if any(k in t for k in ['55', '56', '5550', '5560', '5570', '35', '3540', '3550', '3560', '3570']): return (1.95, "chassis_decoder") if return_source else 1.95
            return (2.30, "chassis_decoder") if return_source else 2.30

        # Algorithmic syntax decoders for weight
        dell_m = cls._DELL_MODEL_SIMPLE_RE.search(t)
        if dell_m and ('dell' in t or 'latitude' in t):
            tier = dell_m.group(1)
            s_digit = dell_m.group(2)
            if tier in ('7', '9'):
                w = 1.20 if s_digit == '3' else 1.35
            elif tier == '5':
                w = 1.35 if s_digit == '3' else (1.55 if s_digit == '4' else 1.75)
            elif tier == '3':
                w = 1.60 if s_digit == '4' else 1.85
            else:
                w = 1.50
            return (w, "chassis_decoder") if return_source else w

        tp_m = cls._TP_MODEL_RE.search(t)
        if tp_m:
            s_digit = tp_m.group(2)
            if tp_m.group(3): w = 1.25 if s_digit == '13' else 1.35
            elif s_digit == '13': w = 1.35
            elif s_digit == '14': w = 1.55
            elif s_digit == '15': w = 1.75
            elif s_digit == '16': w = 1.85
            else: w = 1.50
            return (w, "chassis_decoder") if return_source else w

        hp_m = cls._HP_MODEL_RE.search(t)
        if hp_m and ('hp' in t or 'elitebook' in t or 'probook' in t):
            tier = hp_m.group(1)
            s_digit = hp_m.group(2)
            if tier == '8': w = 1.28 if s_digit == '3' else 1.38
            else: w = 1.40 if s_digit == '3' else (1.50 if s_digit == '4' else 1.78)
            return (w, "chassis_decoder") if return_source else w

        # Fallback by screen size
        if screen_size <= 12.5: return (1.20, "fallback_estimate") if return_source else 1.20
        if screen_size <= 13.5: return (1.30, "fallback_estimate") if return_source else 1.30
        if screen_size <= 14.0: return (1.50, "fallback_estimate") if return_source else 1.50
        if screen_size <= 15.6: return (1.80, "fallback_estimate") if return_source else 1.80
        return (2.40, "fallback_estimate") if return_source else 2.40

    @classmethod
    def detect_battery_wh(cls, title: str, weight_kg: float, return_source: bool = False) -> Union[int, Tuple[int, str]]:
        t = title.lower()

        # Check explicit battery in text
        bat_m = cls._BATTERY_HEBREW_RE.search(t)
        if not bat_m:
            bat_m = cls._BATTERY_ENGLISH_RE.search(t)
        if bat_m:
            try:
                b = int(bat_m.group(1))
                if 25 <= b <= 120:
                    return (b, "listing_explicit") if return_source else b
            except (ValueError, TypeError):
                pass

        # Heavy Workstations / Long Battery beasts
        if any(k in t for k in ['p52', 'p15 gen', 'p15 g1', 'zbook fury 15', 'p1 gen 3']): return (90, "chassis_decoder") if return_source else 90
        if any(k in t for k in ['zbook 15 g6', '5531', '5431', 'p15v']): return (68, "chassis_decoder") if return_source else 68
        if any(k in t for k in ['7420', '7430', '5420', '5421', '5520', '5521']): return (63, "chassis_decoder") if return_source else 63
        if any(k in t for k in ['x1 carbon', 't14s', '7320', '7330', '5430', '5530', '5330', 't490s']): return (57, "chassis_decoder") if return_source else 57
        if any(k in t for k in ['t14', 'p14s', 'e14 gen 4', '830 g8', '840 g8', 'firefly 14', 'p15s', 't490']): return (51, "chassis_decoder") if return_source else 51
        if any(k in t for k in ['a2337', 'a1706', 'a1708', 'a1989', 'a2179', 'a2251', 'surface 3', 'surface 4']): return (49, "chassis_decoder") if return_source else 49
        if any(k in t for k in ['e480', '5410', '5480', 'x280', 'x13', '840 g3', 'e7440', '435 g7']): return (45, "chassis_decoder") if return_source else 45
        if any(k in t for k in ['e1504', 'x515', '250 g7', '255 g5', 'ay010nj', 'a517', '330 15ikb']): return (41, "chassis_decoder") if return_source else 41

        if any(k in t for k in ['workstation', 'precision', 'fury', 'p15', 'p52', 'p53']): return (90, "chassis_decoder") if return_source else 90

        # Fallback by weight
        if weight_kg >= 2.3: return (83, "fallback_estimate") if return_source else 83
        if weight_kg >= 1.7: return (54, "fallback_estimate") if return_source else 54
        return (50, "fallback_estimate") if return_source else 50

    @classmethod
    def is_laptop(cls, title: str) -> bool:
        t = title.lower()
        if any(k in t for k in cls._NON_LAPTOP_KEYWORDS):
            return False
        return True

    @classmethod
    def validate_hardware_sanity(
        cls,
        title: str,
        screen_size: float,
        weight_kg: float,
        battery_wh: int,
        is_2in1: bool,
    ) -> Tuple[str, str]:
        """Validate physical hardware sanity and detect impossible / copy-pasted seller claims."""
        t = title.lower()
        weight_warning = ""
        battery_warning = ""

        # 1. 2-in-1 Touchscreen Weight Floor
        # Dual steel 360 hinges + digitizer + front glass impose a physical floor (~1.35kg for 14"+).
        if is_2in1 and screen_size >= 13.5 and weight_kg < 1.25:
            weight_warning = f"Seller states {weight_kg}kg (likely clamshell typo; 14\" 2-in-1 chassis floor is ~1.36kg)"

        # 2. Mainstream 15.6"+ Weight Floor
        elif screen_size >= 15.6 and weight_kg < 1.40 and 'gram' not in t:
            weight_warning = f"Seller states {weight_kg}kg (unusually low for {screen_size}\" screen; expected ~1.75kg)"

        # 3. Heavy Workstation Weight Floor (Precision 7000, ZBook Fury, ThinkPad P-Series thick)
        elif (
            ('zbook fury' in t or 'thinkpad p52' in t or 'thinkpad p53' in t or ('thinkpad p15' in t and 'p15s' not in t and 'p15v' not in t))
            or (('precision 7' in t or 'precision 35' in t) and 'precision 55' not in t)
        ) and weight_kg < 1.85:
            weight_warning = f"Seller states {weight_kg}kg (heavy workstation expected ~2.2kg-2.6kg)"

        # 4. Battery Capacity vs AC Charger Wattage
        # Flight carry-on legal limit is 100 Wh (99.9 Wh). Listings claiming > 100 Wh usually confuse charger watts.
        if battery_wh > 100:
            battery_warning = f"Seller states {battery_wh}Wh (likely AC adapter wattage; airline safety limit is 99Wh)"

        return weight_warning, battery_warning

    @classmethod
    def build_laptop(
        cls,
        store: str,
        title: str,
        price_ils: int,
        url: str,
        deal_price_ils: Optional[int] = None,
        deal_label: Optional[str] = None,
        warranty_months: int = 12,
        stock_status: str = "🟢 In Stock",
        model: Optional[str] = None,
        gpu: Optional[str] = None,
        is_touch: Optional[bool] = None,
        is_2in1: Optional[bool] = None,
        analysis_text: Optional[str] = None,
        image_url: str = "",
        scraped_at: Optional[str] = None,
    ) -> LaptopItem:
        """Factory that constructs a fully normalized LaptopItem with hardware analysis and provenance tags."""
        text = analysis_text or title

        brand = cls.detect_brand(title)
        if brand == "Business Laptop" and analysis_text:
            brand = cls.detect_brand(analysis_text)

        series = cls.detect_series(title)
        if series == "Business Series" and analysis_text:
            series = cls.detect_series(analysis_text)
        resolved_model = model or (title.split('/')[0].strip() if '/' in title else title)
        cpu = cls.detect_cpu(text)
        ram_gb = cls.detect_ram_gb(text)
        storage_gb = cls.detect_storage_gb(text)

        score, storage_type, ram_type = cls.analyze_architecture(text)
        ram_gen, ram_src = cls.detect_ram_generation(text, cpu=cpu, ram_type=ram_type, return_source=True)
        screen_size, screen_src = cls.detect_screen_size(text, return_source=True)
        weight_kg, weight_src = cls.detect_weight_kg(text, screen_size, return_source=True)
        battery_wh, battery_src = cls.detect_battery_wh(text, weight_kg, return_source=True)
        confidence_level = "estimated" if (screen_src == "fallback_estimate" or weight_src == "fallback_estimate" or ram_src == "fallback_estimate") else "verified"

        resolved_touch = is_touch if is_touch is not None else (cls.is_touch(title) or (cls.is_touch(analysis_text) if analysis_text else False))
        resolved_2in1 = is_2in1 if is_2in1 is not None else (cls.is_2in1(title) or (cls.is_2in1(analysis_text) if analysis_text else False))

        weight_warn, battery_warn = cls.validate_hardware_sanity(
            title=text,
            screen_size=screen_size,
            weight_kg=weight_kg,
            battery_wh=battery_wh,
            is_2in1=resolved_2in1,
        )
        if weight_warn or battery_warn:
            confidence_level = "warning"

        if gpu is None:
            resolved_gpu = "NVIDIA Quadro P520" if any(k in text.lower() for k in ['p520', 'p14s', 'p15s']) else "Integrated"
        else:
            resolved_gpu = gpu

        resolved_deal_price = deal_price_ils if deal_price_ils is not None else price_ils
        resolved_deal_label = deal_label or f"{resolved_deal_price:,} ₪"
        resolved_scraped_at = scraped_at or datetime.date.today().isoformat()

        return LaptopItem(
            store=store,
            title=title,
            brand=brand,
            series=series,
            model=resolved_model,
            cpu=cpu,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            price_ils=price_ils,
            deal_price_ils=resolved_deal_price,
            deal_label=resolved_deal_label,
            storage_type=storage_type,
            ram_type=ram_type,
            upgradability_score=score,
            warranty_months=warranty_months,
            stock_status=stock_status,
            url=url,
            gpu=resolved_gpu,
            is_touch=resolved_touch,
            is_2in1=resolved_2in1,
            image_url=image_url,
            screen_size_in=round(screen_size, 1),
            weight_kg=round(weight_kg, 2),
            battery_wh=battery_wh,
            ram_gen=ram_gen,
            ram_source=ram_src,
            screen_source=screen_src,
            weight_source=weight_src,
            battery_source=battery_src,
            confidence_level=confidence_level,
            weight_warning=weight_warn,
            battery_warning=battery_warn,
            scraped_at=resolved_scraped_at,
        )

