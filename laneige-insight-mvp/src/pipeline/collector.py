import json
from typing import List
from sqlalchemy.orm import Session
from src.models import ProductSnapshot
from src.utils.images import fetch_image_bytes, phash_from_bytes

def save_snapshots(db: Session, items: List, compute_image_hash: bool = True) -> int:
    saved = 0
    for it in items:
        img_phash = ""
        if compute_image_hash and it.image_url:
            try:
                img_bytes = fetch_image_bytes(it.image_url)
                if img_bytes:
                    img_phash = phash_from_bytes(img_bytes)
            except:
                img_phash = ""

        snap = ProductSnapshot(
            source=it.source,
            market=it.market,
            category=it.category,
            captured_at=it.captured_at,
            rank=it.rank,
            product_id=it.product_id,
            title=it.title[:512],
            product_url=it.product_url,
            price=float(it.price or 0.0),
            rating=float(it.rating or 0.0),
            review_count=int(it.review_count or 0),
            image_url=it.image_url or "",
            image_phash=img_phash,
            raw_json=json.dumps(it.raw, ensure_ascii=False),
        )
        db.add(snap)
        saved += 1
    db.commit()
    return saved
