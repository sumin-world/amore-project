"""Tests for SQL analysis queries and statistical functions."""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from datetime import datetime, timezone, timedelta

# Ensure DATABASE_URL is set before any src imports
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from src.models import Base, ProductSnapshot
from scripts.sql_analysis import (
    QUERIES,
    pearson_correlation,
    z_scores,
    coefficient_of_variation,
)


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite database with sample data."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    session = Session()

    now = datetime.now(timezone.utc)
    snapshots = [
        ProductSnapshot(
            source="test", market="US", category="Skincare - BrandA",
            captured_at=now - timedelta(hours=2),
            rank=3, product_id="PROD-001", title="Moisturizer A",
            product_url="", price=24.99, rating=4.5, review_count=1200,
        ),
        ProductSnapshot(
            source="test", market="US", category="Skincare - BrandA",
            captured_at=now,
            rank=8, product_id="PROD-001", title="Moisturizer A",
            product_url="", price=19.99, rating=4.4, review_count=1250,
        ),
        ProductSnapshot(
            source="test", market="US", category="Skincare - BrandB",
            captured_at=now - timedelta(hours=2),
            rank=5, product_id="PROD-002", title="Serum B",
            product_url="", price=32.00, rating=4.7, review_count=800,
        ),
        ProductSnapshot(
            source="test", market="US", category="Skincare - BrandB",
            captured_at=now,
            rank=2, product_id="PROD-002", title="Serum B",
            product_url="", price=28.00, rating=4.8, review_count=900,
        ),
    ]
    session.add_all(snapshots)
    session.commit()
    session.close()

    yield eng


class TestSQLQueries:
    """Verify all analysis queries execute without errors."""

    @pytest.mark.parametrize("query_name", list(QUERIES.keys()))
    def test_query_executes(self, db_engine, query_name):
        with db_engine.connect() as conn:
            result = conn.execute(text(QUERIES[query_name]))
            rows = result.fetchall()
            assert isinstance(rows, list)

    def test_price_sensitivity_returns_data(self, db_engine):
        with db_engine.connect() as conn:
            result = conn.execute(text(QUERIES["Price Sensitivity Analysis"]))
            rows = result.fetchall()
            assert len(rows) > 0
            product_ids = [row[0] for row in rows]
            assert "PROD-001" in product_ids

    def test_review_velocity_returns_data(self, db_engine):
        with db_engine.connect() as conn:
            result = conn.execute(text(QUERIES["Review Velocity Leaders"]))
            rows = result.fetchall()
            assert len(rows) > 0

    def test_competitive_gap_returns_brands(self, db_engine):
        with db_engine.connect() as conn:
            result = conn.execute(text(QUERIES["Competitive Gap Analysis"]))
            rows = result.fetchall()
            categories = [row[0] for row in rows]
            assert "Skincare - BrandA" in categories
            assert "Skincare - BrandB" in categories

    def test_anomaly_detection_flags_rank_spike(self, db_engine):
        with db_engine.connect() as conn:
            result = conn.execute(text(QUERIES["Cross-Metric Anomaly Detection"]))
            rows = result.fetchall()
            assert len(rows) > 0
            anomaly_types = [row[-1] for row in rows]
            assert any(t in ("RANK-SPIKE", "MULTI-SIGNAL") for t in anomaly_types)


class TestPearsonCorrelation:
    def test_perfect_positive(self):
        r = pearson_correlation([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert r == 1.0

    def test_perfect_negative(self):
        r = pearson_correlation([1, 2, 3, 4, 5], [10, 8, 6, 4, 2])
        assert r == -1.0

    def test_no_correlation(self):
        r = pearson_correlation([1, 2, 3, 4, 5], [3, 3, 3, 3, 3])
        assert r == 0.0

    def test_insufficient_data(self):
        r = pearson_correlation([1, 2], [3, 4])
        assert r == 0.0

    def test_mismatched_lengths(self):
        r = pearson_correlation([1, 2, 3], [4, 5])
        assert r == 0.0

    def test_moderate_correlation(self):
        r = pearson_correlation([1, 2, 3, 4, 5], [1, 3, 2, 5, 4])
        assert 0.5 < r < 1.0


class TestZScores:
    def test_basic(self):
        zs = z_scores([10, 10, 10, 10, 10, 10, 10, 50])
        assert len(zs) == 8
        # The outlier (50) should have the highest z-score with n=8
        assert zs[-1] > 2.0
        # The normal values should be negative
        assert all(z < 0 for z in zs[:-1])

    def test_uniform_values(self):
        zs = z_scores([5.0, 5.0, 5.0])
        assert all(z == 0.0 for z in zs)

    def test_single_value(self):
        zs = z_scores([42.0])
        assert zs == [0.0]

    def test_empty(self):
        zs = z_scores([])
        assert zs == []

    def test_two_values(self):
        zs = z_scores([0.0, 10.0])
        assert len(zs) == 2
        # With n=2, z-scores should be symmetric
        assert abs(zs[0] + zs[1]) < 0.001


class TestCoefficientOfVariation:
    def test_stable_rankings(self):
        cv = coefficient_of_variation([5.0, 5.0, 5.0, 5.0])
        assert cv == 0.0

    def test_volatile_rankings(self):
        cv = coefficient_of_variation([1.0, 10.0, 1.0, 10.0])
        assert cv > 0.5

    def test_moderate_variation(self):
        cv = coefficient_of_variation([3.0, 4.0, 5.0, 6.0, 7.0])
        assert 0.1 < cv < 0.5

    def test_insufficient_data(self):
        cv = coefficient_of_variation([5.0])
        assert cv == 0.0

    def test_empty(self):
        cv = coefficient_of_variation([])
        assert cv == 0.0
