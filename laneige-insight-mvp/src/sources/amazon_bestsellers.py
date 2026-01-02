from datetime import datetime
from typing import List
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re
import time
from src.sources.base import Source, ProductItem
from src.config import settings

_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")

def _to_float(s: str) -> float:
    try: return float(s.replace("$","").replace(",","").strip())
    except: return 0.0

def _to_int(s: str) -> int:
    try:
        s = s.replace(",","")
        m = re.findall(r"\d+", s)
        return int(m[0]) if m else 0
    except:
        return 0

class AmazonBestSellers(Source):
    def fetch(self, url: str) -> List[ProductItem]:
        captured_at = datetime.utcnow()
        items: List[ProductItem] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(settings.request_sleep_sec)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("div#zg-ordered-list > li")
        if not cards:
            cards = soup.select("div.zg-grid-general-faceout, div.p13n-sc-uncoverable-faceout")

        rank_counter = 0
        for card in cards:
            if rank_counter >= 20:
                break
            a = card.select_one("a.a-link-normal[href*=\"/dp/\"]")
            href = a.get("href","") if a else ""
            m = _ASIN_RE.search(href)
            asin = m.group(1) if m else ""

            img = card.select_one("img")
            title = (img.get("alt","") if img else "").strip()
            img_url = (img.get("src","") if img else "").strip()

            price_el = card.select_one("span.a-price > span.a-offscreen, span.a-color-price")
            price = _to_float(price_el.get_text(strip=True)) if price_el else 0.0

            rating_el = card.select_one("span.a-icon-alt")
            rating = 0.0
            if rating_el:
                try: rating = float(rating_el.get_text(strip=True).split(" ")[0])
                except: rating = 0.0

            rc_el = card.select_one("a[href*=\"#customerReviews\"] span")
            review_count = _to_int(rc_el.get_text(strip=True)) if rc_el else 0

            if not asin or not title:
                continue

            rank_counter += 1
            product_url = "https://www.amazon.com" + href.split("?")[0] if href.startswith("/") else href

            items.append(ProductItem(
                source="amazon_bestsellers",
                market="US",
                category="Amazon Best Sellers (Beauty)",
                captured_at=captured_at,
                rank=rank_counter,
                product_id=asin,
                title=title,
                product_url=product_url,
                price=price,
                rating=rating,
                review_count=review_count,
                image_url=img_url,
                raw={"href": href},
            ))
        return items
