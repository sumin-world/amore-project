from PIL import Image
import imagehash
import io
import httpx

def phash_from_bytes(img_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return str(imagehash.phash(img))

def fetch_image_bytes(url: str, timeout_sec: float = 10.0) -> bytes:
    if not url:
        return b""
    headers = {"User-Agent": "LaneigeInsightBot/0.1 (demo)"}
    with httpx.Client(timeout=timeout_sec, headers=headers, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content
