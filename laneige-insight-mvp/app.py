"""
Streamlit Dashboard for Amazon Product Ranking Analysis

This dashboard provides real-time visualization of product ranking changes,
AI-powered Why Reports, and competitive analysis for K-beauty products.

Features:
    - Product snapshot table with filtering
    - Product slider for detailed view
    - Why Reports with LLM-generated insights
    - ROI simulator for ranking interventions
    - Competitive benchmarking across brands
    - Ranking trend visualization
    - Demo mode for testing

Layout Philosophy:
    - Left column: Data tables and product selection (snapshot + slider)
    - Right column: Analysis and insights (Why Reports + ROI)
    - Bottom: Competitive analysis and trend charts
    - Consistent color scheme for minimalist design

TODO - Future Enhancements:
    - Add CSV/Excel export buttons for reports and snapshots
    - Implement internationalization (i18n) for multi-language support
    - Add scheduled data refresh (currently manual cache TTL)
    - Add alerting system for critical ranking changes
    - Add more advanced filtering (date range, multiple ASINs)
    - Add product comparison view (side-by-side)
"""
import streamlit as st
import pandas as pd
from sqlalchemy import select, desc
from datetime import datetime, timedelta
from src.db import SessionLocal
from src.models import ProductSnapshot, WhyReport

