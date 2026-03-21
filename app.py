"""
Streamlit dashboard: snapshot table, Why Reports, ROI simulator,
competitive analysis, and ranking trend charts.
"""

import re
from datetime import datetime, timedelta, timezone

import altair as alt
import pandas as pd
import streamlit as st
from sqlalchemy import select, desc

from src.db import SessionLocal
from src.models import ProductSnapshot, WhyReport

# ── page config ──────────────────────────────────────────────────────────

st.set_page_config(page_title="Market Intelligence Dashboard", layout="wide")
st.title("Market Intelligence Dashboard")
st.caption("Ranking Snapshot → Change Detection → AI Analysis → ROI Simulation")


# ── helpers ──────────────────────────────────────────────────────────────

def roi_calc(delta_rank: int, sales_per_rank: int = 3500, cost: int = 8500):
    """Linear ROI model: estimated weekly sales per rank position."""
    loss = max(0, delta_rank) * sales_per_rank
    gain = max(0, -delta_rank) * sales_per_rank
    roi = int((gain / cost) * 100) if cost else 0
    return loss, cost, gain, roi


@st.cache_data(ttl=10)
def load_snapshots(limit: int = 500) -> pd.DataFrame:
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(ProductSnapshot)
                .order_by(desc(ProductSnapshot.captured_at))
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return pd.DataFrame(
            [
                {
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
                }
                for r in rows
            ]
        )
    finally:
        db.close()


@st.cache_data(ttl=10)
def load_reports(limit: int = 200) -> pd.DataFrame:
    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(WhyReport)
                .order_by(desc(WhyReport.created_at))
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return pd.DataFrame(
            [
                {
                    "created_at": r.created_at,
                    "product_id": r.product_id,
                    "window_start": r.window_start,
                    "window_end": r.window_end,
                    "summary": r.summary,
                }
                for r in rows
            ]
        )
    finally:
        db.close()


def insert_demo_event(product_id: str, rank_from: int, rank_to: int):
    """Insert two snapshots 5 min apart to simulate a ranking change."""
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        for ts, rank, price in [
            (now - timedelta(minutes=5), rank_from, 24.99),
            (now, rank_to, 19.99),
        ]:
            db.add(
                ProductSnapshot(
                    source="demo",
                    market="US",
                    category="DEMO",
                    captured_at=ts,
                    rank=rank,
                    product_id=product_id,
                    title=f"Demo Product ({product_id})",
                    product_url="",
                    price=price,
                    rating=4.4,
                    review_count=1200 + (50 if ts == now else 0),
                    image_url="",
                    image_phash="",
                    raw_json="{}",
                )
            )
        db.commit()
    finally:
        db.close()


# ── sidebar ──────────────────────────────────────────────────────────────

st.sidebar.header("Filters & Controls")

kw = (
    st.sidebar.text_input(
        "Search (Title or Product ID)",
        placeholder="e.g. sleeping mask, B07KNTK3QG",
    )
    .strip()
    .lower()
)

demo_mode = st.sidebar.toggle("Demo Mode", value=False)
if demo_mode:
    st.sidebar.subheader("Demo Event")
    demo_pid = st.sidebar.text_input("Product ID", value="DEMO-001")
    r_from = st.sidebar.number_input("Rank From", value=3, min_value=1, max_value=100)
    r_to = st.sidebar.number_input("Rank To", value=9, min_value=1, max_value=100)
    if st.sidebar.button("Insert Demo Snapshots"):
        insert_demo_event(demo_pid, int(r_from), int(r_to))
        st.sidebar.success("Demo event inserted.")
        st.sidebar.info("Run: `PYTHONPATH=. python scripts/analyze.py`")
        st.cache_data.clear()

# ── load + filter ────────────────────────────────────────────────────────

df = load_snapshots()
if kw:
    df = df[
        df["title"].str.lower().str.contains(kw, na=False)
        | df["product_id"].str.lower().str.contains(kw, na=False)
    ].copy()

# ── main layout ──────────────────────────────────────────────────────────

col_left, col_right = st.columns([1.5, 1])

with col_left:
    st.subheader("Product Snapshots")
    if df.empty:
        st.info(
            "No data found. Collect first:\n"
            "`PYTHONPATH=. python scripts/collect.py --source amazon_product`"
        )
    else:
        disp = df.copy()
        disp["captured_at"] = pd.to_datetime(disp["captured_at"]).dt.strftime("%m/%d %H:%M")
        disp["price"] = disp["price"].apply(lambda x: f"${x:.2f}")
        disp["rating"] = disp["rating"].apply(lambda x: f"{x:.1f}")
        disp["review_count"] = disp["review_count"].apply(lambda x: f"{x:,}")

        st.dataframe(
            disp[["captured_at", "rank", "product_id", "title", "price", "rating", "review_count"]]
            .sort_values("captured_at", ascending=False),
            use_container_width=True,
            height=400,
            hide_index=True,
        )

        # Product detail
        st.markdown("---")
        st.subheader("Product Detail")
        pids = df["product_id"].unique()
        sel = st.selectbox(
            "Select product",
            pids,
            format_func=lambda x: f"{x} — {df[df['product_id']==x].iloc[0]['title'][:40]}",
        )
        if sel:
            pdf = df[df["product_id"] == sel].sort_values("captured_at", ascending=False)
            latest = pdf.iloc[0]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Rank", f"#{latest['rank']}")
            m2.metric("Price", f"${latest['price']:.2f}")
            m3.metric("Rating", f"{latest['rating']:.1f}")
            m4.metric("Reviews", f"{latest['review_count']:,}")

            if len(pdf) >= 2:
                prev = pdf.iloc[1]
                c1, c2, c3 = st.columns(3)
                c1.metric("Rank Delta", f"{latest['rank'] - prev['rank']:+d}", delta_color="inverse")
                c2.metric("Price Delta", f"${latest['price'] - prev['price']:+.2f}", delta_color="off")
                c3.metric("Review Delta", f"{latest['review_count'] - prev['review_count']:+,d}")

