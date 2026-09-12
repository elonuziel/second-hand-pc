"""
Essential catalog health, spec parser, and web app validation suite.
Specifically tailored for the second-hand-pc catalog (for you and your friends).

Run via:
    python3 test_catalog.py
or:
    python3 -m unittest test_catalog.py
"""

import json
import os
import subprocess
import unittest
from unittest.mock import patch
from enrich_specs import SpecEnricher
from laptop_parsing import is_desktop_title, is_laptop_title, last_valid_price
from scraper import (
    HardwareClassifier,
    CWCScraper,
    GroqSpecEnhancer,
    LTSScraper,
    LaptopItem,
    MasterLaptopAuditor,
    RecompScraper,
    PayngoScraper,
    ALMScraper,
    ShufersalScraper,
    P1000Scraper,
    LastPriceScraper,
    VoltScraper,
    OfekPCScraper,
    ITOutletScraper,
    EcologyScraper,
)


class TestCatalogDataHealth(unittest.TestCase):
    """Verifies that scraped data is alive, valid, and contains all expected stores."""

    @classmethod
    def setUpClass(cls):
        catalog_path = os.path.join(os.path.dirname(__file__), "scraped_laptops.json")
        cls.catalog_path = catalog_path
        if os.path.exists(catalog_path):
            with open(catalog_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, list):
                    cls.items = raw
                elif isinstance(raw, dict):
                    cls.items = []
                    for k, v in raw.items():
                        if isinstance(v, list):
                            cls.items.extend(v)
        else:
            cls.items = []

    def test_catalog_file_exists_and_populated(self):
        """Catalog JSON must exist and contain a healthy pool of laptops (> 40)."""
        self.assertTrue(os.path.exists(self.catalog_path), "scraped_laptops.json does not exist!")
        self.assertGreater(len(self.items), 40, f"Expected > 40 laptops, found only {len(self.items)}")

    def test_all_ten_stores_represented(self):
        """Ensure scrapers for all 12 laptop stores are working."""
        stores_found = set(item.get("store", "") for item in self.items)
        expected_stores = ["Ecology", "IT Outlet", "LTS", "Recomp", "Olam HaKolnoa", "Payngo", "ALM", "Shufersal", "P1000", "LastPrice", "Volt", "Ofek PC"]
        
        for expected in expected_stores:
            matching = [s for s in stores_found if expected.lower().replace(" ", "") in s.lower().replace(" ", "")]
            self.assertTrue(
                len(matching) > 0,
                f"Store '{expected}' has 0 laptops in the catalog! Scraper may have failed."
            )

    def test_every_laptop_has_essential_specs_and_valid_pricing(self):
        """Every laptop must have realistic pricing, valid link, and positive specs."""
        for item in self.items:
            title = item.get("title", "")
            self.assertTrue(bool(title and title.strip()), "Found laptop with empty title")

            # Price must be realistic (300 to 15,000 NIS)
            price = item.get("deal_price_ils") or item.get("price_ils") or 0
            self.assertGreater(price, 300, f"Unrealistic or missing price for: {title} ({price} NIS)")
            self.assertLess(price, 15000, f"Price too high for second hand: {title} ({price} NIS)")

            # Store URL must be valid
            url = item.get("url", "")
            self.assertTrue(url.startswith("http://") or url.startswith("https://"), f"Invalid URL for: {title}")

            # RAM & Storage must be realistic positive numbers
            ram = item.get("ram_gb", 0)
            self.assertIn(ram, [4, 8, 12, 16, 24, 32, 48, 64], f"Unexpected RAM value {ram}GB for {title}")

            storage = item.get("storage_gb", 0)
            self.assertGreaterEqual(storage, 64, f"Unexpected storage {storage}GB for {title}")

    def test_no_broken_local_paths_in_catalog_files(self):
        """Verify markdown catalog contains no absolute local machine paths (/home/...)."""
        md_path = os.path.join(os.path.dirname(__file__), "full_catalog.md")
        if os.path.exists(md_path):
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("/home/elonu/", content, "full_catalog.md contains local absolute path")
            self.assertNotIn("/home/", content, "full_catalog.md contains local absolute path")

    def test_spec_provenance_and_confidence_tagging(self):
        """Every catalog laptop must be tagged with spec sources and confidence levels in raw data."""
        valid_sources = {"listing_explicit", "chassis_decoder", "fallback_estimate", "ai_audit"}
        valid_confidences = {"verified", "estimated", "warning"}
        for item in self.items:
            title = item.get("title", "")
            sc_src = item.get("screen_source")
            wt_src = item.get("weight_source")
            bat_src = item.get("battery_source")
            ram_src = item.get("ram_source")
            ram_gen = item.get("ram_gen")
            conf = item.get("confidence_level")

            self.assertIn(sc_src, valid_sources, f"Invalid screen_source '{sc_src}' for: {title}")
            self.assertIn(wt_src, valid_sources, f"Invalid weight_source '{wt_src}' for: {title}")
            self.assertIn(bat_src, valid_sources, f"Invalid battery_source '{bat_src}' for: {title}")
            self.assertIn(ram_src, valid_sources, f"Invalid ram_source '{ram_src}' for: {title}")
            self.assertTrue(bool(ram_gen), f"Missing ram_gen for: {title}")
            self.assertIn(conf, valid_confidences, f"Invalid confidence_level '{conf}' for: {title}")


