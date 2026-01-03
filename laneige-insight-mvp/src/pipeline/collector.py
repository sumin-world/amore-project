"""
Product Snapshot Collection Pipeline

This module handles the persistence layer for scraped product data,
converting ProductItem objects into database snapshots with optional
image hash computation for visual change detection.

Key Responsibilities:
    - Database transaction management
    - Image hash computation via perceptual hashing (pHash)
    - Data validation and truncation (e.g., title length limits)
    - Robust error handling for image fetching failures

Exception Handling:
    - Image fetch failures: Logged but not raised, sets empty phash
    - Network timeouts: Gracefully handled, continues with next item
    - Invalid image data: Caught and logged, doesn't block snapshot save
    
Design Rationale:
    - Image hashing is optional but enabled by default for change detection
    - Failures in auxiliary operations (image fetch) don't block core function
    - Atomic commits ensure all-or-nothing consistency
"""
import json
from typing import List
from sqlalchemy.orm import Session
from src.models import ProductSnapshot
from src.utils.images import fetch_image_bytes, phash_from_bytes

def save_snapshots(db: Session, items: List, compute_image_hash: bool = True) -> int:
    """
    Save product snapshots to database with optional image hash computation.
    
    Args:
        db: SQLAlchemy database session
        items: List of ProductItem objects from scrapers
        compute_image_hash: Whether to compute perceptual hash for images (default: True)
    
    Returns:
        Integer count of successfully saved snapshots
    
    Process:
        1. For each ProductItem:
           a. Optionally fetch image and compute pHash
           b. Create ProductSnapshot database object
           c. Truncate title to 512 chars (database constraint)
           d. Convert price/rating to float, review_count to int
           e. Serialize raw dict to JSON string
        2. Add all snapshots to session
        3. Commit transaction (atomic operation)
    
    Error Handling:
        - Image fetch failures: Sets img_phash to empty string, continues
        - Exceptions caught per-item to maximize data collection
        - Database errors propagate to caller for transaction control
    
    Notes:
        - Title truncated to 512 chars (matches database schema)
        - Raw JSON stored with ensure_ascii=False for international characters
        - Image pHash enables visual change detection (thumbnail updates)
        - All snapshots committed together (atomic transaction)
    
    TODO:
        - Add retry logic for transient image fetch failures
        - Implement batch commit for very large datasets
        - Add validation for required fields before database insert
    """
    saved = 0
    for it in items:
        img_phash = ""
        if compute_image_hash and it.image_url:
            try:
                # Fetch image bytes from URL
                img_bytes = fetch_image_bytes(it.image_url)
                if img_bytes:
                    # Compute perceptual hash for change detection
                    img_phash = phash_from_bytes(img_bytes)
            except Exception as e:
                # Log failure but continue - image hash is auxiliary data
                # Core snapshot can still be saved without it
                print(f"Warning: Image hash computation failed for {it.product_id}: {e}")
                img_phash = ""

        snap = ProductSnapshot(
            source=it.source,
            market=it.market,
            category=it.category,
            captured_at=it.captured_at,
            rank=it.rank,
            product_id=it.product_id,
            title=it.title[:512],  # Truncate to database limit
            product_url=it.product_url,
            price=float(it.price or 0.0),  # Ensure float type
            rating=float(it.rating or 0.0),
            review_count=int(it.review_count or 0),  # Ensure int type
            image_url=it.image_url or "",
            image_phash=img_phash,
            raw_json=json.dumps(it.raw, ensure_ascii=False),
        )
        db.add(snap)
        saved += 1
    
    # Commit all snapshots atomically
    db.commit()
    return saved
