"""
Amazon Search Results Scraper

This module collects product data from Amazon search result pages.
It's designed to discover new ASINs automatically by searching for
brand names or keywords (e.g., "laneige", "k-beauty").

Status: UNFINISHED - Basic implementation complete but needs enhancements

Current Features:
    - Scrapes Amazon search pages for product listings
    - Extracts ASIN, title, price, rating, review count, image URL
    - Deduplicates ASINs within a single page scrape
    - Supports pagination via URL query parameters

TODO - Future Enhancements:
    - Add multi-page scraping support (auto-detect and follow pagination)
    - Implement search query builder for advanced filters
    - Add support for sponsored vs organic result differentiation
    - Handle "No results found" and search suggestion pages
    - Add search result ranking position tracking (beyond single page)
    - Implement caching to avoid re-scraping recent searches
    - Add support for international Amazon domains (.co.uk, .co.jp, etc.)
    - Improve error handling for CAPTCHA and bot detection pages

Design Intentions:
    - Complement amazon_bestsellers by discovering products outside top 20
    - Enable keyword-based tracking for brand monitoring
    - Support competitive analysis by tracking multiple brands
    - Provide foundation for automated product discovery pipeline

Known Limitations:
    - Single page scraping only (no automatic pagination)
    - No handling of sponsored listings separately
    - Search result order may not reflect actual ranking over time
    - Rate limiting needed for bulk searches
"""
from datetime import datetime
from typing import List, Set
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re, time
from src.sources.base import Source, ProductItem
from src.config import settings

ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")

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

class AmazonSearch(Source):
    """
    Scraper for Amazon search result pages.
    
    Extracts product data from search listings to enable keyword-based
    product discovery and brand monitoring beyond Best Sellers lists.
    
    URL examples:
        - https://www.amazon.com/s?k=laneige
        - https://www.amazon.com/s?k=laneige&page=2
        - https://www.amazon.com/s?k=korean+beauty+skincare
    
    TODO:
        - Implement pagination support
        - Add search quality scoring (relevance)
        - Track sponsored vs organic placement
    """
    def fetch(self, url: str) -> List[ProductItem]:
        """
        Fetch and parse Amazon search results page.
        
        Args:
            url: Amazon search URL with query parameters
        
        Returns:
            List of ProductItem objects from search results
        
        Notes:
            - Deduplicates ASINs within the page
            - Rank reflects order in search results (position on page)
            - Skips results missing ASIN or title
        
        TODO:
            - Add pagination support to scrape multiple pages
            - Separate organic vs sponsored results
            - Add search relevance scoring
        """
        captured_at = datetime.utcnow()
        items: List[ProductItem] = []
        seen: Set[str] = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            # Random sleep delay to avoid bot detection
            time.sleep(settings.request_sleep_sec)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "lxml")

        # Search result tiles - standard Amazon search layout
        cards = soup.select('div[data-component-type="s-search-result"]')
        rank = 0
        for card in cards:
            a = card.select_one('a.a-link-normal[href*="/dp/"]')
            href = a.get("href","") if a else ""
            m = ASIN_RE.search(href)
            asin = m.group(1) if m else ""
            if not asin or asin in seen:
                continue
            seen.add(asin)

            title_el = card.select_one("h2 a span")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            img = card.select_one("img")
            img_url = (img.get("src","") if img else "").strip()

            price_el = card.select_one("span.a-price > span.a-offscreen")
            price = _to_float(price_el.get_text(strip=True)) if price_el else 0.0

            rating_el = card.select_one("span.a-icon-alt")
            rating = 0.0
            if rating_el:
                try:
                    rating = float(rating_el.get_text(strip=True).split(" ")[0])
                except (ValueError, IndexError, AttributeError):
                    rating = 0.0

            rc_el = card.select_one('a[href*="#customerReviews"] span')
            review_count = _to_int(rc_el.get_text(strip=True)) if rc_el else 0

            rank += 1
            product_url = "https://www.amazon.com" + href.split("?")[0] if href.startswith("/") else href

            items.append(ProductItem(
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
            ))
        return items