class TestHardwareParsers(unittest.TestCase):
    """Verifies that CPU generation, RAM, Storage, and form factors are accurately parsed."""

    def test_cpu_generation_detection(self):
        """Accurately identify Intel generations (2nd to 13th), Apple Silicon, AMD, Core Ultra, and Xeon."""
        test_cases = [
            ("Lenovo ThinkPad T14 Gen 2 i5 1135G7", "Core i5 (11th Gen)"),
            ("Dell Latitude 5430 i7 1250U 12th Gen", "Core i7 (12th Gen)"),
            ("Dell Latitude 5420 i5 1145G7", "Core i5 (11th Gen)"),
            ("Lenovo ThinkPad X13 G1 i7 10510U", "Core i7 (10th Gen)"),
            ("Lenovo ThinkPad T480s i5 8350U", "Core i5 (8th Gen)"),
            ("Apple MacBook Air M1", "Apple M1"),
            ("Lenovo ThinkPad T14 AMD Ryzen 5 PRO", "AMD Ryzen 5 PRO"),
            ("Lenovo ThinkPad E14 Intel Core Ultra 5 125U", "Intel Core Ultra 5"),
            ("Lenovo ThinkPad P53 Intel Xeon E-2276M", "Intel Xeon"),
            ("ThinkPad X13 Gen 2 Core i5-1145G7", "Core i5 (11th Gen)"),
            ("Dell Latitude i7-8656U M2 256GB SSD", "Core i7 (8th Gen)"),
            # 5-digit H-series processors
            ("Core i7-10850H 512GB SSD 16GB ThinkPad P15", "Core i7 (10th Gen)"),
            ("Precision 3561 Core i5-11500H 512GB 16GB", "Core i5 (11th Gen)"),
            ("Precision 3561 Core i7-11800H 512GB 32GB", "Core i7 (11th Gen)"),
            # Hebrew Shorthand
            ("Thinkpad X1 Carbon I7-10 16GB 256GB", "Core i7 (10th Gen)"),
            ("T14s I5-10 256 16 ThinkPad T14", "Core i5 (10th Gen)"),
            ("X1 YOGA I7-8 16/512", "Core i7 (8th Gen)"),
            # 2nd & 3rd Gen Intel
            ("HP EliteBook Folio 9470m i7-3687U 180GB SSD", "Core i7 (3rd Gen)"),
            ("ThinkPad X230 Core i5-3210M 8GB", "Core i5 (3rd Gen)"),
            ("Dell Latitude E6420 Core-i5 2nd Gen", "Core i5 (2nd Gen)"),
            ("ThinkPad T420 Core i5 2.5Ghz", "Core i5 (2nd Gen)"),
            ("DELL Inspiron N5110 i5-2410M", "Core i5 (2nd Gen)"),
            # AMD non-Ryzen distinction
            ("Lenovo A4 4GB 64GBSSD מחשב נייד מחודש 11.6", "AMD A-Series"),
            ("Lenovo 4GB 64SSD 11.6\" AMD-4020e", "AMD Athlon"),
            ("HP EliteBook 745 G2 מעבד A10", "AMD A-Series"),
            # Legacy Intel
            ("Lenovo X60 C2D L2400", "Intel Core 2 Duo"),
            ("DELL Inspiron Mini 10v", "Intel Atom"),
            ("Lenovo ThinkPad T43", "Intel Pentium"),
        ]
        for title, expected_cpu in test_cases:
            detected = HardwareClassifier.detect_cpu(title)
            self.assertEqual(detected, expected_cpu, f"Failed CPU detection on: {title}")

    def test_shared_listing_parsers(self):
        self.assertTrue(is_laptop_title("מחשב נייד Dell Latitude 5420"))
        self.assertTrue(is_laptop_title("HP ProBook 450 G8"))
        self.assertTrue(is_laptop_title("Dell Precision 3561 Mobile Workstation"))
        self.assertTrue(is_laptop_title("Lenovo Yoga Slim 7"))
        self.assertFalse(is_laptop_title("מחשב נייח Dell OptiPlex Micro"))
        self.assertTrue(is_desktop_title("Lenovo ThinkCentre Tiny"))
        self.assertEqual(last_valid_price(["newsletter", "2,490 ₪"]), 2490)
        self.assertIsNone(last_valid_price(["no price"], minimum=601))
        self.assertIsNone(last_valid_price(["300 ₪"], minimum=601))

    def test_ram_and_storage_extraction(self):
        """Ensure RAM and SSD sizes are extracted and VRAM is isolated."""
        # RAM
        self.assertEqual(HardwareClassifier.detect_ram_gb("Dell 16GB RAM 512GB SSD"), 16)
        self.assertEqual(HardwareClassifier.detect_ram_gb("ThinkPad 32 GB RAM 1TB"), 32)
        self.assertEqual(HardwareClassifier.detect_ram_gb("Laptop 8g ram"), 8)

        # GPU VRAM isolation: 4GB Graphics / 6GB VRAM must not override system RAM
        self.assertEqual(HardwareClassifier.detect_ram_gb("HP ProBook 450 G8 15.6 with GTX 1650 4GB Graphics"), 16)
        self.assertEqual(HardwareClassifier.detect_ram_gb("Dell Precision 7550 32GB RAM 512GB SSD RTX 3000 6GB"), 32)
        self.assertEqual(HardwareClassifier.detect_ram_gb("Lenovo Legion 5 16GB 512GB RTX 3060 6GB"), 16)

        # Storage (including Hebrew 'טרה' for 1TB, 64GB netbooks, 180GB/320GB)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Dell 256GB SSD"), 256)
        self.assertEqual(HardwareClassifier.detect_storage_gb("HP 512GB SSD NVMe"), 512)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Lenovo 1TB SSD"), 1000)
        self.assertEqual(HardwareClassifier.detect_storage_gb("מחשב נייד 1 טרה אחסון"), 1000)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Lenovo A4 4GB 64GBSSD מחשב נייד"), 64)
        self.assertEqual(HardwareClassifier.detect_storage_gb("HP Folio 9470m 180GB SSD"), 180)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Lenovo X61s 320GB HDD"), 320)

    def test_ram_generation_detection(self):
        """Ensure RAM generation (DDR3L, DDR4, LPDDR4x, DDR5, LPDDR5, Unified LPDDR4x) is detected accurately."""
        test_cases = [
            # Title, CPU, RAM Architecture -> Expected RAM Generation, Expected Source
            ("Dell Latitude 5420 i5 11th Gen", "Core i5 (11th Gen)", "2x SODIMM Slots (up to 64GB)", "DDR4", "chassis_decoder"),
            ("Dell Latitude 7420 i7 11th Gen", "Core i7 (11th Gen)", "Soldered (Fixed)", "LPDDR4x", "chassis_decoder"),
            ("Dell Latitude 7430 i7 12th Gen", "Core i7 (12th Gen)", "Soldered (Fixed)", "LPDDR5", "chassis_decoder"),
            ("Dell Latitude 5430 i5 12th Gen", "Core i5 (12th Gen)", "2x SODIMM Slots (up to 64GB)", "DDR4", "chassis_decoder"),
            ("Lenovo ThinkPad T14 Gen 2", "Core i5 (11th Gen)", "1x Soldered + 1x SODIMM Slot", "DDR4", "chassis_decoder"),
            ("Lenovo ThinkPad L13 Gen 3", "Core i5 (13th Gen)", "2x SODIMM Slots", "DDR5", "chassis_decoder"),
            ("Dell Latitude E7440 i5 4th Gen", "Core i5 (4th Gen)", "2x SODIMM Slots", "DDR3L", "chassis_decoder"),
            ("MacBook Air M1", "Apple M1", "Soldered (Non-upgradeable)", "Unified LPDDR4x", "chassis_decoder"),
            ("HP ProBook x360 435 G7 Ryzen 7", "AMD Ryzen 7 PRO", "2x SODIMM Slots (up to 64GB)", "DDR4", "chassis_decoder"),
            ("Asus Vivobook DDR4 16GB", "Core i5 (10th Gen)", "Modular / Semi-Modular", "DDR4", "listing_explicit"),
            ("Laptop DDR5 32GB", "Core i7 (12th Gen)", "2x SODIMM Slots", "DDR5", "listing_explicit"),
            ("Lenovo ThinkPad X1 Carbon Gen 9", "Core i7 (11th Gen)", "Soldered (Fixed)", "LPDDR4x", "chassis_decoder"),
        ]

        for title, cpu, ram_type, expected_gen, expected_src in test_cases:
            gen, src = HardwareClassifier.detect_ram_generation(title, cpu=cpu, ram_type=ram_type, return_source=True)
            self.assertEqual(gen, expected_gen, f"Failed ram_gen for {title} (got {gen}, expected {expected_gen})")
            self.assertEqual(src, expected_src, f"Failed ram_source for {title} (got {src}, expected {expected_src})")

    def test_physical_specs_enrichment(self):
        """Ensure screen size, weight, and battery Wh are estimated accurately."""
        # Screen size
        self.assertEqual(SpecEnricher.detect_screen_size("ThinkPad T14"), 14.0)
        self.assertEqual(SpecEnricher.detect_screen_size("Dell Latitude 5530 15.6"), 15.6)
        self.assertEqual(SpecEnricher.detect_screen_size("HP EliteBook x360 830 13.3"), 13.3)

        # Algorithmic syntax decoders
        self.assertEqual(SpecEnricher.detect_screen_size("Dell Latitude 7420"), 14.0)
        self.assertEqual(SpecEnricher.detect_screen_size("Dell Latitude 5330"), 13.3)
        self.assertEqual(SpecEnricher.detect_screen_size("Dell Latitude 3540"), 15.6)
        self.assertEqual(SpecEnricher.detect_screen_size("Lenovo ThinkPad X13 Gen 2"), 13.3)
        self.assertEqual(SpecEnricher.detect_screen_size("HP EliteBook 830 G8"), 13.3)
        self.assertEqual(SpecEnricher.detect_screen_size("HP EliteBook 840 G7"), 14.0)

        # Lightweight vs standard weight vs heavy workstation
        self.assertLessEqual(SpecEnricher.detect_weight_kg("ThinkPad X1 Carbon", 14.0), 1.2)
        self.assertGreaterEqual(SpecEnricher.detect_weight_kg("ThinkPad P15 Gen 1", 15.6), 2.0)
        self.assertGreaterEqual(SpecEnricher.detect_weight_kg("Dell Precision 7550", 15.6), 2.4)
        self.assertLessEqual(SpecEnricher.detect_weight_kg("Dell Latitude 7420", 14.0), 1.4)

        # Battery Wh
        self.assertGreaterEqual(SpecEnricher.detect_battery_wh("ThinkPad P15", 2.4), 80)
        self.assertGreaterEqual(SpecEnricher.detect_battery_wh("Dell Latitude 7420", 1.35), 50)

        # Spec source tags verification
        size, src = SpecEnricher.detect_screen_size("Dell Latitude 5530 15.6", return_source=True)
        self.assertEqual(size, 15.6)
        self.assertEqual(src, "listing_explicit")

        size, src = SpecEnricher.detect_screen_size("ThinkPad T14", return_source=True)
        self.assertEqual(size, 14.0)
        self.assertEqual(src, "chassis_decoder")

        size, src = SpecEnricher.detect_screen_size("Mystery Generic Model", return_source=True)
        self.assertEqual(src, "fallback_estimate")

        w, src = SpecEnricher.detect_weight_kg("ThinkPad X1 Carbon", 14.0, return_source=True)
        self.assertEqual(w, 1.10)
        self.assertEqual(src, "chassis_decoder")

        w, src = SpecEnricher.detect_weight_kg("Unknown 14 Laptop", 14.0, return_source=True)
        self.assertEqual(src, "fallback_estimate")

        b, src = SpecEnricher.detect_battery_wh("ThinkPad P15", 2.4, return_source=True)
        self.assertEqual(b, 90)
        self.assertEqual(src, "chassis_decoder")

        b, src = SpecEnricher.detect_battery_wh("Unknown Laptop", 1.5, return_source=True)
        self.assertEqual(src, "fallback_estimate")

    def test_unified_touch_and_2in1_detection(self):
        """Ensure touch and 360 convertible 2-in-1 detection is consistent across all store formats."""
        self.assertTrue(HardwareClassifier.is_2in1("Lenovo ThinkPad X13 Yoga Touch"))
        self.assertTrue(HardwareClassifier.is_2in1("HP EliteBook x360 830 G8"))
        self.assertTrue(HardwareClassifier.is_2in1("Dell Inspiron 14 5410 2-in-1 Touch"))
        self.assertFalse(HardwareClassifier.is_2in1("Dell Latitude 7420 i7 16GB"))

        self.assertTrue(HardwareClassifier.is_touch("Lenovo ThinkPad T14 Touch"))
        self.assertTrue(HardwareClassifier.is_touch("מחשב נייד טאץ 14 אינץ"))
        self.assertFalse(HardwareClassifier.is_touch("HP ProBook 450 G8 15.6 inch"))

    def test_groq_spec_enhancer_graceful_handling(self):
        """Ensure GroqSpecEnhancer initializes safely and handles empty/fallback batches without crashing."""
        from scraper import GroqSpecEnhancer
        enhancer = GroqSpecEnhancer(api_key="fake_key_for_testing")
        self.assertTrue(enhancer.enabled)
        # Empty batch should return empty list immediately
        self.assertEqual(enhancer.enhance_batch([]), [])
        self.assertEqual(enhancer.enhance_batch_chunk([]), [])

    def test_hardware_classifier_build_laptop_factory(self):
        """Ensure HardwareClassifier.build_laptop normalizes specs and sets provenance consistently."""
        # 1. Standard verified business laptop
        laptop = HardwareClassifier.build_laptop(
            store="IT Outlet",
            title="Dell Latitude 5430 i7 16GB 512GB SSD",
            price_ils=2200,
            url="https://itoutlet.co.il/product/123",
        )
        self.assertEqual(laptop.brand, "Dell")
        self.assertEqual(laptop.series, "Latitude")
        self.assertEqual(laptop.ram_gb, 16)
        self.assertEqual(laptop.storage_gb, 512)
        self.assertEqual(laptop.screen_size_in, 14.0)
        self.assertLessEqual(laptop.weight_kg, 1.6)
        self.assertEqual(laptop.screen_source, "chassis_decoder")
        self.assertEqual(laptop.confidence_level, "verified")
        self.assertFalse(laptop.is_touch)
        self.assertFalse(laptop.is_2in1)
        self.assertEqual(laptop.deal_price_ils, 2200)
        self.assertEqual(laptop.ram_gen, "DDR4")
        self.assertEqual(laptop.ram_source, "chassis_decoder")

        # 2. Touch 2-in-1 with analysis_text (LTS style)
        lts_laptop = HardwareClassifier.build_laptop(
            store="LaptopTech LTS",
            title="Lenovo ThinkPad X13 Yoga Touch",
            price_ils=1850,
            url="https://lts.co.il/item",
            analysis_text="thinkpad x13 yoga touch i5 16gb 256gb",
            warranty_months=12,
        )
        self.assertEqual(lts_laptop.brand, "Lenovo")
        self.assertTrue(lts_laptop.is_touch)
        self.assertTrue(lts_laptop.is_2in1)
        self.assertEqual(lts_laptop.screen_size_in, 13.3)
        self.assertEqual(lts_laptop.confidence_level, "verified")

        # 3. Unidentifiable laptop triggering fallback estimate
        unknown = HardwareClassifier.build_laptop(
            store="Recomp Computers",
            title="Generic Laptop With No Identifiers",
            price_ils=1000,
            url="https://recomp.co.il/item",
        )
        self.assertEqual(unknown.screen_source, "fallback_estimate")
        self.assertEqual(unknown.confidence_level, "estimated")

    def test_hardware_sanity_validation(self):
        """Ensure impossible/conflicting hardware claims produce warnings while preserving seller claims."""
        # 1. Latitude 7420 2-in-1 with seller claim 1.18kg (carbon clamshell copy-paste)
        item_2in1 = HardwareClassifier.build_laptop(
            store="P1000",
            title="מחשב נייד מסך מגע 2IN1 DELL Latitude 7420 i5 מחודש",
            price_ils=1999,
            url="https://www.p1000.co.il/sales/saledetails.aspx?productid=216717",
            analysis_text="מחשב נייד מסך מגע 2IN1 DELL Latitude 7420 i5 משקל 1.18 ק\"ג סוללה 63Wh",
        )
        self.assertEqual(item_2in1.weight_kg, 1.18)
        self.assertEqual(item_2in1.weight_source, "listing_explicit")
        self.assertTrue(item_2in1.is_2in1)
        self.assertIn("clamshell typo", item_2in1.weight_warning)
        self.assertIn("1.36kg", item_2in1.weight_warning)
        self.assertEqual(item_2in1.confidence_level, "warning")

        # 2. Mainstream 15.6" laptop claiming 1.2kg
        w_warn, b_warn = HardwareClassifier.validate_hardware_sanity(
            title="Dell Latitude 3520 15.6",
            screen_size=15.6,
            weight_kg=1.2,
            battery_wh=54,
            is_2in1=False,
        )
        self.assertIn("unusually low", w_warn)
        self.assertEqual(b_warn, "")

        # 3. Workstation claiming lightweight 1.4kg
        w_warn_ws, _ = HardwareClassifier.validate_hardware_sanity(
            title="Dell Precision 7550 Workstation",
            screen_size=15.6,
            weight_kg=1.4,
            battery_wh=68,
            is_2in1=False,
        )
        self.assertIn("heavy workstation", w_warn_ws)

        # 4. Charger wattage mistaken for battery capacity (>100Wh)
        _, b_warn_charger = HardwareClassifier.validate_hardware_sanity(
            title="HP EliteBook 840 G8",
            screen_size=14.0,
            weight_kg=1.35,
            battery_wh=130,
            is_2in1=False,
        )
        self.assertIn("AC adapter wattage", b_warn_charger)
        self.assertIn("airline safety limit", b_warn_charger)

        # 5. Normal verified laptop has no warnings
        w_ok, b_ok = HardwareClassifier.validate_hardware_sanity(
            title="Dell Latitude 5430",
            screen_size=14.0,
            weight_kg=1.45,
            battery_wh=54,
            is_2in1=False,
        )
        self.assertEqual(w_ok, "")
        self.assertEqual(b_ok, "")


