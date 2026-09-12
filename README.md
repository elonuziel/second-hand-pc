# second-hand-pc

A data‑driven toolkit for researching, evaluating, and comparing **second‑hand laptops**, with a focus on **2‑in‑1 devices**, **touch laptops**, and detailed model‑specific reviews.  
This repository combines scraping tools, structured datasets, and curated documentation to help buyers make informed decisions when purchasing refurbished or used laptops.

## 🌐 Live site

Project website: https://elonuziel.github.io/second-hand-pc/

---

## 📌 Project Overview

This project provides:

- A **Python scraper** for collecting laptop listings from multiple vendors.
- Structured datasets (`scraped_laptops.csv`, `scraped_laptops.json`) containing normalized laptop attributes.
- Detailed **model reviews** and **accessory guides** (e.g., HP EliteBook x360 series)   [Current page](citation-section://1645521870/2).
- A growing documentation set covering:
  - Pen technology types  
  - Battery capacity & drain metrics  
  - USB‑C port redundancy  
  - Repairability insights  
  - Magnetic adapter tips  
- GitHub Actions workflows for automated scraping and enhancements.

---

## 📁 Repository Structure

```
second-hand-pc/
│
├── scraper.py                     # Main scraping script
├── laptop_domain.py               # Shared LaptopItem domain model
├── laptop_parsing.py              # Pure price and listing validation helpers
├── laptop_pipeline.py             # Concurrent store execution and isolation
├── laptop_recommendations.py      # Deterministic top-pick selection
├── scraped_laptops.csv            # Cleaned dataset of scraped listings
├── scraped_laptops.json           # JSON version of the dataset
│
├── full_catalog.md
├── guides/
│   └── 2in1/                         # Dedicated 2-in-1 and touch laptop guides
│       ├── 2in1_and_touch_laptops_guide.md
│       ├── hp_elitebook_x360_830_g8_master_review.md
│       └── hp_elitebook_x360_accessories_guide.md
│
├── assets/                        # Images or static resources
│
├── .env.example                   # Example environment variables
├── .gitignore
└── .github/workflows/             # GitHub Actions automation
```

---

## 🚀 Features

### 🔍 Laptop Scraper
- Extracts laptop listings from supported marketplaces.
- Normalizes specs such as CPU, RAM, storage, screen type, battery, and price.
- Outputs both CSV and JSON formats for analysis.
- Store adapters must provide a valid source price; listings with missing or invalid prices are skipped and logged rather than receiving an estimated price.
- `LaptopItem` is defined in `laptop_domain.py`; `scraper.py` continues to re-export it for compatibility.
- Pure listing and price validation lives in `laptop_parsing.py`, while recommendation ranking lives in `laptop_recommendations.py`.

### 📝 Expert Reviews & Guides
- In‑depth EliteBook x360 G8 review with repairability and port redundancy notes.
- Accessory guide including chargers, pens, adapters, and docks.
- 2‑in‑1 & touch laptop guide with battery drain metrics and pen technology comparisons.

### ⚙️ GitHub Actions Integration
Automated workflows for:
- Running the scraper on schedule.
- Updating datasets.
- Enhancing code with Groq AI (as referenced in commit messages)   [Current page](citation-section://1645521870/1).

---

## 📦 Installation

```bash
git clone https://github.com/elonuziel/second-hand-pc.git
cd second-hand-pc
pip install -r requirements.txt
```

Create your `.env` file based on `.env.example`.

### Optional: headless-browser fallback for JavaScript bot challenges

Stores behind JavaScript bot challenges cannot be fetched by plain HTTP clients — verified
against `curl_cffi` Chrome impersonation, datacenter proxies, and Crawlbase (Normal and
JavaScript tokens). This affects Olam HaKolnoa (CWC) directly, and Machsanei Hashmal (Payngo)
whenever its catalog is blocked instead of served. Installing Playwright lets those stores
render the challenge in real Chromium instead of being skipped:

```bash
pip install playwright
playwright install chromium          # add --with-deps on a fresh Linux box
```

The fallback is opt-in by installation: when Playwright (or its Chromium binary) is missing,
scrapers keep using plain HTTP and log exactly why a store was skipped. It only launches a
browser when a store is actually challenged or blocked, so healthy stores never pay for it —
and if the browser still cannot clear the block, the store is reported as blocked and the
pipeline preserves its previously scraped data.

| Env var | Effect |
| --- | --- |
| `SCRAPER_DISABLE_BROWSER=1` | Never launch a browser, even when Playwright is installed |
| `SCRAPER_BROWSER_HEADLESS=0` | Run the browser headed, for debugging |
| `PLAYWRIGHT_BROWSERS_PATH` | Where Chromium lives (default `~/.cache/ms-playwright`) |

### Request pacing and backoff (per-host politeness)

WAFs escalate on bursts, so every resilient fetch keeps a minimum gap between requests to
the same host, which also serialises that host's concurrency to one. Each store scrapes a
single host, so per-host overrides are effectively per-store pacing:

| Env var | Effect |
| --- | --- |
| `SCRAPER_HOST_DELAY` | Seconds between requests to the same host (default `1.0`; `0` disables) |
| `SCRAPER_HOST_DELAYS` | Per-host overrides, e.g. `payngo.co.il=3,cwc.co.il=2` (suffix match; `0` zeroes one host) |
| `SCRAPER_BACKOFF_BUDGET` | Seconds of waiting per URL before retrying a challenge/`503` (default `0`, i.e. off) |
| `SCRAPER_BACKOFF_WAIT` | Cooldown before each retry (default `30`) |
| `SCRAPER_HOST_PENALTY` | Seconds a host is parked after spending its budget (default `300`) |

Cooldown-retry ships **off**, based on measurement: enabling it on payngo with a 30s cooldown
pushed runs from ~10s to 61-127s while producing no more items, because retrying *adds* the
request volume these walls penalise. Raise `SCRAPER_BACKOFF_BUDGET` only when a store's
catalog is transiently blocked and you can afford roughly a minute per store. `429` is never
retried: the pycurl → curl_cffi → requests chain inside a single attempt already absorbs
per-request throttling.

Pacing bounds the damage but is not a cure: these WAFs also apply short-lived per-IP penalty
windows that a slower fixed pace does not avoid, because the first request of each run always
fires immediately. When a store is throttled it is reported as blocked and its previously
scraped data is preserved.

**Known limitation:** the fallback clears the JavaScript challenge, but it cannot beat an
IP-level WAF block. When CWC answers a *cleared* challenge with a Cloudflare `403 - Forbidden`
on every path (as it does for flagged datacenter IPs), the store is reported as blocked rather
than silently empty — no content is returned. That case needs a non-blocked IP.

---

## 🧪 Usage

Run the scraper:

```bash
python scraper.py
```

View the dataset:

```bash
cat scraped_laptops.csv
```

Explore documentation:

- `full_catalog.md` for complete multi-store market research and live stock audits
- `guides/2in1/` for dedicated 2-in-1, touch laptop, and HP EliteBook deep dives  

---

## 📊 Data

The dataset includes fields such as:

- Model name  
- CPU / RAM / Storage  
- Screen size & type  
- Battery capacity & drain  
- Price & condition  
- Seller metadata  

Use it for comparison, filtering, or building recommendation tools.

---

## 🤝 Contributing

Contributions are welcome!  
You can help by:

- Adding new laptop reviews  
- Improving the scraper  
- Expanding accessory guides  
- Enhancing documentation clarity  

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## ⭐ Acknowledgements

Thanks to the open‑source community and refurbished laptop marketplaces that make this research possible.
