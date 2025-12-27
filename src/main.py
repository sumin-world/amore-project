import os
from datetime import datetime
import pandas as pd
from .config import DATA_DIR

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    ymd = datetime.now().strftime("%Y%m%d")

    df = pd.DataFrame([
        {"rank": 1, "brand": "OTHERS", "name": "Example Product A", "date": today},
        {"rank": 2, "brand": "LANEIGE", "name": "LANEIGE Example Product", "date": today},
    ])

    out = os.path.join(DATA_DIR, f"ranking_{ymd}.csv")
    df.to_csv(out, index=False, encoding="utf-8-sig")

    laneige = df[df["brand"] == "LANEIGE"]
    print(f"[OK] saved: {out}")
    print(f"[SUMMARY] laneige_items={len(laneige)}")

if __name__ == "__main__":
    main()
