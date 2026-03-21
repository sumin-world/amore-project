"""Tests for the Why Report generation module (rule-based fallback)."""

from datetime import datetime, timedelta, timezone

from src.models import ProductSnapshot
from src.pipeline.why import _rule_fallback, build_why_report


def _make_snapshot(
    rank=1,
    price=25.00,
    rating=4.5,
    review_count=1000,
    minutes_ago=0,
) -> ProductSnapshot:
    return ProductSnapshot(
        source="test",
        market="US",
        category="beauty",
        product_id="B0TEST",
        title="Test Product",
        product_url="https://example.com",
        rank=rank,
        price=price,
        rating=rating,
        review_count=review_count,
        image_url="",
        image_phash="",
        raw_json="{}",
        captured_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )


class TestRuleFallback:
    def test_rank_increase_with_price_hike(self):
        prev = _make_snapshot(rank=3, price=20.00, minutes_ago=60)
        curr = _make_snapshot(rank=9, price=25.00, minutes_ago=0)
        evidence = {"image_diff": {"changed": False}}
        result = _rule_fallback(prev, curr, evidence)
        assert "Rank 3→9" in result
        assert "price hike" in result
        assert "urgent action" in result  # rank delta > 3

    def test_rank_stable(self):
        prev = _make_snapshot(rank=5, minutes_ago=60)
        curr = _make_snapshot(rank=5, minutes_ago=0)
        evidence = {"image_diff": {"changed": False}}
        result = _rule_fallback(prev, curr, evidence)
        assert "stable" in result

    def test_review_surge(self):
        prev = _make_snapshot(rank=5, review_count=500, minutes_ago=60)
        curr = _make_snapshot(rank=3, review_count=700, minutes_ago=0)
        evidence = {"image_diff": {"changed": False}}
        result = _rule_fallback(prev, curr, evidence)
        assert "review surge" in result

    def test_review_growth(self):
        prev = _make_snapshot(rank=5, review_count=500, minutes_ago=60)
        curr = _make_snapshot(rank=4, review_count=550, minutes_ago=0)
        evidence = {"image_diff": {"changed": False}}
        result = _rule_fallback(prev, curr, evidence)
        assert "review growth" in result

    def test_rating_change(self):
        prev = _make_snapshot(rating=4.5, minutes_ago=60)
        curr = _make_snapshot(rating=4.2, minutes_ago=0)
        evidence = {"image_diff": {"changed": False}}
        result = _rule_fallback(prev, curr, evidence)
        assert "rating down" in result

    def test_thumbnail_changed(self):
        prev = _make_snapshot(minutes_ago=60)
        curr = _make_snapshot(minutes_ago=0)
        evidence = {"image_diff": {"changed": True}}
        result = _rule_fallback(prev, curr, evidence)
        assert "thumbnail changed" in result

    def test_no_drivers(self):
        prev = _make_snapshot(minutes_ago=60)
        curr = _make_snapshot(minutes_ago=0)
        evidence = {"image_diff": {"changed": False}}
        result = _rule_fallback(prev, curr, evidence)
        assert "no significant drivers" in result


class TestBuildWhyReport:
    def test_returns_string_without_api_keys(self):
        """Without LLM keys, should fall back to rule-based and still return a string."""
        import os
        os.environ["USE_GROQ"] = "false"
        os.environ["USE_CLAUDE"] = "false"
        prev = _make_snapshot(rank=3, price=20.00, minutes_ago=60)
        curr = _make_snapshot(rank=8, price=25.00, minutes_ago=0)
        evidence = {"image_diff": {"changed": False}}
        result = build_why_report(prev, curr, evidence)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Rank 3→8" in result
