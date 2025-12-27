import os, glob
import pandas as pd
import streamlit as st
from .config import DATA_DIR

st.set_page_config(page_title="Trend Monitor", layout="wide")
st.title("Global Trend Monitor (Demo-safe)")

if not os.path.exists(DATA_DIR):
    st.error(f"DATA_DIR not found: {DATA_DIR}")
    st.stop()

files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
if not files:
    st.warning("CSV가 없습니다. 먼저 make run 하세요.")
    st.stop()

latest = max(files, key=os.path.getctime)
df = pd.read_csv(latest)

st.caption(f"latest file: {os.path.basename(latest)}")
st.dataframe(df, use_container_width=True, hide_index=True)
