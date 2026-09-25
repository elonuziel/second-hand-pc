"""Report and catalog export generators for laptop dataset."""

from __future__ import annotations

import csv
import datetime
import json
import logging
import os
from typing import Dict, List

from laptop_domain import LaptopItem
from laptop_recommendations import TopPicksEngine

logger = logging.getLogger("ReportGenerator")

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
FULL_CATALOG_MD_PATH = os.path.join(WORKSPACE_DIR, "full_catalog.md")
SUMMARY_MD_PATH = FULL_CATALOG_MD_PATH
JSON_PATH = os.path.join(WORKSPACE_DIR, "scraped_laptops.json")
CSV_PATH = os.path.join(WORKSPACE_DIR, "scraped_laptops.csv")
ENV_FILE_PATH = os.path.join(WORKSPACE_DIR, ".env")
SCRAPER_STATUS_PATH = os.path.join(WORKSPACE_DIR, "scraper_status.json")


class ReportGenerator:
    """Exports structured datasets and generates comprehensive comparison markdown guides."""

    @staticmethod
    def update_scraper_status(
        results: Dict[str, List[LaptopItem]],
        fresh_counts: Dict[str, int],
        preserved_counts: Dict[str, int],
        block_reasons: Dict[str, str],
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
                reason = block_reasons.get(name) or "Anti-bot challenge or unreachable in CI"
                note = f"Preserved stock ({reason})"

            store_map[name] = {
                "display_name": display_name,
                "count": count,
                "scraped_at": scraped_at,
                "status": st,
                "days_ago": days_ago,
                "note": note
            }

        status_data["last_updated"] = datetime.datetime.now().isoformat()
        status_data["laptops"] = {
            "total_items": total_items,
            "stores": store_map
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Updated scraper status JSON: {filepath}")
        except Exception as e:
            logger.warning(f"Could not write scraper status: {e}")

    @staticmethod
    def export_json(data: Dict[str, List[LaptopItem]], filepath: str):
        serializable = {k: [item.to_dict() for item in v] for k, v in data.items()}
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON export saved to: {filepath}")

    @staticmethod
    def export_csv(all_items: List[LaptopItem], filepath: str):
        if not all_items:
            return
        fieldnames = list(all_items[0].to_dict().keys())
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in all_items:
                writer.writerow(item.to_dict())
        logger.info(f"CSV export saved to: {filepath}")

    @staticmethod
    def build_store_status_lines(
        store_order: List[str],
        fresh_counts: Dict[str, int],
        preserved_counts: Dict[str, int],
        block_reasons: Dict[str, str],
    ) -> List[str]:
        """Renders one line per store that produced no fresh data, explaining why.

        Healthy stores are skipped, so a fully successful run prints nothing here.
        """
        lines: List[str] = []
        for name in store_order:
            if fresh_counts.get(name, 0):
                continue
            reason = block_reasons.get(name) or "no block detected — 0 items parsed (site layout change?)"
            preserved = preserved_counts.get(name, 0)
            state = f"using {preserved} preserved items" if preserved else "nothing preserved"
            lines.append(f"  • {name:18}: {reason} — {state}")
        return lines

    @staticmethod
    def update_summary_markdown(all_results: Dict[str, List[LaptopItem]], filepath: str):
        now_str = datetime.datetime.now().strftime("%B %d, %Y (%H:%M)")
        it_items = all_results.get('itoutlet', [])
        eco_items = all_results.get('ecology', [])
        lts_items = all_results.get('lts', [])
        rec_items = all_results.get('recomp', [])
        cwc_items = all_results.get('cwc', [])
        payngo_items = all_results.get('payngo', [])
        alm_items = all_results.get('alm', [])
        shuf_items = all_results.get('shufersal', [])
        p1000_items = all_results.get('p1000', [])
        lp_items = all_results.get('lastprice', [])
        volt_items = all_results.get('volt', [])
        ofek_items = all_results.get('ofekpc', [])

        # Flatten all items to dynamically compute Top Overall Picks
        all_laptops: List[LaptopItem] = []
        for v in all_results.values():
            all_laptops.extend(v)

        top_picks = TopPicksEngine.select_top_picks(all_laptops)

        md_parts = []
        md_parts.append(f"""# 💻 Refurbished Laptops Market Research & Multi-Store Comparison Guide
**Stores Audited & Researched:**
1. 🏬 **Ecology Computers (אקולוגיה לקהילה מוגנת):** [ecommunity.org.il/מחשבים-ניידים](https://www.ecommunity.org.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D)
2. 🏬 **IT Outlet (איי טי אאוטלט):** [itoutlet.co.il/מחשבים-ניידים](https://www.itoutlet.co.il/164920-%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D?order=up_price)
3. 🏬 **LaptopTech LTS (לפטופ.טק):** [lts.co.il/מחשבים-ניידים-מחודשים-יד-2](https://lts.co.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%99%D7%93-2/)
4. 🏬 **Recomp Computers (ריקומפ):** [recomp.co.il/מחשבים-מחודשים-במבצע](https://recomp.co.il/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%D7%95%D7%93%d7%a9%d7%99%d7%9d-%d7%91%d7%9e%d7%91%d7%a6%d7%a2/)
5. 🏬 **Olam HaKolnoa (עולם הקולנוע):** [cwc.co.il/מחשבים-מחודשים](https://www.cwc.co.il/product-category/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%95%D7%A6%D7%99%D7%95%D7%93-%D7%A0%D7%9C%D7%95%D7%95%D7%94-1/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D/)
6. 🏬 **Machsanei Hashmal (מחסני חשמל / Payngo):** [payngo.co.il/direct-imports-tech](https://www.payngo.co.il/computers-pcs/computing-gaming/direct-imports-tech.html)
7. 🏬 **A.L.M (א.ל.מ):** [alm.co.il/compoutlet](https://www.alm.co.il/smartphones-laptops-techproducts/compoutlet.html)
8. 🏬 **Shufersal Online (שופרסל):** [shufersal.co.il/G030401](https://www.shufersal.co.il/online/he/%D7%A7%D7%98%D7%92%D7%95%D7%A8%D7%99%D7%95%D7%AA/%D7%94%D7%A7%D7%A0%D7%99%D7%95%D7%9F-%D7%94%D7%9B%D7%9C-%D7%9C%D7%91%D7%99%D7%AA/%D7%90%D7%9C%D7%A7%D7%98%D7%A8%D7%95%D7%A0%D7%99%D7%A7%D7%94-%D7%95%D7%A1%D7%9C%D7%95%D7%9C%D7%A8/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%95%D7%92%D7%99%D7%99%D7%9E%D7%99%D7%A0%D7%92/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%95%D7%A0%D7%99%D7%99%D7%97%D7%99%D7%9D/c/G030401)
9. 🏬 **P1000 (פי אלף):** [p1000.co.il/laptopoutlet](https://www.p1000.co.il/categories/category.aspx?categoryname=laptopoutlet)
10. 🏬 **LastPrice (לאסטפרייס):** [lastprice.co.il/c/85](https://www.lastprice.co.il/c/85/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%95%D7%92%D7%99%D7%99%D7%9E%D7%99%D7%A0%D7%92/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%95%D7%A2%D7%95%D7%93%D7%A4%D7%99-%D7%9E%D7%9C%D7%90%D7%99)
11. 🏬 **VOLT (וולט מחשוב ירוק):** [volt.co.il/23409-ניידים-מחודשים](https://www.volt.co.il/23409-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D)
12. 🏬 **Ofek PC (אופק פי סי):** [ofekpc.co.il/מחשבים-ניידים-מחודשים](https://ofekpc.co.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D)

*Last Automated Live Audit: {now_str}*

---

## 📌 Quick Navigation
- [💾 Storage Interfaces Explained](#-storage-interfaces-explained-nvme-vs-sata-vs-soldered)
- [🔧 Upgradability Scoring Guide](#-upgradability-scoring-guide)
- [🏷️ Store Discounts & Coupons](#️-it-outlet-discounts--coupon-optimization)
- [🏆 Top Recommended Picks](#-top-overall-available-picks-dynamically-auto-ranked-from-live-inventory)
- [📸 Featured Deal: ThinkPad P14s](#-featured-deal-lenovo-thinkpad-p14s-gen-1-it-outlet)
- [🏬 IT Outlet Live Audit](#-1-it-outlet-איי-טי-אאוטלט--live-catalog--stock-audit)
- [🏬 Ecology Computers Live Audit](#-2-ecology-computers-אקולוגיה-לקהילה-מוגנת--live-stock-audit)
- [🏬 LaptopTech LTS Live Audit](#-3-laptoptech-lts-לפטופטק--live-stock-audit)
- [🏬 Recomp Computers Live Audit](#-4-recomp-computers-ריקומפ--live-stock-audit)
- [🏬 Olam HaKolnoa Live Audit](#-5-olam-hakolnoa-עולם-הקולנוע--live-stock-audit)
- [🏬 Machsanei Hashmal Live Audit](#-6-machsanei-hashmal-מחסני-חשמל--payngo--live-stock-audit)
- [🏬 A.L.M Live Audit](#-7-alm-אלמ--live-stock-audit)
- [🏬 Shufersal Online Live Audit](#-8-shufersal-online-שופרסל--live-stock-audit)
- [🏬 P1000 Live Audit](#-9-p1000-פי-אלף--live-stock-audit)
- [🏬 LastPrice Live Audit](#-10-lastprice-לאסטפרייס--live-stock-audit)
- [🏬 VOLT Live Audit](#-11-volt-וולט-מחשוב-ירוק--live-stock-audit)
- [🏬 Ofek PC Live Audit](#-12-ofek-pc-אופק-פי-סי--live-stock-audit)
- [🎯 Buyer Rules of Thumb](#-quick-rules-of-thumb)

---

## 💾 Storage Interfaces Explained (NVMe vs SATA vs Soldered)

| Storage Type | Speed & Bus | Form Factor | Upgradability |
| :--- | :--- | :--- | :--- |
| ⚡ **M.2 PCIe NVMe (Gen 3 / Gen 4)** | **2,500 – 7,000 MB/s** *(Ultra-fast)* | M.2 2280 stick (looks like a stick of gum) | ✅ **100% Removable / Upgradable** to any size (1TB, 2TB, 4TB). |
| ⚡ **Dual M.2 NVMe Slots** | **Up to 7,000 MB/s** | 2 separate M.2 slots (2280 + 2242) | ✅ **Can install TWO independent internal SSDs** simultaneously. |
| 🐢 **2.5" SATA SSD / M.2 SATA** | **~500 – 550 MB/s** *(6x slower than NVMe)* | 2.5-inch drive bay or M.2 SATA key | ✅ **Removable / Upgradable**, but capped at legacy SATA III speeds. |
| 🔒 **Soldered BGA NVMe / eMMC** | **Fast (PCIe) or Slow (eMMC)** | Chips soldered directly to the logic board | ❌ **NON-UPGRADABLE** (cannot be removed or replaced). |

---

## 🔧 Upgradability Scoring Guide

* 🟢 **10/10 (Extreme Workstation):** 4x RAM slots (up to 128GB) + 2 to 4 M.2 NVMe SSD slots + tool-less access.
* 🟢 **9/10 (Full Enterprise Modular):** 2x SODIMM RAM slots (0% soldered, up to 64GB) + replaceable M.2 NVMe SSD.
* 🟢 **8.5/10 (Dual M.2 SSD Champion):** 1x RAM slot + **Dual internal M.2 NVMe SSD slots** (add a 2nd drive anytime).
* 🟡 **7.5/10 (Semi-Modular):** 1x Soldered RAM + 1x SODIMM slot (up to 40GB/48GB total) + replaceable M.2 NVMe SSD.
* 🟠 **5/10 (Storage Only / Soldered RAM):** 100% Soldered RAM (fixed) + **Standard M.2 PCIe NVMe SSD (fully replaceable)**.
* 🔴 **1/10 (Locked Down):** 100% Soldered RAM + Soldered SSD + Glued chassis (no DIY upgrades).

---

## 🏷️ IT Outlet Discounts & Coupon Optimization

IT Outlet features multiple discount programs. Note that coupons and club discounts **do not stack** (*אין כפל מבצעים / קופונים*): only **one** discount method can be applied to an order.

### 💡 How the Discounts & Sales Work:

1. **📧 100 ₪ Newsletter Sign-Up Coupon:**
   * **How to claim:** Visit [itoutlet.co.il](https://www.itoutlet.co.il), wait for the customer club pop-up modal, and enter your email address. You will receive an instant 100 ₪ discount coupon code.
   * **Conditions:** Valid on purchases **over 1,500 ₪**.
   * **Optimal range:** Best for laptops priced **between 1,500 ₪ and 2,500 ₪** (saving ~4% to 6.6% off the base price).

2. **💳 4% Credit Card & Consumer Club Discount:**
   * **How to claim:** Valid **strictly via phone orders** (*הזמנות טלפוניות בלבד*).
   * **Supported cards & clubs:** Non-bank credit cards including MAX, Isracard, Amex, LifeStyle, Hot, Tov, ביחד בשבילך, אשמורת, בהצדעה.
   * **Optimal range:** Best for laptops priced **above 2,500 ₪** (since 4% of 2,500 ₪ is 100 ₪, and at 3,000 ₪ you save 120 ₪, at 3,500 ₪ you save 140 ₪).

3. **🏷️ Special Promo Code `IT14` (ThinkPad P14s Deal):**
   * Drops the flagship **Lenovo ThinkPad P14s Gen 1** (Core i7, 32GB RAM, 1TB SSD, Dedicated GPU) from 2,800 ₪ down to **2,500 ₪** (saving 300 ₪!).
   * Also includes a complimentary laptop carrying bag and wireless optical mouse.

| 📧 100 ₪ Email Newsletter Coupon | 💳 4% Credit Card / Club Discount |
| :---: | :---: |
| ![100 NIS Newsletter Discount](./assets/itoutlet_100nis_discount.png) | ![4 Percent Credit Card Discount](./assets/itoutlet_4percent_discount.png) |

---

## 🏆 Top Overall Available Picks (Dynamically Auto-Ranked from Live Inventory)

| Category | Model | Key Specs | Best Deal Price | Store | Storage Interface | RAM Architecture | Upgradability | Direct Link |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- | :---: | :---: |
""")
        for cat_emoji, cat_desc, p in top_picks:
            score_badge = f"🟢 {p.upgradability_score}" if p.upgradability_score >= 8.5 else (f"🟡 {p.upgradability_score}" if p.upgradability_score >= 7.0 else f"🟠 {p.upgradability_score}")
            ram_gen_str = f" {p.ram_gen}" if getattr(p, 'ram_gen', '') else ""
            specs_summary = f"{p.cpu} • **{p.ram_gb}GB{ram_gen_str} RAM** • {p.storage_gb}GB SSD"
            md_parts.append(f"| **{cat_emoji}** | **{p.title}** | {specs_summary} | **{p.deal_label}** | {p.store} | {p.storage_type} | {p.ram_type} | {score_badge} | [View Product]({p.url}) |\n")

        md_parts.append("""
---

## 📸 Featured Deal: Lenovo ThinkPad P14s Gen 1 (IT Outlet)

> **Direct Link:** [Lenovo ThinkPad P14s Gen 1 Product Page](https://www.itoutlet.co.il/items/8733190-%D7%9E%D7%97%D7%A9%D7%91-%D7%A0%D7%99%D7%99%D7%93-%D7%9E%D7%97%D7%95%D7%93%D7%A9-%D7%9C%D7%A2%D7%A8%D7%99%D7%9B%D7%94-%D7%92%D7%A8%D7%A4%D7%99%D7%AA-Lenovo-ThinkPad-P14s-Gen-1-i7-32GB-1TB-SSD)  
> **Status:** 🟢 **AVAILABLE & IN STOCK**  
> **Offer Price:** **2,500 ₪** *(Original 2,800 ₪, with coupon `IT14` — saves 300 ₪)*  
> **Includes:** Free laptop carry bag and wireless optical mouse  
> **Storage:** ⚡ **1 TB M.2 2280 PCIe 3.0 NVMe SSD** *(Fully swappable up to 2TB/4TB)*  
> **Memory:** 16 GB Soldered + 16 GB SODIMM Slot = **32 GB RAM** *(Expandable up to 48 GB)*  
> **Graphics:** Dedicated NVIDIA Quadro P520 GPU  
> **Upgradability Score:** 🟡 **7.5/10**

![Lenovo ThinkPad P14s Deal Offer](./assets/thinkpad_p14s_offer.png)
""")

        def _append_store_section(store_num: int, store_title: str, items_list: List[LaptopItem], extra_note: str = ""):
            md_parts.append(f"""
---

## 🏬 {store_num}. {store_title} — Live Stock Audit
""")
            if extra_note:
                md_parts.append(f"\n*({extra_note})*\n")
            md_parts.append("""
| # | Model / Product Title | CPU & Gen | RAM & SSD | Screen | Weight | Battery | Deal Price | Storage Interface | Upgradability | Scraped | Direct Link |
| :-: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: | :---: |
""")
            today = datetime.date.today()
            for i, itm in enumerate(items_list, 1):
                score_badge = f"🟢 {itm.upgradability_score}" if itm.upgradability_score >= 8.5 else (f"🟡 {itm.upgradability_score}" if itm.upgradability_score >= 7.0 else f"🟠 {itm.upgradability_score}")
                ram_gen_str = f" {itm.ram_gen}" if getattr(itm, 'ram_gen', '') else ""
                weight_warn_str = " ⚠️ *(Typo alert)*" if getattr(itm, 'weight_warning', '') else ""
                battery_warn_str = " ⚠️ *(Typo alert)*" if getattr(itm, 'battery_warning', '') else ""
                scraped_str = getattr(itm, 'scraped_at', '') or today.isoformat()
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
                md_parts.append(f"| {i} | **{itm.title}** | {itm.cpu} | {itm.ram_gb}GB{ram_gen_str} / {itm.storage_gb}GB | {itm.screen_size_in}\" | ⚖️ {itm.weight_kg} kg{weight_warn_str} | 🔋 {itm.battery_wh} Wh{battery_warn_str} | **{itm.deal_label}** | {itm.storage_type} | {score_badge} | {scraped_cell} | [View Product]({itm.url}) |\n")

        _append_store_section(1, "IT Outlet (איי טי אאוטלט)", it_items)
        _append_store_section(2, "Ecology Computers (אקולוגיה לקהילה מוגנת)", eco_items, "All laptops include a full 24-Month / 2-Year Warranty")
        _append_store_section(3, "LaptopTech LTS (לפטופ.טק)", lts_items)
        _append_store_section(4, "Recomp Computers (ריקומפ)", rec_items)
        _append_store_section(5, "Olam HaKolnoa (עולם הקולנוע)", cwc_items, "Most laptops include a full 36-Month / 3-Year Hardware Warranty")
        _append_store_section(6, "Machsanei Hashmal (מחסני חשמל / Payngo)", payngo_items)
        _append_store_section(7, "A.L.M (א.ל.מ)", alm_items)
        _append_store_section(8, "Shufersal Online (שופרסל)", shuf_items)
        _append_store_section(9, "P1000 (פי אלף)", p1000_items)
        _append_store_section(10, "LastPrice (לאסטפרייס)", lp_items)
        _append_store_section(11, "VOLT (וולט מחשוב ירוק)", volt_items)
        _append_store_section(12, "Ofek PC (אופק פי סי)", ofek_items)

        md_parts.append("""
---

## 🎯 Quick Rules of Thumb

1. **⚡ Fast M.2 NVMe SSDs (Up to 3,500 - 7,000 MB/s):**
   * Almost all 8th–12th Gen business laptops here (ThinkPad T14/P14s, EliteBook 830/840, Latitude 7000/5000) have a standard **M.2 2280 PCIe NVMe SSD slot** that you can unscrew and upgrade anytime.
2. **🌟 Dual Internal SSD Slots:**
   * Look at the **ThinkPad E14 Gen 4 / Gen 2** or **HP ZBook Fury / ThinkPad P15** if you want to install two (or four) physical SSDs simultaneously.
3. **⚠️ Soldered RAM vs Upgradable RAM:**
   * If you see **🟠 5/10**, the **NVMe SSD is fully upgradeable**, but the **RAM is soldered**.
   * If you see **🟢 9/10** or **🟢 10/10**, both the **RAM and NVMe SSD are 100% modular and upgradeable**.
   * If you see **🔴 1/10 (Surface Laptop 2)**, everything is permanently soldered and glued shut.
""")
        md = "".join(md_parts)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md.strip() + "\n")
        logger.info(f"Markdown guide updated: {filepath}")


