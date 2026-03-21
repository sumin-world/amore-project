"""Tests for the change detection and driver scoring module."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, ProductSnapshot
from src.pipeline.detector import get_recent_pair, score_drivers
from src.pipeline.why import compute_image_diff_score


@pytest.fixture
def db():
    """In-memory SQLite database with tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_snapshot(
    rank=1,
    price=25.00,
    rating=4.5,
    review_count=1000,
    product_id="B0TEST",
    image_phash="",
    minutes_ago=0,
) -> ProductSnapshot:
    return ProductSnapshot(
        source="test",
        market="US",
        category="beauty",
        product_id=product_id,
        title="Test Product",
        product_url="https://example.com/test",
        rank=rank,
        price=price,
        rating=rating,
        review_count=review_count,
        image_url="",
        image_phash=image_phash,
        raw_json="{}",
        captured_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )


class TestScoreDrivers:
    def test_rank_delta(self):
        prev = _make_snapshot(rank=3, minutes_ago=60)
        curr = _make_snapshot(rank=9, minutes_ago=0)
        result = score_drivers(prev, curr)
        assert result["rank_delta"] == 6

    def test_price_delta(self):
        prev = _make_snapshot(price=25.00, minutes_ago=60)
        curr = _make_snapshot(price=22.50, minutes_ago=0)
        result = score_drivers(prev, curr)
        assert result["price_delta"] == -2.50

    def test_review_delta(self):
        prev = _make_snapshot(review_count=1000, minutes_ago=60)
        curr = _make_snapshot(review_count=1150, minutes_ago=0)
        result = score_drivers(prev, curr)
        assert result["review_delta"] == 150

    def test_rating_delta(self):
        prev = _make_snapshot(rating=4.5, minutes_ago=60)
        curr = _make_snapshot(rating=4.3, minutes_ago=0)
        result = score_drivers(prev, curr)
        assert result["rating_delta"] == -0.2

    def test_no_change(self):
        prev = _make_snapshot(minutes_ago=60)
        curr = _make_snapshot(minutes_ago=0)
        result = score_drivers(prev, curr)
        assert result["rank_delta"] == 0
        assert result["price_delta"] == 0.0
        assert result["review_delta"] == 0
        assert result["rating_delta"] == 0.0


class TestImageDiffScore:
    def test_identical_phash(self):
        prev = _make_snapshot(image_phash="abcdef0123456789")
        curr = _make_snapshot(image_phash="abcdef0123456789")
        result = compute_image_diff_score(prev, curr)
        assert result["changed"] is False
        assert result["distance"] == 0

    def test_different_phash_above_threshold(self):
        # Hashes with many differing bits
        prev = _make_snapshot(image_phash="0000000000000000")
        curr = _make_snapshot(image_phash="ffffffffffffffff")
        result = compute_image_diff_score(prev, curr)
        assert result["changed"] is True
        assert result["distance"] > 10

    def test_missing_phash(self):
        prev = _make_snapshot(image_phash="")
        curr = _make_snapshot(image_phash="abcdef0123456789")
        result = compute_image_diff_score(prev, curr)
        assert result["changed"] is False

    def test_both_missing(self):
        prev = _make_snapshot(image_phash="")
        curr = _make_snapshot(image_phash="")
        result = compute_image_diff_score(prev, curr)
        assert result["changed"] is False
        assert result["distance"] == 0


class TestGetRecentPair:
    def test_returns_pair(self, db):
        s1 = _make_snapshot(rank=3, minutes_ago=60)
        s2 = _make_snapshot(rank=5, minutes_ago=0)
        db.add_all([s1, s2])
        db.commit()
        prev, curr = get_recent_pair(db, "test", "US", "beauty", "B0TEST")
        assert prev is not None
        assert curr is not None
        assert prev.rank == 3
        assert curr.rank == 5

    def test_returns_none_if_single(self, db):
        s1 = _make_snapshot(rank=3)
        db.add(s1)
        db.commit()
        prev, curr = get_recent_pair(db, "test", "US", "beauty", "B0TEST")
        assert prev is None
        assert curr is None

    def test_returns_none_if_empty(self, db):
        prev, curr = get_recent_pair(db, "test", "US", "beauty", "B0NONE")
        assert prev is None
        assert curr is None
