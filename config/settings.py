from typing import Optional
import os
from dotenv import load_dotenv

# Load .env file at module import
load_dotenv()

# Attempt to import pydantic-based settings; provide a robust fallback for environments
# where pydantic/pydantic-core wheels are unavailable (e.g., Python 3.13 without wheels).
try:
    from pydantic_settings import BaseSettings  # type: ignore
    from pydantic import Field  # type: ignore

    class Settings(BaseSettings):
        # IIFL API Configuration
        iifl_client_id: str = Field("", env="IIFL_CLIENT_ID")
        iifl_auth_code: str = Field("", env="IIFL_AUTH_CODE")
        iifl_app_secret: str = Field("", env="IIFL_APP_SECRET")
        iifl_base_url: str = Field("https://api.iiflcapital.com/v1", env="IIFL_BASE_URL")

        # Trading Configuration
        auto_trade: bool = Field(False, env="AUTO_TRADE")
        dry_run: bool = Field(True, env="DRY_RUN")
        signal_timeout: int = Field(300, env="SIGNAL_TIMEOUT")  # seconds
        risk_per_trade: float = Field(0.02, env="RISK_PER_TRADE")  # 2%
        max_positions: int = Field(10, env="MAX_POSITIONS")
        max_daily_loss: float = Field(0.05, env="MAX_DAILY_LOSS")  # 5%
        min_price: float = Field(10.0, env="MIN_PRICE")
        min_liquidity: float = Field(100000.0, env="MIN_LIQUIDITY")
        # Order product defaults and short selling
        allow_short_selling: bool = Field(True, env="ALLOW_SHORT_SELLING")
        default_buy_product: str = Field("NORMAL", env="DEFAULT_BUY_PRODUCT")  # NORMAL or DELIVERY
        default_sell_product: str = Field("NORMAL", env="DEFAULT_SELL_PRODUCT")  # For sell to exit longs
        short_sell_product: str = Field("INTRADAY", env="SHORT_SELL_PRODUCT")  # For initiating shorts
        day_trading_product: str = Field("INTRADAY", env="DAY_TRADING_PRODUCT")

        # Telegram Bot
        telegram_bot_token: str = Field("", env="TELEGRAM_BOT_TOKEN")
        telegram_chat_id: str = Field("", env="TELEGRAM_CHAT_ID")

        # Database
        database_url: str = Field("sqlite+aiosqlite:///./trading_system.db", env="DATABASE_URL")

        # Security
        secret_key: str = Field("dev-secret", env="SECRET_KEY")
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

except Exception:
    # Lightweight fallback that reads from environment without pydantic
    class Settings:  # type: ignore
        def __init__(self) -> None:
            # IIFL API Configuration
            self.iifl_client_id: str = os.getenv("IIFL_CLIENT_ID", "")
            self.iifl_auth_code: str = os.getenv("IIFL_AUTH_CODE", "")
            self.iifl_app_secret: str = os.getenv("IIFL_APP_SECRET", "")
            self.iifl_base_url: str = os.getenv("IIFL_BASE_URL", "https://api.iiflcapital.com/v1")

            # Trading Configuration
            self.auto_trade: bool = os.getenv("AUTO_TRADE", "false").lower() == "true"
            self.dry_run: bool = os.getenv("DRY_RUN", "true").lower() != "false"
            self.signal_timeout: int = int(os.getenv("SIGNAL_TIMEOUT", "300") or 300)
            self.risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", "0.02") or 0.02)
            self.max_positions: int = int(os.getenv("MAX_POSITIONS", "10") or 10)
            self.max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", "0.05") or 0.05)
            self.min_price: float = float(os.getenv("MIN_PRICE", "10.0") or 10.0)
            self.min_liquidity: float = float(os.getenv("MIN_LIQUIDITY", "100000") or 100000)
            self.allow_short_selling: bool = os.getenv("ALLOW_SHORT_SELLING", "true").lower() != "false"
            self.default_buy_product: str = os.getenv("DEFAULT_BUY_PRODUCT", "NORMAL")
            self.default_sell_product: str = os.getenv("DEFAULT_SELL_PRODUCT", "NORMAL")
            self.short_sell_product: str = os.getenv("SHORT_SELL_PRODUCT", "INTRADAY")
            self.day_trading_product: str = os.getenv("DAY_TRADING_PRODUCT", "INTRADAY")

            # Telegram Bot
            self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
            self.telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

            # Database
            self.database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_system.db")

            # Security
            self.secret_key: str = os.getenv("SECRET_KEY", "dev-secret")
            self.access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30") or 30)

            # Logging
            self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
            self.log_file: str = os.getenv("LOG_FILE", "logs/trading_system.log")
            self.log_retention_days: int = int(os.getenv("LOG_RETENTION_DAYS", "14") or 14)

            # Environment
            self.environment: str = os.getenv("ENVIRONMENT", "development")
            self.sentry_dsn: Optional[str] = os.getenv("SENTRY_DSN")
            try:
                self.sentry_traces_sample_rate: float = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0") or 0.0)
            except Exception:
                self.sentry_traces_sample_rate = 0.0
            try:
                self.sentry_profiles_sample_rate: float = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0") or 0.0)
            except Exception:
                self.sentry_profiles_sample_rate = 0.0

            self.api_secret_key: Optional[str] = os.getenv("API_SECRET_KEY")

            # Server Configuration
            self.host: str = os.getenv("HOST", "0.0.0.0")
            try:
                self.port: int = int(os.getenv("PORT", "8000") or 8000)
            except Exception:
                self.port = 8000

# Global settings instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get settings singleton"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
