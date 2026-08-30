# second-hand-pc

A data‑driven toolkit for researching, evaluating, and comparing **second‑hand laptops**, with a focus on **2‑in‑1 devices**, **touch laptops**, and detailed model‑specific reviews.  
This repository combines scraping tools, structured datasets, and curated documentation to help buyers make informed decisions when purchasing refurbished or used laptops.

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
├── scraped_laptops.csv            # Cleaned dataset of scraped listings
├── scraped_laptops.json           # JSON version of the dataset
│
├── 2in1_and_touch_laptops_guide.md
├── hp_elitebook_x360_830_g8_master_review.md
├── hp_elitebook_x360_accessories_guide.md
├── summary.md
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

- `summary.md` for high‑level insights  
- Model‑specific guides for deeper analysis  

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

standart MIT license

---

## ⭐ Acknowledgements

Thanks to the open‑source community and refurbished laptop marketplaces that make this research possible.
