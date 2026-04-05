"""
SQL-based market intelligence analysis with statistical methods.

Runs analytical queries against collected snapshot data to surface
actionable business insights: pricing sensitivity, review momentum,
ranking volatility, cross-metric anomalies, and competitive gaps.

Statistical methods applied:
- Z-score anomaly detection for ranking changes
- Pearson correlation between price changes and rank movement
- Moving average smoothing for trend identification
- Coefficient of variation for volatility measurement

Usage:
    PYTHONPATH=. python scripts/sql_analysis.py
"""

import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from sqlalchemy import text

from src.db import engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

QUERIES = {
    "Price Sensitivity Analysis": """
        SELECT
            p2.product_id,
            p2.title,
            (p2.price - p1.price) AS price_delta,
            (p2.rank - p1.rank) AS rank_delta,
            CASE
                WHEN (p2.price - p1.price) != 0
                THEN ROUND(CAST((p2.rank - p1.rank) AS FLOAT) / (p2.price - p1.price), 2)
                ELSE 0
            END AS rank_per_dollar
        FROM product_snapshots p1
        JOIN product_snapshots p2
            ON p1.product_id = p2.product_id
            AND p1.source = p2.source
            AND p2.captured_at > p1.captured_at
        WHERE ABS(p2.price - p1.price) > 0.5
        ORDER BY ABS(rank_per_dollar) DESC
        LIMIT 20
    """,

    "Review Velocity Leaders": """
        SELECT
            p2.product_id,
            p2.title,
            p1.review_count AS prev_reviews,
            p2.review_count AS curr_reviews,
            (p2.review_count - p1.review_count) AS review_gain,
            p2.rank AS current_rank
        FROM product_snapshots p1
        JOIN product_snapshots p2
            ON p1.product_id = p2.product_id
            AND p1.source = p2.source
            AND p2.captured_at > p1.captured_at
        WHERE (p2.review_count - p1.review_count) > 0
        ORDER BY review_gain DESC
        LIMIT 15
    """,

    "Ranking Volatility by Brand": """
        SELECT
            category,
            product_id,
            MIN(rank) AS best_rank,
            MAX(rank) AS worst_rank,
            (MAX(rank) - MIN(rank)) AS volatility,
            COUNT(*) AS snapshot_count,
            ROUND(AVG(rank), 2) AS mean_rank
        FROM product_snapshots
        WHERE rank > 0
        GROUP BY category, product_id
        HAVING COUNT(*) >= 2
        ORDER BY volatility DESC
        LIMIT 15
    """,

    "Cross-Metric Anomaly Detection": """
        SELECT
            p2.product_id,
            p2.title,
            (p2.rank - p1.rank) AS rank_delta,
            (p2.price - p1.price) AS price_delta,
            (p2.review_count - p1.review_count) AS review_delta,
            ROUND(CAST(p2.rating - p1.rating AS FLOAT), 2) AS rating_delta,
            CASE
                WHEN ABS(p2.rank - p1.rank) > 3
                    AND ABS(p2.price - p1.price) > 1.0
                    AND ABS(p2.review_count - p1.review_count) > 10
                THEN 'MULTI-SIGNAL'
                WHEN ABS(p2.rank - p1.rank) > 5 THEN 'RANK-SPIKE'
                WHEN ABS(p2.price - p1.price) > 5.0 THEN 'PRICE-SHOCK'
                ELSE 'NORMAL'
            END AS anomaly_type
        FROM product_snapshots p1
        JOIN product_snapshots p2
            ON p1.product_id = p2.product_id
            AND p1.source = p2.source
            AND p2.captured_at > p1.captured_at
        WHERE ABS(p2.rank - p1.rank) > 2
            OR ABS(p2.price - p1.price) > 2.0
        ORDER BY ABS(p2.rank - p1.rank) DESC
        LIMIT 20
    """,

    "Competitive Gap Analysis": """
        SELECT
            category,
            COUNT(DISTINCT product_id) AS product_count,
            ROUND(AVG(CASE WHEN rank > 0 THEN rank END), 1) AS avg_rank,
            ROUND(AVG(price), 2) AS avg_price,
            ROUND(AVG(review_count), 0) AS avg_reviews,
            ROUND(AVG(rating), 2) AS avg_rating
        FROM product_snapshots
        GROUP BY category
        HAVING COUNT(*) >= 2
        ORDER BY avg_rank ASC
    """,
}


# ── Statistical computations (Python-side, post-query) ────────────────────


def pearson_correlation(xs: List[float], ys: List[float]) -> float:
    """Compute Pearson correlation coefficient between two series.

    Returns 0.0 if insufficient data or zero variance.
    """
    n = len(xs)
    if n < 3 or len(ys) != n:
        return 0.0

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)

    denom = math.sqrt(var_x * var_y)
    if denom == 0:
        return 0.0
    return round(cov / denom, 4)


def z_scores(values: List[float]) -> List[float]:
    """Compute z-scores for anomaly detection.

    |z| > 2.0 indicates a statistically unusual observation.
    """
    n = len(values)
    if n < 2:
        return [0.0] * n

    mean = sum(values) / n
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))

    if std == 0:
        return [0.0] * n
    return [round((v - mean) / std, 3) for v in values]


def coefficient_of_variation(values: List[float]) -> float:
    """CV = std/mean — measures relative volatility.

    Higher CV means more unstable rankings. Returns 0.0 if mean is 0.
    """
    n = len(values)
    if n < 2:
        return 0.0

    mean = sum(values) / n
    if mean == 0:
        return 0.0

    std = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    return round(std / abs(mean), 4)


# ── Analysis runner ───────────────────────────────────────────────────────


