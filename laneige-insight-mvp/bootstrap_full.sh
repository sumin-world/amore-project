#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/6] venv"
python3 -m venv .venv
source .venv/bin/activate

echo "[2/6] dirs"
mkdir -p src/sources src/pipeline src/utils scripts data reports logs snapshots
touch src/__init__.py src/sources/__init__.py src/pipeline/__init__.py src/utils/__init__.py

echo "[3/6] requirements + env"
cat > requirements.txt <<'EOF'
playwright==1.48.0
beautifulsoup4==4.12.3
lxml==5.3.0
httpx==0.27.2
pydantic==2.9.2
python-dotenv==1.0.1
SQLAlchemy==2.0.36
Pillow==10.4.0
imagehash==4.3.1
pandas==2.2.3
streamlit==1.39.0
EOF

cat > .env.example <<'EOF'
DATABASE_URL=sqlite+pysqlite:///./local.db
APP_TZ=Asia/Seoul
REQUEST_SLEEP_SEC=1.2
EOF
cp -f .env.example .env

echo "[4/6] write code"
cat > src/config.py <<'EOF'
from pydantic import BaseModel
from dotenv import load_dotenv
import os
load_dotenv()

class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "").strip()
    request_sleep_sec: float = float(os.getenv("REQUEST_SLEEP_SEC", "1.2"))

settings = Settings()
if not settings.database_url:
    raise RuntimeError("DATABASE_URL empty. fill .env")
EOF

cat > src/db.py <<'EOF'
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import settings
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
EOF

cat > src/models.py <<'EOF'
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, DateTime, Text, Index, UniqueConstraint
from datetime import datetime

class Base(DeclarativeBase):
    pass

class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    market: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(128), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    rank: Mapped[int] = mapped_column(Integer, index=True)
    product_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512))
    product_url: Mapped[str] = mapped_column(Text)

    price: Mapped[float] = mapped_column(Float, default=0.0)
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    image_url: Mapped[str] = mapped_column(Text, default="")
    image_phash: Mapped[str] = mapped_column(String(32), default="")
    raw_json: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (Index("ix_snap_key", "source", "market", "category", "product_id", "captured_at"),)

class WhyReport(Base):
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

    __table_args__ = (UniqueConstraint("source","market","category","product_id","window_start","window_end", name="uq_report_key"),)
EOF

cat > src/utils/images.py <<'EOF'
from PIL import Image
import imagehash
import io
import httpx

