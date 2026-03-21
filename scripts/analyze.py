"""
Analyze ranking changes and generate Why Reports.

For each product with >= 2 recent snapshots, scores ranking drivers
and produces an LLM or rule-based explanation.

Usage:
    PYTHONPATH=. python scripts/analyze.py
"""

import json
import logging

from sqlalchemy import select, desc

from src.db import get_db
from src.models import ProductSnapshot
from src.pipeline.detector import get_recent_pair, score_drivers
from src.pipeline.why import build_why_report, upsert_report

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


def main():
    with get_db() as db:
        recent = (
            db.execute(
                select(ProductSnapshot)
                .order_by(desc(ProductSnapshot.captured_at))
                .limit(200)
            )
            .scalars()
            .all()
        )

        seen = set()
        analyzed = 0
        for s in recent:
            key = (s.source, s.market, s.category, s.product_id)
            if key in seen:
                continue
            seen.add(key)

            prev, curr = get_recent_pair(
                db, s.source, s.market, s.category, s.product_id
            )
            if not prev or not curr:
                continue

            evidence = score_drivers(prev, curr)
            summary = build_why_report(prev, curr, evidence)
            upsert_report(
                db,
                s.source,
                s.market,
                s.category,
                s.product_id,
                prev.captured_at,
                curr.captured_at,
                summary,
                json.dumps(evidence, ensure_ascii=False),
            )
            analyzed += 1
            logger.info("Analyzed %s: rank %d → %d", s.product_id, prev.rank, curr.rank)

        logger.info("Total products analyzed: %d", analyzed)


if __name__ == "__main__":
    main()
