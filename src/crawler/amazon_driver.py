import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

class AmazonCrawler:
    def __init__(self):
        self.driver = self._setup_driver()

    def _setup_driver(self):
        options = Options()
        
        # 시스템에 설치된 Chromium 위치 지정
        options.binary_location = "/usr/bin/chromium-browser"
        
        # 리눅스 서버 필수 옵션
        options.add_argument("--headless") 
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # User-Agent 설정
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        options.add_argument(f"user-agent={user_agent}")
        
        # 자동화 감지 방지 설정
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 시스템 드라이버 경로 사용
        service = Service("/usr/bin/chromedriver")
        
        driver = webdriver.Chrome(service=service, options=options)
        
        # navigator.webdriver 속성 제거
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        return driver

    def run(self):
        print("[Stealth Mode] Amazon 접속 시도 중... (System Chromium)")
        target_url = "https://www.amazon.com/Best-Sellers-Beauty/zgbs/beauty/"
        
        try:
            self.driver.get(target_url)
            
            # 3~6초 대기
            time.sleep(random.uniform(3, 6))
            
            title = self.driver.title
            print(f"접속 성공! 현재 페이지 제목: {title}")
            print(f"수집된 데이터 크기: {len(self.driver.page_source)} bytes")
            
            return self.driver.page_source
            
        except Exception as e:
            print(f"크롤링 중 에러 발생: {e}")
            return None
        finally:
            print("브라우저 종료")
            self.driver.quit()

if __name__ == "__main__":
    bot = AmazonCrawler()
    bot.run()
