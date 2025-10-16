from typing import Optional
import os
from dotenv import load_dotenv

# Load .env file at module import
load_dotenv()

# Attempt to import pydantic-based settings; provide a robust fallback for environments
# where pydantic/pydantic-core wheels are unavailable (e.g., Python 3.13 without wheels).
try:
    from pydantic_settings import BaseSettings  # type: ignore
    from pydantic import Field, ConfigDict  # type: ignore

    class Settings(BaseSettings):
        model_config = ConfigDict(env_file=".env", case_sensitive=False, extra="allow")
        
        # IIFL API Configuration
        iifl_client_id: str = Field(default="", alias="IIFL_CLIENT_ID")
        iifl_auth_code: str = Field(default="", alias="IIFL_AUTH_CODE")
        iifl_app_secret: str = Field(default="", alias="IIFL_APP_SECRET")
        iifl_base_url: str = Field(default="https://api.iiflcapital.com/v1", alias="IIFL_BASE_URL")
        
        # Additional Security Keys
        jwt_secret_key: str = Field(default="", alias="JWT_SECRET_KEY")
        encryption_key: str = Field(default="", alias="ENCRYPTION_KEY")
        api_secret_key: str = Field(default="", alias="API_SECRET_KEY")
        
        # Development/Debug Configuration
        debug: bool = Field(default=False, alias="DEBUG")
        reload: bool = Field(default=False, alias="RELOAD")
        
        # Extended IIFL API Configuration
        iifl_api_base_url: str = Field(default="https://ttblaze.iifl.com/apimarketdata", alias="IIFL_API_BASE_URL")

        # Trading Configuration
        auto_trade: bool = Field(default=False, alias="AUTO_TRADE")
        dry_run: bool = Field(default=True, alias="DRY_RUN")
        signal_timeout: int = Field(default=300, alias="SIGNAL_TIMEOUT")  # seconds
        risk_per_trade: float = Field(default=0.025, alias="RISK_PER_TRADE")  # 2.5% (increased based on 1.5:1 avg R/R)
        max_positions: int = Field(default=12, alias="MAX_POSITIONS")  # Increased for diversification
        max_daily_loss: float = Field(default=0.06, alias="MAX_DAILY_LOSS")  # 6% (adjusted for higher risk per trade)
        min_price: float = Field(default=50.0, alias="MIN_PRICE")  # Higher minimum for quality stocks
        min_liquidity: float = Field(default=200000.0, alias="MIN_LIQUIDITY")  # Doubled for better execution
        
        # Extended Trading Risk Management
        max_position_size: int = Field(default=100000, alias="MAX_POSITION_SIZE")
        max_positions_per_day: int = Field(default=20, alias="MAX_POSITIONS_PER_DAY")
        position_size_percent: float = Field(default=0.02, alias="POSITION_SIZE_PERCENT")
        stop_loss_percent: float = Field(default=0.02, alias="STOP_LOSS_PERCENT")
        take_profit_percent: float = Field(default=0.04, alias="TAKE_PROFIT_PERCENT")
        
        # Strategy-specific Configuration (New)
        min_confidence_threshold: float = Field(default=0.65, alias="MIN_CONFIDENCE_THRESHOLD")  # Based on 70% avg confidence
        volume_confirmation_multiplier: float = Field(default=0.8, alias="VOLUME_CONFIRMATION_MULTIPLIER")  # Relaxed from current 0.9
        momentum_threshold: float = Field(default=0.015, alias="MOMENTUM_THRESHOLD")  # 1.5% momentum requirement
        trend_strength_multiplier: float = Field(default=1.2, alias="TREND_STRENGTH_MULTIPLIER")  # EMA separation requirement
        
        # Risk Management - Sector Concentration (New)
        max_sector_exposure: float = Field(default=0.3, alias="MAX_SECTOR_EXPOSURE")  # 30% max in any single sector
        enable_sector_diversification: bool = Field(default=True, alias="ENABLE_SECTOR_DIVERSIFICATION")  # Force diversification
        
        # Signal Quality Improvements (New)
        require_trend_confirmation: bool = Field(default=True, alias="REQUIRE_TREND_CONFIRMATION")  # Must be above EMA50 for buy signals
        price_quality_filter: bool = Field(default=True, alias="PRICE_QUALITY_FILTER")  # Filter out low-quality price action
        # Order product defaults and short selling
        allow_short_selling: bool = Field(default=True, alias="ALLOW_SHORT_SELLING")
        default_buy_product: str = Field(default="NORMAL", alias="DEFAULT_BUY_PRODUCT")  # NORMAL or DELIVERY
        default_sell_product: str = Field(default="NORMAL", alias="DEFAULT_SELL_PRODUCT")  # For sell to exit longs
        short_sell_product: str = Field(default="INTRADAY", alias="SHORT_SELL_PRODUCT")  # For initiating shorts
        day_trading_product: str = Field(default="INTRADAY", alias="DAY_TRADING_PRODUCT")

        # Telegram Bot
        telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
        telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")

        # Feature Flags
        telegram_bot_enabled: bool = Field(default=False, alias="TELEGRAM_BOT_ENABLED")
        enable_system_status_checks: bool = Field(default=False, alias="ENABLE_SYSTEM_STATUS_CHECKS")
        telegram_background_tasks_enabled: bool = Field(default=False, alias="TELEGRAM_BACKGROUND_TASKS_ENABLED")
        telegram_notifications_enabled: bool = Field(default=True, alias="TELEGRAM_NOTIFICATIONS_ENABLED")
        telegram_error_notifications: bool = Field(default=True, alias="TELEGRAM_ERROR_NOTIFICATIONS")
        telegram_trade_notifications: bool = Field(default=True, alias="TELEGRAM_TRADE_NOTIFICATIONS")
        # Scheduler Configuration
        enable_scheduler: bool = Field(default=False, alias="ENABLE_SCHEDULER")
        scheduler_enabled: bool = Field(default=True, alias="SCHEDULER_ENABLED")
        
        # Scheduler Intervals
        signal_generation_interval: int = Field(default=300, alias="SIGNAL_GENERATION_INTERVAL")
        risk_check_interval: int = Field(default=60, alias="RISK_CHECK_INTERVAL")
        portfolio_update_interval: int = Field(default=120, alias="PORTFOLIO_UPDATE_INTERVAL")
        log_cleanup_interval: int = Field(default=86400, alias="LOG_CLEANUP_INTERVAL")
        
        # Market Schedule
        market_open_time: str = Field(default="09:15", alias="MARKET_OPEN_TIME")
        market_close_time: str = Field(default="15:30", alias="MARKET_CLOSE_TIME")
        timezone: str = Field(default="Asia/Kolkata", alias="TIMEZONE")
        
        # Strategy Scheduling Frequencies (in minutes)
        day_trading_frequency: int = Field(default=5, alias="DAY_TRADING_FREQUENCY")      # Every 5 minutes
        short_selling_frequency: int = Field(default=30, alias="SHORT_SELLING_FREQUENCY")  # Every 30 minutes  
        short_term_frequency: int = Field(default=120, alias="SHORT_TERM_FREQUENCY")       # Every 2 hours
        long_term_frequency: int = Field(default=1440, alias="LONG_TERM_FREQUENCY")       # Once daily
        
        # Market Hours Configuration (IST)
        market_start_hour: int = Field(default=9, alias="MARKET_START_HOUR")
        market_start_minute: int = Field(default=15, alias="MARKET_START_MINUTE")
        market_end_hour: int = Field(default=15, alias="MARKET_END_HOUR")  
        market_end_minute: int = Field(default=30, alias="MARKET_END_MINUTE")
        
        # Strategy Execution Configuration
        enable_day_trading_scheduler: bool = Field(default=True, alias="ENABLE_DAY_TRADING_SCHEDULER")
        enable_short_selling_scheduler: bool = Field(default=True, alias="ENABLE_SHORT_SELLING_SCHEDULER")
        enable_short_term_scheduler: bool = Field(default=True, alias="ENABLE_SHORT_TERM_SCHEDULER")
        enable_long_term_scheduler: bool = Field(default=True, alias="ENABLE_LONG_TERM_SCHEDULER")
        
        # Pre/Post Market Configuration
        enable_pre_market_analysis: bool = Field(default=True, alias="ENABLE_PRE_MARKET_ANALYSIS")
        enable_post_market_analysis: bool = Field(default=True, alias="ENABLE_POST_MARKET_ANALYSIS")
        
        # Resource Management
        max_concurrent_strategies: int = Field(default=3, alias="MAX_CONCURRENT_STRATEGIES")
        strategy_timeout_minutes: int = Field(default=15, alias="STRATEGY_TIMEOUT_MINUTES")

        # Database
        database_url: str = Field(default="sqlite+aiosqlite:///./trading_system.db", alias="DATABASE_URL")
        db_pool_size: int = Field(default=20, alias="DB_POOL_SIZE")
        db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
        db_pool_recycle: int = Field(default=3600, alias="DB_POOL_RECYCLE")
        
        # Cache Configuration
        market_data_cache_ttl: int = Field(default=300, alias="MARKET_DATA_CACHE_TTL")
        historical_data_cache_ttl: int = Field(default=3600, alias="HISTORICAL_DATA_CACHE_TTL")
        max_symbols_per_request: int = Field(default=50, alias="MAX_SYMBOLS_PER_REQUEST")

        # Email Configuration
        email_enabled: bool = Field(default=False, alias="EMAIL_ENABLED")
        smtp_server: str = Field(default="smtp.gmail.com", alias="SMTP_SERVER")
        smtp_port: int = Field(default=587, alias="SMTP_PORT")
        smtp_username: str = Field(default="your_email@gmail.com", alias="SMTP_USERNAME")
        smtp_password: str = Field(default="your_app_password_here", alias="SMTP_PASSWORD")
        email_from: str = Field(default="your_email@gmail.com", alias="EMAIL_FROM")
        email_to: str = Field(default="admin@yourdomain.com", alias="EMAIL_TO")
        
        # Monitoring & Analytics
        sentry_environment: str = Field(default="production", alias="SENTRY_ENVIRONMENT")
        performance_monitoring_enabled: bool = Field(default=True, alias="PERFORMANCE_MONITORING_ENABLED")
        metrics_collection_enabled: bool = Field(default=True, alias="METRICS_COLLECTION_ENABLED")
        health_check_interval: int = Field(default=30, alias="HEALTH_CHECK_INTERVAL")
        health_check_url: str = Field(default="http://localhost:8000/health", alias="HEALTH_CHECK_URL")
        metrics_url: str = Field(default="http://localhost:8000/metrics", alias="METRICS_URL")
        
        # Backup Configuration
        backup_enabled: bool = Field(default=True, alias="BACKUP_ENABLED")
        backup_interval: int = Field(default=86400, alias="BACKUP_INTERVAL")
        backup_retention_days: int = Field(default=30, alias="BACKUP_RETENTION_DAYS")
        backup_location: str = Field(default="./backups", alias="BACKUP_LOCATION")
        
        # CORS & Security Configuration
        allowed_origins: str = Field(default="https://yourdomain.com,https://trading.yourdomain.com", alias="ALLOWED_ORIGINS")
        cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
        cors_allow_methods: str = Field(default="GET,POST,PUT,DELETE", alias="CORS_ALLOW_METHODS")
        cors_max_age: int = Field(default=3600, alias="CORS_MAX_AGE")
        
        # Rate Limiting
        rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
        rate_limit_auth_requests: int = Field(default=5, alias="RATE_LIMIT_AUTH_REQUESTS")
        rate_limit_auth_window: int = Field(default=60, alias="RATE_LIMIT_AUTH_WINDOW")
        rate_limit_api_requests: int = Field(default=100, alias="RATE_LIMIT_API_REQUESTS")
        rate_limit_api_window: int = Field(default=60, alias="RATE_LIMIT_API_WINDOW")
        rate_limit_orders_requests: int = Field(default=60, alias="RATE_LIMIT_ORDERS_REQUESTS")
        rate_limit_orders_window: int = Field(default=60, alias="RATE_LIMIT_ORDERS_WINDOW")
        
        # Session Security
        session_max_age: int = Field(default=1800, alias="SESSION_MAX_AGE")
        session_same_site: str = Field(default="strict", alias="SESSION_SAME_SITE")
        session_https_only: bool = Field(default=True, alias="SESSION_HTTPS_ONLY")
        
        # System Configuration
        container_memory_limit: str = Field(default="1g", alias="CONTAINER_MEMORY_LIMIT")
        container_cpu_limit: str = Field(default="1.0", alias="CONTAINER_CPU_LIMIT")
        umask: str = Field(default="022", alias="UMASK")
        file_permissions_strict: bool = Field(default=True, alias="FILE_PERMISSIONS_STRICT")
        
        # Security Headers
        security_headers_enabled: bool = Field(default=True, alias="SECURITY_HEADERS_ENABLED")
        hsts_max_age: int = Field(default=31536000, alias="HSTS_MAX_AGE")
        content_security_policy: str = Field(default="default-src 'self'", alias="CONTENT_SECURITY_POLICY")
        x_frame_options: str = Field(default="DENY", alias="X_FRAME_OPTIONS")
        x_content_type_options: str = Field(default="nosniff", alias="X_CONTENT_TYPE_OPTIONS")
        
        # Security
        secret_key: str = Field(default="dev-secret", alias="SECRET_KEY")
        access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

        # Logging Configuration
        log_level: str = Field(default="INFO", alias="LOG_LEVEL")
        log_file: str = Field(default="logs/trading_system.log", alias="LOG_FILE")
        log_retention_days: int = Field(default=14, alias="LOG_RETENTION_DAYS")
        
        # Extended Logging Configuration
        log_file_enabled: bool = Field(default=True, alias="LOG_FILE_ENABLED")
        log_json_format: bool = Field(default=True, alias="LOG_JSON_FORMAT")
        log_max_bytes: int = Field(default=52428800, alias="LOG_MAX_BYTES")
        log_rotation_time: int = Field(default=86400, alias="LOG_ROTATION_TIME")
        
        # Component-Specific Logging Levels
        log_level_trading: str = Field(default="INFO", alias="LOG_LEVEL_TRADING")
        log_level_orders: str = Field(default="INFO", alias="LOG_LEVEL_ORDERS")
        log_level_signals: str = Field(default="INFO", alias="LOG_LEVEL_SIGNALS")
        log_level_scheduler: str = Field(default="WARNING", alias="LOG_LEVEL_SCHEDULER")
        log_level_database: str = Field(default="ERROR", alias="LOG_LEVEL_DATABASE")
        log_level_market_data: str = Field(default="WARNING", alias="LOG_LEVEL_MARKET_DATA")
        log_level_backtest: str = Field(default="ERROR", alias="LOG_LEVEL_BACKTEST")
        log_level_telegram: str = Field(default="WARNING", alias="LOG_LEVEL_TELEGRAM")
        log_level_trades: str = Field(default="INFO", alias="LOG_LEVEL_TRADES")
        log_level_api: str = Field(default="WARNING", alias="LOG_LEVEL_API")
        log_level_risk: str = Field(default="INFO", alias="LOG_LEVEL_RISK")
        log_level_strategy: str = Field(default="INFO", alias="LOG_LEVEL_STRATEGY")
        log_level_data: str = Field(default="WARNING", alias="LOG_LEVEL_DATA")
        
        # Performance Logging
        log_performance_threshold: int = Field(default=1000, alias="LOG_PERFORMANCE_THRESHOLD")
        enable_performance_logging: bool = Field(default=True, alias="ENABLE_PERFORMANCE_LOGGING")
        performance_threshold_ms: int = Field(default=1000, alias="PERFORMANCE_THRESHOLD_MS")
        log_slow_queries: bool = Field(default=True, alias="LOG_SLOW_QUERIES")
        slow_query_threshold_ms: int = Field(default=500, alias="SLOW_QUERY_THRESHOLD_MS")
        
        # Log Rate Limiting and Sampling
        log_rate_limit_enabled: bool = Field(default=True, alias="LOG_RATE_LIMIT_ENABLED")
        log_rate_limit_messages: int = Field(default=60, alias="LOG_RATE_LIMIT_MESSAGES")
        log_rate_limit_window: int = Field(default=60, alias="LOG_RATE_LIMIT_WINDOW")
        log_error_aggregation_enabled: bool = Field(default=True, alias="LOG_ERROR_AGGREGATION_ENABLED")
        log_error_aggregation_window: int = Field(default=300, alias="LOG_ERROR_AGGREGATION_WINDOW")
        log_sampling_enabled: bool = Field(default=True, alias="LOG_SAMPLING_ENABLED")
        log_sampling_rate: float = Field(default=0.8, alias="LOG_SAMPLING_RATE")
        
        # Advanced Logging Settings
        log_max_file_size_mb: int = Field(default=10, alias="LOG_MAX_FILE_SIZE_MB")
        log_backup_count: int = Field(default=5, alias="LOG_BACKUP_COUNT")
        log_format: str = Field(default="json", alias="LOG_FORMAT")  # json, text, or structured
        log_console_enabled: bool = Field(default=True, alias="LOG_CONSOLE_ENABLED")
        
        # Critical Events Logging
        enable_critical_events: bool = Field(default=True, alias="ENABLE_CRITICAL_EVENTS")
        critical_events_immediate_flush: bool = Field(default=True, alias="CRITICAL_EVENTS_IMMEDIATE_FLUSH")
        critical_events_max_size_mb: int = Field(default=25, alias="CRITICAL_EVENTS_MAX_SIZE_MB")
        
        # Log Sampling and Rate Limiting
        enable_log_sampling: bool = Field(default=False, alias="ENABLE_LOG_SAMPLING")
        log_sample_rate: float = Field(default=1.0, alias="LOG_SAMPLE_RATE")
        api_log_rate_limit: int = Field(default=100, alias="API_LOG_RATE_LIMIT")  # per minute
        
        # Structured Logging Context
        log_include_hostname: bool = Field(default=True, alias="LOG_INCLUDE_HOSTNAME")
        log_include_process_id: bool = Field(default=True, alias="LOG_INCLUDE_PROCESS_ID")
        log_include_thread_id: bool = Field(default=False, alias="LOG_INCLUDE_THREAD_ID")
        log_correlation_id_header: str = Field(default="X-Correlation-ID", alias="LOG_CORRELATION_ID_HEADER")
        
        # Error Tracking
        enable_error_aggregation: bool = Field(default=True, alias="ENABLE_ERROR_AGGREGATION")
        error_aggregation_window_minutes: int = Field(default=5, alias="ERROR_AGGREGATION_WINDOW_MINUTES")
        max_error_details_length: int = Field(default=2048, alias="MAX_ERROR_DETAILS_LENGTH")

        # Environment
        environment: str = Field(default="development", alias="ENVIRONMENT")
        sentry_dsn: Optional[str] = Field(default=None, alias="SENTRY_DSN")
        sentry_traces_sample_rate: float = Field(default=0.0, alias="SENTRY_TRACES_SAMPLE_RATE")
        sentry_profiles_sample_rate: float = Field(default=0.0, alias="SENTRY_PROFILES_SAMPLE_RATE")



        # Server Configuration
        host: str = Field(default="0.0.0.0", alias="HOST")
        port: int = Field(default=8000, alias="PORT")

