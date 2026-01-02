from datetime import datetime
from typing import List, Dict
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import time
import re
from src.sources.base import Source, ProductItem
from src.config import settings

class AmazonProduct(Source):
    """특정 ASIN 제품 직접 추적"""
    
    # 추적할 제품 리스트
    TARGET_PRODUCTS = {
        # Laneige
        "B07KNTK3QG": {"brand": "Laneige", "name": "Water Sleeping Mask"},
        "B00LUSHW18": {"brand": "Laneige", "name": "Lip Sleeping Mask"},
        "B084GYN2K4": {"brand": "Laneige", "name": "Cream Skin Refiner"},
        
        # 경쟁사 (K-뷰티)
        "B00PBX3L7K": {"brand": "COSRX", "name": "Snail Mucin"},
        "B016NRXO06": {"brand": "COSRX", "name": "Low pH Cleanser"},
        "B07YZ8MJQY": {"brand": "Innisfree", "name": "Green Tea Serum"},
        "B01N5SMQM3": {"brand": "Etude House", "name": "SoonJung Toner"},
    }
    
    def fetch_asin(self, asin: str) -> ProductItem:
        """개별 ASIN 크롤링"""
        url = f"https://www.amazon.com/dp/{asin}"
        captured_at = datetime.utcnow()
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(settings.request_sleep_sec)
            html = page.content()
            browser.close()
        
        soup = BeautifulSoup(html, "lxml")
        
        # 제목
        title_el = soup.select_one("#productTitle")
        title = title_el.get_text(strip=True) if title_el else ""
        
        # 가격
        price = 0.0
        price_el = soup.select_one("span.a-price span.a-offscreen")
        if price_el:
            try:
                price = float(price_el.get_text(strip=True).replace("$","").replace(",",""))
            except:
                pass
        
        # 평점
        rating = 0.0
        rating_el = soup.select_one("span.a-icon-alt")
        if rating_el:
            try:
                rating = float(rating_el.get_text(strip=True).split()[0])
            except:
                pass
        
        # 리뷰 수
        review_count = 0
        review_el = soup.select_one("#acrCustomerReviewText")
        if review_el:
            try:
                text = review_el.get_text(strip=True).replace(",", "")
                review_count = int(re.search(r'\d+', text).group())
            except:
                pass
        
        # 이미지
        image_url = ""
        img_el = soup.select_one("#landingImage")
        if img_el:
            image_url = img_el.get("src", "")
        
        # Best Sellers Rank 추출
        rank = -1
        bsr_el = soup.find("th", string="Best Sellers Rank")
        if bsr_el:
            td = bsr_el.find_next("td")
            if td:
                bsr_text = td.get_text(strip=True)
                m = re.search(r'#([\d,]+)\s+in', bsr_text)
                if m:
                    rank = int(m.group(1).replace(",", ""))
        
        # 브랜드/카테고리 정보
        meta = self.TARGET_PRODUCTS.get(asin, {"brand": "Unknown", "name": "Unknown"})
        
        return ProductItem(
            source="amazon_product",
            market="US",
            category=f"Target Tracking - {meta['brand']}",
            captured_at=captured_at,
            rank=rank,
            product_id=asin,
            title=title or meta["name"],
            product_url=url,
            price=price,
            rating=rating,
            review_count=review_count,
            image_url=image_url,
            raw={"brand": meta["brand"], "product_name": meta["name"]},
        )
    
    def fetch(self, url: str) -> List[ProductItem]:
        """전체 타겟 제품 수집"""
        items = []
        
        for asin, meta in self.TARGET_PRODUCTS.items():
            try:
                item = self.fetch_asin(asin)
                items.append(item)
                print(f"✓ {meta['brand']:12s} | {meta['name']:25s} | Rank: {item.rank:4d} | ${item.price:.2f}")
            except Exception as e:
                print(f"✗ {asin} ({meta['brand']}): {e}")
            
            time.sleep(settings.request_sleep_sec * 1.5)  # Rate limiting
        
        return items