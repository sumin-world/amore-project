"""
Database Models for Product Ranking Analysis

This module defines the SQLAlchemy ORM models for storing product snapshots
and analysis reports. The schema is optimized for time-series analysis and
efficient querying of ranking trends.

Database Schema Design Philosophy:
    - Time-series optimized: Frequent writes, range queries
    - Composite indexes for multi-field lookups
    - Normalized structure with clear field purposes
    - Unicode support for international product names

Storage Strategy:
    - SQLite for MVP (simple deployment, no server needed)
    - Schema prepared for PostgreSQL migration (uses standard SQL types)
    - Indexes tuned for common query patterns

TODO - Future Enhancements:
    - Add partitioning strategy for large-scale deployments
    - Implement archival policy for old snapshots (>90 days)
    - Add materialized views for common aggregations
    - Consider TimescaleDB for time-series optimization
    - Add database connection pooling configuration
"""
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, DateTime, Text, Index, UniqueConstraint
from datetime import datetime

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass

class ProductSnapshot(Base):
    """
    Time-series storage for product ranking snapshots.
    
    Each row represents a single observation of a product at a specific point in time.
    Enables trend analysis, change detection, and competitive benchmarking.
    
    Field Descriptions:
        id: Primary key, auto-increment integer
        
        source: Data source identifier (e.g., "amazon_bestsellers", "amazon_product")
            - Used to separate different data collection methods
            - Indexed for source-specific queries
        
        market: Geographic market code (e.g., "US", "UK", "JP")
            - Enables multi-market expansion
            - Indexed for market-specific analysis
        
        category: Product category or tracking group
            - Examples: "Amazon Best Sellers (Beauty)", "Target Tracking - Laneige"
            - Allows category-level aggregation
            - Indexed for category performance reports
        
        captured_at: Timestamp of data collection (UTC)
            - Primary timestamp for time-series analysis
            - Used as baseline for all temporal calculations
            - Indexed for chronological queries and window functions
            - CRITICAL: Always use UTC to avoid timezone issues
        
        rank: Product ranking position
            - Lower number = better position (1 is best)
            - -1 indicates not ranked (for amazon_product when no BSR)
            - Indexed for ranking-based filters and sorting
        
        product_id: Unique product identifier (ASIN for Amazon)
            - Primary key for product tracking across snapshots
            - Indexed for product-specific queries
            - Max 128 chars to support various ID formats
        
        title: Product name/title
            - Truncated to 512 chars (database constraint)
            - Used for search and display
            - May contain Unicode characters
        
        product_url: Direct link to product page
            - Stored as TEXT for unlimited length
            - Used for navigation and verification
        
        price: Current listing price in USD
            - Float for decimal precision
            - 0.0 indicates unavailable or not found
            - Used for pricing trend analysis
        
        rating: Average customer rating (0-5 stars)
            - Float for decimal precision
            - 0.0 indicates no rating or not available
            - Used for quality trend analysis
        
        review_count: Total number of customer reviews
            - Integer count
            - 0 indicates no reviews or not available
            - Key metric for popularity and credibility
        
        image_url: Product thumbnail/main image URL
            - Stored as TEXT for unlimited length
            - Used for visual tracking
            - May be empty if image not available
        
        image_phash: Perceptual hash of product image (hex string)
            - 64-bit pHash in hexadecimal format (16 chars)
            - Enables visual change detection
            - Empty string if hash not computed
            - See detector.py for threshold explanation
        
        raw_json: Additional metadata in JSON format
            - Flexible storage for source-specific data
            - UTF-8 encoded (ensure_ascii=False)
            - Used for debugging and future feature extraction
    
    Indexes:
        ix_snap_key: Composite index (source, market, category, product_id, captured_at)
            - Optimizes the most common query pattern: fetch recent snapshots for a product
            - Enables efficient time-series queries
            - Critical for get_recent_pair() performance in detector.py
    
    Query Optimization Notes:
        - Composite index covers product identification + time ordering
        - Individual field indexes support filtering and aggregation
        - Index selectivity: source > market > category > product_id > captured_at
        - Consider adding index on (captured_at DESC) for dashboard queries
    
    TODO:
        - Add check constraint: rank >= -1 (validate rank values)
        - Add check constraint: price >= 0.0 (no negative prices)
        - Add check constraint: rating >= 0.0 AND rating <= 5.0
        - Consider adding updated_at timestamp for data freshness tracking
        - Add foreign key to products master table (when implementing normalization)
    """
    __tablename__ = "product_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    market: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(128), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    rank: Mapped[int] = mapped_column(Integer, index=True)
    product_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512))
    product_url: Mapped[str] = mapped_column(Text)

    price: Mapped[float] = mapped_column(Float, default=0.0)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    image_url: Mapped[str] = mapped_column(Text, default="")
    image_phash: Mapped[str] = mapped_column(String(32), default="")
    raw_json: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        Index("ix_snap_key", "source", "market", "category", "product_id", "captured_at"),
    )

