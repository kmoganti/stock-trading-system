from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os
from dotenv import load_dotenv

# Load .env file at module import
load_dotenv()

class Settings(BaseSettings):
    # IIFL API Configuration
    iifl_client_id: str = Field(..., env="IIFL_CLIENT_ID")
    iifl_auth_code: str = Field(..., env="IIFL_AUTH_CODE")
    iifl_app_secret: str = Field(..., env="IIFL_APP_SECRET")
    iifl_base_url: str = Field("https://ttblaze.iifl.com/apimarketdata", env="IIFL_BASE_URL")
    
    # Trading Configuration
    auto_trade: bool = Field(False, env="AUTO_TRADE")
    dry_run: bool = Field(True, env="DRY_RUN")
    signal_timeout: int = Field(300, env="SIGNAL_TIMEOUT")  # seconds
    risk_per_trade: float = Field(0.02, env="RISK_PER_TRADE")  # 2%
    max_positions: int = Field(10, env="MAX_POSITIONS")
    max_daily_loss: float = Field(0.05, env="MAX_DAILY_LOSS")  # 5%
    min_price: float = Field(10.0, env="MIN_PRICE")
    min_liquidity: float = Field(100000.0, env="MIN_LIQUIDITY")
    
    # Telegram Bot
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(..., env="TELEGRAM_CHAT_ID")
    
    # Database
    database_url: str = Field("sqlite+aiosqlite:///./trading_system.db", env="DATABASE_URL")
    
    # Security
    secret_key: str = Field(..., env="SECRET_KEY")
    access_token_expire_minutes: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("logs/trading_system.log", env="LOG_FILE")
    log_retention_days: int = Field(14, env="LOG_RETENTION_DAYS")
    
    # Environment
    environment: str = Field("development", env="ENVIRONMENT")
    sentry_dsn: Optional[str] = Field(None, env="SENTRY_DSN")
    sentry_traces_sample_rate: float = Field(0.0, env="SENTRY_TRACES_SAMPLE_RATE")
    sentry_profiles_sample_rate: float = Field(0.0, env="SENTRY_PROFILES_SAMPLE_RATE")

    api_secret_key: Optional[str] = Field(None, env="API_SECRET_KEY")
    
    # Server Configuration
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get settings singleton"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
