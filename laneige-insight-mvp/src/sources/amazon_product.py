"""
Amazon Product Direct Tracking (ASIN Fixed Tracking Mode)

This module implements direct ASIN tracking for predefined product lists,
enabling focused monitoring of specific products without scraping lists.
Ideal for competitive analysis and brand portfolio tracking.

Features:
    - Direct product page scraping using ASIN identifiers
    - Tracks both own products and competitor products
    - Extracts Best Sellers Rank (BSR) from product detail pages
    - Configurable product list for easy maintenance
    - Rate-limited requests to respect Amazon's policies

ASIN Fixed Tracking Mode:
    Instead of scraping Best Sellers or search pages, this module directly
    fetches product detail pages for a curated list of ASINs. This provides:
    - More reliable data (direct from product page)
    - Faster execution (no list parsing)
    - Cleaner data (structured product pages vs list cards)
    - Better tracking of products outside top rankings
    
Use Cases:
    - Track own product portfolio (e.g., all Laneige products)
    - Monitor key competitors (e.g., COSRX, Innisfree)
    - Benchmark against market leaders
    - Long-term trend analysis for specific products

TODO - Future Enhancements:
    - Add automatic ASIN discovery from brand pages
    - Implement product variant tracking (size, color variations)
    - Add inventory availability monitoring
    - Track seller information (Amazon vs 3P sellers)
    - Add coupon and promotion detection
    - Implement BSR history tracking per category
    - Add A+ content change detection
    - Support bulk ASIN import from CSV/Excel
"""
from datetime import datetime
from typing import List, Dict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import re
from src.sources.base import Source, ProductItem
from src.config import settings

