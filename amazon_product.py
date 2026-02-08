"""
Direct ASIN tracking via Playwright.

Fetches individual product detail pages to extract title, price, rating,
review count, image URL, and Best Sellers Rank (BSR). Includes minimal
CAPTCHA detection with optional manual-solve wait.

Env vars:
    PW_HEADLESS          "true"/"false" (default: true)
    PW_WAIT_ON_CAPTCHA_SEC  seconds to wait on CAPTCHA (default: 0)
    PW_STORAGE_STATE     path to Playwright storage state JSON (optional)
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from typing import Dict, List

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from src.config import settings
from src.sources.base import Source, ProductItem

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


def _to_float(s: str) -> float:
    try:
        return float(s.replace("$", "").replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _to_int(s: str) -> int:
    try:
        nums = re.findall(r"\d+", s.replace(",", ""))
        return int(nums[0]) if nums else 0
    except (ValueError, IndexError):
        return 0


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
    """Curated ASIN tracking for Laneige + K-beauty competitors."""

    TARGET_PRODUCTS: Dict[str, Dict[str, str]] = {
        # Laneige
        "B07KNTK3QG": {"brand": "Laneige",     "name": "Water Sleeping Mask"},
        "B00LUSHW18": {"brand": "Laneige",     "name": "Lip Sleeping Mask"},
        "B084GYN2K4": {"brand": "Laneige",     "name": "Cream Skin Refiner"},
        # Competitors
        "B00PBX3L7K": {"brand": "COSRX",       "name": "Snail Mucin"},
        "B016NRXO06": {"brand": "COSRX",       "name": "Low pH Cleanser"},
        "B07YZ8MJQY": {"brand": "Innisfree",   "name": "Green Tea Serum"},
        "B01N5SMQM3": {"brand": "Etude House", "name": "SoonJung Toner"},
    }

    # ── single ASIN ─────────────────────────────────────────────────────

    def fetch_asin(self, asin: str) -> ProductItem:
        url = f"https://www.amazon.com/dp/{asin}"
        captured_at = datetime.utcnow()

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
                print(f"[CAPTCHA] {asin} — waiting {wait_sec}s")
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
        meta = self.TARGET_PRODUCTS.get(asin, {"brand": "Unknown", "name": "Unknown"})

        # Title
        el = soup.select_one("#productTitle")
        title = el.get_text(strip=True) if el else meta["name"]

        # Price (multiple fallback selectors)
        price = 0.0
        for sel in ("span.a-price span.a-offscreen",
                     "#corePriceDisplay_desktop_feature_div span.a-offscreen"):
            el = soup.select_one(sel)
            if el:
                price = _to_float(el.get_text(strip=True))
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
            review_count = _to_int(el.get_text(strip=True))

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
        for asin, meta in self.TARGET_PRODUCTS.items():
            try:
                it = self.fetch_asin(asin)
                print(
                    f"  ✓ {meta['brand']:<11} | {meta['name']:<22} "
                    f"| Rank: {it.rank:>6} | ${it.price:.2f}"
                )
                items.append(it)
            except Exception as e:
                print(f"  ✗ {asin} ({meta['brand']}): {e}")
            time.sleep(settings.request_sleep_sec * 1.5)
        return items
