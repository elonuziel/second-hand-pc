"""Real-time progress, ETA, and status tracking for store scrapers."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional


def format_duration(seconds: float) -> str:
    """Format duration into human-readable string (e.g. '1.4s', '45.2s', '1m 24s')."""
    if seconds < 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    mins = int(seconds // 60)
    rem = seconds % 60
    return f"{mins}m {rem:.0f}s"


class ScrapeProgressTracker:
    """Tracks scraper completion, concurrency, in-flight stores, elapsed time, and ETA."""

    def __init__(
        self,
        total_stores: int,
        store_names: List[str],
        worker_count: int,
        category: str = "laptops",
        logger: Optional[logging.Logger] = None,
        heartbeat_interval: float = 5.0,
        progress_json_path: Optional[str] = None,
        status_log_path: Optional[str] = None,
    ):
        self.total_stores = max(0, total_stores)
        self.store_names = list(store_names)
        self.worker_count = max(1, worker_count)
        self.category = category
        self.logger = logger or logging.getLogger("ScraperProgress")
        self.heartbeat_interval = heartbeat_interval
        self.progress_json_path = progress_json_path
        self.status_log_path = status_log_path

        self._lock = threading.Lock()
        self._start_time = 0.0
        self._completed_count = 0
        self._store_start_times: Dict[str, float] = {}
        self._store_durations: Dict[str, float] = {}
        self._store_items: Dict[str, int] = {}
        self._store_status: Dict[str, str] = {name: "pending" for name in store_names}
        self._store_errors: Dict[str, str] = {}
        self._active_stores: Dict[str, float] = {}

        self._stop_event = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._finished = False

    def start(self) -> None:
        """Start the tracker and background heartbeat."""
        self._start_time = time.time()
        self.logger.info(
            "🚀 [%s] Starting live scrape of %d store(s) with %d concurrent worker(s)...",
            self.category.capitalize(),
            self.total_stores,
            self.worker_count,
        )
        self._write_status(status="running")

        if self.heartbeat_interval > 0 and self.total_stores > 1:
            self._heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True,
                name=f"{self.category}-progress-heartbeat"
            )
            self._heartbeat_thread.start()

    def on_store_start(self, store_key: str, display_name: Optional[str] = None) -> None:
        """Called when a worker thread begins scraping a specific store."""
        now = time.time()
        with self._lock:
            self._store_start_times[store_key] = now
            self._active_stores[store_key] = now
            self._store_status[store_key] = "running"
        self._write_status(status="running")

    def on_store_finish(
        self,
        store_key: str,
        item_count: int,
        error: Optional[Exception] = None,
        display_name: Optional[str] = None
    ) -> None:
        """Called when a store scrape concludes (successfully or with an error)."""
        now = time.time()
        with self._lock:
            start = self._store_start_times.get(store_key, now)
            duration = max(0.01, now - start)
            self._store_durations[store_key] = duration
            self._store_items[store_key] = item_count
            self._active_stores.pop(store_key, None)

            if error:
                self._store_status[store_key] = "error"
                self._store_errors[store_key] = str(error)
            else:
                self._store_status[store_key] = "completed"

            self._completed_count += 1
            completed = self._completed_count
            remaining = max(0, self.total_stores - completed)
            elapsed = max(0.01, now - self._start_time)
            percent = (completed / self.total_stores * 100.0) if self.total_stores > 0 else 100.0

            # Calculate ETA based on average store duration and effective parallelism
            completed_durations = list(self._store_durations.values())
            avg_duration = sum(completed_durations) / len(completed_durations)
            effective_concurrency = max(1, min(self.worker_count, remaining))
            eta_seconds = (remaining * avg_duration) / effective_concurrency if remaining > 0 else 0.0

            active_info = [
                f"{k} ({now - t:.1f}s)" for k, t in self._active_stores.items()
            ]
            active_str = f" | In progress: [{', '.join(active_info)}]" if active_info else ""

            name_to_show = display_name or store_key
            dur_str = format_duration(duration)
            el_str = format_duration(elapsed)
            eta_str = format_duration(eta_seconds) if remaining > 0 else "0s"

            if error:
                msg = (
                    f"⏱️ [{self.category.capitalize()} {completed}/{self.total_stores} ({percent:.1f}%)] "
                    f"⚠️ Store '{name_to_show}' failed after {dur_str} ({error}) | "
                    f"Stores left: {remaining} | Elapsed: {el_str} | ETA: ~{eta_str}{active_str}"
                )
                self.logger.warning(msg)
            else:
                msg = (
                    f"⏱️ [{self.category.capitalize()} {completed}/{self.total_stores} ({percent:.1f}%)] "
                    f"🏬 Store '{name_to_show}' finished in {dur_str} ({item_count} items) | "
                    f"Stores left: {remaining} | Elapsed: {el_str} | ETA: ~{eta_str}{active_str}"
                )
                self.logger.info(msg)

            self._append_status_log(msg)

        self._write_status(status="running" if remaining > 0 else "completed")

    def _heartbeat_loop(self) -> None:
        """Periodic background status log if scraping takes multiple seconds."""
        while not self._stop_event.wait(self.heartbeat_interval):
            with self._lock:
                if self._finished or self._completed_count >= self.total_stores:
                    break
                now = time.time()
                completed = self._completed_count
                remaining = max(0, self.total_stores - completed)
                elapsed = max(0.01, now - self._start_time)
                percent = (completed / self.total_stores * 100.0) if self.total_stores > 0 else 0.0

                if self._store_durations:
                    avg_duration = sum(self._store_durations.values()) / len(self._store_durations)
                else:
                    avg_duration = elapsed

                effective_concurrency = max(1, min(self.worker_count, remaining))
                eta_seconds = (remaining * avg_duration) / effective_concurrency if remaining > 0 else 0.0

                active_info = [
                    f"{k} ({now - t:.1f}s)" for k, t in self._active_stores.items()
                ]
                active_str = f" | In progress: [{', '.join(active_info)}]" if active_info else " | Waiting for workers..."

                el_str = format_duration(elapsed)
                eta_str = format_duration(eta_seconds)

                msg = (
                    f"⏳ [{self.category.capitalize()} Status] "
                    f"{completed}/{self.total_stores} stores finished ({percent:.1f}%) | "
                    f"Stores left: {remaining} | Elapsed: {el_str} | Est. Remaining: ~{eta_str}{active_str}"
                )
                self.logger.info(msg)
                self._append_status_log(msg)
            self._write_status(status="running")

    def finish(self) -> None:
        """Conclude tracking, stop heartbeat thread, and log overall summary."""
        self._stop_event.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=0.2)

        now = time.time()
        with self._lock:
            self._finished = True
            total_elapsed = max(0.01, now - self._start_time)
            total_items = sum(self._store_items.values())
            durations = list(self._store_durations.values())
            avg_store = (sum(durations) / len(durations)) if durations else 0.0

            fastest = min(self._store_durations.items(), key=lambda x: x[1]) if self._store_durations else ("none", 0.0)
            slowest = max(self._store_durations.items(), key=lambda x: x[1]) if self._store_durations else ("none", 0.0)

            msg = (
                f"🏁 [{self.category.capitalize()}] All {self.total_stores} store(s) completed in {format_duration(total_elapsed)} "
                f"({total_items} items total, avg store time: {format_duration(avg_store)}). "
                f"Fastest: '{fastest[0]}' ({format_duration(fastest[1])}), "
                f"Slowest: '{slowest[0]}' ({format_duration(slowest[1])})."
            )
            self.logger.info(msg)
            self._append_status_log(msg)

        self._write_status(status="completed")

    def _append_status_log(self, message: str) -> None:
        if not self.status_log_path:
            return
        try:
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            line = f"[{ts}] {message}\n"
            os.makedirs(os.path.dirname(os.path.abspath(self.status_log_path)), exist_ok=True)
            with open(self.status_log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception as e:
            self.logger.debug("Failed writing to status_log_path: %s", e)

    def _write_status(self, status: str = "running") -> None:
        if not self.progress_json_path:
            return
        try:
            now = time.time()
            with self._lock:
                completed = self._completed_count
                remaining = max(0, self.total_stores - completed)
                elapsed = max(0.0, now - self._start_time) if self._start_time else 0.0
                percent = (completed / self.total_stores * 100.0) if self.total_stores > 0 else 100.0

                if self._store_durations:
                    avg_dur = sum(self._store_durations.values()) / len(self._store_durations)
                else:
                    avg_dur = 0.0
                effective_workers = max(1, min(self.worker_count, remaining))
                eta_seconds = (remaining * avg_dur) / effective_workers if (remaining > 0 and avg_dur > 0) else 0.0

                data = {
                    "category": self.category,
                    "status": status,
                    "total_stores": self.total_stores,
                    "completed_stores": completed,
                    "remaining_stores": remaining,
                    "percent_complete": round(percent, 1),
                    "elapsed_seconds": round(elapsed, 1),
                    "formatted_elapsed": format_duration(elapsed),
                    "eta_seconds": round(eta_seconds, 1),
                    "formatted_eta": format_duration(eta_seconds),
                    "active_stores": list(self._active_stores.keys()),
                    "store_results": {
                        k: {
                            "status": self._store_status.get(k, "pending"),
                            "items": self._store_items.get(k, 0),
                            "duration_seconds": round(self._store_durations.get(k, 0.0), 2),
                            "error": self._store_errors.get(k),
                        }
                        for k in self.store_names
                    },
                    "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }

            os.makedirs(os.path.dirname(os.path.abspath(self.progress_json_path)), exist_ok=True)
            temp_path = f"{self.progress_json_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.progress_json_path)
        except Exception as e:
            self.logger.debug("Failed writing progress JSON: %s", e)

