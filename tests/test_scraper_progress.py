"""Unit tests for ScrapeProgressTracker progress, ETA, and status logging."""

import json
import logging
import os
import tempfile
import time
import unittest

from scraper_progress import ScrapeProgressTracker, format_duration


class TestScraperProgress(unittest.TestCase):
    def test_format_duration(self):
        self.assertEqual(format_duration(-5), "0s")
        self.assertEqual(format_duration(0), "0.0s")
        self.assertEqual(format_duration(1.42), "1.4s")
        self.assertEqual(format_duration(59.9), "59.9s")
        self.assertEqual(format_duration(60), "1m 0s")
        self.assertEqual(format_duration(125), "2m 5s")

    def test_progress_tracker_lifecycle_and_json_export(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "progress.json")
            log_path = os.path.join(tmpdir, "status.log")

            test_logger = logging.getLogger("TestProgressTracker")
            test_logger.setLevel(logging.INFO)

            store_names = ["store_a", "store_b", "store_c", "store_d"]
            tracker = ScrapeProgressTracker(
                total_stores=4,
                store_names=store_names,
                worker_count=2,
                category="laptops",
                logger=test_logger,
                heartbeat_interval=0.1,  # Fast heartbeat for testing
                progress_json_path=json_path,
                status_log_path=log_path,
            )

            tracker.start()
            self.assertTrue(os.path.exists(json_path))

            # Store A starts and finishes
            tracker.on_store_start("store_a", display_name="Store A")
            time.sleep(0.05)
            tracker.on_store_finish("store_a", item_count=15, display_name="Store A")

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["completed_stores"], 1)
            self.assertEqual(data["remaining_stores"], 3)
            self.assertEqual(data["percent_complete"], 25.0)
            self.assertIn("store_a", data["store_results"])
            self.assertEqual(data["store_results"]["store_a"]["items"], 15)
            self.assertEqual(data["store_results"]["store_a"]["status"], "completed")

            # Store B fails with an error
            tracker.on_store_start("store_b", display_name="Store B")
            time.sleep(0.02)
            tracker.on_store_finish("store_b", item_count=0, error=ValueError("Connection timed out"), display_name="Store B")

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["completed_stores"], 2)
            self.assertEqual(data["remaining_stores"], 2)
            self.assertEqual(data["percent_complete"], 50.0)
            self.assertEqual(data["store_results"]["store_b"]["status"], "error")
            self.assertIn("Connection timed out", data["store_results"]["store_b"]["error"])

            # Stores C and D finish
            tracker.on_store_start("store_c", display_name="Store C")
            tracker.on_store_finish("store_c", item_count=8, display_name="Store C")
            tracker.on_store_start("store_d", display_name="Store D")
            tracker.on_store_finish("store_d", item_count=12, display_name="Store D")

            tracker.finish()

            with open(json_path, "r", encoding="utf-8") as f:
                final_data = json.load(f)
            self.assertEqual(final_data["status"], "completed")
            self.assertEqual(final_data["completed_stores"], 4)
            self.assertEqual(final_data["remaining_stores"], 0)
            self.assertEqual(final_data["percent_complete"], 100.0)

            # Check status.log lines were appended
            self.assertTrue(os.path.exists(log_path))
            with open(log_path, "r", encoding="utf-8") as f:
                log_lines = f.readlines()
            self.assertGreaterEqual(len(log_lines), 4)
            self.assertTrue(any("Store A" in line for line in log_lines))
            self.assertTrue(any("Store B" in line for line in log_lines))

    def test_progress_tracker_zero_stores(self):
        tracker = ScrapeProgressTracker(
            total_stores=0,
            store_names=[],
            worker_count=1,
            category="laptops",
        )
        tracker.start()
        tracker.finish()
        self.assertEqual(tracker._completed_count, 0)

    def test_prompt_user_mode_choices(self):
        from unittest.mock import patch
        from scraper import prompt_user_mode

        with patch("builtins.input", return_value="1"):
            self.assertEqual(prompt_user_mode(), "all")
        with patch("builtins.input", return_value=""):
            self.assertEqual(prompt_user_mode(), "all")
        with patch("builtins.input", return_value="2"):
            self.assertEqual(prompt_user_mode(), "laptops")
        with patch("builtins.input", return_value="3"):
            self.assertEqual(prompt_user_mode(), "mobile")
        with patch("builtins.input", return_value="phones"):
            self.assertEqual(prompt_user_mode(), "mobile")
        with patch("builtins.input", return_value="4"):
            self.assertEqual(prompt_user_mode(), "store")
        with patch("builtins.input", return_value="0"):
            with self.assertRaises(SystemExit):
                prompt_user_mode()

    def test_prompt_specific_store_choices(self):
        from unittest.mock import patch
        from scraper import prompt_specific_store

        with patch("builtins.input", return_value="1"):
            cat, store = prompt_specific_store()
            self.assertEqual(cat, "laptops")
            self.assertEqual(store, "itoutlet")

        with patch("builtins.input", return_value="superprice"):
            cat, store = prompt_specific_store()
            self.assertEqual(cat, "laptops")
            self.assertEqual(store, "superprice")

        with patch("builtins.input", return_value="gomobile"):
            cat, store = prompt_specific_store()
            self.assertEqual(cat, "mobile")
            self.assertEqual(store, "gomobile")

        with patch("builtins.input", return_value="0"):
            with self.assertRaises(SystemExit):
                prompt_specific_store()


if __name__ == "__main__":
    unittest.main()

