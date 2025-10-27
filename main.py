# Standard library imports
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager

# STARTUP TIMING LOGGER
startup_time = time.time()
print(f"🚀 [STARTUP] {time.time() - startup_time:.3f}s - Starting main.py imports")

def log_timing(message):
    global startup_time
    elapsed = time.time() - startup_time
    print(f"🚀 [STARTUP] {elapsed:.3f}s - {message}")
    return elapsed

# Third-party imports
log_timing("Starting third-party imports")
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
log_timing("Completed third-party imports")

# Local imports
log_timing("Starting local imports")
from config.settings import get_settings
log_timing("Loaded config.settings")
from models.database import init_db, close_db
log_timing("Loaded models.database")
from services.logging_service import trading_logger
log_timing("Loaded services.logging_service")

# API routers
log_timing("Starting API router imports")
from api import (
    system_router, signals_router, portfolio_router, 
    risk_router, reports_router, backtest_router, settings_router, events_router
)
log_timing("Loaded main API routers")
from api.margin import router as margin_router
from api.auth_management import router as auth_router
from api.watchlist import router as watchlist_router
from api.scheduler import router as scheduler_router
log_timing("Loaded additional API routers")

# Services scheduler for global access
log_timing("Loading trading scheduler")
from services.scheduler import get_trading_scheduler
log_timing("Completed all imports")

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# The TradingLogger service handles all application-specific logging configurations.

