# Laneige INSIGHT MVP

**Automated Market Intelligence for K-Beauty on Amazon**

An end-to-end pipeline that captures product ranking snapshots, detects changes, generates AI-powered root-cause reports, and simulates ROI for interventions — all in a single Streamlit dashboard.

---

## Architecture

```
Data Sources              Pipeline                    Output
┌──────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│ Amazon       │    │ Collector        │    │ Streamlit Dashboard  │
│  - ASIN list │───>│  snapshot + pHash│───>│  - Snapshot table    │
│  - Bestseller│    │                  │    │  - Why Reports       │
│  - Search    │    │ Detector         │    │  - ROI simulator     │
│  - Keepa API │    │  score_drivers() │    │  - Competitive view  │
└──────────────┘    │                  │    │  - Trend charts      │
                    │ Why Report       │    └─────────────────────┘
                    │  Groq → Claude   │
                    │  → rule fallback │
                    └──────────────────┘
```

### Data Flow

1. **Collect** — Scrape or pull product data (rank, price, rating, reviews, thumbnail) and persist as timestamped snapshots with perceptual image hashes.
2. **Detect** — Compare the two most recent snapshots per product; score each driver (price Δ, review velocity, image change, etc.).
3. **Explain** — Generate a concise Why Report via LLM (Groq free-tier → Claude → deterministic rules as fallback).
4. **Simulate** — Estimate weekly loss, intervention cost, expected gain, and ROI%.

---

## Key Features

| Module | Description |
|---|---|
| **Snapshot Collector** | Persists product state with pHash-based image fingerprinting |
| **Change Detector** | Scores ranking drivers across price, reviews, rating, and thumbnails |
| **Why Report Generator** | LLM-first with guaranteed rule-based fallback |
| **ROI Simulator** | Translates rank deltas into dollar-denominated action plans |
| **Competitive Dashboard** | Side-by-side K-beauty brand comparison (Laneige vs COSRX, Innisfree, Etude House) |

---

## Quick Start

### Prerequisites

- Python 3.10+
- (Optional) Chromium for Playwright — only needed for live scraping

### 1. Install

```bash
cd laneige-insight-mvp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# edit .env — at minimum set DATABASE_URL
```

### 3. Initialize Database

```bash
PYTHONPATH=. python scripts/init_db.py
```

### 4. Run (Demo Mode)

```bash
bash run_demo.sh
# or manually:
DEMO_MODE=1 PYTHONPATH=. python scripts/analyze.py
streamlit run app.py --server.port 8502
```

Open `http://localhost:8502`.

### 5. Run (Live Collection)

```bash
# Collect from curated ASIN list
PYTHONPATH=. python scripts/collect.py --source amazon_product

# Or from Bestsellers page
PYTHONPATH=. python scripts/collect.py --source amazon_bestsellers \
  --url "https://www.amazon.com/gp/bestsellers/beauty/..."

# Analyze and generate reports
PYTHONPATH=. python scripts/analyze.py

# Launch dashboard
streamlit run app.py
```

---

## Project Structure

```
laneige-insight-mvp/
├── src/
│   ├── config.py               # Pydantic settings (env validation)
│   ├── db.py                   # SQLAlchemy engine + session factory
│   ├── models.py               # ORM models (ProductSnapshot, WhyReport)
│   ├── sources/
│   │   ├── base.py             # Abstract Source + ProductItem dataclass
│   │   ├── amazon_bestsellers.py
│   │   ├── amazon_product.py   # Direct ASIN tracking with CAPTCHA handling
│   │   ├── amazon_search.py    # Keyword-based discovery
│   │   └── amazon_keepa.py     # Keepa API (ToS-friendly alternative)
│   ├── pipeline/
│   │   ├── collector.py        # Snapshot persistence + image hashing
│   │   ├── detector.py         # Change detection + driver scoring
│   │   └── why.py              # Report generation (LLM + fallback)
│   └── utils/
│       └── images.py           # pHash computation + image fetching
├── scripts/
│   ├── init_db.py              # Create tables
│   ├── collect.py              # Data collection CLI
│   └── analyze.py              # Analysis + report generation
├── app.py                      # Streamlit dashboard
├── run_demo.sh                 # One-command demo launcher
├── requirements.txt
└── .env.example
```

---

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | SQLAlchemy connection string |
| `REQUEST_SLEEP_SEC` | | `1.2` | Delay between HTTP requests (seconds) |
| `USE_GROQ` | | `true` | Enable Groq LLM for reports |
| `GROQ_API_KEY` | | — | Groq API key (free tier) |
| `USE_CLAUDE` | | `false` | Enable Claude LLM for reports |
| `ANTHROPIC_API_KEY` | | — | Anthropic API key |
| `DEMO_MODE` | | `false` | Disable live collection for safe demos |

> If no LLM keys are configured, the system uses deterministic rule-based fallback.

---

## Data Sources

| Source | Best For | Notes |
|---|---|---|
| `amazon_product` | Focused ASIN tracking | Curated list, tracks BSR + detail metrics |
| `amazon_bestsellers` | Category overview | Top-20 from any Bestsellers page |
| `amazon_search` | Brand discovery | Keyword search, experimental |
| `amazon_keepa` | ToS-friendly collection | Requires Keepa API key |

---

## Technical Highlights

- **Perceptual Hashing (pHash)**: 64-bit image fingerprints detect thumbnail A/B tests and rebranding with a Hamming distance threshold of 10 bits (~15.6% tolerance).
- **Fault-Tolerant LLM Pipeline**: Groq (free) → Claude (paid) → rule-based, each isolated with independent error handling.
- **Upsert Logic**: Why Reports are deduplicated by product + time window via unique constraints.
- **Composite Indexing**: `(source, market, category, product_id, captured_at)` optimizes the primary query path.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `RuntimeError: DATABASE_URL empty` | Set `DATABASE_URL` in `.env` |
| `no such table: product_snapshots` | Run `PYTHONPATH=. python scripts/init_db.py` |
| `Playwright Executable doesn't exist` | Run `playwright install chromium` |
| Bot detection / CAPTCHA | Increase `REQUEST_SLEEP_SEC` or use `amazon_keepa` source |
| `Saved 0 snapshots` | Check DEMO_MODE, API keys, or network access |

---

## License

See repository root for license information.
