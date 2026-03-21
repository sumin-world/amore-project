"""
Change detection: fetch consecutive snapshot pairs and score ranking drivers.

pHash threshold rationale (64-bit perceptual hash):
    0-5 bits   identical (compression artifacts)
    6-10 bits  very similar (minor edits)
    11-20 bits noticeable differences
    >20 bits   significantly different images
We use >10 bits as the meaningful-change threshold.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session

from src.models import ProductSnapshot
from src.pipeline.why import compute_image_diff_score

logger = logging.getLogger(__name__)


def get_recent_pair(
    db: Session,
    source: str,
    market: str,
    category: str,
    product_id: str,
    max_gap_hours: int = 48,
):
    """Return (previous, current) snapshots or (None, None) if < 2 exist."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_gap_hours)

    rows = (
        db.execute(
            select(ProductSnapshot)
            .where(
                and_(
                    ProductSnapshot.source == source,
                    ProductSnapshot.market == market,
                    ProductSnapshot.category == category,
                    ProductSnapshot.product_id == product_id,
                    ProductSnapshot.captured_at >= cutoff,
                )
            )
            .order_by(desc(ProductSnapshot.captured_at))
            .limit(2)
        )
        .scalars()
        .all()
    )

    if len(rows) < 2:
        return None, None
    return rows[1], rows[0]


def score_drivers(prev: ProductSnapshot, curr: ProductSnapshot) -> dict:
    """Score all ranking-change drivers between two snapshots."""
    return {
        "rank_delta": curr.rank - prev.rank,
        "price_delta": round(curr.price - prev.price, 2),
        "review_delta": curr.review_count - prev.review_count,
        "rating_delta": round(curr.rating - prev.rating, 2),
        "image_diff": compute_image_diff_score(prev, curr),
    }
