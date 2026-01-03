"""
Change Detection Module

This module identifies ranking changes by comparing consecutive product snapshots
and scoring the drivers of those changes (price, reviews, ratings, images).

Key Concepts:
    - Snapshot Pair: Two consecutive captures of the same product
    - Ranking Drivers: Factors that influence Amazon ranking (price, reviews, etc.)
    - Time Window: Maximum time gap between snapshots for valid comparison

pHash Distance Threshold Explanation:
    - pHash (perceptual hash) creates a 64-bit fingerprint of an image
    - Hamming distance measures bit differences between two pHashes
    - Threshold of 10 bits chosen based on empirical testing:
        * 0-5 bits: Identical or near-identical images (compression artifacts only)
        * 6-10 bits: Very similar images (minor edits, lighting changes)
        * 11-20 bits: Similar images with noticeable differences
        * >20 bits: Significantly different images
    - Our threshold (10 bits) detects meaningful thumbnail changes while
      ignoring compression artifacts and minor variations
    - For 64-bit hash, 10 bits = ~15.6% difference threshold

TODO - Future Enhancements:
    - Add competitor comparison in score_drivers() to measure relative performance
    - Calculate growth rates (delta % vs top 3 competitors)
    - Add market share estimation based on ranking positions
    - Implement seasonality detection for ranking patterns
    - Add anomaly detection for unusual ranking jumps
"""

from datetime import datetime, timedelta
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session
from src.models import ProductSnapshot
from src.pipeline.why import compute_image_diff_score


def get_recent_pair(
    db: Session,
    source: str,
    market: str,
    category: str,
    product_id: str,
    max_gap_hours: int = 48
):
    """
    Retrieve the two most recent snapshots for a specific product.
    
    Args:
        db: Database session
        source: Data source identifier (e.g., "amazon_bestsellers")
        market: Market identifier (e.g., "US")
        category: Product category
        product_id: Unique product identifier (ASIN for Amazon)
        max_gap_hours: Maximum time gap between snapshots (default: 48 hours)
    
    Returns:
        Tuple of (previous_snapshot, current_snapshot) or (None, None) if insufficient data
    
    Notes:
        - Only considers snapshots within max_gap_hours window
        - Returns None if fewer than 2 snapshots found
        - Ordered by captured_at descending (newest first)
        - Used for change detection and trend analysis
    
    Query Optimization:
        - Uses composite index (source, market, category, product_id, captured_at)
        - Limits to 2 rows for efficiency
        - Filters by time window to focus on recent changes
    """
    cutoff = datetime.utcnow() - timedelta(hours=max_gap_hours)
    
    rows = db.execute(
        select(ProductSnapshot)
        .where(and_(
            ProductSnapshot.source == source,
            ProductSnapshot.market == market,
            ProductSnapshot.category == category,
            ProductSnapshot.product_id == product_id,
            ProductSnapshot.captured_at >= cutoff
        ))
        .order_by(desc(ProductSnapshot.captured_at))
        .limit(2)
    ).scalars().all()
    
    if len(rows) < 2:
        return None, None
    
    return rows[1], rows[0]  # (previous, current)


def score_drivers(prev: ProductSnapshot, curr: ProductSnapshot) -> dict:
    """
    Score ranking change drivers by comparing two snapshots.
    
    Args:
        prev: Previous product snapshot
        curr: Current product snapshot
    
    Returns:
        Dictionary containing scored deltas for all ranking drivers:
            - rank_delta: Change in ranking position (negative = improvement)
            - price_delta: Price change in dollars (negative = price decrease)
            - review_delta: Change in review count (positive = growth)
            - rating_delta: Change in rating (positive = improvement)
            - image_diff: Image change detection result (dict with changed/score/distance)
    
    Ranking Driver Analysis:
        - Rank: Lower rank = better position (rank 1 > rank 10)
        - Price: Lower price typically improves ranking
        - Reviews: More reviews signal popularity and credibility
        - Rating: Higher rating improves customer trust
        - Image: Thumbnail changes can indicate product updates or A/B testing
    
    TODO - Competitive Benchmarking:
        - Add comparison with top 3 competitors in same category
        - Calculate relative growth rates (vs market average)
        - Score competitive advantages (better price/rating ratio)
        - Identify market share shifts
        - Example: "Review growth +50 vs competitor avg +20 = 2.5x advantage"
    
    Example Output:
        {
            "rank_delta": 3,  # Dropped from rank 7 to 10
            "price_delta": -2.50,  # Price decreased by $2.50
            "review_delta": 150,  # Gained 150 reviews
            "rating_delta": 0.2,  # Rating improved by 0.2 stars
            "image_diff": {"changed": True, "score": 23.4, "distance": 15}
        }
    """
    evidence = {
        "rank_delta": curr.rank - prev.rank,
        "price_delta": round(curr.price - prev.price, 2),
        "review_delta": curr.review_count - prev.review_count,
        "rating_delta": round(curr.rating - prev.rating, 2),
        "image_diff": compute_image_diff_score(prev, curr),
    }
    
    # TODO: Add competitor comparison
    # evidence["competitor_review_growth"] = compare_review_growth_vs_competitors(...)
    # evidence["price_competitiveness"] = calculate_price_position_vs_top3(...)
    
    return evidence