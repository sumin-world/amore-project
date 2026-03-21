"""
Direct ASIN tracking via Playwright.

Fetches individual product detail pages to extract title, price, rating,
review count, image URL, and Best Sellers Rank (BSR). Includes minimal
CAPTCHA detection with optional manual-solve wait.

Target products are loaded from config/products.json (configurable).

Env vars:
    PW_HEADLESS            "true"/"false" (default: true)
    PW_WAIT_ON_CAPTCHA_SEC seconds to wait on CAPTCHA (default: 0)
    PW_STORAGE_STATE       path to Playwright storage state JSON (optional)
    PRODUCTS_CONFIG        path to products JSON file (optional)
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, List

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from src.config import settings, load_target_products
from src.sources.base import Source, ProductItem
from src.utils.parsing import to_float, to_int

logger = logging.getLogger(__name__)

_BSR_RE = re.compile(r"#\s*([\d,]+)\s+in\b", re.IGNORECASE)


# ── helpers ──────────────────────────────────────────────────────────────

def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return v.strip().lower() in ("1", "true", "yes", "y", "on") if v else default


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    try:
        return int(v.strip()) if v else default
    except ValueError:
        return default


def _looks_like_captcha(html: str) -> bool:
    h = (html or "").lower()
    return any(
        k in h
        for k in (
            "robot check",
            "captcha",
            "enter the characters you see below",
            "sorry, we just need to make sure",
        )
    )


# ── source ───────────────────────────────────────────────────────────────

class AmazonProduct(Source):
    """Configurable ASIN tracking with CAPTCHA detection."""

    def __init__(self, products: Dict[str, Dict[str, str]] | None = None):
        config_path = os.getenv("PRODUCTS_CONFIG")
        self.target_products = products or load_target_products(config_path)

    # ── single ASIN ─────────────────────────────────────────────────────

    def fetch_asin(self, asin: str) -> ProductItem:
        url = f"https://www.amazon.com/dp/{asin}"
        captured_at = datetime.now(timezone.utc)

        headless = _env_bool("PW_HEADLESS", True)
        wait_sec = _env_int("PW_WAIT_ON_CAPTCHA_SEC", 0)
        storage_path = os.getenv("PW_STORAGE_STATE", "").strip()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)

            ctx_kwargs = {}
            if storage_path and os.path.exists(storage_path):
                ctx_kwargs["storage_state"] = storage_path

            context = browser.new_context(**ctx_kwargs)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(settings.request_sleep_sec)
            html = page.content()

            if _looks_like_captcha(html) and wait_sec > 0:
                logger.warning("CAPTCHA detected for %s — waiting %ds", asin, wait_sec)
                page.wait_for_timeout(wait_sec * 1000)
                time.sleep(1.0)
                html = page.content()
                if storage_path:
                    os.makedirs(os.path.dirname(storage_path) or ".", exist_ok=True)
                    context.storage_state(path=storage_path)

            if _looks_like_captcha(html):
                context.close()
                browser.close()
                raise RuntimeError("Blocked by CAPTCHA")

            context.close()
            browser.close()

        soup = BeautifulSoup(html, "lxml")
        meta = self.target_products.get(asin, {"brand": "Unknown", "name": "Unknown"})

        # Title
        el = soup.select_one("#productTitle")
        title = el.get_text(strip=True) if el else meta["name"]

        # Price (multiple fallback selectors)
        price = 0.0
        for sel in ("span.a-price span.a-offscreen",
                     "#corePriceDisplay_desktop_feature_div span.a-offscreen"):
            el = soup.select_one(sel)
            if el:
                price = to_float(el.get_text(strip=True))
                break

        # Rating
        rating = 0.0
        el = soup.select_one("span.a-icon-alt")
        if el:
            try:
                rating = float(el.get_text(strip=True).split()[0])
            except (ValueError, IndexError):
                pass

        # Review count
        review_count = 0
        el = soup.select_one("#acrCustomerReviewText")
        if el:
            review_count = to_int(el.get_text(strip=True))

        # Image
        img_el = soup.select_one("#landingImage")
        image_url = img_el.get("src", "") if img_el else ""

        # Best Sellers Rank
        rank = -1
        th = soup.find("th", string=re.compile(r"Best Sellers Rank", re.IGNORECASE))
        if th and th.find_next("td"):
            m = _BSR_RE.search(th.find_next("td").get_text(" ", strip=True))
            if m:
                rank = int(m.group(1).replace(",", ""))

        return ProductItem(
            source="amazon_product",
            market="US",
            category=f"Target Tracking - {meta['brand']}",
            captured_at=captured_at,
            rank=rank,
            product_id=asin,
            title=title,
            product_url=url,
            price=price,
            rating=rating,
            review_count=review_count,
            image_url=image_url,
            raw={"brand": meta["brand"], "name": meta["name"]},
        )

    # ── batch ────────────────────────────────────────────────────────────

    def fetch(self, url: str) -> List[ProductItem]:
        items: List[ProductItem] = []
        for asin, meta in self.target_products.items():
            try:
                it = self.fetch_asin(asin)
                logger.info(
                    "OK %s | %s | Rank: %d | $%.2f",
                    meta["brand"], meta["name"], it.rank, it.price,
                )
                items.append(it)
            except Exception as e:
                logger.error("Failed %s (%s): %s", asin, meta["brand"], e)
            time.sleep(settings.request_sleep_sec * 1.5)
        return items
