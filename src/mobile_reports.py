"""Reports, JSON/CSV exports, and Markdown catalog generator for mobile devices."""
from __future__ import annotations

import csv
import datetime
import json
import logging
import os
from typing import Dict, List

from mobile_domain import MobileItem

logger = logging.getLogger("MobileReportGenerator")

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(WORKSPACE_DIR, "data")
SCRAPER_STATUS_PATH = os.path.join(DATA_DIR, "scraper_status.json")


class MobileReportGenerator:
    SCRAPER_STATUS_PATH = SCRAPER_STATUS_PATH

    @staticmethod
    def update_scraper_status(
        results: Dict[str, List[MobileItem]],
        fresh_counts: Dict[str, int],
        preserved_counts: Dict[str, int],
        filepath: str = SCRAPER_STATUS_PATH,
    ):
        status_data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    status_data = json.load(f)
            except Exception:
                pass

        today = datetime.date.today()
        store_map = {}
        total_items = 0
        for name, items in results.items():
            count = len(items)
            total_items += count
            fresh = fresh_counts.get(name, 0)
            scraped_at = items[0].scraped_at if items and hasattr(items[0], "scraped_at") and items[0].scraped_at else today.isoformat()
            days_ago = 0
            try:
                s_dt = datetime.date.fromisoformat(scraped_at)
                days_ago = (today - s_dt).days
            except Exception:
                pass

            display_name = getattr(items[0], "store", name) if items else name
            if fresh > 0:
                st = "fresh"
                note = "Successfully scraped fresh catalog"
            else:
                st = "preserved"
                note = "Preserved stock (anti-bot challenge or unreachable in CI)"

            store_map[name] = {
                "display_name": display_name,
                "count": count,
                "scraped_at": scraped_at,
                "status": st,
                "days_ago": days_ago,
                "note": note
            }

        status_data["last_updated"] = datetime.datetime.now().isoformat()
        status_data["mobile"] = {
            "total_items": total_items,
            "stores": store_map
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Updated scraper status JSON (mobile): {filepath}")
        except Exception as e:
            logger.warning(f"Could not write mobile scraper status: {e}")

    @staticmethod
    def export_json(data: Dict[str, List[MobileItem]], filepath: str):
        serializable = {k: [item.to_dict() for item in v] for k, v in data.items()}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        logger.info(f"Mobile JSON export saved to: {filepath}")

    @staticmethod
    def export_csv(all_items: List[MobileItem], filepath: str):
        if not all_items:
            return
        fieldnames = list(all_items[0].to_dict().keys())
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in all_items:
                writer.writerow(item.to_dict())
        logger.info(f"Mobile CSV export saved to: {filepath}")

    @staticmethod
    def update_summary_markdown(all_results: Dict[str, List[MobileItem]], filepath: str):
        now_str = datetime.datetime.now().strftime("%B %d, %Y (%H:%M)")
        all_devices: List[MobileItem] = []
        for v in all_results.values():
            all_devices.extend(v)

        md_parts = [
            "# 📱 Refurbished Phones & Tablets Market Research Guide\n",
            "**Stores Audited & Researched:**\n",
            "1. 🏬 **IT Outlet (איי טי אאוטלט):** [itoutlet.co.il/סלולר-וטאבלטים](https://www.itoutlet.co.il/173553-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8-%D7%95%D7%98%D7%90%D7%91%D7%9C%D7%98%D7%99%D7%9D)\n",
            "2. 🏬 **GoMobile Outlet (גו מוביל):** [gomobile.co.il/category/סמארטפונים-מחודשים-תצוגה](https://www.gomobile.co.il/category/%D7%A1%D7%9E%D7%90%D7%A8%D7%98%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%AA%D7%A6%D7%95%D7%92%D7%94/)\n",
            "3. 🏬 **Partner Plus Renewed (פרטנר פלוס):** [partnerplus.partner.co.il/renewed](https://partnerplus.partner.co.il/renewed)\n",
            "4. 🏬 **Dynamica Outlet (דינמיקה אאוטלט):** [dynamica.co.il/325880-Outlet](https://www.dynamica.co.il/325880-Outlet)\n",
            "5. 🏬 **VMobile (וי מובייל):** [vmobile.co.il/361324-מחודשים](https://www.vmobile.co.il/361324-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D)\n",
            "6. 🏬 **LastPrice (לאסטפרייס):** [lastprice.co.il/טלפונים-סלולרים-מחודשים](https://www.lastprice.co.il/c/531/%D7%9E%D7%97%D7%A9%D7%95%D7%91-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%98%D7%9C%D7%A4%D7%95%D7%A0%D7%99%D7%9D-%D7%A1%D7%9C%D7%95%D7%9C%D7%A8%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D?filter1=20710526,20670485)\n",
            "7. 🏬 **iStore CPO (אייסטור מחודשים ועודפים):** [istoreil.co.il/refurbish](https://www.istoreil.co.il/refurbish)\n",
            "8. 🏬 **BuyMobile (ביי מובייל תצוגה / מחודש):** [buy-mobile.co.il](https://buy-mobile.co.il/product-category/%D7%AA%D7%A6%D7%95%D7%92%D7%94/)\n\n",
            f"*Last Automated Live Audit: {now_str}*\n\n",
            "---\n\n",
            "## 📱 Live Mobile Devices Catalog & Stock Audit\n\n",
            "| # | Model / Device Title | Brand | Type | RAM & Storage | Screen | Deal Price | Store | Warranty | Scraped | Direct Link |\n",
            "| :-: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n"
        ]

        today = datetime.date.today()
        for i, dev in enumerate(all_devices, 1):
            type_badge = "📱 Phone" if dev.device_type == "phone" else "📱 Tablet"
            scraped_str = getattr(dev, 'scraped_at', '') or today.isoformat()
            stale_badge = ""
            try:
                s_dt = datetime.date.fromisoformat(scraped_str)
                days_old = (today - s_dt).days
                if days_old > 30:
                    stale_badge = f" ⚠️ *({days_old}d ago - Stale)*"
                elif days_old > 1:
                    stale_badge = f" *({days_old}d ago)*"
            except Exception:
                pass
            scraped_cell = f"{scraped_str}{stale_badge}"
            md_parts.append(
                f"| {i} | **{dev.title}** | {dev.brand} | {type_badge} | {dev.ram_gb}GB / {dev.storage_gb}GB | {dev.screen_size_in}\" | **{dev.deal_label}** | {dev.store} | {dev.warranty_months}M | {scraped_cell} | [View Product]({dev.url}) |\n"
            )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("".join(md_parts).strip() + "\n")
        logger.info(f"Mobile Markdown catalog saved to: {filepath}")

