"""
Data collection CLI.

Usage:
    PYTHONPATH=. python scripts/collect.py --source amazon_product
    PYTHONPATH=. python scripts/collect.py --source amazon_bestsellers --url <URL>
    PYTHONPATH=. python scripts/collect.py --source amazon_product --keyword laneige
"""

import argparse
import os

from src.db import SessionLocal
from src.sources.amazon_bestsellers import AmazonBestSellers
from src.sources.amazon_product import AmazonProduct
from src.sources.amazon_keepa import AmazonKeepa
from src.pipeline.collector import save_snapshots

SOURCES = {
    "amazon_bestsellers": AmazonBestSellers,
    "amazon_product": AmazonProduct,
    "amazon_keepa": AmazonKeepa,
}


def main():
    if os.getenv("DEMO_MODE", "").strip().lower() in ("1", "true", "yes"):
        print("[DEMO_MODE] Live collection disabled.")
        return

    ap = argparse.ArgumentParser(description="Collect product snapshots")
    ap.add_argument("--source", required=True, choices=SOURCES.keys())
    ap.add_argument("--url", default="")
    ap.add_argument("--keyword", default="")
    args = ap.parse_args()

    src = SOURCES[args.source]()
    items = src.fetch(args.url)

    if not items:
        print("No items fetched. Skipping save.")
        return

    if args.keyword.strip():
        kw = args.keyword.strip().lower()
        items = [it for it in items if kw in (it.title or "").lower()]

    db = SessionLocal()
    try:
        n = save_snapshots(db, items, compute_image_hash=True)
        print(f"\nSaved {n} snapshots.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