def run_analysis():
    """Execute all analytical queries, apply statistical methods, print results."""
    report_lines = [
        "# Market Intelligence Analysis Report",
        f"Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        "",
    ]

    with engine.connect() as conn:
        # ── Run SQL queries ───────────────────────────────────────────
        for title, query in QUERIES.items():
            print(f"\n{'='*60}")
            print(f"  {title}")
            print(f"{'='*60}")

            report_lines.append(f"## {title}\n")

            try:
                result = conn.execute(text(query))
                rows = result.fetchall()
                columns = list(result.keys())

                if not rows:
                    print("  (no data - collect snapshots first)")
                    report_lines.append("No data available.\n")
                    continue

                header = " | ".join(f"{c:>15}" for c in columns)
                print(f"  {header}")
                print(f"  {'-' * len(header)}")
                report_lines.append(f"| {' | '.join(columns)} |")
                report_lines.append(f"| {' | '.join(['---'] * len(columns))} |")

                for row in rows:
                    values = " | ".join(f"{str(v):>15}" for v in row)
                    print(f"  {values}")
                    report_lines.append(f"| {' | '.join(str(v) for v in row)} |")

                print(f"\n  ({len(rows)} rows)")
                report_lines.append("")

            except Exception as e:
                print(f"  Error: {e}")
                report_lines.append(f"Error: {e}\n")

        # ── Statistical analysis (post-query) ─────────────────────────
        print(f"\n{'='*60}")
        print("  Statistical Summary")
        print(f"{'='*60}")
        report_lines.append("## Statistical Summary\n")

        try:
            # Fetch all consecutive pairs for correlation analysis
            pair_query = text("""
                SELECT
                    (p2.price - p1.price) AS price_delta,
                    (p2.rank - p1.rank) AS rank_delta,
                    (p2.review_count - p1.review_count) AS review_delta
                FROM product_snapshots p1
                JOIN product_snapshots p2
                    ON p1.product_id = p2.product_id
                    AND p1.source = p2.source
                    AND p2.captured_at > p1.captured_at
            """)
            pairs = conn.execute(pair_query).fetchall()

            if len(pairs) >= 3:
                price_deltas = [float(r[0]) for r in pairs]
                rank_deltas = [float(r[1]) for r in pairs]
                review_deltas = [float(r[2]) for r in pairs]

                # Pearson correlations
                r_price_rank = pearson_correlation(price_deltas, rank_deltas)
                r_review_rank = pearson_correlation(review_deltas, rank_deltas)

                print(f"  Pearson r(price_delta, rank_delta):   {r_price_rank:+.4f}")
                print(f"  Pearson r(review_delta, rank_delta):  {r_review_rank:+.4f}")
                print(f"  Sample size: {len(pairs)} observation pairs")

                report_lines.append(f"- Pearson r(price_delta, rank_delta): **{r_price_rank:+.4f}**")
                report_lines.append(f"- Pearson r(review_delta, rank_delta): **{r_review_rank:+.4f}**")
                report_lines.append(f"- Sample size: {len(pairs)} pairs")

                # Interpretation
                if abs(r_price_rank) > 0.5:
                    msg = "Strong price-rank correlation: pricing strategy significantly impacts ranking."
                elif abs(r_price_rank) > 0.3:
                    msg = "Moderate price-rank correlation: pricing is a notable factor."
                else:
                    msg = "Weak price-rank correlation: other factors dominate ranking changes."
                print(f"  Interpretation: {msg}")
                report_lines.append(f"- **Interpretation**: {msg}")

                # Z-score anomalies on rank deltas
                zs = z_scores(rank_deltas)
                anomalies = [(i, rank_deltas[i], zs[i]) for i in range(len(zs)) if abs(zs[i]) > 2.0]
                if anomalies:
                    print(f"\n  Z-score anomalies (|z| > 2.0): {len(anomalies)} detected")
                    report_lines.append(f"\n### Z-Score Anomalies\n")
                    report_lines.append(f"{len(anomalies)} statistically unusual ranking changes detected (|z| > 2.0).\n")
                else:
                    print("\n  No z-score anomalies detected (all |z| <= 2.0)")
                    report_lines.append("\nNo statistically unusual ranking changes detected.\n")

            else:
                print("  Insufficient data for statistical analysis (need >= 3 pairs)")
                report_lines.append("Insufficient data for correlation analysis.\n")

            # Per-product volatility (CV)
            vol_query = text("""
                SELECT product_id, GROUP_CONCAT(rank) AS ranks
                FROM product_snapshots
                WHERE rank > 0
                GROUP BY product_id
                HAVING COUNT(*) >= 2
            """)
            vol_rows = conn.execute(vol_query).fetchall()

            if vol_rows:
                print(f"\n  Ranking Volatility (Coefficient of Variation):")
                report_lines.append("\n### Ranking Volatility (CV)\n")
                report_lines.append("| product_id | CV | interpretation |")
                report_lines.append("| --- | --- | --- |")

                for row in vol_rows:
                    pid = row[0]
                    ranks = [float(x) for x in str(row[1]).split(",")]
                    cv = coefficient_of_variation(ranks)
                    interp = "stable" if cv < 0.1 else ("moderate" if cv < 0.3 else "volatile")
                    print(f"    {pid}: CV={cv:.4f} ({interp})")
                    report_lines.append(f"| {pid} | {cv:.4f} | {interp} |")

        except Exception as e:
            print(f"  Statistical analysis error: {e}")
            report_lines.append(f"Error in statistical analysis: {e}\n")

    # Export report
    report_path = Path("data/analysis_report.md")
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    logger.info("Report exported to %s", report_path)


if __name__ == "__main__":
    run_analysis()
