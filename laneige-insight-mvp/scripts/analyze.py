import json
from sqlalchemy import select, desc
from src.db import SessionLocal
from src.models import ProductSnapshot
from src.pipeline.detector import get_recent_pair, score_drivers
from src.pipeline.why import build_why_report, upsert_report

def main():
    db = SessionLocal()
    try:
        recent = db.execute(select(ProductSnapshot).order_by(desc(ProductSnapshot.captured_at)).limit(200)).scalars().all()
        seen = set()
        for s in recent:
            key = (s.source, s.market, s.category, s.product_id)
            if key in seen:
                continue
            seen.add(key)

            prev, curr = get_recent_pair(db, s.source, s.market, s.category, s.product_id)
            if not prev or not curr:
                continue

            evidence = score_drivers(prev, curr)
            summary = build_why_report(prev, curr, evidence)
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
