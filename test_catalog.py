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
from enrich_specs import SpecEnricher
from scraper import HardwareClassifier


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

    def test_all_four_stores_represented(self):
        """Ensure scrapers for all 4 stores (Ecology, IT Outlet, LTS, Recomp) are working."""
        stores_found = set(item.get("store", "") for item in self.items)
        expected_stores = ["Ecology", "IT Outlet", "LTS", "Recomp"]
        
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
            self.assertGreaterEqual(storage, 120, f"Unexpected storage {storage}GB for {title}")

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
        valid_confidences = {"verified", "estimated"}
        for item in self.items:
            title = item.get("title", "")
            sc_src = item.get("screen_source")
            wt_src = item.get("weight_source")
            bat_src = item.get("battery_source")
            conf = item.get("confidence_level")

            self.assertIn(sc_src, valid_sources, f"Invalid screen_source '{sc_src}' for: {title}")
            self.assertIn(wt_src, valid_sources, f"Invalid weight_source '{wt_src}' for: {title}")
            self.assertIn(bat_src, valid_sources, f"Invalid battery_source '{bat_src}' for: {title}")
            self.assertIn(conf, valid_confidences, f"Invalid confidence_level '{conf}' for: {title}")


class TestHardwareParsers(unittest.TestCase):
    """Verifies that CPU generation, RAM, Storage, and form factors are accurately parsed."""

    def test_cpu_generation_detection(self):
        """Accurately identify Intel generations (8th to 13th), Apple Silicon, AMD, Core Ultra, and Xeon."""
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
        ]
        for title, expected_cpu in test_cases:
            detected = HardwareClassifier.detect_cpu(title)
            self.assertEqual(detected, expected_cpu, f"Failed CPU detection on: {title}")

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

        # Storage (including Hebrew 'טרה' for 1TB)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Dell 256GB SSD"), 256)
        self.assertEqual(HardwareClassifier.detect_storage_gb("HP 512GB SSD NVMe"), 512)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Lenovo 1TB SSD"), 1000)
        self.assertEqual(HardwareClassifier.detect_storage_gb("מחשב נייד 1 טרה אחסון"), 1000)

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