class TestNewLaptopScrapers(unittest.TestCase):
    """Unit tests for the 6 newly integrated laptop scrapers using mock payloads."""

    def test_missing_detail_page_prices_do_not_use_synthetic_fallbacks(self):
        self.assertIsNone(LTSScraper(None)._parse_product_page_price("<html>No price</html>"))
        self.assertIsNone(RecompScraper(None)._parse_recomp_price("<html>No price</html>"))

    def test_master_auditor_returns_configured_store_order(self):
        class FakeScraper:
            def __init__(self, session):
                self.session = session

            def scrape(self):
                return []

        auditor = MasterLaptopAuditor(session=object())
        auditor.scraper_classes = {"first": FakeScraper, "second": FakeScraper, "third": FakeScraper}
        self.assertEqual(list(auditor.run(max_workers=3)), ["first", "second", "third"])

    @patch("scraper.requests.post")
    def test_ai_provenance_only_marks_returned_fields(self, mock_post):
        item = LaptopItem(
            store="Test",
            title="Test Laptop",
            brand="Test",
            series="Test",
            model="Test",
            cpu="Core i5",
            ram_gb=16,
            storage_gb=512,
            price_ils=1000,
            deal_price_ils=1000,
            deal_label="1,000 NIS",
            storage_type="NVMe",
            ram_type="DDR4",
            upgradability_score=5.0,
            warranty_months=12,
            stock_status="In Stock",
            url="https://example.com/test",
        )
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": '[{"id": 0, "battery_wh": 60}]'}}]
        }

        enhanced = GroqSpecEnhancer(api_key="test").enhance_batch([item])
        self.assertEqual(enhanced[0].battery_source, "ai_audit")
        self.assertEqual(enhanced[0].ram_source, "chassis_decoder")

    @patch("scraper.fetch_resilient_url")
    def test_cwc_scraper_parsing(self, mock_fetch):
        mock_fetch.return_value = (200, json.dumps([
            {
                "name": "מחשב נייד מחודש Dell Latitude 5420 i7 16GB 512GB",
                "prices": {"price": "219000", "currency_minor_unit": 2},
                "permalink": "https://www.cwc.co.il/product/dell-5420",
                "images": [{"src": "https://www.cwc.co.il/img/dell5420.jpg"}],
                "description": "מעבד i7-1185G7 סוללה 63Wh משקל 1.35 ק\"ג כולל 3 שנות אחריות VIP",
                "short_description": "מחשב מעולה"
            },
            {
                "name": "מחשב נייח מחודש Lenovo Tiny M720q",
                "prices": {"price": "120000", "currency_minor_unit": 2},
                "permalink": "https://www.cwc.co.il/product/lenovo-tiny",
                "images": [],
                "description": "מיני מחשב נייח",
                "short_description": ""
            }
        ]))
        scraper = CWCScraper()
        items = scraper.scrape()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].store, "Olam HaKolnoa")
        self.assertEqual(items[0].brand, "Dell")
        self.assertEqual(items[0].price_ils, 2190)
        self.assertEqual(items[0].warranty_months, 36)
        self.assertEqual(items[0].ram_gb, 16)
        self.assertEqual(items[0].storage_gb, 512)
        self.assertEqual(items[0].cpu, "Core i7 (11th Gen)")
        self.assertEqual(items[0].battery_wh, 63)
        self.assertEqual(items[0].battery_source, "listing_explicit")
        self.assertEqual(items[0].weight_kg, 1.35)
        self.assertEqual(items[0].weight_source, "listing_explicit")

    @patch("scraper.fetch_resilient_url")
    def test_payngo_scraper_parsing(self, mock_fetch):
        mock_html = '''
        <form method="post" action="https://www.payngo.co.il/checkout/cart/add/product/12345/">
            <a class="product-item-link" href="https://www.payngo.co.il/lenovo-thinkpad-t14.html">
                מחשב נייד מחודש Lenovo ThinkPad T14 Gen 2 i5 16GB 512GB
            </a>
            <span class="price-wrapper" data-price-amount="1990">1,990 ₪</span>
            <img class="product-image-photo" src="https://www.payngo.co.il/media/t14.jpg" />
            <div>שנתיים אחריות יבואן</div>
        </form>
        <form method="post" action="https://www.payngo.co.il/checkout/cart/add/product/67890/">
            <a class="product-item-link" href="https://www.payngo.co.il/dell-optiplex.html">
                מחשב נייח מחודש Dell OptiPlex Micro
            </a>
            <span class="price-wrapper" data-price-amount="1490">1,490 ₪</span>
        </form>
        '''
        mock_fetch.return_value = (200, mock_html)
        scraper = PayngoScraper()
        items = scraper.scrape()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].store, "Payngo")
        self.assertEqual(items[0].brand, "Lenovo")
        self.assertEqual(items[0].price_ils, 1990)
        self.assertEqual(items[0].warranty_months, 24)

    @patch("scraper.fetch_resilient_url")
    def test_alm_scraper_parsing(self, mock_fetch):
        mock_json = {
            "data": {
                "categoryList": [
                    {
                        "products": {
                            "items": [
                                {
                                    "name": "מחשב נייד HP EliteBook 840 G8 i5 16GB 256GB SSD מחודש",
                                    "sku": "HP840G8",
                                    "url_key": "hp-elitebook-840-g8",
                                    "price_range": {
                                        "minimum_price": {
                                            "final_price": {"value": 1790.0}
                                        }
                                    },
                                    "small_image": {"url": "https://www.alm.co.il/media/hp.jpg"},
                                    "description": {"html": "<p>מחשב נייד יוקרתי לעסקים כולל 12 חודשי אחריות</p>"}
                                },
                                {
                                    "name": "מחשב נייח שולחני HP ProDesk 400 Mini",
                                    "sku": "HP400MINI",
                                    "url_key": "hp-prodesk-mini",
                                    "price_range": {
                                        "minimum_price": {
                                            "final_price": {"value": 1190.0}
                                        }
                                    },
                                    "small_image": {},
                                    "description": {"html": "<p>מחשב מיני</p>"}
                                }
                            ]
                        }
                    }
                ]
            }
        }
        mock_fetch.return_value = (200, json.dumps(mock_json))
        scraper = ALMScraper()
        items = scraper.scrape()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].store, "ALM")
        self.assertEqual(items[0].brand, "HP")
        self.assertEqual(items[0].price_ils, 1790)
        self.assertEqual(items[0].ram_gb, 16)
        self.assertEqual(items[0].storage_gb, 256)

    @patch("scraper.fetch_resilient_url")
    def test_shufersal_scraper_parsing(self, mock_fetch):
        mock_html = '''
        <li class="tile miglog-prod">
            <div class="text description">
                <a href="/online/he/p/P_12345/">
                    מחשב נייד מחודש Dell Latitude 7420 i7 16GB 512GB
                </a>
            </div>
            <div class="smallText">מעבד דור 11 כולל מקלדת מוארת</div>
            <span class="number">2,490</span>
            <img class="pic" src="https://res.cloudinary.com/shufersal/image/upload/dell7420.jpg" />
        </li>
        <li class="tile miglog-prod">
            <div class="text description">
                <a href="/online/he/p/P_99999/">
                    שולחן כתיבה למחשב מעץ
                </a>
            </div>
            <span class="number">399</span>
        </li>
        '''
        mock_fetch.return_value = (200, mock_html)
        scraper = ShufersalScraper()
        items = scraper.scrape()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].store, "Shufersal")
        self.assertEqual(items[0].brand, "Dell")
        self.assertEqual(items[0].price_ils, 2490)
        self.assertTrue(items[0].url.startswith("https://www.shufersal.co.il"))

    @patch("scraper.fetch_resilient_url")
    def test_p1000_scraper_parsing(self, mock_fetch):
        mock_html = '''
        <li data-sku="284729" data-title="מחשב נייד מחודש Lenovo ThinkPad X1 Carbon 14 Gen 8 i7 16GB 512GB SSD">
            <a href="/sales/saledetails.aspx?productid=284729">
                <div class="categoryResults_itemBuy">מחיר: 2,890 ₪</div>
                <img src="/images/lenovo_x1.jpg" />
                <span>16GB RAM</span>
                <span>512GB SSD</span>
                <span>שנתיים אחריות</span>
            </a>
        </li>
        <li data-sku="111111" data-title="מחשב נייח מיני Tiny Mini PC">
            <div class="categoryResults_itemBuy">890 ₪</div>
        </li>
        '''
        mock_fetch.return_value = (200, mock_html)
        scraper = P1000Scraper()
        items = scraper.scrape()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].store, "P1000")
        self.assertEqual(items[0].brand, "Lenovo")
        self.assertEqual(items[0].price_ils, 2890)
        self.assertEqual(items[0].warranty_months, 24)
        self.assertTrue(items[0].url.startswith("https://www.p1000.co.il"))

    @patch("scraper.fetch_resilient_url")
    def test_lastprice_scraper_parsing(self, mock_fetch):
        mock_html = '''
        <div class="col-lg-4 col-md-4 col-sm-6 infinite-item">
            <a href="https://www.lastprice.co.il/p/1000888/dell-latitude-5430">
                <img class="prodimg" src="/uploadimages/dell5430.jpg" />
                <h3>מחשב נייד עסקי Dell Latitude 5430 i5 16GB 512GB SSD כולל שנתיים אחריות מחודש</h3>
                <div class="lprice">₪2,190</div>
            </a>
        </div>
        '''
        mock_fetch.return_value = (200, mock_html)
        scraper = LastPriceScraper()
        items = scraper.scrape()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].store, "LastPrice")
        self.assertEqual(items[0].brand, "Dell")
        self.assertEqual(items[0].price_ils, 2190)
        self.assertEqual(items[0].warranty_months, 24)
        self.assertEqual(items[0].image_url, "https://www.lastprice.co.il/uploadimages/dell5430.jpg")

    @patch("scraper.fetch_resilient_url")
    def test_volt_scraper_parsing(self, mock_fetch):
        mock_html = '''
        <div id="item_id_2962959" class="layout_list_item css_class_23409 ">
          <div class="list_item_title_with_brand">
            <h3><a href="/items/2962959-thinkpad-t480s">נייד אולטרבוק מסך 14" ThinkPad T480s Core i5-8250U 16GB 512GB SSD Windows 10 PRO לנובו</a></h3>
          </div>
          <div class="list_item_current_list_item_content">
            <p>מחשב נייד מחודש אולטרבוק לנובו מסדרה T דיסק SSD מהיר</p>
          </div>
          <div class="list_item_show_price">
            <a class="price" href="/items/2962959"><span>מחיר</span><strong>1,950 ₪</strong></a>
          </div>
          <div class="list_item_image">
            <img alt="ThinkPad T480s" src="https://d3m9l0v76dty0.cloudfront.net/system/photos/5042885/show/t480s.jpg" />
          </div>
        </div>
        <!-- end layout_list_item -->
        <div id="item_id_9999999" class="layout_list_item css_class_23409 ">
          <div class="list_item_title_with_brand">
            <h3><a href="/items/9999999">מחשב שולחני נייח דל אופטיפלקס OptiPlex</a></h3>
          </div>
          <div class="list_item_show_price">
            <strong>1,200 ₪</strong>
          </div>
        </div>
        <!-- end layout_list_item -->
        <div id="item_id_8888888" class="layout_list_item css_class_23409 ">
          <div class="list_item_title_with_brand">
            <h3><a href="/items/8888888">מחשב נייד ישן ללא מחיר</a></h3>
          </div>
          <div class="list_item_show_price">
            <a class="zero_price_link" href="/items/8888888"></a>
          </div>
        </div>
        <!-- end layout_list_item -->
        '''
        mock_fetch.return_value = (200, mock_html)
        scraper = VoltScraper()
        items = scraper.scrape()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].store, "Volt")
        self.assertEqual(items[0].brand, "Lenovo")
        self.assertEqual(items[0].price_ils, 1950)
        self.assertEqual(items[0].ram_gb, 16)
        self.assertEqual(items[0].storage_gb, 512)
        self.assertEqual(items[0].warranty_months, 12)
        self.assertEqual(items[0].url, "https://www.volt.co.il/items/2962959-thinkpad-t480s")
        self.assertEqual(items[0].image_url, "https://d3m9l0v76dty0.cloudfront.net/system/photos/5042885/show/t480s.jpg")

    @patch("scraper.fetch_resilient_url")
    def test_ofekpc_scraper_parsing(self, mock_fetch):
        mock_html = '''
        <div class="item-box">
          <div class="product-item">
            <div class="picture">
              <a href="/dell-latitude-5420-i5-11th-gen"><img alt="Dell Latitude 5420" src="https://ofekpc.co.il/images/thumbs/default.jpg" data-lazyloadsrc="https://ofekpc.co.il/images/thumbs/dell-latitude-5420.jpg" /></a>
            </div>
            <div class="details">
              <h2 class="product-title">
                <a href="/dell-latitude-5420-i5-11th-gen">מחשב נייד מחודש Dell Latitude 5420 מעבד i5-1135G7 זיכרון 16GB דיסק 512GB SSD</a>
              </h2>
              <div class="description">מחשב נייד לעסקים במצב מצוין, אחריות שנתיים</div>
              <div class="add-info">
                <div class="prices">
                  <span class="price actual-price">&#x20AA;1,790</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="item-box">
          <div class="product-item">
            <h2 class="product-title">
              <a href="/dell-optiplex-mini-pc">מחשב שולחני נייח Dell OptiPlex Tiny Core i5</a>
            </h2>
            <span class="price actual-price">&#x20AA;1,200</span>
          </div>
        </div>
        '''
        mock_fetch.return_value = (200, mock_html)
        scraper = OfekPCScraper()
        items = scraper.scrape()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].store, "Ofek PC")
        self.assertEqual(items[0].brand, "Dell")
        self.assertEqual(items[0].price_ils, 1790)
        self.assertEqual(items[0].ram_gb, 16)
        self.assertEqual(items[0].storage_gb, 512)
        self.assertEqual(items[0].warranty_months, 24)
        self.assertEqual(items[0].url, "https://ofekpc.co.il/dell-latitude-5420-i5-11th-gen")
        self.assertEqual(items[0].image_url, "https://ofekpc.co.il/images/thumbs/dell-latitude-5420.jpg")

    def test_p1000_detail_page_specs_parsing(self):
        """P1000 detail page specs must extract exact CPU, explicit 1.18kg weight and 63Wh battery."""
        mock_detail_html = '''
        <li id="MainContent_Properties_productDetails">
            סוג מעבד: 11th Generation Intel® Core™ i5-1185G7<br />
            מסך 14 אינץ': FHD 1920 x 1080<br />
            זכרון: 16GB DDR4<br />
            כוננים: 256GB SSD<br />
            משקל: 1.18 ק"ג<br />
            סוג ספק הכוח והסוללה: 4-Cell, 63 WHr
        </li>
        '''
        scraper = P1000Scraper()
        with patch.object(scraper, "_fetch_detail_specs", return_value="11th Generation Intel Core i5-1185G7 משקל: 1.18 ק\"ג 4-Cell, 63 WHr"):
            with patch("scraper.fetch_resilient_url") as mock_cat:
                mock_cat.return_value = (200, '<li data-sku="216717" data-title="מחשב נייד מסך מגע 2IN1 DELL Latitude 7420 i5 מחודש"><a href="/sales/saledetails.aspx?productid=216717"></a><div class="categoryResults_itemBuy">2,390 ₪</div></li>')
                items = scraper.scrape()
                self.assertEqual(len(items), 1)
                laptop = items[0]
                self.assertEqual(laptop.cpu, "Core i5 (11th Gen)")
                self.assertEqual(laptop.weight_kg, 1.18)
                self.assertEqual(laptop.weight_source, "listing_explicit")
                self.assertEqual(laptop.battery_wh, 63)
                self.assertEqual(laptop.battery_source, "listing_explicit")

    def test_itoutlet_detail_page_specs_parsing(self):
        """IT Outlet detail page parser extracts sub-title and specs attributes."""
        mock_detail_html = '''
        <div id="item_current_sub_title">מחשב נייד Dell Latitude 7420 מעבד i7-1165G7 זיכרון 16GB נפח אחסון 512GB SSD</div>
        <div id="item_attributes">
            <ul><li><b>משקל</b> <span class="he_true">1.3 ק"ג</span></li></ul>
        </div>
        <!-- show_html_in_tabs -->
        '''
        class FakeResponse:
            status_code = 200
            text = mock_detail_html
        class FakeSession:
            def get(self, url, timeout=8):
                return FakeResponse()

        scraper = ITOutletScraper(FakeSession())
        specs = scraper._fetch_detail_specs("https://www.itoutlet.co.il/items/12345")
        self.assertIn("i7-1165G7", specs)
        self.assertIn("1.3", specs)

    def test_lastprice_detail_page_specs_parsing(self):
        """LastPrice detail page parser extracts #html-description block with battery and specs."""
        mock_html = '''
        <div id="html-description">
            <p>מעבד: 11th Generation Intel Core i5-1145G7<br />
            ספק כוח וסוללה: 4-Cell, 63 WHr<br />
            שלוש שנים אחריות</p>
        </div>
        '''
        scraper = LastPriceScraper()
        with patch("laptop_scrapers.lastprice.fetch_resilient_url", return_value=(200, mock_html)):
            specs = scraper._fetch_detail_specs("https://www.lastprice.co.il/p/12345")
            self.assertIn("i5-1145G7", specs)
            self.assertIn("63 WHr", specs)

    def test_lts_and_recomp_desc_parsing(self):
        """LTS and Recomp detail page parsers extract WooCommerce short-desc and tab-desc."""
        mock_html = '''
        <div class="woocommerce-product-details__short-description">מעבד Intel Core i5-1135G7 זיכרון 16GB</div>
        <div id="tab-description">סוללה 57Wh משקל 1.35 ק"ג</div>
        '''
        lts = LTSScraper(None)
        recomp = RecompScraper(None)
        self.assertIn("i5-1135G7", lts._parse_product_page_desc(mock_html))
        self.assertIn("57Wh", recomp._parse_recomp_desc(mock_html))


