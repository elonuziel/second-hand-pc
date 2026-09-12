"""A.L.M (ALM) scraper."""
from __future__ import annotations
import html
import json
import logging
import re
from typing import Any, List, Optional
from laptop_scrapers.base import fetch_resilient_url
from laptop_domain import LaptopItem
from laptop_classification import HardwareClassifier
from laptop_parsing import is_laptop_title

logger = logging.getLogger("ALMScraper")

# --- Store 7: A.L.M (ALM) Scraper ---
class ALMScraper:
    STORE_NAME = "ALM"
    GRAPHQL_URL = "https://www.alm.co.il/graphql"
    QUERY = """
query getCategoryProducts($urlKey: String!) {
  categoryList(filters: {url_key: {eq: $urlKey}}) {
    products(pageSize: 50) {
      items {
        name
        sku
        url_key
        price_range {
          minimum_price {
            final_price {
              value
            }
          }
        }
        small_image {
          url
        }
        description {
          html
        }
      }
    }
  }
}
"""

    def __init__(self, session: Any = None):
        self.session = session

    def scrape(self) -> List[LaptopItem]:
        logger.info("Scraping A.L.M (ALM)...")
        items: List[LaptopItem] = []
        try:
            payload = json.dumps({"query": self.QUERY, "variables": {"urlKey": "compoutlet"}})
            status, text = fetch_resilient_url(
                self.GRAPHQL_URL,
                post_data=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            )
            if status != 200 or not text:
                logger.warning(f"ALM GraphQL returned HTTP {status}")
                return items

            data = json.loads(text)
            cat_list = data.get("data", {}).get("categoryList", [])
            if not cat_list:
                return items

            prods = cat_list[0].get("products", {}).get("items", [])
            for p in prods:
                name = html.unescape(p.get("name", "")).strip()
                if not is_laptop_title(name):
                    continue

                price_obj = p.get("price_range", {}).get("minimum_price", {}).get("final_price", {})
                price = int(round(float(price_obj.get("value", 0))))
                if price <= 0:
                    continue

                ukey = p.get("url_key", "")
                url = f"https://www.alm.co.il/{ukey}.html" if ukey else "https://www.alm.co.il"
                img = p.get("small_image", {}).get("url", "")
                desc_html = p.get("description", {}).get("html", "")
                clean_desc = re.sub(r'<[^>]+>', ' ', desc_html)
                analysis = f"{name} {clean_desc}"

                items.append(HardwareClassifier.build_laptop(
                    store=self.STORE_NAME,
                    title=name,
                    price_ils=price,
                    url=url,
                    analysis_text=analysis,
                    warranty_months=12,
                    stock_status="🟢 In Stock",
                    image_url=img
                ))
        except Exception as e:
            logger.error(f"Error scraping ALM: {e}")
        return items
