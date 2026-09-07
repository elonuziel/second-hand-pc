import timeit
import json
from scraper import HardwareClassifier

# Sample titles from scraped dataset or synthetic titles
SAMPLE_TITLES = [
    "Lenovo ThinkPad P14s Gen 1 i7 32GB 1TB SSD",
    "HP ZBook Fury 15 G8 i7 16GB 512GB (45W GPU)",
    'alt="Dell Latitude 7320 i7 16GB 256GB" 93070 - מחשב נייד מחודש לעריכה גרפית',
    "HP EliteBook x360 830 G8 Touch i7 16GB 512GB",
    "Lenovo ThinkPad E14 i5 16GB 512GB Dual SSD",
    "Dell Latitude 5410 i5 8GB 240GB",
    "HP EliteBook 840 G8 i5 16GB 256GB",
    "Lenovo ThinkPad E480 i7 16GB 240GB",
    "Dell Latitude 5480 i5 8GB 256GB",
    "Lenovo ThinkPad X280 i5 8GB 240GB",
    "HP/Dell/Lenovo G-4 i5 8GB 240GB",
    "Apple MacBook Pro M1 16GB 1TB SSD",
    "Asus VivoBook i7 12th Gen 1250u 32GB 2TB SSD",
    "Dell Precision 5530 Intel Core i9 10th Gen 64GB 1000gb SSD",
    "HP ProBook 430 G8 Intel Core i3 11th Gen 8g ram 128gb ssd",
    "Lenovo ThinkPad T14 Touch i5 16GB 1 טרה אחסון",
    "HP ZBook G7 14\" i5 16GB 1000g ssd",
]

def benchmark():
    iterations = 20000

    def run_all():
        for t in SAMPLE_TITLES:
            HardwareClassifier.clean_text(t)
            HardwareClassifier.detect_brand(t)
            HardwareClassifier.detect_series(t)
            HardwareClassifier.detect_cpu(t)
            HardwareClassifier.detect_ram_gb(t)
            HardwareClassifier.detect_storage_gb(t)

    total_time = timeit.timeit(run_all, number=iterations)
    print(f"Total time for {iterations} iterations over {len(SAMPLE_TITLES)} titles: {total_time:.5f} seconds")
    print(f"Average time per iteration: {(total_time / iterations) * 1000:.5f} ms")

if __name__ == '__main__':
    benchmark()
