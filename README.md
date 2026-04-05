# E-Commerce Market Intelligence Pipeline

**Automated product ranking analysis with change detection, AI-generated reports, and an interactive dashboard.**

Built for the [2026 Amorepacific AI Innovation Challenge](https://amorepacific-ai.notion.site) (AGENT track: Trend Analysis & Content Automation).

## Business Context

Consumer goods brands competing on e-commerce platforms face a recurring problem: **ranking changes happen fast, but understanding *why* they happen is slow and manual.** A product drops from #3 to #12 overnight — was it a competitor's price cut, a review surge, a thumbnail A/B test, or an algorithm change?

Brand managers currently monitor this by hand, checking dashboards daily and comparing screenshots. This pipeline replaces that manual cycle with an automated system that **collects, detects, explains, and quantifies** every ranking change.

### What Decisions Does This Support?

| Business Question | How This Pipeline Answers It |
|---|---|
| Why did our product ranking drop? | Change detection scores each driver (price, reviews, rating, image) and generates an AI explanation |
| Should we intervene or wait? | ROI simulator estimates weekly loss vs. intervention cost |
| How are competitors performing? | Competitive dashboard compares rankings, prices, and review velocity across brands |
| Are competitors A/B testing thumbnails? | Perceptual hashing (pHash) detects image changes with 15.6% tolerance |
| What is the trend over time? | Interactive trend charts track ranking movements across products |

## Dashboard

![Dashboard Overview](docs/dashboard-overview.png)

![Product Detail & ROI Simulator](docs/product-detail-roi.png)

![Competitive Analysis](docs/competitive-analysis.png)

![Ranking Trend](docs/ranking-trend.png)

## Problem

Tracking product ranking changes on e-commerce platforms (price shifts, review velocity, thumbnail A/B tests) and understanding *why* they happen requires manual, repetitive monitoring. This pipeline automates the cycle: collect product snapshots → detect changes → score drivers → generate explanations → visualize trends.

## Architecture

```
Data Sources              Pipeline                    Output
┌──────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│ E-commerce   │    │ Collector        │    │ Streamlit Dashboard  │
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

## Key Features

| Module | Description |
|---|---|
| **Snapshot Collector** | Persists product state with pHash-based image fingerprinting |
| **Change Detector** | Scores ranking drivers across price, reviews, rating, and thumbnails |
| **Why Report Generator** | LLM-first with guaranteed rule-based fallback |
| **ROI Simulator** | Translates rank deltas into dollar-denominated action plans |
| **Competitive Dashboard** | Dynamic multi-brand comparison with trend charts |

## Quick Start

### Prerequisites

- Python 3.10+
- (Optional) Chromium for Playwright — only needed for live scraping
- (Optional) Docker

### 1. Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# edit .env — at minimum set DATABASE_URL
# example: DATABASE_URL=sqlite+pysqlite:///./data/market_insight.db
```

To track different products, edit `config/products.json`:

```json
{
  "products": {
    "B07KNTK3QG": { "brand": "YourBrand", "name": "Product Name" }
  }
}
```

### 3. Initialize Database

```bash
PYTHONPATH=. python scripts/init_db.py
```

### 4. Run (Demo Mode — no API keys needed)

```bash
bash run_demo.sh
# or manually:
DEMO_MODE=1 PYTHONPATH=. python scripts/analyze.py
streamlit run app.py --server.port 8502
```

Open `http://localhost:8502`.

### 5. Run Tests

```bash
PYTHONPATH=. python -m pytest tests/ -v
```

### 6. Run (Live Collection)

```bash
PYTHONPATH=. python scripts/collect.py --source amazon_product
PYTHONPATH=. python scripts/analyze.py
streamlit run app.py
```

### 7. Docker

```bash
docker compose up --build
# Dashboard at http://localhost:8502
```

## Project Structure

```
├── src/
│   ├── config.py               # Pydantic settings + product config loader
│   ├── db.py                   # SQLAlchemy engine + session context manager
│   ├── models.py               # ORM models (ProductSnapshot, WhyReport)
│   ├── sources/
│   │   ├── base.py             # Abstract Source + ProductItem dataclass
│   │   ├── amazon_bestsellers.py
│   │   ├── amazon_product.py   # Configurable ASIN tracking with CAPTCHA handling
│   │   ├── amazon_search.py    # Keyword-based discovery (experimental)
│   │   └── amazon_keepa.py     # Keepa API (ToS-friendly alternative)
│   ├── pipeline/
│   │   ├── collector.py        # Snapshot persistence + image hashing
│   │   ├── detector.py         # Change detection + driver scoring
│   │   └── why.py              # Report generation (LLM + fallback)
│   └── utils/
│       ├── parsing.py          # Shared numeric parsing helpers
│       └── images.py           # pHash computation + image fetching
├── config/
│   └── products.json           # Target product definitions (configurable)
├── scripts/
│   ├── init_db.py              # Create tables
│   ├── collect.py              # Data collection CLI
│   ├── analyze.py              # Analysis + report generation
│   └── sql_analysis.py         # Statistical analysis (correlation, z-score, CV)
├── tests/                      # 63 unit tests
│   ├── test_detector.py        # Change detection + image diff (12 tests)
│   ├── test_why.py             # Rule-based report generation (8 tests)
│   ├── test_models.py          # ORM schema + constraints (4 tests)
│   ├── test_parsing.py         # Shared parsing utilities (11 tests)
│   ├── test_config.py          # Config loading (3 tests)
│   └── test_sql_analysis.py    # SQL queries + statistical functions (24 tests)
├── app.py                      # Streamlit dashboard
├── Dockerfile                  # Container image
├── docker-compose.yml          # One-command deployment (SQLite)
├── docker-compose.postgres.yml # PostgreSQL deployment
├── run_demo.sh                 # Demo launcher
├── requirements.txt
└── .env.example
```

## Configuration

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | SQLAlchemy connection string |
| `REQUEST_SLEEP_SEC` | | `1.2` | Delay between HTTP requests (seconds) |
| `USE_GROQ` | | `true` | Enable Groq LLM for reports |
| `GROQ_API_KEY` | | — | Groq API key (free tier) |
| `USE_CLAUDE` | | `false` | Enable Claude LLM for reports |
| `ANTHROPIC_API_KEY` | | — | Anthropic API key |
| `PRODUCTS_CONFIG` | | `config/products.json` | Custom product definitions |
| `DEMO_MODE` | | `false` | Disable live collection for safe demos |

If no LLM keys are configured, the system uses deterministic rule-based fallback — it always produces output.

## Technical Highlights

- **Perceptual Hashing (pHash)**: 64-bit image fingerprints detect thumbnail A/B tests and rebranding with a Hamming distance threshold of 10 bits (~15.6% tolerance).
- **Fault-Tolerant LLM Pipeline**: Groq (free) → Claude (paid) → rule-based, each isolated with independent error handling.
- **Statistical Analysis Layer**: Pearson correlation for price-rank sensitivity, z-score anomaly detection, coefficient of variation for volatility measurement — implemented in pure Python with full test coverage.
- **Dual Database Support**: SQLite for development, PostgreSQL for production — SQLAlchemy ORM abstracts the backend.
- **Upsert Logic**: Why Reports are deduplicated by product + time window via unique constraints.
- **Composite Indexing**: `(source, market, category, product_id, captured_at)` optimizes the primary query path.
- **Pluggable Data Sources**: Abstract `Source` base class; 4 built-in sources (direct ASIN, bestsellers, search, Keepa API).
- **Configurable Targets**: Product list externalized to JSON; swap tracking targets without code changes.
- **Containerized**: Dockerfile + docker-compose for one-command deployment (SQLite and PostgreSQL variants).

## SQL Analysis

The pipeline includes analytical queries that surface actionable insights from collected data. Run them via:

```bash
PYTHONPATH=. python scripts/sql_analysis.py
```

| Query | Business Purpose |
|---|---|
| Price sensitivity analysis | Measures correlation between price changes and ranking movement |
| Review velocity leaders | Identifies which products are gaining review momentum fastest |
| Ranking volatility by brand | Finds products with unstable rankings that need attention |
| Cross-metric anomaly detection | Flags products where multiple signals change simultaneously |
| Competitive gap analysis | Compares average rank, price, and review velocity across brands |

Results are printed as formatted tables and exported to `data/analysis_report.md`.

### Statistical Methods

The analysis layer applies statistical techniques beyond basic aggregation:

| Method | Application | Why It Matters |
|---|---|---|
| **Pearson Correlation** | Measures linear relationship between price changes and rank movement | Quantifies whether pricing strategy actually drives ranking — separates signal from noise |
| **Z-Score Anomaly Detection** | Flags ranking changes that are statistically unusual (\|z\| > 2.0) | Identifies events that warrant investigation vs. normal fluctuation |
| **Coefficient of Variation** | Measures relative ranking volatility per product (std/mean) | A product at rank #50 with CV=0.4 needs different treatment than rank #5 with CV=0.4 |

These methods are implemented in pure Python (no scipy/numpy dependency for the analysis layer) and tested with 17 unit tests covering edge cases.

## Database Support

The pipeline supports both **SQLite** (zero-config, good for development) and **PostgreSQL** (production-ready, concurrent access).

### SQLite (default)
```bash
DATABASE_URL=sqlite+pysqlite:///./data/market_insight.db
```

### PostgreSQL
```bash
# Using docker-compose with PostgreSQL:
docker compose -f docker-compose.postgres.yml up --build

# Or connect to an existing PostgreSQL instance:
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/market_insight
```

SQLAlchemy ORM abstracts the database layer — all queries, models, and migrations work identically on both backends.

## Limitations

- No automated scraping schedule (manual `collect.py` or cron required).
- ROI model uses a fixed linear assumption ($3,500/rank position) — not calibrated on real data.
- `amazon_search` source is experimental (single-page only).
- Playwright scraping can trigger CAPTCHA on repeated runs without rate limiting.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `RuntimeError: DATABASE_URL empty` | Set `DATABASE_URL` in `.env` |
| `no such table: product_snapshots` | Run `PYTHONPATH=. python scripts/init_db.py` |
| `Playwright Executable doesn't exist` | Run `playwright install chromium` |
| Bot detection / CAPTCHA | Increase `REQUEST_SLEEP_SEC` or use `amazon_keepa` source |
| `Saved 0 snapshots` | Check DEMO_MODE, API keys, or network access |
