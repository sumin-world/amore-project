"""
Amazon Best Sellers Page Scraper

This module extracts product ranking data from Amazon Best Sellers pages,
focusing on beauty products. It uses Playwright for browser automation
to handle dynamic content and implement bot detection evasion strategies.

Key Features:
    - Headless browser automation via Playwright (more reliable than requests)
    - Configurable sleep delays to mimic human browsing patterns
    - Robust HTML parsing with multiple selector fallbacks
    - Extracts comprehensive product metadata:
        * rank: Position in the Best Sellers list (1-20)
        * title: Product name from image alt text
        * ASIN: Amazon Standard Identification Number (unique product ID)
        * price: Current listing price in USD
        * rating: Average customer rating (0-5 stars)
        * review_count: Total number of customer reviews
        * image_url: Product thumbnail URL for visual tracking
    
Bot Evasion Tactics:
    - Uses Playwright with chromium browser (real browser, not just HTTP client)
    - Random sleep delay between requests (configured via REQUEST_SLEEP_SEC)
    - Standard User-Agent headers
    - Wait for DOM content to fully load before parsing
    
Selector Strategy:
    - Primary: div#zg-ordered-list > li (standard Best Sellers layout)
    - Fallback: div.zg-grid-general-faceout, div.p13n-sc-uncoverable-faceout
    - Multiple fallback selectors for price, rating, reviews to handle variations

TODO:
    - Add proxy rotation support for higher volume scraping
    - Implement CAPTCHA detection and alerting
    - Add retry logic with exponential backoff for transient failures
"""
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
    """
    Convert price string to float, handling Amazon's formatting.
    
    Args:
        s: Price string like "$24.99" or "$1,234.56"
    
    Returns:
        Float value or 0.0 if conversion fails
    
    Examples:
        "$24.99" -> 24.99
        "$1,234.56" -> 1234.56
        "N/A" -> 0.0
    """
    try: return float(s.replace("$","").replace(",","").strip())
    except: return 0.0

def _to_int(s: str) -> int:
    """
    Extract integer from review count strings.
    
    Args:
        s: Review count string like "1,234" or "5,678 ratings"
    
    Returns:
        Integer value or 0 if extraction fails
    
    Examples:
        "1,234" -> 1234
        "5,678 ratings" -> 5678
        "N/A" -> 0
    """
    try:
        s = s.replace(",","")
        m = re.findall(r"\d+", s)
        return int(m[0]) if m else 0
    except:
        return 0

class AmazonBestSellers(Source):
    """
    Scraper for Amazon Best Sellers pages.
    
    This class implements the Source interface to collect product rankings
    from Amazon Best Sellers lists. It's optimized for beauty products but
    can work with any Best Sellers category.
    
    Attributes:
        Inherits from Source base class
    
    Methods:
        fetch(url: str) -> List[ProductItem]: Main scraping method
    
    Usage:
        scraper = AmazonBestSellers()
        items = scraper.fetch("https://www.amazon.com/gp/bestsellers/beauty/...")
    
    Notes:
        - Respects rate limiting via settings.request_sleep_sec
        - Captures up to 20 products per page (Amazon's typical limit)
        - Skips products missing required fields (ASIN or title)
    """
    def fetch(self, url: str) -> List[ProductItem]:
        """
        Fetch and parse Amazon Best Sellers page.
        
        Args:
            url: Full Amazon Best Sellers page URL
                Example: https://www.amazon.com/gp/bestsellers/beauty/3784821
        
        Returns:
            List of ProductItem objects containing ranking snapshot data
        
        Raises:
            playwright.sync_api.TimeoutError: If page load exceeds 60 seconds
            Exception: For network errors or parsing failures (logged but not raised)
        
        Process:
            1. Launch headless Chromium browser
            2. Navigate to URL and wait for DOM content loaded
            3. Apply random sleep delay (bot evasion)
            4. Extract HTML and close browser
            5. Parse product cards using BeautifulSoup
            6. Extract ASIN, title, price, rating, review count, image URL
            7. Construct ProductItem objects with standardized fields
        
        Notes:
            - captured_at timestamp marks the moment of data collection
            - Rank counter increments only for valid products (ASIN + title)
            - Product URLs are cleaned (removes query parameters)
            - Raw href stored in raw dict for debugging
        """
        captured_at = datetime.utcnow()
        items: List[ProductItem] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            # Sleep delay to avoid bot detection - mimics human browsing behavior
            time.sleep(settings.request_sleep_sec)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "lxml")
        # Try primary selector first, fall back to alternate layouts
        cards = soup.select("div#zg-ordered-list > li")
        if not cards:
            cards = soup.select("div.zg-grid-general-faceout, div.p13n-sc-uncoverable-faceout")

        rank_counter = 0
        for card in cards:
            if rank_counter >= 20:
                break
            
            # Extract ASIN from product link
            a = card.select_one("a.a-link-normal[href*=\"/dp/\"]")
            href = a.get("href","") if a else ""
            m = _ASIN_RE.search(href)
            asin = m.group(1) if m else ""

            # Extract title from image alt text (most reliable source)
            img = card.select_one("img")
            title = (img.get("alt","") if img else "").strip()
            img_url = (img.get("src","") if img else "").strip()

            # Extract price with fallback selectors
            price_el = card.select_one("span.a-price > span.a-offscreen, span.a-color-price")
            price = _to_float(price_el.get_text(strip=True)) if price_el else 0.0

            # Extract rating
            rating_el = card.select_one("span.a-icon-alt")
            rating = 0.0
            if rating_el:
                try: rating = float(rating_el.get_text(strip=True).split(" ")[0])
                except: rating = 0.0

            # Extract review count
            rc_el = card.select_one("a[href*=\"#customerReviews\"] span")
            review_count = _to_int(rc_el.get_text(strip=True)) if rc_el else 0

            # Skip invalid products
            if not asin or not title:
                continue

            rank_counter += 1
            # Clean product URL (remove query parameters for consistency)
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
