from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Settings
    APP_NAME: str = "Mutual Fund Recommendation Engine"
    API_V1_STR: str = "/api/v1"
    
    # MongoDB Settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "mf_engine"
    
    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379"
    SESSION_TTL_SECONDS: int = 3600
    
    # MySQL Settings (User Portfolio)
    MYSQL_HOST: str = "localhost"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "user_portfolio"
    
    # External Services
    GEMINI_API_KEY: str = ""
    DEEPGRAM_API_KEY: str = ""
    CARTESIA_API_KEY: str = ""

    DAILY_API_KEY: str =""
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
