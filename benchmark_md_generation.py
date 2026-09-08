import os
import json
import timeit
import tempfile
from scraper import LaptopItem, ReportGenerator

# Load sample data from scraped_laptops.json
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(WORKSPACE_DIR, "scraped_laptops.json")

def load_sample_data():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = {}
    for store_key, item_list in data.items():
        results[store_key] = [LaptopItem(**item) for item in item_list]
    return results

def benchmark():
    data = load_sample_data()
    iterations = 5000

    with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as tmp:
        tmp_path = tmp.name

    try:
        def run_update():
            ReportGenerator.update_summary_markdown(data, tmp_path)

        total_time = timeit.timeit(run_update, number=iterations)
        avg_time_ms = (total_time / iterations) * 1000
        print(f"Iterations: {iterations}")
        print(f"Total time: {total_time:.5f} seconds")
        print(f"Average time per call: {avg_time_ms:.5f} ms")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    benchmark()
