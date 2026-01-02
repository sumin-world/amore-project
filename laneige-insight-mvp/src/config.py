from pydantic import BaseModel
from dotenv import load_dotenv
import os
load_dotenv()

class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "").strip()
    request_sleep_sec: float = float(os.getenv("REQUEST_SLEEP_SEC", "1.2"))

settings = Settings()
if not settings.database_url:
    raise RuntimeError("DATABASE_URL empty. fill .env")
