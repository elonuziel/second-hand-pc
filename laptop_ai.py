"""Groq AI Hardware Intelligence Assistant for laptop spec auditing."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import List, Optional

import requests

from laptop_domain import LaptopItem

logger = logging.getLogger("LaptopAI")

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE_PATH = os.path.join(WORKSPACE_DIR, ".env")


def get_groq_api_key() -> str:
    """Safely loads GROQ_API_KEY from environment or .env without logging secret values."""
    if "GROQ_API_KEY" in os.environ and os.environ["GROQ_API_KEY"]:
        return os.environ["GROQ_API_KEY"].strip()
    if os.path.exists(ENV_FILE_PATH):
        try:
            with open(ENV_FILE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        return line.strip().split("=", 1)[1].strip()
        except Exception:
            pass
    return ""


class GroqSpecEnhancer:
    """Uses Groq's high-speed LLM inference to perform deep hardware spec audits."""

    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODEL = "openai/gpt-oss-20b"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_groq_api_key()
        self.enabled = bool(self.api_key)

    def enhance_batch_chunk(self, chunk: List[LaptopItem]) -> List[LaptopItem]:
        """Audits a chunk of LaptopItems in a single prompt to minimize API calls and avoid rate limits."""
        if not self.enabled or not chunk:
            return chunk

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        prompt = (
            "You are a senior PC hardware engineer. Analyze the following laptops and extract exact factory specs.\n"
            "STRICT RULES:\n"
            "1. Never invent or substitute GPU models (e.g. if title says Quadro RTX 3000, return 'NVIDIA Quadro RTX 3000', NOT RTX 3060. If unmentioned or integrated, return 'Integrated' or 'Intel Iris Xe').\n"
            "2. For Apple MacBooks (2016+) and Microsoft Surface laptops with soldered RAM/SSD, upgradability_score MUST be between 1.0 and 2.0.\n\n"
            "For each laptop, return an object with:\n"
            '- "id": int (matching input id)\n'
            '- "screen_size_in": float (e.g. 13.3, 14.0, 15.6)\n'
            '- "weight_kg": float (e.g. 1.25, 1.47, 2.45)\n'
            '- "battery_wh": int (e.g. 50, 57, 90)\n'
            '- "gpu": str (exact GPU model or "Integrated")\n'
            '- "is_touch": bool\n'
            '- "is_2in1": bool (true if 360 convertible hinge)\n'
            '- "upgradability_score": float (1.0 to 10.0)\n\n'
            "Return ONLY a valid JSON array of objects.\n\n"
            "Laptops:\n" + "\n".join(f"{idx}: {item.title}" for idx, item in enumerate(chunk))
        )
        payload = {
            "model": self.DEFAULT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1500
        }

        try:
            import scraper
            res = scraper.requests.post(self.GROQ_API_URL, headers=headers, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                content = data['choices'][0]['message'].get('content', '')
                clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
                parsed = json.loads(clean)
                if isinstance(parsed, list):
                    for obj in parsed:
                        idx = obj.get("id")
                        if idx is not None and 0 <= idx < len(chunk):
                            target = chunk[idx]
                            updated_fields = set()
                            if obj.get("screen_size_in"):
                                try:
                                    target.screen_size_in = round(float(obj["screen_size_in"]), 1)
                                    updated_fields.add("screen")
                                except (ValueError, TypeError):
                                    pass
                            if obj.get("weight_kg"):
                                try:
                                    target.weight_kg = round(float(obj["weight_kg"]), 2)
                                    updated_fields.add("weight")
                                except (ValueError, TypeError):
                                    pass
                            if obj.get("battery_wh"):
                                try:
                                    target.battery_wh = int(obj["battery_wh"])
                                    updated_fields.add("battery")
                                except (ValueError, TypeError):
                                    pass
                            if obj.get("gpu"):
                                target.gpu = str(obj["gpu"])
                                updated_fields.add("gpu")
                            if "is_touch" in obj:
                                target.is_touch = bool(obj["is_touch"])
                                updated_fields.add("touch")
                            if "is_2in1" in obj:
                                target.is_2in1 = bool(obj["is_2in1"])
                                updated_fields.add("form_factor")
                            if obj.get("upgradability_score") is not None:
                                try:
                                    score = float(obj["upgradability_score"])
                                    if any(k in target.title.lower() for k in ['macbook', 'apple', 'surface']):
                                        score = min(score, 2.0)
                                    if 1.0 <= score <= 10.0:
                                        target.upgradability_score = score
                                        updated_fields.add("upgradability")
                                except (ValueError, TypeError):
                                    pass
                            if "screen" in updated_fields:
                                target.screen_source = "ai_audit"
                            if "weight" in updated_fields:
                                target.weight_source = "ai_audit"
                            if "battery" in updated_fields:
                                target.battery_source = "ai_audit"
                            if updated_fields:
                                target.confidence_level = "verified"
            else:
                logger.warning(f"Groq API returned HTTP {res.status_code}: {res.text[:100]}")
        except Exception as e:
            logger.warning(f"Groq batch enhancement failed: {e}")

        return chunk

    def enhance_batch(self, items: List[LaptopItem], chunk_size: int = 5) -> List[LaptopItem]:
        """Enhances items in sequential chunks to respect Groq rate limits with minimal latency."""
        if not self.enabled or not items:
            return items

        logger.info(f"🤖 Groq AI auditing {len(items)} laptops in chunked batches ({chunk_size} per call)...")
        enhanced = []
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            enhanced.extend(self.enhance_batch_chunk(chunk))
            if i + chunk_size < len(items):
                time.sleep(1.0)
        return enhanced

