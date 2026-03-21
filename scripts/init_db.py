"""Create all database tables. Safe to run multiple times (IF NOT EXISTS)."""

import logging

from src.db import engine
from src.models import Base

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

Base.metadata.create_all(bind=engine)
logging.getLogger(__name__).info("Database tables created.")
