"""
Database Connection Management

This module configures SQLAlchemy engine and session factory for database operations.
Implements connection pooling and health checks for production reliability.

Database Strategy:
    - SQLite for MVP (simple, no server, file-based)
    - Connection pooling for reuse and efficiency
    - Health checks (pool_pre_ping) for stale connections
    - Session management via context managers in application code

Connection Pooling:
    - SQLite: Single connection (not thread-safe for writes)
    - PostgreSQL: Pool of 5-20 connections (configurable)
    - pool_pre_ping: Checks connection health before use
    - Prevents "database is locked" and "connection closed" errors

TODO:
    - Add connection pool size configuration
    - Add connection pool timeout settings
    - Implement read replica support for scaling
    - Add connection retry logic with exponential backoff
    - Add database migration management (Alembic)
    - Add query performance monitoring
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.config import settings

# Create database engine with connection health checks
# pool_pre_ping=True: Test connection before use, reconnect if stale
# This prevents "connection closed" errors in long-running applications
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Test connection liveness before use
    # TODO: Add pool_size and max_overflow for production PostgreSQL
    # pool_size=10,  # Number of persistent connections
    # max_overflow=20,  # Additional connections when pool exhausted
)

# Session factory for database operations
# Usage:
#   db = SessionLocal()
#   try:
#       # Use db for queries
#       db.commit()
#   finally:
#       db.close()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,  # Manual flush control for batch operations
    autocommit=False  # Explicit transaction control
)
