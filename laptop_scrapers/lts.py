import html
import logging
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Optional
import requests
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import last_valid_price

logger = logging.getLogger("LTSScraper")

# --- Store 3: LaptopTech LTS Scraper ---
class LTSScraper:
    STORE_NAME = "LaptopTech LTS"
    CATALOG_URL = "https://lts.co.il/%D7%9E%D7%97%D7%A9%D7%91%D7%99%D7%9D-%D7%A0%D7%99%D7%99%D7%93%D7%99%D7%9D-%D7%9E%D7%97%D7%95%D7%93%D7%A9%D7%99%D7%9D-%D7%99%D7%93-2/"

    def __init__(self, session: requests.Session):
        self.session = session

    def _parse_product_page_price(self, html: str) -> Optional[int]:
        cleaned = html.replace('&#8362;', '₪').replace('&nbsp;', ' ')
        widget = re.findall(r'elementor-widget-woocommerce-product-price(.*?)</div>\s*</div>', cleaned, re.DOTALL)
        if widget:
            ins = re.findall(r'<ins[^>]*>.*?([0-9]{1,2},[0-9]{3}|[0-9]{3,5}).*?</ins>', widget[0], re.DOTALL)
            if ins:
                return last_valid_price(ins)
            nums = re.findall(r'([0-9]{1,2},[0-9]{3}|[0-9]{3,5})', widget[0])
            price = last_valid_price((n for n in nums if n.replace(',', '') != '8362'))
            if price is not None:
                return price

        cur_match = re.findall(r'המחיר הנוכחי הוא:[^\d]*([\d,]+)', cleaned)
        if cur_match:
            return last_valid_price(cur_match)

        single = re.findall(r'<p class=\"price\">(.*?)</p>', cleaned, re.DOTALL)
        if single:
            nums = re.findall(r'([0-9]{1,2},[0-9]{3}|[0-9]{3,5})', single[-1])
            price = last_valid_price((n for n in nums if n.replace(',', '') != '8362'))
            if price is not None:
                return price

        schema = re.findall(r'\"price\"\s*:\s*\"?(\d+)\"?', cleaned)
        if schema:
            return int(schema[-1])
        return None

    def _parse_product_page_image(self, html: str) -> str:
        og_m = re.search(r'<meta\s+property=[\"\']og:image[\"\']\s+content=[\"\']([^\"\']+)[\"\']', html, re.I)
        if og_m:
            return og_m.group(1).strip()
        img_m = re.search(r'<img[^>]*src=[\"\']([^\"\']+(?:uploads|product)[^\"\']+)[\"\']', html, re.I)
        if img_m:
            return img_m.group(1).strip()
        return ""

    def _parse_product_page_desc(self, page_html: str) -> str:
        short_m = re.search(r'class=[\"\'][^\"\']*woocommerce-product-details__short-description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        tab_m = re.search(r'id=[\"\']tab-description[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        if not tab_m:
            tab_m = re.search(r'class=[\"\'][^\"\']*woocommerce-Tabs-panel--description[^\"\']*[\"\'][^>]*>([\s\S]*?)</div>', page_html)
        parts = []
        if short_m:
            parts.append(short_m.group(1))
        if tab_m:
            parts.append(tab_m.group(1))
        if parts:
            return html.unescape(re.sub(r'<[^>]+>', ' ', ' '.join(parts))).strip()
        return ""

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping LaptopTech LTS...")
        items: List[LaptopItem] = []
        try:
            r = self.session.get(self.CATALOG_URL, timeout=12)
            if r.status_code == 200:
                raw_links = set(re.findall(r'href=[\"\']\s*(https://lts\.co\.il/(?:פריט|product)/[^\"\']+)[\"\']', r.text))
                valid_links = []
                for link in sorted(raw_links):
                    slug = link.rstrip('/').split('/')[-1]
                    slug_clean = urllib.parse.unquote(slug).replace('-', ' ')
                    if HardwareClassifier.is_laptop(slug_clean):
                        valid_links.append((link, slug_clean))

                # Fetch exact prices and descriptions concurrently for all laptops
                def fetch_item_details(item_tuple):
                    link, slug_clean = item_tuple
                    try:
                        res = self.session.get(link, timeout=8)
                        p = self._parse_product_page_price(res.text)
                        img = self._parse_product_page_image(res.text)
                        desc = self._parse_product_page_desc(res.text)
                        return link, slug_clean, p, img, desc
                    except Exception:
                        return link, slug_clean, None, "", ""

                with ThreadPoolExecutor(max_workers=10) as executor:
                    fetched_results = list(executor.map(fetch_item_details, valid_links))

                for link, slug_clean, price, img, desc in fetched_results:
                    if price is None:
                        logger.warning("Skipping LTS listing without a valid price: %s", link)
                        continue
                    words = slug_clean.split()
                    title = ' '.join(w.capitalize() if not any(c.isdigit() for c in w) else w.upper() for w in words)
                    analysis = f"{title} {slug_clean} {desc}".strip()

                    warranty = 12
                    if any(k in analysis for k in ["3 שנות אחריות", "3 שנים", "שלוש שנים", "36 חודש"]):
                        warranty = 36
                    elif any(k in analysis for k in ["שנתיים אחריות", "שנתיים", "24 חודש"]):
                        warranty = 24

                    items.append(HardwareClassifier.build_laptop(
                        store=self.STORE_NAME,
                        title=title,
                        price_ils=price,
                        url=link,
                        analysis_text=analysis,
                        warranty_months=warranty,
                        stock_status="🟢 In Stock",
                        image_url=img,
                    ))
        except Exception as e:
            logger.error(f"Error scraping LTS: {e}")
        return items