class TestFrontendCompatibility(unittest.TestCase):
    """Verifies that the catalog data works cleanly with app.js without crashing the browser."""

    def test_app_js_value_score_and_filter_logic(self):
        """Run a fast node validation to ensure app.js processes all catalog laptops without NaN."""
        node_script = """
        const fs = require('fs');
        const { calculateValueScore, matchesCpuGen } = require('./app.js');
        const raw = JSON.parse(fs.readFileSync('scraped_laptops.json'));
        let items = Array.isArray(raw) ? raw : [];
        if (!Array.isArray(raw)) {
            Object.keys(raw).forEach(k => { if (Array.isArray(raw[k])) items = items.concat(raw[k]); });
        }

        let scored = 0;
        for (const laptop of items) {
            const score = calculateValueScore(laptop);
            if (isNaN(score) || score < 4.0 || score > 10.0) {
                console.error('Invalid score', score, 'for', laptop.title);
                process.exit(1);
            }
            scored++;
        }

        // Test range filters
        if (!matchesCpuGen('Core i7 (12th Gen)', '11-up')) process.exit(2);
        if (matchesCpuGen('Core i5 (8th Gen)', '11-up')) process.exit(3);
        if (!matchesCpuGen('Core i5 (8th Gen)', '8-down')) process.exit(4);

        console.log('OK: ' + scored + ' laptops scored cleanly');
        """
        try:
            res = subprocess.run(
                ["node", "-e", node_script],
                cwd=os.path.dirname(__file__),
                capture_output=True,
                text=True,
                check=True
            )
            self.assertIn("OK:", res.stdout)
        except FileNotFoundError:
            # Node not installed; pass gracefully
            pass


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 Running Second-Hand PC Catalog & Spec Validation Suite")
    print("=" * 60 + "\n")
    unittest.main(verbosity=2)
