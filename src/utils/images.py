"""Image utilities: perceptual hashing and HTTP fetching."""

import io

import httpx
import imagehash
from PIL import Image


def phash_from_bytes(img_bytes: bytes) -> str:
    """Compute a 64-bit perceptual hash and return its hex representation."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return str(imagehash.phash(img))


def fetch_image_bytes(url: str, timeout_sec: float = 10.0) -> bytes:
    """Download an image with redirect-following and a polite User-Agent."""
    if not url:
        return b""
    headers = {"User-Agent": "MarketInsightBot/0.1 (demo)"}
    with httpx.Client(timeout=timeout_sec, headers=headers, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.content
