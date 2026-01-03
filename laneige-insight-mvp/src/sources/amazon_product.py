"""
Amazon Product Direct Tracking (ASIN Fixed Tracking Mode)

- Curated ASIN list tracking (portfolio + competitors)
- Uses Playwright to fetch product detail pages
- Extracts: title, price, rating, review_count, image_url, Best Sellers Rank (BSR)

Captcha handling (minimal):
- If captcha is detected and PW_WAIT_ON_CAPTCHA_SEC > 0, waits (use PW_HEADLESS=false to solve manually)
- If still blocked after waiting, raises Exception (item skipped)

Env:
- PW_HEADLESS: "true"/"false" (default: true)
- PW_WAIT_ON_CAPTCHA_SEC: seconds to wait on captcha (default: 0)
- PW_STORAGE_STATE: path to storage_state json (optional; if exists, will be loaded; if set, will be saved after wait)
- REQUEST_SLEEP_SEC: delay between requests (already in settings via .env)
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from typing import List, Dict

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from src.config import settings
from src.sources.base import Source, ProductItem

_BSR_RE = re.compile(r"#\s*([\d,]+)\s+in\b", re.IGNORECASE)


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    try:
        return int(v.strip())
    except Exception:
        return default


def _to_float(s: str) -> float:
    try:
        return float(s.replace("$", "").replace(",", "").strip())
    except Exception:
        return 0.0


def _to_int(s: str) -> int:
    try:
        s = s.replace(",", "")
        m = re.findall(r"\d+", s)
        return int(m[0]) if m else 0
    except Exception:
        return 0


def _looks_like_captcha(html: str) -> bool:
    if not html:
        return False
    h = html.lower()
    keys = [
        "robot check",
        "captcha",
        "enter the characters you see below",
        "sorry, we just need to make sure",
    ]
    return any(k in h for k in keys)


class AmazonProduct(Source):
    """
    Direct ASIN tracking for curated product lists.
    """

    TARGET_PRODUCTS: Dict[str, Dict[str, str]] = {
        # Laneige
        "B07KNTK3QG": {"brand": "Laneige", "name": "Water Sleeping Mask"},
        "B00LUSHW18": {"brand": "Laneige", "name": "Lip Sleeping Mask"},
        "B084GYN2K4": {"brand": "Laneige", "name": "Cream Skin Refiner"},

        # Competitors (K-beauty)
        "B00PBX3L7K": {"brand": "COSRX", "name": "Snail Mucin"},
        "B016NRXO06": {"brand": "COSRX", "name": "Low pH Cleanser"},
        "B07YZ8MJQY": {"brand": "Innisfree", "name": "Green Tea Serum"},
        "B01N5SMQM3": {"brand": "Etude House", "name": "SoonJung Toner"},
    }

    def fetch_asin(self, asin: str) -> ProductItem:
        url = f"https://www.amazon.com/dp/{asin}"
        captured_at = datetime.utcnow()

        headless = _env_bool("PW_HEADLESS", True)
        wait_sec = _env_int("PW_WAIT_ON_CAPTCHA_SEC", 0)
        storage_state_path = os.getenv("PW_STORAGE_STATE", "").strip()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)

            context_kwargs = {}
            if storage_state_path and os.path.exists(storage_state_path):
                context_kwargs["storage_state"] = storage_state_path

            context = browser.new_context(**context_kwargs)
            page = context.new_page()

            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(float(settings.request_sleep_sec))

            html = page.content()

            # If captcha, allow manual solve when headless=false
            if _looks_like_captcha(html) and wait_sec > 0:
                print(f"[CAPTCHA] Detected for {asin}. Waiting up to {wait_sec}s (PW_HEADLESS={headless})...")
                page.wait_for_timeout(wait_sec * 1000)
                time.sleep(1.0)
                html = page.content()

                # save storage state after possible manual solve
                if storage_state_path:
                    os.makedirs(os.path.dirname(storage_state_path), exist_ok=True)
                    context.storage_state(path=storage_state_path)

            # still blocked -> skip
            if _looks_like_captcha(html):
                context.close()
                browser.close()
                raise Exception("Blocked by captcha check (try PW_HEADLESS=false + PW_WAIT_ON_CAPTCHA_SEC)")

            context.close()
            browser.close()

        soup = BeautifulSoup(html, "lxml")

        # Title
        title_el = soup.select_one("#productTitle")
        title = title_el.get_text(strip=True) if title_el else ""

        # Price (multiple fallbacks)
        price = 0.0
        price_el = soup.select_one("span.a-price span.a-offscreen")
        if price_el:
            price = _to_float(price_el.get_text(strip=True))
        else:
            price_el2 = soup.select_one("#corePriceDisplay_desktop_feature_div span.a-offscreen")
            if price_el2:
                price = _to_float(price_el2.get_text(strip=True))

        # Rating
        rating = 0.0
        rating_el = soup.select_one("span.a-icon-alt")
        if rating_el:
            try:
                rating = float(rating_el.get_text(strip=True).split(" ")[0])
            except Exception:
                rating = 0.0

        # Review count
        review_count = 0
        review_el = soup.select_one("#acrCustomerReviewText")
        if review_el:
            review_count = _to_int(review_el.get_text(strip=True))

        # Image
        image_url = ""
        img_el = soup.select_one("#landingImage")
        if img_el:
            image_url = img_el.get("src", "") or ""

        # Best Sellers Rank (BSR)
        rank = -1
        th = soup.find("th", string=re.compile(r"Best Sellers Rank", re.IGNORECASE))
        if th and th.find_next("td"):
            txt = th.find_next("td").get_text(" ", strip=True)
            m = _BSR_RE.search(txt)
            if m:
                rank = int(m.group(1).replace(",", ""))

        meta = self.TARGET_PRODUCTS.get(asin, {"brand": "Unknown", "name": "Unknown"})

        return ProductItem(
            source="amazon_product",
            market="US",
            category=f"Target Tracking - {meta['brand']}",
            captured_at=captured_at,
            rank=rank,  # BSR rank, -1 if not ranked/unknown
            product_id=asin,
            title=title or meta["name"],
            product_url=url,
            price=price,
            rating=rating,
            review_count=review_count,
            image_url=image_url,
            raw={"brand": meta["brand"], "name": meta["name"]},
        )

    def fetch(self, url: str) -> List[ProductItem]:
        items: List[ProductItem] = []

        for asin, meta in self.TARGET_PRODUCTS.items():
            try:
                it = self.fetch_asin(asin)
                print(f"✓ {meta['brand']:<11} | {meta['name']:<22} | Rank: {it.rank:>4} | ${it.price:.2f}")
                items.append(it)
            except Exception as e:
                print(f"✗ {asin} ({meta['brand']}): {e}")

            # Product pages are heavier: sleep a bit more
            time.sleep(float(settings.request_sleep_sec) * 1.5)

        return items