def phash_from_bytes(img_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return str(imagehash.phash(img))

def fetch_image_bytes(url: str, timeout_sec: float = 10.0) -> bytes:
    if not url:
        return b""
    headers = {"User-Agent": "LaneigeInsightBot/0.1 (demo)"}
    with httpx.Client(timeout=timeout_sec, headers=headers, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content
EOF

cat > src/sources/base.py <<'EOF'
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any

@dataclass
class ProductItem:
    source: str
    market: str
    category: str
    captured_at: datetime
    rank: int
    product_id: str
    title: str
    product_url: str
    price: float
    rating: float
    review_count: int
    image_url: str
    raw: Dict[str, Any]

class Source(ABC):
    @abstractmethod
    def fetch(self, url: str) -> List[ProductItem]:
        raise NotImplementedError
EOF

cat > src/sources/amazon_bestsellers.py <<'EOF'
from datetime import datetime
from typing import List
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import re
import time
from src.sources.base import Source, ProductItem
from src.config import settings

_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")

def _to_float(s: str) -> float:
    try: return float(s.replace("$","").replace(",","").strip())
    except: return 0.0

def _to_int(s: str) -> int:
    try:
        s = s.replace(",","")
        m = re.findall(r"\d+", s)
        return int(m[0]) if m else 0
    except:
        return 0

class AmazonBestSellers(Source):
    def fetch(self, url: str) -> List[ProductItem]:
        captured_at = datetime.utcnow()
        items: List[ProductItem] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(settings.request_sleep_sec)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("div#zg-ordered-list > li")
        if not cards:
            cards = soup.select("div.zg-grid-general-faceout, div.p13n-sc-uncoverable-faceout")

        rank_counter = 0
        for card in cards:
            if rank_counter >= 20:
                break
            a = card.select_one("a.a-link-normal[href*=\"/dp/\"]")
            href = a.get("href","") if a else ""
            m = _ASIN_RE.search(href)
            asin = m.group(1) if m else ""

            img = card.select_one("img")
            title = (img.get("alt","") if img else "").strip()
            img_url = (img.get("src","") if img else "").strip()

            price_el = card.select_one("span.a-price > span.a-offscreen, span.a-color-price")
            price = _to_float(price_el.get_text(strip=True)) if price_el else 0.0

            rating_el = card.select_one("span.a-icon-alt")
            rating = 0.0
            if rating_el:
                try: rating = float(rating_el.get_text(strip=True).split(" ")[0])
                except: rating = 0.0

            rc_el = card.select_one("a[href*=\"#customerReviews\"] span")
            review_count = _to_int(rc_el.get_text(strip=True)) if rc_el else 0

            if not asin or not title:
                continue

            rank_counter += 1
            product_url = "https://www.amazon.com" + href.split("?")[0] if href.startswith("/") else href

            items.append(ProductItem(
                source="amazon_bestsellers",
                market="US",
                category="Amazon Best Sellers (Beauty)",
                captured_at=captured_at,
                rank=rank_counter,
                product_id=asin,
                title=title,
                product_url=product_url,
                price=price,
                rating=rating,
                review_count=review_count,
                image_url=img_url,
                raw={"href": href},
            ))
        return items
EOF

cat > src/pipeline/collector.py <<'EOF'
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
EOF

cat > src/pipeline/detector.py <<'EOF'
from sqlalchemy import select, desc
from src.models import ProductSnapshot
import imagehash

def get_recent_pair(db, source: str, market: str, category: str, product_id: str):
    q = (
        select(ProductSnapshot)
        .where(
            ProductSnapshot.source == source,
            ProductSnapshot.market == market,
            ProductSnapshot.category == category,
            ProductSnapshot.product_id == product_id,
        )
        .order_by(desc(ProductSnapshot.captured_at))
        .limit(2)
    )
    rows = db.execute(q).scalars().all()
    if len(rows) < 2:
        return None, None
    return rows[1], rows[0]

def score_drivers(prev: ProductSnapshot, curr: ProductSnapshot) -> dict:
    drivers = []
    if prev.price and curr.price:
        pct = (curr.price - prev.price) / max(prev.price, 1e-6)
        drivers.append({"type": "price", "score": min(100, int(abs(pct) * 300)), "detail": {"prev": prev.price, "curr": curr.price, "pct": pct}})

    d_reviews = (curr.review_count or 0) - (prev.review_count or 0)
    drivers.append({"type": "review_velocity", "score": min(100, max(0, int(d_reviews * 2))), "detail": {"prev": prev.review_count, "curr": curr.review_count, "delta": d_reviews}})

    if prev.image_phash and curr.image_phash:
        dist = imagehash.hex_to_hash(prev.image_phash) - imagehash.hex_to_hash(curr.image_phash)
        drivers.append({"type": "thumbnail_change", "score": min(100, abs(int(dist)) * 8), "detail": {"dist": int(dist), "phash_prev": prev.image_phash, "phash_curr": curr.image_phash}})

    d_rank = (curr.rank or 0) - (prev.rank or 0)
    drivers.append({"type": "rank_change", "score": min(100, abs(d_rank) * 10), "detail": {"prev": prev.rank, "curr": curr.rank, "delta": int(d_rank)}})

    drivers_sorted = sorted(drivers, key=lambda x: x["score"], reverse=True)
    return {"drivers": drivers_sorted}
EOF

cat > src/pipeline/why.py <<'EOF'
import json
from sqlalchemy import select
from src.models import WhyReport

def build_why_report(prev, curr, evidence: dict) -> str:
    top = evidence["drivers"][:3]
    lines = []
    lines.append(f"랭킹 변화: {prev.rank}위 → {curr.rank}위 (Δ {curr.rank - prev.rank:+d})")
    for d in top:
        t, sc, det = d["type"], d["score"], d["detail"]
        if t == "price":
            lines.append(f"- 가격 변동(점수 {sc}): {det['prev']:.2f} → {det['curr']:.2f} ({det['pct']*100:+.1f}%)")
        elif t == "review_velocity":
            lines.append(f"- 리뷰 증가 속도(점수 {sc}): {det['prev']} → {det['curr']} (Δ {det['delta']:+d})")
        elif t == "thumbnail_change":
            lines.append(f"- 썸네일 변경 감지(점수 {sc}): pHash distance={det['dist']}")
    lines.append("권장 액션(초안): 가격/쿠폰 시나리오 검토 + 썸네일 A/B + 리뷰 이슈(배송/품질) 모니터링")
    return "\n".join(lines)

def upsert_report(db, source, market, category, product_id, window_start, window_end, summary, evidence_json):
    existing = db.execute(
        select(WhyReport).where(
            WhyReport.source==source,
            WhyReport.market==market,
            WhyReport.category==category,
            WhyReport.product_id==product_id,
            WhyReport.window_start==window_start,
            WhyReport.window_end==window_end,
        )
    ).scalars().first()

    if existing:
        existing.summary = summary
        existing.evidence_json = evidence_json
    else:
        db.add(WhyReport(
            source=source, market=market, category=category, product_id=product_id,
            window_start=window_start, window_end=window_end,
            summary=summary, evidence_json=evidence_json
        ))
    db.commit()
EOF

cat > scripts/init_db.py <<'EOF'
from src.db import engine
from src.models import Base
Base.metadata.create_all(bind=engine)
print("DB tables created.")
EOF

cat > scripts/collect.py <<'EOF'
import argparse
from src.db import SessionLocal
from src.sources.amazon_bestsellers import AmazonBestSellers
from src.pipeline.collector import save_snapshots

SOURCES = {"amazon_bestsellers": AmazonBestSellers}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=SOURCES.keys())
    ap.add_argument("--url", required=True)
    args = ap.parse_args()

    src = SOURCES[args.source]()
    items = src.fetch(args.url)

    db = SessionLocal()
    try:
        n = save_snapshots(db, items, compute_image_hash=True)
        print(f"saved {n} snapshots")
    finally:
        db.close()

if __name__ == "__main__":
    main()
EOF

cat > scripts/analyze.py <<'EOF'
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
EOF

cat > app.py <<'EOF'
import streamlit as st
import pandas as pd
from sqlalchemy import select, desc
from src.db import SessionLocal
from src.models import ProductSnapshot, WhyReport

st.set_page_config(page_title="Laneige INSIGHT MVP", layout="wide")
st.title("Laneige INSIGHT MVP")

@st.cache_data(ttl=10)
def load_latest(limit=200):
    db = SessionLocal()
    try:
        rows = db.execute(select(ProductSnapshot).order_by(desc(ProductSnapshot.captured_at)).limit(limit)).scalars().all()
        return pd.DataFrame([{
            "captured_at": r.captured_at,
            "rank": r.rank,
            "product_id": r.product_id,
            "title": r.title,
            "price": r.price,
            "rating": r.rating,
            "review_count": r.review_count,
            "product_url": r.product_url,
            "image_url": r.image_url
        } for r in rows])
    finally:
        db.close()

@st.cache_data(ttl=10)
def load_reports(limit=50):
    db = SessionLocal()
    try:
        rows = db.execute(select(WhyReport).order_by(desc(WhyReport.created_at)).limit(limit)).scalars().all()
        return pd.DataFrame([{
            "created_at": r.created_at,
            "product_id": r.product_id,
            "window_start": r.window_start,
            "window_end": r.window_end,
            "summary": r.summary,
        } for r in rows])
    finally:
        db.close()

df = load_latest()
if df.empty:
    st.warning("데이터 없음. 먼저 수집: PYTHONPATH=. python scripts/collect.py ...")
    st.stop()

c1, c2 = st.columns([2, 1])
with c1:
    st.subheader("최신 스냅샷")
    st.dataframe(df, use_container_width=True, height=420, hide_index=True)

with c2:
    st.subheader("Why 리포트")
    rep = load_reports()
    st.dataframe(rep[["created_at","product_id","window_start","window_end"]], use_container_width=True, height=240, hide_index=True)
    if not rep.empty:
        idx = st.selectbox("리포트 선택", list(rep.index))
        st.text_area("summary", rep.loc[idx, "summary"], height=420)
EOF

echo "[5/6] install"
pip -q install -U pip
pip -q install -r requirements.txt
python -m playwright install chromium

echo "[6/6] init db"
PYTHONPATH=. python scripts/init_db.py

echo "[OK] done"
echo "Run:"
echo "  source .venv/bin/activate"
echo "  PYTHONPATH=. python scripts/collect.py --source amazon_bestsellers --url \"https://www.amazon.com/Best-Sellers-Beauty/zgbs/beauty\""
echo "  PYTHONPATH=. python scripts/analyze.py"
echo "  streamlit run app.py --server.address 0.0.0.0 --server.port 8502"