# Suppress watchfiles logging spam
logging.getLogger('watchfiles').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def init_sentry(settings):
    try:
        import sentry_sdk
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
        from sentry_sdk.integrations.logging import LoggingIntegration
        if settings.sentry_dsn:
            sentry_logging = LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            )
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                traces_sample_rate=settings.sentry_traces_sample_rate or 0.0,
                profiles_sample_rate=settings.sentry_profiles_sample_rate or 0.0,
                integrations=[sentry_logging],
                environment=settings.environment,
            )
            trading_logger.enable_sentry()
            logger.info("Sentry initialized")
            return SentryAsgiMiddleware
    except Exception as e:
        logger.warning(f"Sentry initialization failed or disabled: {str(e)}")
    return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    log_timing("Starting lifespan - application startup")
    logger.info("Starting Stock Trading System...")
    # Ensure database schema is up-to-date (idempotent)
    try:
        from models.database import init_db as _ensure_db
        await _ensure_db()
        log_timing("Database initialized/migrated")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        log_timing(f"Database init failed: {e}")
    
    log_timing("Logging system events")
    trading_logger.log_system_event("application_startup", {"version": "1.0.0"})
    trading_logger.log_system_event("database_initialized")
    app.state.market_stream_service = None
    
    # Start Telegram bot if configured (disabled by default unless explicitly enabled)
    log_timing("Starting Telegram bot initialization")
    app.state.telegram_bot = None
    try:
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        log_timing("Getting settings for Telegram")
        settings_for_telegram = get_settings()
        if telegram_token and telegram_chat_id and getattr(settings_for_telegram, "telegram_bot_enabled", False):
            log_timing("Importing Telegram bot modules")
            from telegram_bot.bot import TelegramBot
            from telegram_bot.handlers import setup_handlers
            log_timing("Creating Telegram bot instance")
            bot = TelegramBot()
            
            # Initialize bot in background to avoid blocking startup
            log_timing("Starting Telegram bot background initialization")
            async def init_telegram_bot():
                try:
                    await setup_handlers(bot)
                    await bot.start()
                    app.state.telegram_bot = bot
                    logger.info("Telegram bot started successfully in background")
                except Exception as e:
                    logger.error(f"Failed to start Telegram bot in background: {str(e)}")
            
            # Start bot initialization in background
            asyncio.create_task(init_telegram_bot())
            log_timing("Telegram bot background initialization queued")
        else:
            logger.warning("Telegram bot not started: disabled or missing TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID")
            log_timing("Telegram bot skipped (disabled or missing config)")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {str(e)}")
        log_timing(f"Telegram bot failed: {str(e)}")

    # Start Market Data Stream listener
    log_timing("Starting Market Data Stream initialization")
    try:
        # Check if market stream is enabled
        log_timing("Getting settings for market stream")
        settings_for_stream = get_settings()
        enable_market_stream = getattr(settings_for_stream, "enable_market_stream", True)
        enable_market_stream = os.getenv("ENABLE_MARKET_STREAM", "true").lower() == "true" if enable_market_stream else False
        
        if not enable_market_stream:
            logger.info("Market stream disabled by configuration (ENABLE_MARKET_STREAM=false)")
            log_timing("Market stream disabled by configuration")
        else:
            log_timing("Importing market stream services")
            from services.market_stream import MarketStreamService
            from models.database import AsyncSessionLocal

            # Authenticate first to get a token
            log_timing("Importing IIFL API service")
            from services.iifl_api import IIFLAPIService
            from services.watchlist import WatchlistService  
            from services.screener import ScreenerService
            
            log_timing("Creating IIFL API service instance")
            iifl_service = IIFLAPIService()
            
            log_timing("Starting IIFL authentication")
            auth_result = await iifl_service.authenticate()
            log_timing(f"IIFL authentication completed: {auth_result}")
            
            # Check for authentication errors
            if isinstance(auth_result, dict):
                if auth_result.get("auth_code_expired"):
                    logger.error("🔒 Auth code has expired. Please update IIFL_AUTH_CODE in .env file")
                    log_timing("Authentication failed: auth code expired")
                elif auth_result.get("error"):
                    logger.error(f"❌ Authentication error: {auth_result['error']}")
                    log_timing(f"Authentication failed: {auth_result['error']}")
            
            if auth_result and not iifl_service.session_token.startswith("mock_"):
                log_timing("IIFL authentication successful, starting database session")
                async with AsyncSessionLocal() as session:
                    log_timing("Creating watchlist service")
                    watchlist_service = WatchlistService(session)
                    log_timing("Creating screener service")
                    screener_service = ScreenerService(watchlist_service)
                    log_timing("Creating market stream service")
                    stream_service = MarketStreamService(iifl_service, screener_service)
                    
                    # Initialize market stream in background to avoid blocking startup
                    log_timing("Starting market stream background initialization")
                    async def init_market_stream():
                        try:
                            await stream_service.connect_and_subscribe()
                            app.state.market_stream_service = stream_service
                            logger.info("Market stream service connected successfully in background")
                        except Exception as e:
                            logger.error(f"Failed to connect market stream in background: {str(e)}")
                    
                    # Start market stream initialization in background
                    asyncio.create_task(init_market_stream())
                    log_timing("Market stream background initialization queued")
            else:
                logger.warning("Could not start market stream: IIFL authentication failed or using mock token.")
                log_timing("Market stream skipped: IIFL authentication failed or using mock token")
    except Exception as e:
        logger.error(f"Failed to start market data stream: {e}", exc_info=True)
        log_timing(f"Market stream failed: {str(e)}")
    
    # One-time daily refresh of portfolio and margin caches at startup to avoid repeated calls
    log_timing("Starting portfolio and margin cache warmup")
    try:
        log_timing("Importing DataFetcher for cache warmup")
        from services.data_fetcher import DataFetcher
        from services.iifl_api import IIFLAPIService
        log_timing("Creating IIFL service for cache warmup")
        iifl_for_cache = IIFLAPIService()
        log_timing("Creating DataFetcher instance")
        fetcher_for_cache = DataFetcher(iifl_for_cache)
        log_timing("Getting portfolio data (force refresh)")
        await fetcher_for_cache.get_portfolio_data(force_refresh=True)
        log_timing("Getting margin info (force refresh)")
        await fetcher_for_cache.get_margin_info(force_refresh=True)
        logger.info("Startup portfolio and margin caches warmed up.")
        log_timing("Portfolio and margin cache warmup completed")
    except Exception as e:
        logger.warning(f"Failed startup cache warmup: {str(e)}")
        log_timing(f"Cache warmup failed: {str(e)}")
    
    # Schedule daily housekeeping (log pruning) at 00:30
    log_timing("Starting scheduler initialization")
    try:
        log_timing("Getting settings for scheduler")
        settings = get_settings()
        if getattr(settings, "enable_scheduler", False):
            log_timing("Creating AsyncIOScheduler")
            scheduler = AsyncIOScheduler()
            # Daily housekeeping at 00:30
            log_timing("Adding daily housekeeping job")
            scheduler.add_job(
                lambda: asyncio.create_task(trading_logger.daily_housekeeping()),
                CronTrigger(hour=0, minute=30),
                name="daily_housekeeping"
            )

            # Schedule to run every weekday at 9:00 AM: build intraday watchlist
            log_timing("Adding intraday watchlist builder job")
            try:
                from services.scheduler_tasks import build_daily_intraday_watchlist
                scheduler.add_job(
                    lambda: asyncio.create_task(build_daily_intraday_watchlist()),
                    CronTrigger(day_of_week='mon-fri', hour=9, minute=0),
                    name="build_intraday_watchlist"
                )
                logger.info("Scheduled daily intraday watchlist builder (weekdays at 09:00)")
                log_timing("Intraday watchlist builder job added successfully")
            except Exception as e:
                logger.warning(f"Failed to schedule intraday watchlist builder: {str(e)}")
                log_timing(f"Intraday watchlist builder scheduling failed: {str(e)}")

            # Prefetch watchlist historical data every 30 minutes
            log_timing("Adding watchlist historical data prefetch job")
            try:
                from services.scheduler_tasks import prefetch_watchlist_historical_data
                scheduler.add_job(
                    lambda: asyncio.create_task(prefetch_watchlist_historical_data()),
                    IntervalTrigger(minutes=30),
                    name="prefetch_watchlist_historical_30m",
                    coalesce=True,
                    max_instances=1
                )
                logger.info("Scheduled 30-minute watchlist historical prefetch")
                log_timing("Watchlist historical data prefetch job added successfully")
            except Exception as e:
                logger.warning(f"Failed to schedule 30-minute historical prefetch: {str(e)}")
                log_timing(f"Watchlist historical prefetch scheduling failed: {str(e)}")

            log_timing("Starting main scheduler")
            scheduler.start()
            app.state.scheduler = scheduler
            logger.info("Scheduler started for housekeeping and screening tasks")
            log_timing("Main scheduler started successfully")
            
            # Start the trading strategy scheduler if enabled
            log_timing("Starting trading strategy scheduler")
            try:
                trading_scheduler = get_trading_scheduler()
                await trading_scheduler.start()
                app.state.trading_scheduler = trading_scheduler
                logger.info("🚀 Trading strategy scheduler started successfully")
                log_timing("Trading strategy scheduler started successfully")
            except Exception as e:
                logger.warning(f"Failed to start trading strategy scheduler: {str(e)}")
                log_timing(f"Trading strategy scheduler failed: {str(e)}")
        else:
            logger.info("Scheduler disabled by configuration (ENABLE_SCHEDULER=false)")
            log_timing("Scheduler disabled by configuration")
    except Exception as e:
        logger.warning(f"Failed to start scheduler: {str(e)}")
        log_timing(f"Scheduler initialization failed: {str(e)}")

    log_timing("STARTUP COMPLETE - Application ready to serve requests")
    yield
    
    # Shutdown
    log_timing("Starting application shutdown")
    logger.info("Shutting down Stock Trading System...")
    trading_logger.log_system_event("application_shutdown")
    try:
        if getattr(app.state, "market_stream_service", None):
            await app.state.market_stream_service.disconnect()
            logger.info("Market stream service stopped.")
    except Exception as e:
        logger.error(f"Error stopping market stream service: {e}")
    try:
        if getattr(app.state, "telegram_bot", None):
            await app.state.telegram_bot.stop()
            logger.info("Telegram bot stopped")
    except Exception as e:
        logger.error(f"Error stopping Telegram bot: {str(e)}")
    try:
        if getattr(app.state, "scheduler", None):
            app.state.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {str(e)}")
    try:
        if getattr(app.state, "trading_scheduler", None):
            await app.state.trading_scheduler.stop()
            logger.info("🛑 Trading strategy scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping trading scheduler: {str(e)}")
    await close_db()
    logger.info("Database connections closed")
    trading_logger.log_system_event("database_closed")

