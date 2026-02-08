"""Abstract base class and common data structure for all product data sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any


@dataclass
class ProductItem:
    """Standardized product observation returned by every source implementation."""

    source: str            # e.g. "amazon_bestsellers", "amazon_keepa"
    market: str            # e.g. "US"
    category: str          # e.g. "Amazon Best Sellers (Beauty)"
    captured_at: datetime  # UTC timestamp of collection
    rank: int              # 1-based position; -1 if unavailable
    product_id: str        # ASIN for Amazon
    title: str
    product_url: str
    price: float
    rating: float
    review_count: int
    image_url: str
    raw: Dict[str, Any]    # source-specific metadata


class Source(ABC):
    """All scrapers inherit from this and implement fetch()."""

    @abstractmethod
    def fetch(self, url: str) -> List[ProductItem]:
        raise NotImplementedError
