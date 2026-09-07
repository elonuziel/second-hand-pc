import unittest
from scraper import HardwareClassifier

class TestHardwareClassifier(unittest.TestCase):
    def test_clean_text(self):
        sample = '<a href="#">alt="Lenovo ThinkPad X1 Carbon" 93070 - מחשב נייד מחודש לעריכה גרפית</a>'
        cleaned = HardwareClassifier.clean_text(sample)
        self.assertNotIn('<', cleaned)
        self.assertNotIn('מחשב נייד', cleaned)

    def test_detect_brand(self):
        self.assertEqual(HardwareClassifier.detect_brand("Lenovo ThinkPad T14"), "Lenovo")
        self.assertEqual(HardwareClassifier.detect_brand("Dell Latitude 5420"), "Dell")
        self.assertEqual(HardwareClassifier.detect_brand("HP EliteBook 840 G8"), "HP")
        self.assertEqual(HardwareClassifier.detect_brand("Apple MacBook Pro"), "Apple")

    def test_detect_series(self):
        self.assertEqual(HardwareClassifier.detect_series("ThinkPad T14"), "ThinkPad")
        self.assertEqual(HardwareClassifier.detect_series("Dell Latitude 5420"), "Latitude")

    def test_detect_cpu(self):
        self.assertEqual(HardwareClassifier.detect_cpu("Intel Core i7 12th Gen 1250U"), "Core i7 (12th Gen)")
        self.assertEqual(HardwareClassifier.detect_cpu("HP EliteBook 840 G8 i5 1135G7"), "Core i5 (11th Gen)")
        self.assertEqual(HardwareClassifier.detect_cpu("Apple M1 Max"), "Apple M1")

    def test_detect_ram_gb(self):
        self.assertEqual(HardwareClassifier.detect_ram_gb("Lenovo ThinkPad 16GB RAM 512GB SSD"), 16)
        self.assertEqual(HardwareClassifier.detect_ram_gb("Dell Latitude 32 GB RAM"), 32)
        self.assertEqual(HardwareClassifier.detect_ram_gb("Laptop 8g ram"), 8)
        self.assertEqual(HardwareClassifier.detect_ram_gb("No RAM specified"), 16)

    def test_detect_storage_gb(self):
        self.assertEqual(HardwareClassifier.detect_storage_gb("Dell 256GB SSD"), 256)
        self.assertEqual(HardwareClassifier.detect_storage_gb("HP 1TB SSD"), 1000)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Lenovo 2TB NVMe"), 2000)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Laptop 512 g אחסון"), 512)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Laptop 1000g"), 1000)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Laptop 1 טרה"), 1000)
        self.assertEqual(HardwareClassifier.detect_storage_gb("Unknown storage"), 512)

if __name__ == '__main__':
    unittest.main()
