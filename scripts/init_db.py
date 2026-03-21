"""Create all database tables. Safe to run multiple times (IF NOT EXISTS)."""

from src.db import engine
from src.models import Base

Base.metadata.create_all(bind=engine)
print("Database tables created.")
