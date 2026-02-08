"""ORM models for product snapshots and analysis reports."""

from datetime import datetime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, DateTime, Text, Index, UniqueConstraint


class Base(DeclarativeBase):
    pass


class ProductSnapshot(Base):
    """
    Time-series record of a product at a single point in time.

    The composite index (source, market, category, product_id, captured_at)
    covers the primary query pattern: fetch the latest N snapshots for a product.
    """

    __tablename__ = "product_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    market: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(128), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    rank: Mapped[int] = mapped_column(Integer, index=True)          # BSR position; -1 = unavailable
    product_id: Mapped[str] = mapped_column(String(128), index=True) # ASIN for Amazon
    title: Mapped[str] = mapped_column(String(512))
    product_url: Mapped[str] = mapped_column(Text)

    price: Mapped[float] = mapped_column(Float, default=0.0)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    image_url: Mapped[str] = mapped_column(Text, default="")
    image_phash: Mapped[str] = mapped_column(String(32), default="")  # 64-bit pHash hex
    raw_json: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        Index("ix_snap_key", "source", "market", "category", "product_id", "captured_at"),
    )


class WhyReport(Base):
    """
    AI or rule-based analysis of a ranking change over a time window.

    Unique constraint prevents duplicate reports for the same product + window.
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
            "source", "market", "category", "product_id",
            "window_start", "window_end",
            name="uq_report_key",
        ),
    )