class WhyReport(Base):
    """
    Storage for ranking change analysis reports.
    
    Each row represents an AI or rule-based analysis of ranking changes
    for a specific product over a time window. Linked to ProductSnapshot
    records via product identifiers.
    
    Field Descriptions:
        id: Primary key, auto-increment integer
        
        created_at: Report generation timestamp (UTC)
            - Tracks when analysis was performed
            - Indexed for sorting recent reports
            - Different from window_start/window_end which are snapshot times
        
        source: Data source identifier (matches ProductSnapshot.source)
            - Enables source-specific report queries
            - Indexed for filtering
        
        market: Market code (matches ProductSnapshot.market)
            - Enables market-specific analysis
            - Indexed for filtering
        
        category: Product category (matches ProductSnapshot.category)
            - Enables category-level insights
            - Indexed for filtering
        
        product_id: Product identifier (matches ProductSnapshot.product_id)
            - Links report to product snapshots
            - Indexed for product-specific report lookup
        
        window_start: Beginning timestamp of analysis window (UTC)
            - Corresponds to previous snapshot's captured_at
            - Part of unique constraint (prevents duplicate reports)
            - Indexed for time-range queries
        
        window_end: Ending timestamp of analysis window (UTC)
            - Corresponds to current snapshot's captured_at
            - Defines the period of change being analyzed
            - Indexed for time-range queries
        
        summary: Natural language explanation of ranking change
            - Generated by LLM (Groq/Claude) or rule-based fallback
            - TEXT type for unlimited length
            - Primary output displayed in dashboard
            - Format: Korean text, ~150-400 characters
        
        evidence_json: JSON string of scored ranking drivers
            - Contains rank_delta, price_delta, review_delta, rating_delta, image_diff
            - UTF-8 encoded (ensure_ascii=False)
            - Used for programmatic analysis and visualization
            - See detector.score_drivers() for structure
    
    Constraints:
        uq_report_key: Unique constraint on (source, market, category, product_id, window_start, window_end)
            - Prevents duplicate reports for same time window
            - Enables upsert logic in why.upsert_report()
            - All fields required for uniqueness (no partial matches)
            - Justification: Multiple reports for same window would be redundant and confusing
    
    Query Patterns:
        - Get latest reports: ORDER BY created_at DESC
        - Get product reports: WHERE product_id = ? ORDER BY window_start DESC
        - Get reports in time range: WHERE window_start >= ? AND window_end <= ?
        - Upsert check: WHERE [all unique constraint fields] = ?
    
    TODO:
        - Add report_type field ("llm_groq", "llm_claude", "rule_based") for analytics
        - Add confidence_score for LLM-generated reports
        - Add action_items field for structured recommendations
        - Consider adding vector embeddings for semantic search
        - Add foreign key to product_snapshots (when implementing referential integrity)
    """
    __tablename__ = "why_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    source: Mapped[str] = mapped_column(String(64), index=True)
    market: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(128), index=True)
    product_id: Mapped[str] = mapped_column(String(128), index=True)

    window_start: Mapped[datetime] = mapped_column(DateTime, index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime, index=True)

    summary: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        UniqueConstraint(
            "source", "market", "category", "product_id", "window_start", "window_end",
            name="uq_report_key"
        ),
    )