except Exception:
    # Lightweight fallback that reads from environment without pydantic
    class Settings:  # type: ignore
        def __init__(self) -> None:
            # IIFL API Configuration
            self.iifl_client_id: str = os.getenv("IIFL_CLIENT_ID", "")
            self.iifl_auth_code: str = os.getenv("IIFL_AUTH_CODE", "")
            self.iifl_app_secret: str = os.getenv("IIFL_APP_SECRET", "")
            self.iifl_base_url: str = os.getenv("IIFL_BASE_URL", "https://api.iiflcapital.com/v1")
            
            # Additional Security Keys
            self.jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "")
            self.encryption_key: str = os.getenv("ENCRYPTION_KEY", "")
            
            # Development Configuration
            self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"
            self.reload: bool = os.getenv("RELOAD", "false").lower() == "true"
            
            # Extended IIFL API Configuration
            self.iifl_api_base_url: str = os.getenv("IIFL_API_BASE_URL", "https://ttblaze.iifl.com/apimarketdata")

            # Trading Configuration
            self.auto_trade: bool = os.getenv("AUTO_TRADE", "false").lower() == "true"
            self.dry_run: bool = os.getenv("DRY_RUN", "true").lower() != "false"
            self.signal_timeout: int = int(os.getenv("SIGNAL_TIMEOUT", "300") or 300)
            self.risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", "0.025") or 0.025)
            self.max_positions: int = int(os.getenv("MAX_POSITIONS", "12") or 12)
            self.max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", "0.06") or 0.06)
            self.min_price: float = float(os.getenv("MIN_PRICE", "50.0") or 50.0)
            self.min_liquidity: float = float(os.getenv("MIN_LIQUIDITY", "200000") or 200000)
            
            # Extended Trading Risk Management
            self.max_position_size: int = int(os.getenv("MAX_POSITION_SIZE", "100000") or 100000)
            self.max_positions_per_day: int = int(os.getenv("MAX_POSITIONS_PER_DAY", "20") or 20)
            self.position_size_percent: float = float(os.getenv("POSITION_SIZE_PERCENT", "0.02") or 0.02)
            self.stop_loss_percent: float = float(os.getenv("STOP_LOSS_PERCENT", "0.02") or 0.02)
            self.take_profit_percent: float = float(os.getenv("TAKE_PROFIT_PERCENT", "0.04") or 0.04)
            
            # Strategy-specific Configuration (New)
            self.min_confidence_threshold: float = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", "0.65") or 0.65)
            self.volume_confirmation_multiplier: float = float(os.getenv("VOLUME_CONFIRMATION_MULTIPLIER", "0.8") or 0.8)
            self.momentum_threshold: float = float(os.getenv("MOMENTUM_THRESHOLD", "0.015") or 0.015)
            self.trend_strength_multiplier: float = float(os.getenv("TREND_STRENGTH_MULTIPLIER", "1.2") or 1.2)
            
            # Risk Management - Sector Concentration (New)
            self.max_sector_exposure: float = float(os.getenv("MAX_SECTOR_EXPOSURE", "0.3") or 0.3)
            self.enable_sector_diversification: bool = os.getenv("ENABLE_SECTOR_DIVERSIFICATION", "true").lower() != "false"
            
            # Signal Quality Improvements (New)
            self.require_trend_confirmation: bool = os.getenv("REQUIRE_TREND_CONFIRMATION", "true").lower() != "false"
            self.price_quality_filter: bool = os.getenv("PRICE_QUALITY_FILTER", "true").lower() != "false"
            self.allow_short_selling: bool = os.getenv("ALLOW_SHORT_SELLING", "true").lower() != "false"
            self.default_buy_product: str = os.getenv("DEFAULT_BUY_PRODUCT", "NORMAL")
            self.default_sell_product: str = os.getenv("DEFAULT_SELL_PRODUCT", "NORMAL")
            self.short_sell_product: str = os.getenv("SHORT_SELL_PRODUCT", "INTRADAY")
            self.day_trading_product: str = os.getenv("DAY_TRADING_PRODUCT", "INTRADAY")

            # Telegram Bot
            self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
            self.telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

            # Feature Flags
            self.telegram_bot_enabled: bool = os.getenv("TELEGRAM_BOT_ENABLED", "false").lower() == "true"
            self.enable_system_status_checks: bool = os.getenv("ENABLE_SYSTEM_STATUS_CHECKS", "false").lower() == "true"
            self.telegram_background_tasks_enabled: bool = os.getenv("TELEGRAM_BACKGROUND_TASKS_ENABLED", "false").lower() == "true"
            self.telegram_notifications_enabled: bool = os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "true").lower() != "false"
            self.telegram_error_notifications: bool = os.getenv("TELEGRAM_ERROR_NOTIFICATIONS", "true").lower() == "true"
            self.telegram_trade_notifications: bool = os.getenv("TELEGRAM_TRADE_NOTIFICATIONS", "true").lower() == "true"

            # Scheduler Configuration
            self.enable_scheduler: bool = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"
            self.scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
            
            # Strategy Scheduling Frequencies (in minutes)
            self.day_trading_frequency: int = int(os.getenv("DAY_TRADING_FREQUENCY", "5") or 5)
            self.short_selling_frequency: int = int(os.getenv("SHORT_SELLING_FREQUENCY", "30") or 30)
            self.short_term_frequency: int = int(os.getenv("SHORT_TERM_FREQUENCY", "120") or 120)
            self.long_term_frequency: int = int(os.getenv("LONG_TERM_FREQUENCY", "1440") or 1440)
            
            # Market Hours Configuration (IST)
            self.market_start_hour: int = int(os.getenv("MARKET_START_HOUR", "9") or 9)
            self.market_start_minute: int = int(os.getenv("MARKET_START_MINUTE", "15") or 15)
            self.market_end_hour: int = int(os.getenv("MARKET_END_HOUR", "15") or 15)
            self.market_end_minute: int = int(os.getenv("MARKET_END_MINUTE", "30") or 30)
            
            # Strategy Execution Configuration
            self.enable_day_trading_scheduler: bool = os.getenv("ENABLE_DAY_TRADING_SCHEDULER", "true").lower() != "false"
            self.enable_short_selling_scheduler: bool = os.getenv("ENABLE_SHORT_SELLING_SCHEDULER", "true").lower() != "false"
            self.enable_short_term_scheduler: bool = os.getenv("ENABLE_SHORT_TERM_SCHEDULER", "true").lower() != "false"
            self.enable_long_term_scheduler: bool = os.getenv("ENABLE_LONG_TERM_SCHEDULER", "true").lower() != "false"
            
            # Pre/Post Market Configuration
            self.enable_pre_market_analysis: bool = os.getenv("ENABLE_PRE_MARKET_ANALYSIS", "true").lower() != "false"
            self.enable_post_market_analysis: bool = os.getenv("ENABLE_POST_MARKET_ANALYSIS", "true").lower() != "false"
            
            # Resource Management
            self.max_concurrent_strategies: int = int(os.getenv("MAX_CONCURRENT_STRATEGIES", "3") or 3)
            self.strategy_timeout_minutes: int = int(os.getenv("STRATEGY_TIMEOUT_MINUTES", "15") or 15)

            # Database
            self.database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_system.db")

            # Security
            self.secret_key: str = os.getenv("SECRET_KEY", "dev-secret")
            self.access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30") or 30)

            # Scheduler Configuration  
            self.scheduler_enabled: bool = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
            self.signal_generation_interval: int = int(os.getenv("SIGNAL_GENERATION_INTERVAL", "300") or 300)
            self.risk_check_interval: int = int(os.getenv("RISK_CHECK_INTERVAL", "60") or 60)
            self.portfolio_update_interval: int = int(os.getenv("PORTFOLIO_UPDATE_INTERVAL", "120") or 120)
            self.log_cleanup_interval: int = int(os.getenv("LOG_CLEANUP_INTERVAL", "86400") or 86400)
            self.market_open_time: str = os.getenv("MARKET_OPEN_TIME", "09:15")
            self.market_close_time: str = os.getenv("MARKET_CLOSE_TIME", "15:30")
            self.timezone: str = os.getenv("TIMEZONE", "Asia/Kolkata")
            
            # Database Configuration
            self.db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "20") or 20)
            self.db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "10") or 10)
            self.db_pool_recycle: int = int(os.getenv("DB_POOL_RECYCLE", "3600") or 3600)
            
            # Cache Configuration
            self.market_data_cache_ttl: int = int(os.getenv("MARKET_DATA_CACHE_TTL", "300") or 300)
            self.historical_data_cache_ttl: int = int(os.getenv("HISTORICAL_DATA_CACHE_TTL", "3600") or 3600)
            self.max_symbols_per_request: int = int(os.getenv("MAX_SYMBOLS_PER_REQUEST", "50") or 50)
            
            # Email Configuration
            self.email_enabled: bool = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
            self.smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            self.smtp_port: int = int(os.getenv("SMTP_PORT", "587") or 587)
            self.smtp_username: str = os.getenv("SMTP_USERNAME", "your_email@gmail.com")
            self.smtp_password: str = os.getenv("SMTP_PASSWORD", "your_app_password_here")
            self.email_from: str = os.getenv("EMAIL_FROM", "your_email@gmail.com")
            self.email_to: str = os.getenv("EMAIL_TO", "admin@yourdomain.com")
            
            # Monitoring & Analytics
            self.sentry_environment: str = os.getenv("SENTRY_ENVIRONMENT", "production")
            self.performance_monitoring_enabled: bool = os.getenv("PERFORMANCE_MONITORING_ENABLED", "true").lower() == "true"
            self.metrics_collection_enabled: bool = os.getenv("METRICS_COLLECTION_ENABLED", "true").lower() == "true"
            self.health_check_interval: int = int(os.getenv("HEALTH_CHECK_INTERVAL", "30") or 30)
            self.health_check_url: str = os.getenv("HEALTH_CHECK_URL", "http://localhost:8000/health")
            self.metrics_url: str = os.getenv("METRICS_URL", "http://localhost:8000/metrics")
            
            # Backup Configuration
            self.backup_enabled: bool = os.getenv("BACKUP_ENABLED", "true").lower() == "true"
            self.backup_interval: int = int(os.getenv("BACKUP_INTERVAL", "86400") or 86400)
            self.backup_retention_days: int = int(os.getenv("BACKUP_RETENTION_DAYS", "30") or 30)
            self.backup_location: str = os.getenv("BACKUP_LOCATION", "./backups")
            
            # CORS & Security Configuration
            self.allowed_origins: str = os.getenv("ALLOWED_ORIGINS", "https://yourdomain.com,https://trading.yourdomain.com")
            self.cors_allow_credentials: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
            self.cors_allow_methods: str = os.getenv("CORS_ALLOW_METHODS", "GET,POST,PUT,DELETE")
            self.cors_max_age: int = int(os.getenv("CORS_MAX_AGE", "3600") or 3600)
            
            # Rate Limiting
            self.rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
            self.rate_limit_auth_requests: int = int(os.getenv("RATE_LIMIT_AUTH_REQUESTS", "5") or 5)
            self.rate_limit_auth_window: int = int(os.getenv("RATE_LIMIT_AUTH_WINDOW", "60") or 60)
            self.rate_limit_api_requests: int = int(os.getenv("RATE_LIMIT_API_REQUESTS", "100") or 100)
            self.rate_limit_api_window: int = int(os.getenv("RATE_LIMIT_API_WINDOW", "60") or 60)
            self.rate_limit_orders_requests: int = int(os.getenv("RATE_LIMIT_ORDERS_REQUESTS", "60") or 60)
            self.rate_limit_orders_window: int = int(os.getenv("RATE_LIMIT_ORDERS_WINDOW", "60") or 60)
            
            # Session Security
            self.session_max_age: int = int(os.getenv("SESSION_MAX_AGE", "1800") or 1800)
            self.session_same_site: str = os.getenv("SESSION_SAME_SITE", "strict")
            self.session_https_only: bool = os.getenv("SESSION_HTTPS_ONLY", "true").lower() == "true"
            
            # System Configuration
            self.container_memory_limit: str = os.getenv("CONTAINER_MEMORY_LIMIT", "1g")
            self.container_cpu_limit: str = os.getenv("CONTAINER_CPU_LIMIT", "1.0")
            self.umask: str = os.getenv("UMASK", "022")
            self.file_permissions_strict: bool = os.getenv("FILE_PERMISSIONS_STRICT", "true").lower() == "true"
            
            # Security Headers
            self.security_headers_enabled: bool = os.getenv("SECURITY_HEADERS_ENABLED", "true").lower() == "true"
            self.hsts_max_age: int = int(os.getenv("HSTS_MAX_AGE", "31536000") or 31536000)
            self.content_security_policy: str = os.getenv("CONTENT_SECURITY_POLICY", "default-src 'self'")
            self.x_frame_options: str = os.getenv("X_FRAME_OPTIONS", "DENY")
            self.x_content_type_options: str = os.getenv("X_CONTENT_TYPE_OPTIONS", "nosniff")

            # Logging Configuration
            self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
            self.log_file: str = os.getenv("LOG_FILE", "logs/trading_system.log")
            self.log_retention_days: int = int(os.getenv("LOG_RETENTION_DAYS", "14") or 14)
            
            # Extended Logging Configuration
            self.log_file_enabled: bool = os.getenv("LOG_FILE_ENABLED", "true").lower() == "true"
            self.log_json_format: bool = os.getenv("LOG_JSON_FORMAT", "true").lower() == "true"
            self.log_max_bytes: int = int(os.getenv("LOG_MAX_BYTES", "52428800") or 52428800)
            self.log_rotation_time: int = int(os.getenv("LOG_ROTATION_TIME", "86400") or 86400)
            
            # Component-Specific Logging Levels
            self.log_level_trading: str = os.getenv("LOG_LEVEL_TRADING", "INFO")
            self.log_level_orders: str = os.getenv("LOG_LEVEL_ORDERS", "INFO")
            self.log_level_signals: str = os.getenv("LOG_LEVEL_SIGNALS", "INFO")
            self.log_level_scheduler: str = os.getenv("LOG_LEVEL_SCHEDULER", "WARNING")
            self.log_level_database: str = os.getenv("LOG_LEVEL_DATABASE", "ERROR")
            self.log_level_market_data: str = os.getenv("LOG_LEVEL_MARKET_DATA", "WARNING")
            self.log_level_backtest: str = os.getenv("LOG_LEVEL_BACKTEST", "ERROR")
            self.log_level_telegram: str = os.getenv("LOG_LEVEL_TELEGRAM", "WARNING")
            self.log_level_trades: str = os.getenv("LOG_LEVEL_TRADES", "INFO")
            self.log_level_api: str = os.getenv("LOG_LEVEL_API", "WARNING")
            self.log_level_risk: str = os.getenv("LOG_LEVEL_RISK", "INFO")
            self.log_level_strategy: str = os.getenv("LOG_LEVEL_STRATEGY", "INFO")
            self.log_level_data: str = os.getenv("LOG_LEVEL_DATA", "WARNING")
            
            # Performance Logging
            self.log_performance_threshold: int = int(os.getenv("LOG_PERFORMANCE_THRESHOLD", "1000") or 1000)
            self.enable_performance_logging: bool = os.getenv("ENABLE_PERFORMANCE_LOGGING", "true").lower() != "false"
            self.performance_threshold_ms: int = int(os.getenv("PERFORMANCE_THRESHOLD_MS", "1000") or 1000)
            self.log_slow_queries: bool = os.getenv("LOG_SLOW_QUERIES", "true").lower() != "false"
            self.slow_query_threshold_ms: int = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "500") or 500)
            
            # Log Rate Limiting and Sampling
            self.log_rate_limit_enabled: bool = os.getenv("LOG_RATE_LIMIT_ENABLED", "true").lower() == "true"
            self.log_rate_limit_messages: int = int(os.getenv("LOG_RATE_LIMIT_MESSAGES", "60") or 60)
            self.log_rate_limit_window: int = int(os.getenv("LOG_RATE_LIMIT_WINDOW", "60") or 60)
            self.log_error_aggregation_enabled: bool = os.getenv("LOG_ERROR_AGGREGATION_ENABLED", "true").lower() == "true"
            self.log_error_aggregation_window: int = int(os.getenv("LOG_ERROR_AGGREGATION_WINDOW", "300") or 300)
            self.log_sampling_enabled: bool = os.getenv("LOG_SAMPLING_ENABLED", "true").lower() == "true"
            self.log_sampling_rate: float = float(os.getenv("LOG_SAMPLING_RATE", "0.8") or 0.8)
            
            # Advanced Logging Settings
            self.log_max_file_size_mb: int = int(os.getenv("LOG_MAX_FILE_SIZE_MB", "10") or 10)
            self.log_backup_count: int = int(os.getenv("LOG_BACKUP_COUNT", "5") or 5)
            self.log_format: str = os.getenv("LOG_FORMAT", "json")
            self.log_console_enabled: bool = os.getenv("LOG_CONSOLE_ENABLED", "true").lower() != "false"
            
            # Critical Events Logging
            self.enable_critical_events: bool = os.getenv("ENABLE_CRITICAL_EVENTS", "true").lower() != "false"
            self.critical_events_immediate_flush: bool = os.getenv("CRITICAL_EVENTS_IMMEDIATE_FLUSH", "true").lower() != "false"
            self.critical_events_max_size_mb: int = int(os.getenv("CRITICAL_EVENTS_MAX_SIZE_MB", "25") or 25)
            
            # Log Sampling and Rate Limiting
            self.enable_log_sampling: bool = os.getenv("ENABLE_LOG_SAMPLING", "false").lower() == "true"
            try:
                self.log_sample_rate: float = float(os.getenv("LOG_SAMPLE_RATE", "1.0") or 1.0)
            except Exception:
                self.log_sample_rate = 1.0
            self.api_log_rate_limit: int = int(os.getenv("API_LOG_RATE_LIMIT", "100") or 100)
            
            # Structured Logging Context
            self.log_include_hostname: bool = os.getenv("LOG_INCLUDE_HOSTNAME", "true").lower() != "false"
            self.log_include_process_id: bool = os.getenv("LOG_INCLUDE_PROCESS_ID", "true").lower() != "false"
            self.log_include_thread_id: bool = os.getenv("LOG_INCLUDE_THREAD_ID", "false").lower() == "true"
            self.log_correlation_id_header: str = os.getenv("LOG_CORRELATION_ID_HEADER", "X-Correlation-ID")
            
            # Error Tracking
            self.enable_error_aggregation: bool = os.getenv("ENABLE_ERROR_AGGREGATION", "true").lower() != "false"
            self.error_aggregation_window_minutes: int = int(os.getenv("ERROR_AGGREGATION_WINDOW_MINUTES", "5") or 5)
            self.max_error_details_length: int = int(os.getenv("MAX_ERROR_DETAILS_LENGTH", "2048") or 2048)

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
