"""
Database Initialization Script

Creates all database tables defined in models.py using SQLAlchemy metadata.
This script should be run once during initial setup or after schema changes.

Usage:
    PYTHONPATH=. python scripts/init_db.py

Operations:
    - Creates product_snapshots table with indexes
    - Creates why_reports table with unique constraints
    - Idempotent: Safe to run multiple times (uses CREATE TABLE IF NOT EXISTS)

Notes:
    - Requires DATABASE_URL in .env file
    - Does not drop existing tables (preserves data)
    - For schema migrations, consider using Alembic

TODO:
    - Add Alembic migrations for production schema changes
    - Add database backup before init in production
    - Add schema version tracking
"""
from src.db import engine
from src.models import Base

# Create all tables defined in Base metadata
Base.metadata.create_all(bind=engine)
print("✅ Database tables created successfully.")
