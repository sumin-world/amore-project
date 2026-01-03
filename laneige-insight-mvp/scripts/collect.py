"""
Data Collection Script for Amazon Product Rankings

This script collects product ranking data from various Amazon sources using Playwright
for web scraping. It supports multiple source types including Best Sellers pages,
search results, and direct ASIN tracking.

Usage:
    python scripts/collect.py --source amazon_bestsellers --url <AMAZON_URL>
    python scripts/collect.py --source amazon_product  # Uses predefined ASIN list
    python scripts/collect.py --source amazon_bestsellers --url <URL> --keyword "laneige"

Features:
    - Uses Playwright for robust browser automation and bot detection evasion
    - Configurable random sleep delays to mimic human browsing behavior
    - Computes perceptual image hashes for product thumbnail tracking
    - Supports keyword filtering for targeted product collection
    - Stores snapshots with timestamps for time-series analysis

Dependencies:
    - Playwright: For headless browser automation
    - BeautifulSoup4: For HTML parsing
    - SQLAlchemy: For database operations
"""
import argparse
from src.db import SessionLocal
from src.sources.amazon_bestsellers import AmazonBestSellers
from src.sources.amazon_product import AmazonProduct
from src.pipeline.collector import save_snapshots

SOURCES = {
    "amazon_bestsellers": AmazonBestSellers,
    "amazon_product": AmazonProduct,
}

def main():
    """
    Main collection function that orchestrates the data gathering pipeline.
    
    Workflow:
        1. Parse command-line arguments for source type, URL, and optional keyword filter
        2. Initialize the appropriate source handler (AmazonBestSellers, AmazonProduct, etc.)
        3. Fetch product data from the source
        4. Apply keyword filtering if specified
        5. Save snapshots to database with computed image hashes
    
    Args (via argparse):
        --source: Data source type (amazon_bestsellers, amazon_product)
        --url: Target URL for scraping (optional for amazon_product which uses predefined ASINs)
        --keyword: Optional filter to only save products matching this keyword in title
    
    Returns:
        None. Prints count of saved snapshots to stdout.
    
    Notes:
        - Database connection is automatically closed in finally block
        - Image hashing is enabled by default for change detection
        - Sleep delays between requests are configured via REQUEST_SLEEP_SEC env variable
          to avoid bot detection (mimics human browsing patterns)
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=SOURCES.keys())
    ap.add_argument("--url", default="")  # amazon_product does not require URL
    ap.add_argument("--keyword", default="")
    args = ap.parse_args()
    
    src = SOURCES[args.source]()
    items = src.fetch(args.url)
    
    if args.keyword.strip():
        kw = args.keyword.strip().lower()
        items = [it for it in items if kw in (it.title or "").lower()]
    
    db = SessionLocal()
    try:
        n = save_snapshots(db, items, compute_image_hash=True)
        print(f"\nSaved {n} snapshots successfully")
    finally:
        db.close()

if __name__ == "__main__":
    main()