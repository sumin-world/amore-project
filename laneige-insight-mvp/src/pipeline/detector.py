"""
변화 감지 모듈
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
    특정 제품의 최근 2개 스냅샷 페어 반환
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
    
    return rows[1], rows[0]  # (이전, 현재)


def score_drivers(prev: ProductSnapshot, curr: ProductSnapshot) -> dict:
    """
    변화 요인 점수화
    - rank_delta
    - price_delta
    - review_delta
    - rating_delta
    - image_diff (이미지 변경 감지)
    """
    evidence = {
        "rank_delta": curr.rank - prev.rank,
        "price_delta": round(curr.price - prev.price, 2),
        "review_delta": curr.review_count - prev.review_count,
        "rating_delta": round(curr.rating - prev.rating, 2),
        "image_diff": compute_image_diff_score(prev, curr),
    }
    
    return evidence