# Configure page for wide layout and consistent theming
st.set_page_config(
    page_title="Laneige INSIGHT MVP", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Color scheme for consistent minimalist design
COLORS = {
    "primary": "#1e3a5f",     # Dark blue for Laneige brand
    "secondary": "#4a90e2",   # Light blue for accents
    "success": "#28a745",     # Green for positive metrics
    "warning": "#ffc107",     # Yellow for alerts
    "danger": "#dc3545",      # Red for critical issues
}

st.title("Laneige INSIGHT MVP")
st.caption("Product Ranking Tracker → Change Detection → AI Analysis + ROI Simulation")

def roi_calc(delta_rank: int):
    """
    Calculate ROI for ranking interventions.
    
    Args:
        delta_rank: Change in ranking position (positive = worse, negative = better)
    
    Returns:
        Tuple of (expected_loss, intervention_cost, expected_gain, roi_percentage)
    
    Model Assumptions:
        - $3,500 weekly sales per ranking position
        - $8,500 typical intervention cost (coupons, ads, etc.)
        - Linear relationship between rank and sales (simplification)
    
    TODO:
        - Add configurable parameters via sidebar
        - Implement non-linear ranking curve (top 10 more valuable)
        - Add historical validation of ROI predictions
    """
    sales_per_rank = 3500
    expected_loss = max(0, delta_rank) * sales_per_rank
    coupon_cost = 8500
    expected_gain = max(0, -delta_rank) * sales_per_rank
    roi = 0 if coupon_cost == 0 else int((expected_gain / coupon_cost) * 100)
    return expected_loss, coupon_cost, expected_gain, roi

@st.cache_data(ttl=10)
def load_latest(limit=500):
    """
    Load recent product snapshots from database.
    
    Args:
        limit: Maximum number of snapshots to retrieve
    
    Returns:
        DataFrame with snapshot data
    
    Notes:
        - Cached for 10 seconds to reduce database load
        - Ordered by captured_at descending (newest first)
        - Converts ORM objects to DataFrame for Streamlit
    """
    db = SessionLocal()
    try:
        rows = db.execute(
            select(ProductSnapshot)
            .order_by(desc(ProductSnapshot.captured_at))
            .limit(limit)
        ).scalars().all()
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
    """
    Load Why Reports from database.
    
    Args:
        limit: Maximum number of reports to retrieve
    
    Returns:
        DataFrame with report data
    
    Notes:
        - Cached for 10 seconds to reduce database load
        - Ordered by created_at descending (newest first)
    """
    db = SessionLocal()
    try:
        rows = db.execute(
            select(WhyReport)
            .order_by(desc(WhyReport.created_at))
            .limit(limit)
        ).scalars().all()
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
    """
    Insert demo ranking change event for testing.
    
    Creates two snapshots with 5-minute gap showing ranking change.
    Used for testing Why Report generation and ROI calculation.
    
    Args:
        product_id: Demo product identifier
        rank_from: Starting rank position
        rank_to: Ending rank position
    """
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

# ============================================================================
# SIDEBAR: Filters and Controls
# ============================================================================
st.sidebar.header("🎛️ Filters & Controls")

# Keyword filter (searches in title and ASIN)
kw = st.sidebar.text_input(
    "🔍 Search (Title or ASIN)", 
    value="",
    placeholder="e.g., laneige, B07KNTK3QG",
    help="Filter products by keyword in title or ASIN"
).strip().lower()

# Demo mode toggle
demo_mode = st.sidebar.toggle(
    "🧪 Demo Mode", 
    value=False,
    help="Enable demo mode to insert test ranking events"
)

if demo_mode:
    st.sidebar.subheader("Demo Event Generator")
    demo_pid = st.sidebar.text_input("Product ID", value="LANEIGE-DEMO-001")
    r_from = st.sidebar.number_input("Rank From", value=3, min_value=1, max_value=100)
    r_to = st.sidebar.number_input("Rank To", value=9, min_value=1, max_value=100)
    if st.sidebar.button("📝 Insert Demo Snapshots"):
        insert_demo_event(demo_pid, int(r_from), int(r_to))
        st.sidebar.success("✅ Demo event inserted!")
        st.sidebar.info("Run analysis: `PYTHONPATH=. python scripts/analyze.py`")
        st.cache_data.clear()

# Load data
df = load_latest()

# Apply filters
if kw:
    # Search in both title and product_id (ASIN)
    df = df[
        df["title"].str.lower().str.contains(kw, na=False) | 
        df["product_id"].str.lower().str.contains(kw, na=False)
    ].copy()

# ============================================================================
# MAIN LAYOUT: Left Column (Data) + Right Column (Analysis)
# ============================================================================
col_left, col_right = st.columns([1.5, 1])

with col_left:
    st.subheader("📊 Product Snapshots")
    
    # Display snapshot table
    if not df.empty:
        # Format for display
        display_df = df.copy()
        display_df["captured_at"] = pd.to_datetime(display_df["captured_at"]).dt.strftime("%m/%d %H:%M")
        display_df["price"] = display_df["price"].apply(lambda x: f"${x:.2f}")
        display_df["rating"] = display_df["rating"].apply(lambda x: f"{x:.1f}⭐")
        display_df["review_count"] = display_df["review_count"].apply(lambda x: f"{x:,}")
        
        st.dataframe(
            display_df[["captured_at", "rank", "product_id", "title", "price", "rating", "review_count"]].sort_values("captured_at", ascending=False),
            use_container_width=True,
            height=400,
            hide_index=True
        )
        
        # Product detail slider
        st.markdown("---")
        st.subheader("🔍 Product Detail View")
        
        if not df.empty:
            product_ids = df["product_id"].unique()
            selected_pid = st.selectbox(
                "Select Product",
                product_ids,
                format_func=lambda x: f"{x} - {df[df['product_id']==x].iloc[0]['title'][:40]}..."
            )
            
            if selected_pid:
                product_df = df[df["product_id"] == selected_pid].sort_values("captured_at", ascending=False)
                if not product_df.empty:
                    latest = product_df.iloc[0]
                    
                    # Display metrics in columns
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Current Rank", f"#{latest['rank']}")
                    m2.metric("Price", f"${latest['price']:.2f}")
                    m3.metric("Rating", f"{latest['rating']:.1f}⭐")
                    m4.metric("Reviews", f"{latest['review_count']:,}")
                    
                    # Show trend if multiple snapshots
                    if len(product_df) >= 2:
                        prev = product_df.iloc[1]
                        rank_delta = latest['rank'] - prev['rank']
                        price_delta = latest['price'] - prev['price']
                        review_delta = latest['review_count'] - prev['review_count']
                        
                        st.markdown("**Recent Change:**")
                        change_cols = st.columns(3)
                        change_cols[0].metric("Rank Change", f"{rank_delta:+d}", delta_color="inverse")
                        change_cols[1].metric("Price Change", f"${price_delta:+.2f}", delta_color="off")
                        change_cols[2].metric("Review Growth", f"{review_delta:+,d}")
    else:
        st.info("No data found. Run data collection first:\n`PYTHONPATH=. python scripts/collect.py --source amazon_product`")

with col_right:
    st.subheader("📋 Why Reports")
    
    rep = load_reports()
    if rep.empty:
        st.info("No reports yet. Generate analysis:\n`PYTHONPATH=. python scripts/analyze.py`")
    else:
        # Display report summary table
        report_display = rep.copy()
        report_display["created_at"] = pd.to_datetime(report_display["created_at"]).dt.strftime("%m/%d %H:%M")
        
        st.dataframe(
            report_display[["created_at", "product_id"]].head(10),
            use_container_width=True,
            height=180,
            hide_index=True
        )
        
        # Report selector
        idx = st.selectbox(
            "Select Report",
            list(rep.index),
            format_func=lambda x: f"{rep.loc[x, 'product_id']} - {rep.loc[x, 'created_at'].strftime('%m/%d %H:%M')}",
            index=0
        )
        
        summary = rep.loc[idx, "summary"]
        st.text_area("Analysis Summary", summary, height=150, disabled=True)
        
        # Extract rank delta from summary for ROI calculation
        import re
        delta = 0
        m = re.search(r"Δ\s*([+\-]?\d+)", summary)
        if m:
            delta = int(m.group(1))
        
        # ROI Simulator
        st.markdown("---")
        st.subheader("💰 ROI Simulator")
        
        loss, cost, gain, roi = roi_calc(delta)
        
        roi_cols = st.columns(2)
        with roi_cols[0]:
            st.metric("Weekly Loss (No Action)", f"${loss:,}", delta=None)
            st.metric("Intervention Cost", f"${cost:,}", delta=None)
        with roi_cols[1]:
            st.metric("Expected Gain", f"${gain:,}", delta=None)
            st.metric("ROI", f"{roi}%", delta=None)
        
        if roi > 100:
            st.success(f"✅ High ROI: Intervention recommended!")
        elif roi > 0:
            st.info(f"ℹ️ Positive ROI: Consider intervention")
        else:
            st.warning(f"⚠️ Negative ROI: Monitor situation")

# ============================================================================
# COMPETITIVE ANALYSIS SECTION
# ============================================================================
st.markdown("---")
st.header("🏆 Competitive Analysis (K-Beauty)")

brands = ["Laneige", "COSRX", "Innisfree", "Etude House"]
comp_data = []

for brand in brands:
    brand_df = df[df["category"].str.contains(brand, na=False)]
    
    if brand_df.empty:
        continue
    
    # Get latest snapshot for each product
    for pid in brand_df["product_id"].unique():
        product_df = brand_df[brand_df["product_id"] == pid].sort_values("captured_at", ascending=False)
        if not product_df.empty:
            row = product_df.iloc[0]
            
            # Calculate trend
            trend = "→"
            if len(product_df) >= 2:
                prev_rank = product_df.iloc[1]["rank"]
                curr_rank = row["rank"]
                if curr_rank < prev_rank:
                    trend = "↑"
                elif curr_rank > prev_rank:
                    trend = "↓"
            
            comp_data.append({
                "Brand": brand,
                "Product": row["title"][:40] + "..." if len(row["title"]) > 40 else row["title"],
                "Rank": f"#{row['rank']}" if row['rank'] > 0 else "N/A",
                "Trend": trend,
                "Price": f"${row['price']:.2f}",
                "Rating": f"{row['rating']:.1f}⭐",
                "Reviews": f"{row['review_count']:,}",
                "Updated": row["captured_at"].strftime("%m/%d %H:%M"),
            })

if comp_data:
    comp_df = pd.DataFrame(comp_data)
    
    st.dataframe(
        comp_df,
        use_container_width=True,
        height=350,
        hide_index=True,
    )
    
    # Competitive metrics
    laneige_ranks = comp_df[comp_df["Brand"] == "Laneige"]["Rank"].apply(
        lambda x: int(x.replace("#", "")) if x != "N/A" else 9999
    )
    competitor_ranks = comp_df[comp_df["Brand"] != "Laneige"]["Rank"].apply(
        lambda x: int(x.replace("#", "")) if x != "N/A" else 9999
    )
    
    laneige_avg = laneige_ranks.mean() if len(laneige_ranks) > 0 else 0
    competitor_avg = competitor_ranks.mean() if len(competitor_ranks) > 0 else 0
    
    metric_cols = st.columns(3)
    metric_cols[0].metric("Laneige Avg Rank", f"#{laneige_avg:.0f}" if laneige_avg > 0 else "N/A")
    metric_cols[1].metric("Competitor Avg Rank", f"#{competitor_avg:.0f}" if competitor_avg > 0 else "N/A")
    
    if laneige_avg > 0 and competitor_avg > 0:
        if laneige_avg < competitor_avg:
            metric_cols[2].success("✅ Laneige Leading")
        else:
            metric_cols[2].warning("⚠️ Competitors Leading")
else:
    st.info("No competitive data available. Collect data using:\n`PYTHONPATH=. python scripts/collect.py --source amazon_product`")

# ============================================================================
# RANKING TREND CHART
# ============================================================================
st.markdown("---")
st.subheader("📈 Ranking Trend Chart")

chart_products = st.multiselect(
    "Select Products to Compare",
    df["product_id"].unique()[:10] if not df.empty else [],
    default=[],
    format_func=lambda x: f"{x} - {df[df['product_id']==x].iloc[0]['title'][:30]}..." if not df.empty else x
)

if chart_products:
    chart_data = df[df["product_id"].isin(chart_products)].sort_values("captured_at")
    
    import altair as alt
    
    # Unified color scheme for charts
    chart = alt.Chart(chart_data).mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("captured_at:T", title="Time", axis=alt.Axis(format="%m/%d %H:%M")),
        y=alt.Y("rank:Q", title="Ranking Position", scale=alt.Scale(reverse=True)),
        color=alt.Color("product_id:N", title="Product", scale=alt.Scale(scheme="category10")),
        tooltip=[
            alt.Tooltip("captured_at:T", title="Time", format="%m/%d %H:%M"),
            alt.Tooltip("product_id:N", title="Product"),
            alt.Tooltip("rank:Q", title="Rank"),
            alt.Tooltip("price:Q", title="Price", format="$.2f")
        ]
    ).properties(
        height=350
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("Select products above to view ranking trends over time")

# Footer with usage instructions
st.markdown("---")
st.caption("""
**Usage Instructions:**
1. Collect data: `PYTHONPATH=. python scripts/collect.py --source amazon_product`
2. Generate reports: `PYTHONPATH=. python scripts/analyze.py`
3. View dashboard: `streamlit run app.py`

**TODO:** CSV/Excel export, internationalization (i18n), scheduled data refresh, advanced filtering
""")