# Create FastAPI app
app = FastAPI(
    title="Stock Trading System",
    description="Automated stock trading system with IIFL API integration",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Sentry (if configured)
_settings_for_sentry = get_settings()
SentryAsgiMiddleware = init_sentry(_settings_for_sentry)
if SentryAsgiMiddleware is not None:
    try:
        app.add_middleware(SentryAsgiMiddleware)
    except Exception as e:
        logger.warning(f"Failed to add Sentry middleware: {str(e)}")

# Include API routers
app.include_router(system_router)
app.include_router(signals_router)
app.include_router(portfolio_router)
app.include_router(risk_router)
app.include_router(reports_router)
app.include_router(backtest_router)
app.include_router(settings_router)
app.include_router(events_router)
app.include_router(auth_router)
app.include_router(watchlist_router)
app.include_router(margin_router, prefix="/api/margin", tags=["margin"])
app.include_router(scheduler_router, prefix="/api", tags=["scheduler"])

# HTTP logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    body = await request.body()

    async def receive():
        return {"type": "http.request", "body": body}

    new_request = Request(request.scope, receive)

    request_body_to_log = None
    if body:
        try:
            request_body_to_log = json.loads(body)
        except json.JSONDecodeError:
            request_body_to_log = body.decode('utf-8', errors='ignore')

    try:
        response = await call_next(new_request)
        duration = time.perf_counter() - start
        err: str = None
        if response.status_code >= 500:
            err = f"Server error {response.status_code}"
        trading_logger.log_api_call(
            endpoint=str(request.url.path),
            method=request.method,
            status_code=response.status_code,
            response_time=duration,
            error=err,
            request_body=request_body_to_log
        )
        return response
    except Exception as e:
        duration = time.perf_counter() - start
        trading_logger.log_api_call(
            endpoint=str(request.url.path),
            method=request.method,
            status_code=500,
            response_time=duration,
            error=str(e),
            request_body=request_body_to_log
        )
        trading_logger.log_error("api", e, {"path": str(request.url.path), "method": request.method})
        raise

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/reports")
async def reports_page(request: Request):
    """Reports listing page"""
    return templates.TemplateResponse("reports.html", {"request": request})

@app.get("/signals")
async def signals_page(request: Request):
    """Signals management page"""
    return templates.TemplateResponse("signals.html", {"request": request})

@app.get("/backtest")
async def backtest_page(request: Request):
    """Backtesting page"""
    return templates.TemplateResponse("backtest.html", {"request": request})

@app.get("/risk-monitor")
async def risk_monitor_page(request: Request):
    """Real-time risk monitoring page"""
    return templates.TemplateResponse("risk-monitor.html", {"request": request})

@app.get("/portfolio")
async def portfolio_page(request: Request):
    """Portfolio overview page"""
    return templates.TemplateResponse("portfolio.html", {"request": request})

@app.get("/settings")
async def settings_page(request: Request):
    """Settings configuration page"""
    return templates.TemplateResponse("settings.html", {"request": request})

@app.get("/watchlist")
async def watchlist_page(request: Request):
    """Watchlist management page"""
    return templates.TemplateResponse("watchlist.html", {"request": request})

@app.get("/auth")
async def auth_management_page(request: Request):
    """IIFL Authentication management page"""
    return templates.TemplateResponse("auth_management.html", {"request": request})

@app.get("/guide")
async def user_guide_page(request: Request):
    """Static user guide documentation page"""
    # Serve the more comprehensive user guide template; keep the older
    # guide.html present for compatibility but prefer user_guide.html.
    try:
        return templates.TemplateResponse("user_guide.html", {"request": request})
    except Exception:
        return templates.TemplateResponse("guide.html", {"request": request})

if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )
