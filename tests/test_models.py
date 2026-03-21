"""Tests for ORM models and database schema."""

from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.models import Base, ProductSnapshot, WhyReport


def test_create_all_tables():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "product_snapshots" in tables
    assert "why_reports" in tables


def test_snapshot_composite_index():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    indexes = inspector.get_indexes("product_snapshots")
    index_names = [idx["name"] for idx in indexes]
    assert "ix_snap_key" in index_names


def test_why_report_unique_constraint():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    report = WhyReport(
        source="test",
        market="US",
        category="beauty",
        product_id="B0TEST",
        window_start=datetime(2025, 1, 1),
        window_end=datetime(2025, 1, 2),
        summary="test report",
        evidence_json="{}",
    )
    session.add(report)
    session.commit()

    # Duplicate should raise IntegrityError
    import sqlalchemy.exc
    dup = WhyReport(
        source="test",
        market="US",
        category="beauty",
        product_id="B0TEST",
        window_start=datetime(2025, 1, 1),
        window_end=datetime(2025, 1, 2),
        summary="duplicate",
        evidence_json="{}",
    )
    session.add(dup)
    try:
        session.commit()
        assert False, "Expected IntegrityError"
    except sqlalchemy.exc.IntegrityError:
        session.rollback()

    session.close()


def test_snapshot_roundtrip():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    snap = ProductSnapshot(
        source="test",
        market="US",
        category="beauty",
        product_id="B0123",
        title="Sample Product",
        product_url="https://example.com",
        rank=5,
        price=29.99,
        rating=4.3,
        review_count=500,
        captured_at=datetime.now(timezone.utc),
    )
    session.add(snap)
    session.commit()

    loaded = session.query(ProductSnapshot).first()
    assert loaded.rank == 5
    assert loaded.price == 29.99
    assert loaded.product_id == "B0123"
    session.close()
