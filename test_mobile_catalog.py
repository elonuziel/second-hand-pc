#!/usr/bin/env python3
"""
Test Suite for Refurbished Mobile Devices Catalog
===================================================
Tests data health, store representation, spec extraction, accessory filtering,
and frontend compatibility for phones and tablets.
"""

import unittest
import os
import json
import subprocess
from mobile_scraper import MobileClassifier, MasterMobileAuditor, MobileItem

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
MOBILE_JSON_PATH = os.path.join(WORKSPACE_DIR, "scraped_mobile.json")
MOBILE_CSV_PATH = os.path.join(WORKSPACE_DIR, "scraped_mobile.csv")
MOBILE_MD_PATH = os.path.join(WORKSPACE_DIR, "full_mobile_catalog.md")


class TestMobileClassifier(unittest.TestCase):
    def test_accessory_filtering(self):
        accessories = [
            "כיסוי מגן iPhone 12 חזק מפני נפילות",
            "כיסוי מגן לגלקסי S21 PLUS",
            "מטען מהיר לטלפון נייד 20W",
            "מגן זכוכית לסמארטפון",
            "כבל טעינה USB-C",
            "iPhone 13 Case Clear"
        ]
        for title in accessories:
            self.assertFalse(MobileClassifier.is_mobile_device(title), f"Failed to filter accessory: {title}")

    def test_device_detection(self):
        devices = [
            ("טלפון סלולרי מחודש Samsung Galaxy S9 64GB", "Samsung", "phone", 64),
            ("מחודש Apple iPhone 17 Pro 256GB Cosmic Orange", "Apple", "phone", 256),
            ("טאבלט מחודש Samsung Galaxy Tab A 10.1 (2019)", "Samsung", "tablet", 128),
            ("מחודש Motorola Razr 60 Ultra 5G XT2551-6 512GB", "Motorola", "phone", 512),
            ("שיאומי Xiaomi Poco F7 Pro 512GB", "Xiaomi", "phone", 512)
        ]
        for title, expected_brand, expected_type, expected_storage in devices:
            self.assertTrue(MobileClassifier.is_mobile_device(title), f"Failed to accept device: {title}")
            self.assertEqual(MobileClassifier.detect_brand(title), expected_brand)
            self.assertEqual(MobileClassifier.detect_device_type(title), expected_type)
            self.assertEqual(MobileClassifier.detect_storage(title), expected_storage)

    def test_lastprice_parsing(self):
        from mobile_scraper import LastPriceMobileScraper

        class MockResponse:
            status_code = 200
            text = '''
            <div class="col-lg-4 col-md-4 col-sm-6 infinite-item">
                <a class="prodLink" href="https://www.lastprice.co.il/p/100057932/Apple-iPhone-13-Pro-Max">
                    <img class="prodimg" src="/uploadimages/APP_PROMAX13_WHITE.jpg" />
                    <div class="degem">
                        <h3>טלפון סלולרי 6.7" Apple *מחודש* Silver - iPhone 13 Pro Max 256GB/6GB RAM מחודש</h3>
                    </div>
                    <div class="lprice">₪2,890</div>
                </a>
            </div>
            '''

        class MockSession:
            def get(self, url, timeout=15):
                return MockResponse()

        scraper = LastPriceMobileScraper(MockSession())
        items = scraper.scrape()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].store, "LastPrice")
        self.assertEqual(items[0].brand, "Apple")
        self.assertEqual(items[0].price_ils, 2890)
        self.assertEqual(items[0].storage_gb, 256)
        self.assertEqual(items[0].ram_gb, 6)
        self.assertEqual(items[0].image_url, "https://www.lastprice.co.il/uploadimages/APP_PROMAX13_WHITE.jpg")


class TestMobileDataHealth(unittest.TestCase):
    def test_files_exist_and_populated(self):
        self.assertTrue(os.path.exists(MOBILE_JSON_PATH), "scraped_mobile.json missing")
        self.assertTrue(os.path.exists(MOBILE_CSV_PATH), "scraped_mobile.csv missing")
        self.assertTrue(os.path.exists(MOBILE_MD_PATH), "full_mobile_catalog.md missing")

        with open(MOBILE_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        total_items = sum(len(v) for v in data.values())
        self.assertGreaterEqual(total_items, 15, "Mobile catalog should have at least 15 items")

    def test_all_stores_represented(self):
        with open(MOBILE_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("itoutlet", data)
        self.assertIn("gomobile", data)
        self.assertIn("partner", data)
        self.assertIn("dynamica", data)
        self.assertIn("vmobile", data)
        self.assertIn("lastprice", data)

        self.assertGreater(len(data["itoutlet"]), 0, "IT Outlet mobile should have items")
        self.assertGreater(len(data["gomobile"]), 0, "GoMobile should have items")
        self.assertGreater(len(data["partner"]), 0, "Partner Plus should have items")
        self.assertGreater(len(data["dynamica"]), 0, "Dynamica Outlet should have items")
        self.assertGreater(len(data["vmobile"]), 0, "VMobile should have items")
        self.assertGreater(len(data["lastprice"]), 0, "LastPrice mobile should have items")


class TestFrontendCompatibility(unittest.TestCase):
    def test_app_js_compatibility(self):
        cmd = ["node", "-e", "const app = require('./app.js'); console.log(app.escapeHtml('test'));"]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=WORKSPACE_DIR)
        self.assertEqual(res.returncode, 0, f"app.js failed node execution: {res.stderr}")


if __name__ == "__main__":
    unittest.main()
