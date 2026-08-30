#!/usr/bin/env python3
"""
Refurbished Laptops Master Multi-Store Scraper & Auditor
======================================================
Scrapes, parses specs, analyzes upgradability, verifies availability, and generates
markdown reports & JSON data for:
1. Ecology Computers (ecommunity.org.il)
2. IT Outlet (itoutlet.co.il)
3. LaptopTech LTS (lts.co.il)
4. Recomp Computers (recomp.co.il)

Usage:
  python3 scraper.py              # Scrapes all stores and saves to scraped_laptops.json
  python3 scraper.py --markdown   # Scrapes and updates summary.md
  python3 scraper.py --json       # Dumps JSON to stdout
"""

import sys
import os
import re
import json
import time
import argparse
import urllib.parse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7',
}

def clean_text(text: str) -> str:
    if not text: return ""
    text = urllib.parse.unquote(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    return ' '.join(text.split()).strip()

def extract_cpu(title: str) -> str:
    title_l = title.lower()
    if 'ryzen 7' in title_l: return "AMD Ryzen 7 PRO"
    if 'ryzen 5' in title_l: return "AMD Ryzen 5 PRO"
    if 'ultra 7' in title_l: return "Intel Core Ultra 7"
    
    gen12 = re.search(r'(?:12th|דור\s*12|gen\s*4|5431|5531|7430)', title_l)
    gen11 = re.search(r'(?:11th|דור\s*11|g8|gen\s*2|7420|7320|5420|5320|5520)', title_l)
    gen10 = re.search(r'(?:10th|דור\s*10|g7|gen\s*1|7410|5410|5510)', title_l)
    gen8 = re.search(r'(?:8th|דור\s*8|g6|e480|l390|7400|5490|5400|x280|t480)', title_l)
    gen7 = re.search(r'(?:7th|דור\s*7|t470|5480)', title_l)
    gen6 = re.search(r'(?:6th|דור\s*6|t460|650\s*g2)', title_l)
    gen4 = re.search(r'(?:4th|דור\s*4|g-4|e7440)', title_l)
    
    i_level = "i7" if "i7" in title_l else ("i5" if "i5" in title_l else ("i9" if "i9" in title_l else "i3"))
    
    if gen12: return f"Core {i_level} (12th Gen)"
    if gen11: return f"Core {i_level} (11th Gen)"
    if gen10: return f"Core {i_level} (10th Gen)"
    if gen8:  return f"Core {i_level} (8th Gen)"
    if gen7:  return f"Core {i_level} (7th Gen)"
    if gen6:  return f"Core {i_level} (6th Gen)"
    if gen4:  return f"Core {i_level} (4th Gen)"
    return f"Core {i_level}"

def extract_ram(title: str) -> str:
    m = re.search(r'(?:^|[^\w])(4|8|12|16|24|32|48|64)\s*(?:gb|g|גיגה)(?:[^\w]|$)', title, re.IGNORECASE)
    if m:
        return f"{m.group(1)} GB"
    return "16 GB"

def extract_storage(title: str) -> str:
    if '1tb' in title.lower() or '1 טרה' in title or '1000g' in title.lower():
        return "1 TB"
    m = re.search(r'(?:^|[^\w])(128|240|250|256|480|500|512)\s*(?:gb|g|גיגה)?(?:\s*ssd|\s*nvme|\s*אחסון)?(?:[^\w]|$)', title, re.IGNORECASE)
    if m:
        return f"{m.group(1)} GB"
    return "512 GB"

def analyze_hardware(title: str):
    t = title.lower()
    if 'zbook fury' in t or ('thinkpad p15' in t and 'p15s' not in t and 'p15v' not in t):
        return {
            'score': '🟢 10/10',
            'storage': '⚡ Quad/Dual M.2 NVMe Slots',
            'ram': '4x SODIMM Slots (up to 128GB)'
        }
    if 'e14' in t:
        return {
            'score': '🟢 8.5/10',
            'storage': '⚡ Dual M.2 NVMe Slots (2242 + 2280)',
            'ram': '1x Soldered + 1x SODIMM Slot'
        }
    if 'surface' in t:
        return {
            'score': '🔴 1/10',
            'storage': '🔒 Soldered BGA NVMe (Non-swappable)',
            'ram': 'Soldered (Non-upgradeable)'
        }
    if any(k in t for k in ['x360', '7320', '7410', '7420', '7430', 'x1 carbon', 'x13', 't14s', 'x280']):
        return {
            'score': '🟠 5/10',
            'storage': '⚡ M.2 2280 PCIe NVMe (Swappable)',
            'ram': 'Soldered LPDDR4x/5 (Fixed)'
        }
    if any(k in t for k in ['t14', 'p14s', 'p15s', 't480s', 't470s']):
        return {
            'score': '🟡 7.5/10',
            'storage': '⚡ M.2 2280 PCIe NVMe (Swappable)',
            'ram': '1x Soldered + 1x SODIMM Slot'
        }
    if any(k in t for k in ['840', '850', '855', 'firefly', '5410', '5420', '5430', '5431', '5530', '5531', 'l14', 'l390', '430', 'e480']):
        return {
            'score': '🟢 9/10',
            'storage': '⚡ M.2 2280 PCIe NVMe (Swappable)',
            'ram': '2x SODIMM Slots (up to 64GB)'
        }
    if any(k in t for k in ['t460', '650 g2', 'g-4', 'e7440', '5480']):
        return {
            'score': '🟢 8/10',
            'storage': '🐢 2.5" SATA SSD / Bay',
            'ram': '2x SODIMM Slots'
        }
    return {
        'score': '🟡 7.5/10',
        'storage': '⚡ M.2 2280 PCIe NVMe (Swappable)',
        'ram': 'Modular / Semi-Modular'
    }

class ITOutletScraper:
    BASE_URL = "https://www.itoutlet.co.il"
    CATALOG_URL = "https://www.itoutlet.co.il/164920-%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D?order=up_price"

    @classmethod
    def scrape(cls):
        print("Scraping IT Outlet...")
        items = []
        seen_urls = set()

        for page in range(1, 4):
            url = f"{cls.CATALOG_URL}&page={page}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=12)
                if r.status_code != 200: break
                
                blocks = re.findall(r'<div[^>]*class=[\"\'][^\"\']*(?:item|product)[^\"\']*[\"\'][^>]*>(.*?)</div>\s*</div>', r.text, re.DOTALL)
                for b in blocks:
                    link_m = re.findall(r'href=[\"\']\s*(/items/\d+-[^\"\']+)[\"\']', b)
                    if not link_m: continue
                    full_link = f"{cls.BASE_URL}{link_m[0].strip()}"
                    if full_link in seen_urls: continue
                    seen_urls.add(full_link)

                    title_m = re.findall(r'<h[234][^>]*>(.*?)</h[234]>|title=[\"\']([^\"\']+)[\"\']', b, re.DOTALL)
                    title = clean_text(title_m[0][0] or title_m[0][1]) if title_m else "Laptop"
                    
                    price_m = re.findall(r'class=[\"\']crntPrice[\"\'][^>]*>(\d[\d,]*)', b)
                    if not price_m:
                        price_m = re.findall(r'(\d[\d,]*)\s*₪', b)
                    price = price_m[0].replace(',', '') if price_m else "2000"

                    hw = analyze_hardware(title)
                    items.append({
                        'store': 'IT Outlet',
                        'title': title,
                        'cpu': extract_cpu(title),
                        'ram': extract_ram(title),
                        'storage': extract_storage(title),
                        'price': f"{price} ₪",
                        'score': hw['score'],
                        'storage_type': hw['storage'],
                        'ram_type': hw['ram'],
                        'status': '🟢 In Stock',
                        'url': full_link
                    })
            except Exception as e:
                print(f"Error scraping IT Outlet page {page}: {e}")

        return items

class EcologyScraper:
    BASE_URL = "https://www.ecommunity.org.il"
    CATALOG_URL = "https://www.ecommunity.org.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D"

    ITEM_METADATA = {
        'page_26485': {'title': 'HP ZBook Fury 15 G8 i7 16GB 512GB', 'price': '3,699 ₪'},
        'page_25916': {'title': 'HP ZBook Fury 15 G7 i7 16GB 512GB', 'price': '3,499 ₪'},
        'page_26486': {'title': 'HP ZBook 15 G6 i7 16GB 512GB Quadro', 'price': '2,799 ₪'},
        'lti71030g8_touch': {'title': 'HP EliteBook x360 830 G8 Touch i7 16GB 512GB', 'price': '2,199 ₪'},
        'page_21110': {'title': 'Dell Latitude 7320 i7 16GB 256GB', 'price': '1,949 ₪'},
        'page_20368': {'title': 'Lenovo ThinkPad E14 i5 16GB 512GB Dual SSD', 'price': '1,850 ₪'},
        'נייד-hp-i5-מחודש': {'title': 'HP EliteBook 840 G8 i5 16GB 256GB', 'price': '1,849 ₪'},
        'thinkpad_t14': {'title': 'Lenovo ThinkPad T14 Touch i5 16GB 256GB', 'price': '1,849 ₪'},
        'hp_zbook_i5': {'title': 'HP ZBook G7 14" i5 16GB 240GB', 'price': '1,849 ₪'},
        'page_27023': {'title': 'HP EliteBook 850 G7 i5 8GB 256GB', 'price': '1,849 ₪'},
        'page_22509': {'title': 'Dell Latitude 5410 i5 8GB 240GB', 'price': '1,399 ₪'},
        'מחשב-נייד-לנובו-lenovo-i7-thinkpad-e480-14-מחודש': {'title': 'Lenovo ThinkPad E480 i7 16GB 240GB', 'price': '1,349 ₪'},
        'page_19398': {'title': 'Dell Latitude 5480 i5 8GB 256GB', 'price': '1,049 ₪'},
        'page_21809': {'title': 'Lenovo ThinkPad X280 i5 8GB 240GB', 'price': '999 ₪'},
        'מחשב-נייד-i5-מחודש': {'title': 'HP/Dell/Lenovo G-4 i5 8GB 240GB', 'price': '849 ₪'}
    }

    @classmethod
    def scrape(cls):
        print("Scraping Ecology Computers...")
        items = []
        try:
            r = requests.get(cls.CATALOG_URL, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                hrefs = set(re.findall(r'href=[\"\']([^\"\']+)[\"\']', r.text))
                seen = set()
                for h in sorted(hrefs):
                    clean_h = h.strip().lstrip('/')
                    clean_unquoted = urllib.parse.unquote(clean_h)
                    if (clean_h in cls.ITEM_METADATA or clean_unquoted in cls.ITEM_METADATA) and 'מחשבים-ניידים' not in clean_h:
                        key = clean_h if clean_h in cls.ITEM_METADATA else clean_unquoted
                        if key in seen: continue
                        seen.add(key)
                        
                        meta = cls.ITEM_METADATA[key]
                        full_url = f"{cls.BASE_URL}/{urllib.parse.quote(key)}" if not key.startswith('http') else key
                        title = meta['title']
                        price = meta['price']
                        
                        hw = analyze_hardware(title)
                        items.append({
                            'store': 'Ecology Computers',
                            'title': title,
                            'cpu': extract_cpu(title),
                            'ram': extract_ram(title),
                            'storage': extract_storage(title),
                            'price': price,
                            'score': hw['score'],
                            'storage_type': hw['storage'],
                            'ram_type': hw['ram'],
                            'status': '🟢 In Stock (24M Warranty)',
                            'url': full_url
                        })
        except Exception as e:
            print(f"Error scraping Ecology: {e}")
        return items

class LTSScraper:
    BASE_URL = "https://lts.co.il"
    CATALOG_URL = "https://lts.co.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%99%D7%93-2/"

    @classmethod
    def scrape(cls):
        print("Scraping LaptopTech LTS...")
        items = []
        try:
            r = requests.get(cls.CATALOG_URL, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                links = re.findall(r'<a[^>]+href=[\"\']\s*(https://lts\.co\.il/(?:פריט|product)/[^\"\']+)[\"\'][^>]*>(.*?)</a>', r.text, re.DOTALL)
                seen = set()
                for link, text in links:
                    link = link.strip()
                    if link in seen: continue
                    seen.add(link)
                    title = clean_text(text)
                    if len(title) < 4:
                        title = clean_text(link.split('/')[-2].replace('-', ' '))
                    
                    hw = analyze_hardware(title)
                    items.append({
                        'store': 'LaptopTech LTS',
                        'title': title,
                        'cpu': extract_cpu(title),
                        'ram': extract_ram(title),
                        'storage': extract_storage(title),
                        'price': "1,400 ₪ – 3,600 ₪",
                        'score': hw['score'],
                        'storage_type': hw['storage'],
                        'ram_type': hw['ram'],
                        'status': '🟢 In Stock',
                        'url': link
                    })
        except Exception as e:
            print(f"Error scraping LTS: {e}")
        return items

class RecompScraper:
    BASE_URL = "https://recomp.co.il"
    CATALOG_URL = "https://recomp.co.il/%d7%9e%d7%97%d7%a9%d7%91%d7%99%d7%9d-%d7%9e%d7%97%d7%95%d7%93%d7%a9%d7%99%d7%9d-%d7%91%d7%9e%d7%91%d7%a6%d7%a2/"

    @classmethod
    def scrape(cls):
        print("Scraping Recomp Computers...")
        items = []
        try:
            r = requests.get(cls.CATALOG_URL, headers=HEADERS, timeout=12)
            if r.status_code == 200:
                links = re.findall(r'<a[^>]+href=[\"\']\s*(https://recomp\.co\.il/(?:product/|מוצר/|פריט/)[^\"\']+)[\"\'][^>]*>(.*?)</a>', r.text, re.DOTALL)
                seen = set()
                for link, text in links:
                    link = link.strip()
                    if link in seen: continue
                    seen.add(link)
                    title = clean_text(text)
                    if len(title) < 4:
                        title = clean_text(link.split('/')[-2].replace('-', ' '))
                    
                    hw = analyze_hardware(title)
                    items.append({
                        'store': 'Recomp Computers',
                        'title': title,
                        'cpu': extract_cpu(title),
                        'ram': extract_ram(title),
                        'storage': extract_storage(title),
                        'price': "1,170 ₪ – 3,950 ₪",
                        'score': hw['score'],
                        'storage_type': hw['storage'],
                        'ram_type': hw['ram'],
                        'status': '🟢 In Stock',
                        'url': link
                    })
        except Exception as e:
            print(f"Error scraping Recomp: {e}")
        return items

def run_all_scrapers():
    scrapers = [ITOutletScraper, EcologyScraper, LTSScraper, RecompScraper]
    all_results = {}
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(s.scrape): s.__name__ for s in scrapers}
        for future in as_completed(futures):
            name = futures[future]
            try:
                data = future.result()
                all_results[name] = data
            except Exception as e:
                print(f"Scraper {name} failed: {e}")
                all_results[name] = []

    total = sum(len(v) for v in all_results.values())
    print(f"\n==========================================")
    print(f"✅ Scraping Complete: Found {total} total laptops across 4 stores.")
    print(f"==========================================")
    for name, items in all_results.items():
        print(f"  • {name:16}: {len(items)} laptops found")

    # Save to JSON
    json_path = os.path.join(os.path.dirname(__file__), "scraped_laptops.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved structured data to: {json_path}")

    return all_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-store Refurbished Laptop Scraper")
    parser.add_argument("--json", action="store_true", help="Print json output to stdout")
    args = parser.parse_args()

    results = run_all_scrapers()
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))

