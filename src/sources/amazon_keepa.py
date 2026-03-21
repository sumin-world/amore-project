"""
ToS-friendly Amazon product tracking via the Keepa API.

Requires KEEPA_API_KEY in .env. Returns price, rank, rating, and review
data without browser scraping.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List

import keepa

from src.sources.base import Source, ProductItem


def _safe_int(x: Any, default: int = -1) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _extract_price_usd(p: Dict[str, Any]) -> float:
    """Best-effort current price from Keepa stats (values may be in cents)."""
    stats = p.get("stats") or {}

    cur = stats.get("current")
    if isinstance(cur, list) and cur and cur[0] is not None:
        val = _safe_float(cur[0])
        return val / 100.0 if val > 1000 else val

    bb = stats.get("buyBoxPrice")
    if bb is not None:
        val = _safe_float(bb)
        return val / 100.0 if val > 1000 else val

    return 0.0


def _extract_rating(p: Dict[str, Any]) -> float:
    stats = p.get("stats") or {}
    for key in ("rating", "avgRating"):
        if stats.get(key) is not None:
            return _safe_float(stats[key])
    return 0.0


def _extract_reviews(p: Dict[str, Any]) -> int:
    stats = p.get("stats") or {}
    for key in ("reviewCount", "reviewsCount", "totalReviews"):
        if stats.get(key) is not None:
            return _safe_int(stats[key], 0)
    return 0


def _extract_bsr(p: Dict[str, Any]) -> int:
    """Extract latest Best Sellers Rank from salesRanks history or stats."""
    sales_ranks = p.get("salesRanks")
    if isinstance(sales_ranks, dict) and sales_ranks:
        first_cat = next(iter(sales_ranks.values()))
        if isinstance(first_cat, list) and len(first_cat) >= 2:
            return _safe_int(first_cat[-1])

    stats = p.get("stats") or {}
    for key in ("salesRank", "currentSalesRank"):
        if stats.get(key) is not None:
            return _safe_int(stats[key])

    return -1


class AmazonKeepa(Source):
    """Curated ASIN tracking via Keepa API."""

    TARGET_PRODUCTS: Dict[str, Dict[str, str]] = {
        "B07KNTK3QG": {"brand": "Laneige",     "name": "Water Sleeping Mask"},
        "B00LUSHW18": {"brand": "Laneige",     "name": "Lip Sleeping Mask"},
        "B084GYN2K4": {"brand": "Laneige",     "name": "Cream Skin Refiner"},
        "B00PBX3L7K": {"brand": "COSRX",       "name": "Snail Mucin"},
        "B016NRXO06": {"brand": "COSRX",       "name": "Low pH Cleanser"},
        "B07YZ8MJQY": {"brand": "Innisfree",   "name": "Green Tea Serum"},
        "B01N5SMQM3": {"brand": "Etude House", "name": "SoonJung Toner"},
    }

    def fetch(self, url: str) -> List[ProductItem]:
        api_key = os.getenv("KEEPA_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("KEEPA_API_KEY is required in .env")

        k = keepa.Keepa(api_key)
        captured_at = datetime.utcnow()
        asins = list(self.TARGET_PRODUCTS.keys())

        try:
            products = k.query(asins, domain="US", stats=180, wait=True)
        except RuntimeError as e:
            if "REQUEST_REJECTED" in str(e):
                print("[KEEPA] Request rejected — check API key / tokens. Skipping.")
                return []
            raise

        items: List[ProductItem] = []
        for p in products:
            asin = (p.get("asin") or "").strip()
            meta = self.TARGET_PRODUCTS.get(
                asin, {"brand": "Unknown", "name": "Unknown"}
            )
            title = (p.get("title") or "").strip() or meta["name"]

            img = ""
            csv = p.get("imagesCSV")
            if isinstance(csv, str) and csv:
                first = csv.split(",")[0].strip()
                if first:
                    img = f"https://images-na.ssl-images-amazon.com/images/I/{first}"

            it = ProductItem(
                source="amazon_keepa",
                market="US",
                category=f"Target Tracking - {meta['brand']}",
                captured_at=captured_at,
                rank=_extract_bsr(p),
                product_id=asin,
                title=title,
                product_url=f"https://www.amazon.com/dp/{asin}" if asin else "",
                price=_extract_price_usd(p),
                rating=_extract_rating(p),
                review_count=_extract_reviews(p),
                image_url=img,
                raw={"brand": meta["brand"], "name": meta["name"], "keepa": True},
            )
            print(
                f"  ✓ {meta['brand']:<11} | {meta['name']:<22} "
                f"| Rank: {it.rank:>6} | ${it.price:.2f}"
            )
            items.append(it)

        return items
