"""
ToS-friendly Amazon product tracking via the Keepa API.

Requires KEEPA_API_KEY in .env. Returns price, rank, rating, and review
data without browser scraping.

Target products are loaded from config/products.json (configurable).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import keepa

from src.config import load_target_products
from src.sources.base import Source, ProductItem

logger = logging.getLogger(__name__)


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
    """Configurable ASIN tracking via Keepa API."""

    def __init__(self, products: Optional[Dict[str, Dict[str, str]]] = None):
        config_path = os.getenv("PRODUCTS_CONFIG")
        self.target_products = products or load_target_products(config_path)

    def fetch(self, url: str) -> List[ProductItem]:
        api_key = os.getenv("KEEPA_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("KEEPA_API_KEY is required in .env")

        k = keepa.Keepa(api_key)
        captured_at = datetime.now(timezone.utc)
        asins = list(self.target_products.keys())

        try:
            products = k.query(asins, domain="US", stats=180, wait=True)
        except RuntimeError as e:
            if "REQUEST_REJECTED" in str(e):
                logger.error("Keepa request rejected — check API key / tokens")
                return []
            raise

        items: List[ProductItem] = []
        for p in products:
            asin = (p.get("asin") or "").strip()
            meta = self.target_products.get(
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
            logger.info(
                "OK %s | %s | Rank: %d | $%.2f",
                meta["brand"], meta["name"], it.rank, it.price,
            )
            items.append(it)

        return items
