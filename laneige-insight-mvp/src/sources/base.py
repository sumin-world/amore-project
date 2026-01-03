"""
Base Classes for Data Source Implementations

This module defines the abstract base class and data structures for all
product data sources (Amazon, future platforms). Ensures consistent interface
across different scrapers.

Design Pattern:
    - Strategy pattern: Source is the abstract strategy
    - ProductItem is the common data structure returned by all sources
    - Enables easy addition of new sources (Rakuten, Shopee, etc.)

TODO - Future Expansion:
    - Add sources for Japanese market (Rakuten, Yahoo Shopping)
    - Add sources for SE Asia (Shopee, Lazada, Tokopedia)
    - Implement source health monitoring and quality scoring
    - Add source-specific configuration management
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any

@dataclass
class ProductItem:
    """
    Standardized product snapshot data structure.
    
    This dataclass represents a single product observation at a specific point in time.
    All data sources must return List[ProductItem] to ensure consistency.
    
    Attributes:
        source: Source identifier (e.g., "amazon_bestsellers", "amazon_product")
            - Used to distinguish data collection methods
            - Enables source-specific analysis
        
        market: Geographic market code (e.g., "US", "UK", "JP")
            - ISO 3166-1 alpha-2 format recommended
            - Enables multi-market tracking and comparison
        
        category: Product category or tracking group
            - Free-form string, source-specific
            - Examples: "Amazon Best Sellers (Beauty)", "Target Tracking - Laneige"
            - Used for grouping and filtering
        
        captured_at: UTC timestamp of data collection
            - Must be UTC for consistency across markets
            - Set at scraping initiation time
        
        rank: Ranking position (1-based, lower is better)
            - -1 indicates not ranked or rank unavailable
            - Varies by source (Best Sellers rank vs search position)
        
        product_id: Unique product identifier
            - ASIN for Amazon (10 alphanumeric characters)
            - Must be unique within source/market/category
        
        title: Product name/title
            - Full product name as displayed on site
            - May contain brand, model, size information
            - Subject to 512-char truncation in database
        
        product_url: Direct link to product page
            - Absolute URL, cleaned of tracking parameters
            - Used for navigation and verification
        
        price: Current listing price
            - Float in local currency (USD for US market)
            - 0.0 if price unavailable or not displayed
        
        rating: Average customer rating
            - Float, typically 0.0-5.0 scale (Amazon)
            - 0.0 if rating unavailable
        
        review_count: Total number of customer reviews
            - Integer count
            - 0 if reviews unavailable
        
        image_url: Product thumbnail/main image URL
            - Full URL to image resource
            - Empty string if image unavailable
            - Used for perceptual hashing and change detection
        
        raw: Additional source-specific metadata
            - Dictionary for flexible storage
            - Examples: {"href": "/dp/...", "brand": "Laneige"}
            - Preserved in database as JSON for debugging
    
    Usage:
        item = ProductItem(
            source="amazon_bestsellers",
            market="US",
            category="Beauty",
            captured_at=datetime.utcnow(),
            rank=5,
            product_id="B07KNTK3QG",
            title="LANEIGE Water Sleeping Mask",
            product_url="https://www.amazon.com/dp/B07KNTK3QG",
            price=24.99,
            rating=4.5,
            review_count=1234,
            image_url="https://...",
            raw={"original_rank": "#5 in Beauty"}
        )
    """
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
    """
    Abstract base class for all product data sources.
    
    All scrapers must inherit from this class and implement the fetch() method.
    Ensures consistent interface for the data collection pipeline.
    
    Interface Contract:
        - fetch() must return List[ProductItem]
        - fetch() should handle errors gracefully (log but don't crash)
        - fetch() should respect rate limits (via settings.request_sleep_sec)
        - fetch() should set captured_at at collection start time
    
    Usage:
        class MyNewSource(Source):
            def fetch(self, url: str) -> List[ProductItem]:
                # Implementation here
                return items
    
    TODO:
        - Add fetch_async() for concurrent scraping
        - Add validate() method for data quality checks
        - Add get_metadata() for source capabilities and limits
    """
    @abstractmethod
    def fetch(self, url: str) -> List[ProductItem]:
        """
        Fetch product data from source.
        
        Args:
            url: Source-specific URL or identifier
                - May be empty for sources with predefined targets
                - Format varies by source implementation
        
        Returns:
            List of ProductItem objects
            - Empty list if no products found (not an error)
            - Partial results acceptable (continue on individual failures)
        
        Raises:
            Should catch and log errors internally
            Only raise for critical failures that prevent all collection
        """
        raise NotImplementedError
