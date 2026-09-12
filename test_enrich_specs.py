import unittest
from enrich_specs import SpecEnricher

class TestSpecEnricher(unittest.TestCase):
    def test_detect_screen_size(self):
        self.assertEqual(SpecEnricher.detect_screen_size("Acer A517 17.3 I5"), 17.3)
        self.assertEqual(SpecEnricher.detect_screen_size("Dell Latitude 5530 15 6 I7"), 15.6)
        self.assertEqual(SpecEnricher.detect_screen_size("Lenovo ThinkPad T14"), 14.0)
        self.assertEqual(SpecEnricher.detect_screen_size("Toshiba Protege X30L 13 3"), 13.3)
        self.assertEqual(SpecEnricher.detect_screen_size("Lenovo ThinkPad X280"), 12.5)

    def test_detect_weight_kg(self):
        self.assertLess(SpecEnricher.detect_weight_kg("Toshiba Protege X30L", 13.3), 1.0)
        self.assertEqual(SpecEnricher.detect_weight_kg("Lenovo ThinkPad X1 Carbon", 14.0), 1.10)
        self.assertEqual(SpecEnricher.detect_weight_kg("Lenovo ThinkPad T14", 14.0), 1.55)

    def test_detect_battery_wh(self):
        self.assertEqual(SpecEnricher.detect_battery_wh("Lenovo ThinkPad P15 Gen 1", 2.45), 90)
        self.assertEqual(SpecEnricher.detect_battery_wh("Dell Latitude 7420", 1.35), 57)
        self.assertEqual(SpecEnricher.detect_battery_wh("Lenovo ThinkPad T14", 1.55), 51)

    def test_enrich_item_dict(self):
        item = {"title": "Lenovo ThinkPad T14 i5 16GB"}
        enriched = SpecEnricher.enrich_item_dict(item)
        self.assertIn("screen_size_in", enriched)
        self.assertIn("weight_kg", enriched)
        self.assertIn("battery_wh", enriched)

if __name__ == '__main__':
    unittest.main()
