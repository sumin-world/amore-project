import argparse
from src.db import SessionLocal
from src.sources.amazon_bestsellers import AmazonBestSellers
from src.sources.amazon_product import AmazonProduct  # 추가
from src.pipeline.collector import save_snapshots

SOURCES = {
    "amazon_bestsellers": AmazonBestSellers,
    "amazon_product": AmazonProduct,  # 추가
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=SOURCES.keys())
    ap.add_argument("--url", default="")  # amazon_product는 URL 불필요
    ap.add_argument("--keyword", default="")
    args = ap.parse_args()
    
    src = SOURCES[args.source]()
    items = src.fetch(args.url)
    
    if args.keyword.strip():
        kw = args.keyword.strip().lower()
        items = [it for it in items if kw in (it.title or "").lower()]
    
    db = SessionLocal()
    try:
        n = save_snapshots(db, items, compute_image_hash=True)
        print(f"\n✅ Saved {n} snapshots")
    finally:
        db.close()

if __name__ == "__main__":
    main()