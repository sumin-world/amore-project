FROM python:3.11-slim

WORKDIR /app

# System dependencies for Playwright and image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libatspi2.0-0 libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium --with-deps

# Application code
COPY . .

# Create data directory
RUN mkdir -p data

# Default environment
ENV DATABASE_URL=sqlite+pysqlite:///./data/market_insight.db
ENV DEMO_MODE=true
ENV PYTHONPATH=.

# Initialize database
RUN python scripts/init_db.py

EXPOSE 8502

CMD ["streamlit", "run", "app.py", "--server.port", "8502", "--server.address", "0.0.0.0"]
