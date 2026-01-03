"""
Ranking Change Analysis Script

This script analyzes product ranking changes by comparing consecutive snapshots
and generating "Why Reports" that explain ranking fluctuations using AI and rule-based logic.

Features:
    - Retrieves recent product snapshots from the database
    - Identifies pairs of consecutive snapshots for change detection
    - Scores ranking drivers (price changes, review count, ratings, image updates)
    - Generates AI-powered explanations using Groq LLM (free tier) or Claude (paid)
    - Falls back to rule-based analysis if LLM APIs are unavailable
    - Stores analysis results in WhyReport table for dashboard visualization

Usage:
    PYTHONPATH=. python scripts/analyze.py

Environment Variables:
    - GROQ_API_KEY: API key for Groq LLM (recommended, free tier available)
    - ANTHROPIC_API_KEY: API key for Claude (optional, paid alternative)
    - USE_GROQ: Enable/disable Groq usage (default: true)
    - USE_CLAUDE: Enable/disable Claude usage (default: false)

Output:
    Prints analysis progress for each product with ranking change detection.
    Reports are saved to the why_reports table and displayed in the Streamlit dashboard.

Notes:
    - Processes up to 200 most recent snapshots
    - Only analyzes products with at least 2 snapshots within configured time window
    - LLM fallback hierarchy: Groq (free) → Claude (paid) → Rule-based
"""
import json
from sqlalchemy import select, desc
from src.db import SessionLocal
from src.models import ProductSnapshot
from src.pipeline.detector import get_recent_pair, score_drivers
from src.pipeline.why import build_why_report, upsert_report

def main():
    """
    Main analysis function that processes ranking changes and generates Why Reports.
    
    Workflow:
        1. Retrieve recent product snapshots (up to 200) sorted by capture time
        2. Deduplicate by product key (source, market, category, product_id)
        3. For each unique product, fetch the two most recent snapshots
        4. Calculate evidence scores for ranking drivers:
           - Rank delta (position change)
           - Price delta (pricing changes)
           - Review count delta (customer engagement)
           - Rating delta (quality perception)
           - Image diff (thumbnail updates via perceptual hashing)
        5. Generate Why Report using AI or rule-based fallback
        6. Store report in database for dashboard consumption
    
    Returns:
        None. Prints processing status for each analyzed product.
    
    Notes:
        - Skips products with insufficient snapshot history (< 2 snapshots)
        - Processes each unique product only once per run
        - Reports are upserted (updated if exists, inserted if new)
        - Database connection is guaranteed to close via finally block
    """
    db = SessionLocal()
    try:
        # Fetch recent snapshots for analysis
        recent = db.execute(
            select(ProductSnapshot)
            .order_by(desc(ProductSnapshot.captured_at))
            .limit(200)
        ).scalars().all()
        
        seen = set()
        for s in recent:
            # Deduplicate by unique product identifier
            key = (s.source, s.market, s.category, s.product_id)
            if key in seen:
                continue
            seen.add(key)

            # Get the two most recent snapshots for comparison
            prev, curr = get_recent_pair(db, s.source, s.market, s.category, s.product_id)
            if not prev or not curr:
                continue

            # Score ranking change drivers
            evidence = score_drivers(prev, curr)
            
            # Generate AI-powered or rule-based Why Report
            summary = build_why_report(prev, curr, evidence)
            
            # Store report in database
            upsert_report(
                db, s.source, s.market, s.category, s.product_id,
                prev.captured_at, curr.captured_at,
                summary, json.dumps(evidence, ensure_ascii=False)
            )
            print(f"[OK] report: {s.product_id} {prev.rank}->{curr.rank}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
