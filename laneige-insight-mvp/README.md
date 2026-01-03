# Laneige INSIGHT MVP

Amazon product ranking analysis system with AI-powered insights for K-beauty products.

## Features

- **Data Collection**: Scrape Amazon Best Sellers and individual product pages
- **Change Detection**: Track ranking, price, review, and rating changes
- **Why Reports**: AI-powered (Groq/Claude) or rule-based analysis of ranking changes
- **ROI Simulation**: Calculate potential impact of ranking interventions
- **Competitive Analysis**: Compare performance across K-beauty brands
- **Dashboard**: Streamlit web interface for visualization

## Quick Start

### 1. Setup Environment

```bash
# Clone repository and navigate to project
cd laneige-insight-mvp

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for web scraping)
playwright install chromium

# Create .env file from template
cp .env.example .env
# Edit .env and configure DATABASE_URL (required)
```

### 2. Initialize Database

```bash
PYTHONPATH=. python scripts/init_db.py
```

### 3. Collect Data

```bash
# Collect from predefined ASIN list (recommended for testing)
PYTHONPATH=. python scripts/collect.py --source amazon_product

# Or collect from Best Sellers page
PYTHONPATH=. python scripts/collect.py --source amazon_bestsellers --url "https://www.amazon.com/gp/bestsellers/beauty/..."

# Filter by keyword
PYTHONPATH=. python scripts/collect.py --source amazon_product --keyword laneige
```

### 4. Analyze Changes

```bash
PYTHONPATH=. python scripts/analyze.py
```

### 5. Launch Dashboard

```bash
streamlit run app.py
```

## Configuration

### Environment Variables (.env)

- **DATABASE_URL** (required): SQLAlchemy database connection string
  - SQLite: `sqlite+pysqlite:///./data/laneige_insight.db`
  - PostgreSQL: `postgresql://user:pass@host:port/db`

- **REQUEST_SLEEP_SEC** (optional, default: 1.2): Delay between HTTP requests

- **USE_GROQ** (optional, default: true): Enable Groq LLM for Why Reports
- **GROQ_API_KEY** (optional): Groq API key (get free at groq.com)

- **USE_CLAUDE** (optional, default: false): Enable Claude LLM for Why Reports  
- **ANTHROPIC_API_KEY** (optional): Anthropic API key

**Note**: If no LLM APIs are configured, the system uses rule-based fallback.

## Project Structure

```
laneige-insight-mvp/
├── scripts/
│   ├── collect.py          # Data collection script
│   ├── analyze.py          # Analysis and Why Report generation
│   └── init_db.py          # Database initialization
├── src/
│   ├── sources/            # Data source implementations
│   │   ├── amazon_bestsellers.py
│   │   ├── amazon_product.py
│   │   ├── amazon_search.py
│   │   └── base.py
│   ├── pipeline/           # Data processing pipeline
│   │   ├── collector.py    # Snapshot persistence
│   │   ├── detector.py     # Change detection
│   │   └── why.py          # Why Report generation
│   ├── utils/              # Utility modules
│   │   └── images.py       # Image hashing
│   ├── models.py           # Database models
│   ├── db.py              # Database connection
│   └── config.py          # Configuration management
├── app.py                  # Streamlit dashboard
├── requirements.txt        # Python dependencies
└── .env.example           # Environment template
```

## Data Sources

### amazon_product (Recommended)
Tracks specific ASINs from a curated list. Best for:
- Focused product monitoring
- Competitive benchmarking
- Long-term trend analysis

Edit `src/sources/amazon_product.py` to customize the product list.

### amazon_bestsellers
Scrapes Best Sellers pages. Best for:
- Market overview
- New product discovery
- Category trending

Requires URL parameter pointing to Amazon Best Sellers page.

### amazon_search (Experimental)
Searches Amazon for keywords. Best for:
- Brand monitoring
- Product discovery
- Competitive intelligence

## Testing

```bash
# Test imports
python -c "from src.config import settings; print('✓ Config OK')"

# Test database
PYTHONPATH=. python scripts/init_db.py

# Test collection (minimal)
PYTHONPATH=. python scripts/collect.py --source amazon_product --keyword TEST

# Test analysis
PYTHONPATH=. python scripts/analyze.py
```

## Deployment

### Local Development
Follow Quick Start instructions above.

### Production Considerations
1. Use PostgreSQL instead of SQLite for concurrent access
2. Configure LLM APIs (Groq recommended for cost)
3. Set up cron jobs for periodic collection/analysis
4. Add monitoring and alerting
5. Review rate limiting (REQUEST_SLEEP_SEC)
6. Consider proxy rotation for high-volume scraping

## Troubleshooting

### "DATABASE_URL empty" error
- Ensure `.env` file exists with `DATABASE_URL` configured
- Check `.env.example` for proper format

### "Module not found" errors
- Run `pip install -r requirements.txt`
- For Playwright: `playwright install chromium`

### Bot detection / Access denied
- Increase `REQUEST_SLEEP_SEC` value
- Check if IP is blocked (try different network)
- Consider using proxies

### No Why Reports generated
- Run `scripts/analyze.py` after collecting data
- Ensure at least 2 snapshots exist per product
- Check LLM API configuration if expecting AI reports

## Future Enhancements (TODOs)

See inline code comments for detailed TODOs. Key future features:
- CSV/Excel export functionality
- Internationalization (multi-language support)
- Scheduled collection/analysis (cron-like)
- Advanced filtering (date ranges, multiple ASINs)
- Competitive comparison extensions
- Expansion to new markets (Japan, SE Asia)
- Mobile-responsive dashboard

## License

See repository root for license information.

## Contributing

See repository root for contribution guidelines.
