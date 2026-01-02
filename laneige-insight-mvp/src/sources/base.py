from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any

@dataclass
class ProductItem:
    source: str
    market: str
    category: str
    captured_at: datetime
    rank: int
    product_id: str
    title: str
    product_url: str
    price: float
    rating: float
    review_count: int
    image_url: str
    raw: Dict[str, Any]

class Source(ABC):
    @abstractmethod
    def fetch(self, url: str) -> List[ProductItem]:
        raise NotImplementedError
