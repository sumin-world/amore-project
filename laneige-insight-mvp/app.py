import streamlit as st
import pandas as pd
from sqlalchemy import select, desc
from datetime import datetime, timedelta
from src.db import SessionLocal
from src.models import ProductSnapshot, WhyReport

st.set_page_config(page_title="Laneige INSIGHT MVP", layout="wide")
st.title("Laneige INSIGHT MVP")
st.caption("랭킹 스냅샷 → 변화 감지 → Why 리포트 + ROI (데모 모드 포함)")

def roi_calc(delta_rank: int):
    sales_per_rank = 3500
    expected_loss = max(0, delta_rank) * sales_per_rank
    coupon_cost = 8500
    expected_gain = max(0, -delta_rank) * sales_per_rank
    roi = 0 if coupon_cost == 0 else int((expected_gain / coupon_cost) * 100)
    return expected_loss, coupon_cost, expected_gain, roi

@st.cache_data(ttl=10)
def load_latest(limit=500):
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
            "source": r.source,
            "market": r.market,
            "category": r.category,
        } for r in rows])
    finally:
        db.close()

@st.cache_data(ttl=10)
def load_reports(limit=200):
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

def insert_demo_event(product_id: str, rank_from: int, rank_to: int):
    now = datetime.utcnow()
    prev_t = now - timedelta(minutes=5)
    curr_t = now
    db = SessionLocal()
    try:
        db.add(ProductSnapshot(
            source="demo", market="US", category="DEMO",
            captured_at=prev_t, rank=rank_from, product_id=product_id,
            title=f"LANEIGE DEMO ({product_id})", product_url="",
            price=24.99, rating=4.4, review_count=1200,
            image_url="", image_phash="", raw_json="{}",
        ))
        db.add(ProductSnapshot(
            source="demo", market="US", category="DEMO",
            captured_at=curr_t, rank=rank_to, product_id=product_id,
            title=f"LANEIGE DEMO ({product_id})", product_url="",
            price=19.99, rating=4.4, review_count=1250,
            image_url="", image_phash="", raw_json="{}",
        ))
        db.commit()
    finally:
        db.close()

st.sidebar.header("Controls")
kw = st.sidebar.text_input("Keyword (title)", value="").strip().lower()
demo_mode = st.sidebar.toggle("Demo mode (하락 이벤트 생성)", value=True)

if demo_mode:
    st.sidebar.subheader("Demo event")
    demo_pid = st.sidebar.text_input("demo product_id", value="LANEIGE-DEMO-001")
    r_from = st.sidebar.number_input("rank from", value=3, min_value=1, max_value=100)
    r_to = st.sidebar.number_input("rank to", value=9, min_value=1, max_value=100)
    if st.sidebar.button("Insert demo snapshots"):
        insert_demo_event(demo_pid, int(r_from), int(r_to))
        st.sidebar.success("Inserted. Now run: PYTHONPATH=. python scripts/analyze.py")
        st.cache_data.clear()

df = load_latest()
if kw:
    df = df[df["title"].str.lower().str.contains(kw, na=False)].copy()

c1, c2 = st.columns([2.2, 1])
with c1:
    st.subheader("최신 스냅샷")
    st.dataframe(df.sort_values("captured_at", ascending=False), use_container_width=True, height=520, hide_index=True)

with c2:
    st.subheader("Why 리포트")
    rep = load_reports()
    if rep.empty:
        st.info("리포트 없음. 먼저 analyze 실행: PYTHONPATH=. python scripts/analyze.py")
    else:
        st.dataframe(rep[["created_at","product_id","window_start","window_end"]], use_container_width=True, height=220, hide_index=True)
        idx = st.selectbox("리포트 선택", list(rep.index), index=0)
        summary = rep.loc[idx, "summary"]
        st.text_area("summary", summary, height=220)

        import re
        delta = 0
        m = re.search(r"Δ\\s*([+\\-]\\d+)", summary)
        if m:
            delta = int(m.group(1))

        loss, cost, gain, roi = roi_calc(delta)
        st.subheader("ROI 시뮬레이터 (데모)")
        st.write(f"- 대응 안 하면(추정): 주간 손실 ${loss:,}")
        st.write(f"- AI 추천 대응 비용(쿠폰 등): ${cost:,}")
        st.write(f"- 대응 시 주간 개선(추정): ${gain:,}")
        st.write(f"- ROI: {roi}%")
