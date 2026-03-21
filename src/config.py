"""Centralized configuration with Pydantic validation and .env loading."""

import os
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

load_dotenv()


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

    @validator("database_url")
    def _nonempty_url(cls, v):
        if not v:
            raise ValueError(
                "DATABASE_URL is required. "
                "Example: DATABASE_URL=sqlite+pysqlite:///./data/laneige_insight.db"
            )
        return v


settings = Settings()
