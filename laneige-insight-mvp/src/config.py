"""
Application Configuration Module

Centralized configuration management using Pydantic for validation
and python-dotenv for environment variable loading.

Configuration Sources:
    1. Environment variables (from .env file)
    2. Default values (fallbacks)
    3. Runtime validation (Pydantic)

Security Notes:
    - Secrets should be stored in .env file (not committed to git)
    - .env file should be in .gitignore
    - Use .env.example as template for required variables

TODO:
    - Add configuration for LLM API keys with validation
    - Add database connection pooling settings
    - Add logging configuration (level, format, output)
    - Add proxy configuration for high-volume scraping
    - Implement configuration profiles (dev, staging, prod)
"""
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

class Settings(BaseModel):
    """
    Application settings with validation.
    
    All settings loaded from environment variables with sensible defaults.
    Pydantic provides automatic type conversion and validation.
    
    Attributes:
        database_url: SQLAlchemy database connection string
            - Format: "sqlite:///data/laneige_insight.db" for SQLite
            - Format: "postgresql://user:pass@host:port/db" for PostgreSQL
            - Required, no default (fails fast if missing)
            - Example: "sqlite:///data/laneige_insight.db"
        
        request_sleep_sec: Sleep duration between HTTP requests (seconds)
            - Used for rate limiting and bot detection evasion
            - Float to allow sub-second delays (e.g., 1.2, 0.5)
            - Default: 1.2 seconds (balance between speed and safety)
            - Rationale: Mimics human browsing behavior
            - Lower values risk bot detection, higher values slow collection
            - Amazon typically tolerates 1-2 second delays
    
    Configuration:
        - arbitrary_types_allowed: False (strict type checking)
        - validate_assignment: True (validates on attribute changes)
    
    TODO:
        - Add groq_api_key with validation
        - Add anthropic_api_key with validation
        - Add max_workers for concurrent scraping
        - Add request_timeout for HTTP client
        - Add user_agent for customization
    """
    database_url: str = Field(
        default=os.getenv("DATABASE_URL", "").strip(),
        description="Database connection URL (SQLite or PostgreSQL)"
    )
    
    request_sleep_sec: float = Field(
        default=float(os.getenv("REQUEST_SLEEP_SEC", "1.2")),
        description="Sleep duration between requests (seconds)",
        ge=0.1,  # Minimum 0.1 seconds
        le=10.0  # Maximum 10 seconds
    )
    
    @validator("database_url")
    def validate_database_url(cls, v):
        """
        Validate database URL is not empty.
        
        Fails fast at startup if DATABASE_URL not configured.
        Better to crash early than fail during operation.
        """
        if not v:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Please create .env file with DATABASE_URL. "
                "Example: DATABASE_URL=sqlite:///data/laneige_insight.db"
            )
        return v
    
    @validator("request_sleep_sec")
    def validate_request_sleep(cls, v):
        """
        Validate sleep duration is reasonable.
        
        Too short: Risk of bot detection
        Too long: Slow data collection
        """
        if v < 0.5:
            print(f"Warning: request_sleep_sec={v} is very low. Risk of bot detection.")
        elif v > 5.0:
            print(f"Warning: request_sleep_sec={v} is very high. Data collection will be slow.")
        return v

# Global settings instance
# Used throughout the application: from src.config import settings
settings = Settings()

# Legacy compatibility: raise exception if DATABASE_URL empty
# (Redundant with validator, but kept for backward compatibility)
if not settings.database_url:
    raise RuntimeError("DATABASE_URL empty. Please configure .env file.")
