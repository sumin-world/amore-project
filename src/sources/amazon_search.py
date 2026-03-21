"""
Amazon search results scraper for keyword-based product discovery.

Status: functional single-page implementation.
"""

import re
import time
from datetime import datetime
from typing import List, Set

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from src.config import settings
from src.sources.base import Source, ProductItem

_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")


def _to_float(s: str) -> float:
    try:
        return float(s.replace("$", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _to_int(s: str) -> int:
    try:
        nums = re.findall(r"\d+", s.replace(",", ""))
        return int(nums[0]) if nums else 0
    except (ValueError, IndexError):
        return 0


class AmazonSearch(Source):
    """Scrape a single Amazon search results page."""

    def fetch(self, url: str) -> List[ProductItem]:
        captured_at = datetime.utcnow()
        items: List[ProductItem] = []
        seen: Set[str] = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(settings.request_sleep_sec)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "lxml")
        cards = soup.select('div[data-component-type="s-search-result"]')

        rank = 0
        for card in cards:
            a = card.select_one('a.a-link-normal[href*="/dp/"]')
            href = a.get("href", "") if a else ""
            m = _ASIN_RE.search(href)
            asin = m.group(1) if m else ""
            if not asin or asin in seen:
                continue
            seen.add(asin)

            title_el = card.select_one("h2 a span")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            img = card.select_one("img")
            img_url = (img.get("src", "") if img else "").strip()

            price_el = card.select_one("span.a-price > span.a-offscreen")
            price = _to_float(price_el.get_text(strip=True)) if price_el else 0.0

            rating = 0.0
            rating_el = card.select_one("span.a-icon-alt")
            if rating_el:
                try:
                    rating = float(rating_el.get_text(strip=True).split()[0])
                except (ValueError, IndexError):
                    pass

            rc_el = card.select_one('a[href*="#customerReviews"] span')
            review_count = _to_int(rc_el.get_text(strip=True)) if rc_el else 0

            rank += 1
            product_url = (
                "https://www.amazon.com" + href.split("?")[0]
                if href.startswith("/")
                else href
            )

            items.append(
                ProductItem(
                    source="amazon_search",
                    market="US",
                    category="Amazon Search",
                    captured_at=captured_at,
                    rank=rank,
                    product_id=asin,
                    title=title,
                    product_url=product_url,
                    price=price,
                    rating=rating,
                    review_count=review_count,
                    image_url=img_url,
                    raw={"href": href, "search_url": url},
                )
            )

        return items
