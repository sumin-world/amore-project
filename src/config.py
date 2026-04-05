"""Centralized configuration with Pydantic validation and .env loading."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── project root ────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    database_url: str = Field(
        default=os.getenv("DATABASE_URL", "").strip(),
        description="SQLAlchemy connection string",
    )
    request_sleep_sec: float = Field(
        default=float(os.getenv("REQUEST_SLEEP_SEC", "1.2")),
        description="Delay between HTTP requests (seconds)",
        ge=0.1,
        le=10.0,
    )

    @field_validator("database_url")
    @classmethod
    def _nonempty_url(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "DATABASE_URL is required. "
                "Example: DATABASE_URL=sqlite+pysqlite:///./data/market_insight.db"
            )
        return v


settings = Settings()


def load_target_products(path: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """Load target product definitions from a JSON config file.

    Falls back to config/products.json in the project root.
    Returns {ASIN: {"brand": ..., "name": ...}} mapping.
    """
    if path is None:
        path = str(PROJECT_ROOT / "config" / "products.json")

    config_path = Path(path)
    if not config_path.exists():
        logger.warning("Product config not found at %s, using empty product list", path)
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    products = data.get("products", {})
    logger.info("Loaded %d target products from %s", len(products), path)
    return products
