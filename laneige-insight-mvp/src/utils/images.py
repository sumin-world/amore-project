"""
Image Utility Module

Provides image processing utilities for product snapshot tracking,
specifically perceptual hashing for visual change detection.

Key Functions:
    - phash_from_bytes: Compute perceptual hash from image bytes
    - fetch_image_bytes: Download image from URL with retry logic

Perceptual Hashing (pHash):
    - Creates 64-bit fingerprint of image visual content
    - Robust to minor changes (compression, resizing, slight edits)
    - Enables similarity detection via Hamming distance
    - Used for detecting product thumbnail updates on Amazon

Use Cases:
    - Track when products change main images (rebranding, new packaging)
    - Detect A/B testing of product images
    - Monitor competitor visual strategy changes
    - Identify counterfeit products (different images for same ASIN)
"""
from PIL import Image
import imagehash
import io
import httpx

def phash_from_bytes(img_bytes: bytes) -> str:
    """
    Compute perceptual hash (pHash) from image bytes.
    
    Args:
        img_bytes: Raw image data in any PIL-supported format (JPEG, PNG, etc.)
    
    Returns:
        Hex string representation of 64-bit perceptual hash
        Example: "8f373c0f8f373c0f"
    
    Process:
        1. Load image from bytes using PIL
        2. Convert to RGB color space (standardize format)
        3. Compute pHash using imagehash library
        4. Return as hex string for database storage
    
    Notes:
        - RGB conversion ensures consistent hashing regardless of source format
        - pHash algorithm: DCT (Discrete Cosine Transform) based
        - 64-bit hash provides good balance of uniqueness vs storage
        - Case-sensitive hex output
    
    Raises:
        PIL.UnidentifiedImageError: If image bytes are invalid
        ValueError: If image data is corrupted
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return str(imagehash.phash(img))

def fetch_image_bytes(url: str, timeout_sec: float = 10.0) -> bytes:
    """
    Download image from URL with timeout and redirect handling.
    
    Args:
        url: Image URL (must be publicly accessible)
        timeout_sec: Request timeout in seconds (default: 10.0)
    
    Returns:
        Raw image bytes
    
    Raises:
        httpx.HTTPError: For HTTP errors (4xx, 5xx)
        httpx.TimeoutException: If request exceeds timeout
        httpx.RequestError: For network errors
    
    Features:
        - Custom User-Agent to identify bot (polite scraping)
        - Automatic redirect following (handles CDN redirects)
        - Configurable timeout for resilience
    
    Notes:
        - Returns empty bytes if URL is empty/None
        - User-Agent identifies as demo bot (transparency)
        - Follows up to 5 redirects by default
        - Validates HTTP status (raises_for_status)
    
    TODO:
        - Add retry logic with exponential backoff
        - Implement caching to avoid re-downloading same images
        - Add image validation (check MIME type, max size)
    """
    if not url:
        return b""
    headers = {"User-Agent": "LaneigeInsightBot/0.1 (demo)"}
    with httpx.Client(timeout=timeout_sec, headers=headers, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content