st.header("🔥 경쟁사 전쟁 모니터 (K-뷰티)")

# 브랜드별 최신 데이터 집계
brands = ["Laneige", "COSRX", "Innisfree", "Etude House"]
comp_data = []

for brand in brands:
    brand_df = df[df["category"].str.contains(brand, na=False)]
    
    if brand_df.empty:
        continue
    
    # 각 제품의 최신 스냅샷만
    for pid in brand_df["product_id"].unique():
        product_df = brand_df[brand_df["product_id"] == pid].sort_values("captured_at", ascending=False)
        if not product_df.empty:
            row = product_df.iloc[0]
            
            # 랭킹 추세 (최근 2개 스냅샷 비교)
            trend = "→"
            if len(product_df) >= 2:
                prev_rank = product_df.iloc[1]["rank"]
                curr_rank = row["rank"]
                if curr_rank < prev_rank:
                    trend = "↑"
                elif curr_rank > prev_rank:
                    trend = "↓"
            
            comp_data.append({
                "브랜드": brand,
                "제품": row["title"][:35] + "..." if len(row["title"]) > 35 else row["title"],
                "랭킹": f"{row['rank']:,}" if row['rank'] > 0 else "N/A",
                "추세": trend,
                "가격": f"${row['price']:.2f}",
                "평점": f"{row['rating']:.1f}",
                "리뷰": f"{row['review_count']:,}",
                "업데이트": row["captured_at"].strftime("%m/%d %H:%M"),
            })

if comp_data:
    comp_df = pd.DataFrame(comp_data)
    
    # 브랜드별 색상 구분
    def highlight_brand(row):
        if "Laneige" in row["브랜드"]:
            return ['background-color: #1e3a5f'] * len(row)
        return [''] * len(row)
    
    st.dataframe(
        comp_df,
        use_container_width=True,
        height=400,
        hide_index=True,
    )
    
    # 간단한 인사이트
    laneige_avg_rank = comp_df[comp_df["브랜드"] == "Laneige"]["랭킹"].apply(lambda x: int(x.replace(",", "")) if x != "N/A" else 9999).mean()
    competitor_avg_rank = comp_df[comp_df["브랜드"] != "Laneige"]["랭킹"].apply(lambda x: int(x.replace(",", "")) if x != "N/A" else 9999).mean()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Laneige 평균 랭킹", f"{laneige_avg_rank:,.0f}")
    c2.metric("경쟁사 평균 랭킹", f"{competitor_avg_rank:,.0f}")
    
    if laneige_avg_rank < competitor_avg_rank:
        c3.success("✅ Laneige 우위")
    else:
        c3.warning("⚠️ 경쟁사 우위")
else:
    st.info("먼저 amazon_product 모드로 데이터 수집: `PYTHONPATH=. python scripts/collect.py --source amazon_product`")

# 랭킹 추이 차트 (선택)
st.subheader("📈 랭킹 추이 (최근 10회)")

chart_products = st.multiselect(
    "제품 선택",
    df["product_id"].unique()[:5],  # 상위 5개만 표시
    default=[]
)

if chart_products:
    chart_data = df[df["product_id"].isin(chart_products)].sort_values("captured_at")
    
    import altair as alt
    
    chart = alt.Chart(chart_data).mark_line(point=True).encode(
        x=alt.X("captured_at:T", title="시간"),
        y=alt.Y("rank:Q", title="랭킹", scale=alt.Scale(reverse=True)),
        color="product_id:N",
        tooltip=["captured_at", "product_id", "rank", "price"]
    ).properties(height=300)
    
    st.altair_chart(chart, use_container_width=True)