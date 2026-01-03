"""
Amazon Tracking via Keepa API (ToS-friendly alternative to scraping)

Env:
- KEEPA_API_KEY (required)
Notes:
- This avoids Playwright scraping + CAPTCHA issues.
- Keepa returns price/rank history; we extract current-ish values best-effort.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import List, Dict, Any

import keepa

from src.sources.base import Source, ProductItem


def _get_env(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return (v or default).strip()


def _safe_int(x, default=-1) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _extract_current_price_usd(p: Dict[str, Any]) -> float:
    """
    Keepa price is often in cents *or* in Keepa's internal units (cents).
    We do best-effort extraction from 'stats' if present.
    """
    stats = p.get("stats") or {}
    # Keepa 'current' is an array; index meanings vary by config.
    # Commonly: current[0] = Amazon price (in cents), current[1] = Marketplace new, etc.
    cur = stats.get("current")
    if isinstance(cur, list) and len(cur) > 0 and cur[0] is not None:
        val = _safe_float(cur[0], 0.0)
        # many outputs are cents -> convert
        if val > 1000:
            return val / 100.0
        # if already dollars-ish
        return val

    # Fallback: try 'buyBoxPrice' in stats (often cents)
    bb = stats.get("buyBoxPrice")
    if bb is not None:
        val = _safe_float(bb, 0.0)
        if val > 1000:
            return val / 100.0
        return val

    return 0.0


def _extract_current_rating(p: Dict[str, Any]) -> float:
    stats = p.get("stats") or {}
    # Keepa sometimes stores rating in 'rating' or 'avgRating'
    for k in ("rating", "avgRating"):
        if k in stats and stats[k] is not None:
            return _safe_float(stats[k], 0.0)
    return 0.0


def _extract_review_count(p: Dict[str, Any]) -> int:
    stats = p.get("stats") or {}
    for k in ("reviewCount", "reviewsCount", "totalReviews"):
        if k in stats and stats[k] is not None:
            return _safe_int(stats[k], 0)
    return 0


def _extract_bsr_rank(p: Dict[str, Any]) -> int:
    """
    Best-effort BSR: Keepa provides salesRanks history by category.
    We'll try to find the latest rank value if present.
    """
    sales_ranks = p.get("salesRanks")
    if isinstance(sales_ranks, dict) and sales_ranks:
        # pick first category ranks
        first_cat = next(iter(sales_ranks.values()))
        # format: [ts0, rank0, ts1, rank1, ...] or similar
        if isinstance(first_cat, list) and len(first_cat) >= 2:
            # last rank is typically at the end
            last = first_cat[-1]
            return _safe_int(last, -1)

    # fallback: some payloads have stats.salesRank
    stats = p.get("stats") or {}
    for k in ("salesRank", "currentSalesRank"):
        if k in stats and stats[k] is not None:
            return _safe_int(stats[k], -1)

    return -1


class AmazonKeepa(Source):
    """
    Curated ASIN tracking via Keepa API.
    """
    TARGET_PRODUCTS: Dict[str, Dict[str, str]] = {
        # Laneige
        "B07KNTK3QG": {"brand": "Laneige", "name": "Water Sleeping Mask"},
        "B00LUSHW18": {"brand": "Laneige", "name": "Lip Sleeping Mask"},
        "B084GYN2K4": {"brand": "Laneige", "name": "Cream Skin Refiner"},

        # Competitors
        "B00PBX3L7K": {"brand": "COSRX", "name": "Snail Mucin"},
        "B016NRXO06": {"brand": "COSRX", "name": "Low pH Cleanser"},
        "B07YZ8MJQY": {"brand": "Innisfree", "name": "Green Tea Serum"},
        "B01N5SMQM3": {"brand": "Etude House", "name": "SoonJung Toner"},
    }

    def fetch(self, url: str) -> List[ProductItem]:
        api_key = _get_env("KEEPA_API_KEY")
        if not api_key:
            raise RuntimeError("KEEPA_API_KEY is required in .env")

        k = keepa.Keepa(api_key)
        items: List[ProductItem] = []
        captured_at = datetime.utcnow()

        asins = list(self.TARGET_PRODUCTS.keys())
        # Keepa domain="US" is Amazon.com (US)
        try:
            products = k.query(asins, domain="US", stats=180, wait=True)
        except RuntimeError as e:
            msg = str(e)
            if "REQUEST_REJECTED" in msg:
                print("[KEEPA] REQUEST_REJECTED: check KEEPA_API_KEY validity / remaining tokens / IP restrictions. Skipping keepa fetch.")
                return []
            raise


        for p in products:
            asin = (p.get("asin") or "").strip()
            meta = self.TARGET_PRODUCTS.get(asin, {"brand": "Unknown", "name": "Unknown"})
            title = (p.get("title") or "").strip() or meta["name"]
            img = ""
            # Keepa provides imagesCSV sometimes
            images_csv = p.get("imagesCSV")
            if isinstance(images_csv, str) and images_csv:
                # imagesCSV: "img1.jpg,img2.jpg,..."
                first = images_csv.split(",")[0].strip()
                if first:
                    img = "https://images-na.ssl-images-amazon.com/images/I/" + first

            rank = _extract_bsr_rank(p)
            price = _extract_current_price_usd(p)
            rating = _extract_current_rating(p)
            review_count = _extract_review_count(p)

            product_url = f"https://www.amazon.com/dp/{asin}" if asin else ""

            it = ProductItem(
                source="amazon_keepa",
                market="US",
                category=f"Target Tracking - {meta['brand']}",
                captured_at=captured_at,
                rank=rank,
                product_id=asin,
                title=title,
                product_url=product_url,
                price=price,
                rating=rating,
                review_count=review_count,
                image_url=img,
                raw={"brand": meta["brand"], "name": meta["name"], "keepa": True},
            )
            print(f"✓ {meta['brand']:<11} | {meta['name']:<22} | Rank: {it.rank:>6} | ${it.price:.2f}")
            items.append(it)

        return items
