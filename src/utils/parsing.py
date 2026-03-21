"""Shared parsing helpers for numeric extraction from scraped text."""

import re


def to_float(s: str) -> float:
    """Extract a float from a price-like string (e.g. '$29.99', '1,234.56')."""
    try:
        return float(s.replace("$", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def to_int(s: str) -> int:
    """Extract the first integer from a string (e.g. '1,234 ratings' → 1234)."""
    try:
        nums = re.findall(r"\d+", s.replace(",", ""))
        return int(nums[0]) if nums else 0
    except (ValueError, AttributeError, IndexError):
        return 0