class AmazonProduct(Source):
    """
    Direct ASIN tracking for curated product lists.
    
    This scraper fetches individual product detail pages for a predefined
    list of ASINs, providing comprehensive tracking data including BSR
    (Best Sellers Rank) which is not available in list views.
    
    Attributes:
        TARGET_PRODUCTS: Dictionary mapping ASINs to product metadata
            Format: {ASIN: {"brand": str, "name": str}}
    
    Methods:
        fetch_asin(asin: str) -> ProductItem: Scrape single product page
        fetch(url: str) -> List[ProductItem]: Scrape all target products
    
    Usage:
        scraper = AmazonProduct()
        items = scraper.fetch("")  # URL not needed, uses TARGET_PRODUCTS
    
    Notes:
        - Automatically handles rate limiting between requests
        - Continues on individual failures to maximize data collection
        - BSR extraction handles multiple category rankings
    """
    
    # Curated product list for tracking
    # Add or remove products here to adjust tracking scope
    TARGET_PRODUCTS = {
        # Laneige (Own Brand Portfolio)
        "B07KNTK3QG": {"brand": "Laneige", "name": "Water Sleeping Mask"},
        "B00LUSHW18": {"brand": "Laneige", "name": "Lip Sleeping Mask"},
        "B084GYN2K4": {"brand": "Laneige", "name": "Cream Skin Refiner"},
        
        # Competitors (K-Beauty Market Leaders)
        "B00PBX3L7K": {"brand": "COSRX", "name": "Snail Mucin"},
        "B016NRXO06": {"brand": "COSRX", "name": "Low pH Cleanser"},
        "B07YZ8MJQY": {"brand": "Innisfree", "name": "Green Tea Serum"},
        "B01N5SMQM3": {"brand": "Etude House", "name": "SoonJung Toner"},
    }
    
    def fetch_asin(self, asin: str) -> ProductItem:
        """
        Scrape individual product detail page.
        
        Args:
            asin: Amazon Standard Identification Number (10 characters)
        
        Returns:
            ProductItem with comprehensive product data including BSR
        
        Raises:
            Exception: For network errors or parsing failures (caller handles)
        
        Extracted Data:
            - title: Full product name from #productTitle
            - price: Current listing price (handles multiple price selectors)
            - rating: Average customer rating (1-5 stars)
            - review_count: Total number of reviews
            - image_url: Main product image
            - rank: Best Sellers Rank (extracted from product details)
        
        Notes:
            - BSR extraction finds first category ranking (#N in Category)
            - Returns rank=-1 if BSR not found (not in any Best Sellers list)
            - Uses metadata from TARGET_PRODUCTS as fallback for brand/name
        """
        url = f"https://www.amazon.com/dp/{asin}"
        captured_at = datetime.utcnow()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            # Random sleep delay for bot detection evasion
            time.sleep(settings.request_sleep_sec)
            html = page.content()
            browser.close()
        
        soup = BeautifulSoup(html, "lxml")
        
        # Extract title from product detail page
        title_el = soup.select_one("#productTitle")
        title = title_el.get_text(strip=True) if title_el else ""
        
        # Extract price (primary selector, handle variations)
        price = 0.0
        price_el = soup.select_one("span.a-price span.a-offscreen")
        if price_el:
            try:
                price = float(price_el.get_text(strip=True).replace("$","").replace(",",""))
            except (ValueError, AttributeError):
                pass
        
        # Extract rating
        rating = 0.0
        rating_el = soup.select_one("span.a-icon-alt")
        if rating_el:
            try:
                rating = float(rating_el.get_text(strip=True).split()[0])
            except (ValueError, IndexError, AttributeError):
                pass
        
        # Extract review count
        review_count = 0
        review_el = soup.select_one("#acrCustomerReviewText")
        if review_el:
            try:
                text = review_el.get_text(strip=True).replace(",", "")
                review_count = int(re.search(r'\d+', text).group())
            except (ValueError, AttributeError):
                pass
        
        # Extract main product image
        image_url = ""
        img_el = soup.select_one("#landingImage")
        if img_el:
            image_url = img_el.get("src", "")
        
        # Extract Best Sellers Rank (BSR) - key metric for tracking
        # Format: "#1,234 in Beauty & Personal Care"
        rank = -1
        bsr_el = soup.find("th", string="Best Sellers Rank")
        if bsr_el:
            td = bsr_el.find_next("td")
            if td:
                bsr_text = td.get_text(strip=True)
                m = re.search(r'#([\d,]+)\s+in', bsr_text)
                if m:
                    rank = int(m.group(1).replace(",", ""))
        
        # Get product metadata from curated list
        meta = self.TARGET_PRODUCTS.get(asin, {"brand": "Unknown", "name": "Unknown"})
        
        return ProductItem(
            source="amazon_product",
            market="US",
            category=f"Target Tracking - {meta['brand']}",
            captured_at=captured_at,
            rank=rank,  # BSR rank, -1 if not in Best Sellers
            product_id=asin,
            title=title or meta["name"],  # Fallback to metadata if scraping fails
            product_url=url,
            price=price,
            rating=rating,
            review_count=review_count,
            image_url=image_url,
            raw={"brand": meta["brand"], "product_name": meta["name"]},
        )
    
    def fetch(self, url: str) -> List[ProductItem]:
        """
        Scrape all products in TARGET_PRODUCTS list.
        
        Args:
            url: Not used (maintained for Source interface compatibility)
        
        Returns:
            List of ProductItem objects for all successfully scraped products
        
        Notes:
            - Continues scraping even if individual products fail
            - Prints progress for each product (success/failure)
            - Applies enhanced rate limiting (1.5x base delay) between requests
            - Returns partial results on errors (fail-safe design)
        
        Output Format:
            ✓ Laneige      | Water Sleeping Mask      | Rank: 123  | $24.99
            ✗ B07KNTK3QG (Laneige): Connection timeout
        """
        items = []
        
        for asin, meta in self.TARGET_PRODUCTS.items():
            try:
                item = self.fetch_asin(asin)
                items.append(item)
                print(f"✓ {meta['brand']:12s} | {meta['name']:25s} | Rank: {item.rank:4d} | ${item.price:.2f}")
            except Exception as e:
                print(f"✗ {asin} ({meta['brand']}): {e}")
            
            # Enhanced rate limiting for product page scraping
            # Product pages are heavier than list pages
            time.sleep(settings.request_sleep_sec * 1.5)
        
        return items