with col_right:
    st.subheader("Why Reports")
    rep = load_reports()

    if rep.empty:
        st.info("No reports yet.\n`PYTHONPATH=. python scripts/analyze.py`")
    else:
        rd = rep.copy()
        rd["created_at"] = pd.to_datetime(rd["created_at"]).dt.strftime("%m/%d %H:%M")
        st.dataframe(
            rd[["created_at", "product_id"]].head(10),
            use_container_width=True,
            height=180,
            hide_index=True,
        )

        idx = st.selectbox(
            "Select report",
            list(rep.index),
            format_func=lambda x: (
                f"{rep.loc[x, 'product_id']} — "
                f"{rep.loc[x, 'created_at'].strftime('%m/%d %H:%M')}"
            ),
        )
        summary = rep.loc[idx, "summary"]
        st.text_area("Summary", summary, height=150, disabled=True)

        # Extract rank delta for ROI
        delta = 0
        m = re.search(r"Δ\s*([+-]?\d+)", summary)
        if m:
            delta = int(m.group(1))

        st.markdown("---")
        st.subheader("ROI Simulator")
        loss, cost, gain, roi = roi_calc(delta)

        rc1, rc2 = st.columns(2)
        rc1.metric("Weekly Loss (no action)", f"${loss:,}")
        rc1.metric("Intervention Cost", f"${cost:,}")
        rc2.metric("Expected Gain", f"${gain:,}")
        rc2.metric("ROI", f"{roi}%")

        if roi > 100:
            st.success("High ROI — intervention recommended.")
        elif roi > 0:
            st.info("Positive ROI — consider intervention.")
        else:
            st.warning("Negative ROI — monitor situation.")


# ── competitive analysis ─────────────────────────────────────────────────

st.markdown("---")
st.header("Competitive Analysis")

# Dynamically extract brands from category field (e.g. "Target Tracking - BrandName")
brands_in_data = set()
if not df.empty and "category" in df.columns:
    for cat in df["category"].unique():
        if " - " in cat:
            brands_in_data.add(cat.split(" - ", 1)[1])

comp_rows = []
for brand in sorted(brands_in_data):
    bdf = df[df["category"].str.contains(brand, na=False)]
    for pid in bdf["product_id"].unique():
        pf = bdf[bdf["product_id"] == pid].sort_values("captured_at", ascending=False)
        if pf.empty:
            continue
        row = pf.iloc[0]
        trend = "→"
        if len(pf) >= 2:
            trend = "↑" if row["rank"] < pf.iloc[1]["rank"] else ("↓" if row["rank"] > pf.iloc[1]["rank"] else "→")
        comp_rows.append(
            {
                "Brand": brand,
                "Product": row["title"][:40] + ("..." if len(row["title"]) > 40 else ""),
                "Rank": f"#{row['rank']}" if row["rank"] > 0 else "N/A",
                "Trend": trend,
                "Price": f"${row['price']:.2f}",
                "Rating": f"{row['rating']:.1f}",
                "Reviews": f"{row['review_count']:,}",
                "Updated": row["captured_at"].strftime("%m/%d %H:%M"),
            }
        )

if comp_rows:
    cdf = pd.DataFrame(comp_rows)
    st.dataframe(cdf, use_container_width=True, height=350, hide_index=True)

    # Compare first two brands if available
    brand_list = sorted(brands_in_data)
    if len(brand_list) >= 2:
        def _avg_rank(brand_filter):
            ranks = cdf[cdf["Brand"] == brand_filter]["Rank"].apply(
                lambda x: int(x.replace("#", "")) if x != "N/A" else 9999
            )
            return ranks.mean() if len(ranks) else 0

        b1, b2 = brand_list[0], brand_list[1]
        avg1, avg2 = _avg_rank(b1), _avg_rank(b2)
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric(f"{b1} Avg Rank", f"#{avg1:.0f}" if avg1 else "N/A")
        mc2.metric(f"{b2} Avg Rank", f"#{avg2:.0f}" if avg2 else "N/A")
        if avg1 and avg2:
            mc3.success(f"{b1} leading") if avg1 < avg2 else mc3.warning(f"{b2} leading")
else:
    st.info("No competitive data available. Collect data with multiple brands to see analysis.")


# ── trend chart ──────────────────────────────────────────────────────────

st.markdown("---")
st.subheader("Ranking Trend")

chart_pids = st.multiselect(
    "Products to compare",
    df["product_id"].unique()[:10] if not df.empty else [],
    format_func=lambda x: f"{x} — {df[df['product_id']==x].iloc[0]['title'][:30]}" if not df.empty else x,
)

if chart_pids:
    cdata = df[df["product_id"].isin(chart_pids)].sort_values("captured_at")
    chart = (
        alt.Chart(cdata)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("captured_at:T", title="Time", axis=alt.Axis(format="%m/%d %H:%M")),
            y=alt.Y("rank:Q", title="Rank", scale=alt.Scale(reverse=True)),
            color=alt.Color("product_id:N", title="Product", scale=alt.Scale(scheme="category10")),
            tooltip=[
                alt.Tooltip("captured_at:T", title="Time", format="%m/%d %H:%M"),
                alt.Tooltip("product_id:N", title="Product"),
                alt.Tooltip("rank:Q", title="Rank"),
                alt.Tooltip("price:Q", title="Price", format="$.2f"),
            ],
        )
        .properties(height=350)
        .interactive()
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Select products above to view trends.")
