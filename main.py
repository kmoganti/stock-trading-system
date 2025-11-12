# Standard library imports
import asyncio
import functools
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
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
from fastapi.responses import HTMLResponse
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
from api.scheduler_comparison import router as scheduler_comparison_router
log_timing("Loaded additional API routers")

# Services scheduler for global access
log_timing("Loading trading schedulers (old and optimized)")
from services.scheduler import get_trading_scheduler
from services.optimized_scheduler import get_optimized_scheduler, start_optimized_scheduler, stop_optimized_scheduler
log_timing("Completed all imports")

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# The TradingLogger service handles all application-specific logging configurations.

# Suppress watchfiles logging spam
logging.getLogger('watchfiles').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
SAFE_MODE = os.getenv("SAFE_MODE", "false").lower() == "true"

if SAFE_MODE:
    # Reduce noise across common noisy libraries to keep app responsive
    for name in (
        "",
        "trading",
        "trading.main",
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "apscheduler",
        "httpx",
        "sqlalchemy",
        "watchfiles",
    ):
        try:
            logging.getLogger(name).setLevel(logging.WARNING)
        except Exception:
            pass
    logger.warning("SAFE_MODE enabled: reduced logging, optional services disabled")

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
    
    # Initialize Redis connection
    log_timing("Initializing Redis connection")
    try:
        from services.redis_service import get_redis_service
        redis = await get_redis_service()
        if redis.is_connected():
            logger.info("✅ Redis cache connected")
            log_timing("Redis cache connected")
        else:
            logger.warning("⚠️ Redis cache not available - continuing without cache")
            log_timing("Redis cache connection failed")
    except Exception as e:
        logger.warning(f"⚠️ Redis initialization failed: {e} - continuing without cache")
        log_timing(f"Redis init failed: {e}")
    
    # Ensure database schema is up-to-date (idempotent)
    # In SAFE_MODE, skip DB initialization to avoid blocking startup when DB is unavailable
    if SAFE_MODE:
        logger.warning("SAFE_MODE=true - skipping database initialization")
        log_timing("Database initialization skipped (SAFE_MODE)")
    else:
        from models.database import init_db as _ensure_db
        try:
            # Prevent startup hang if DB is unreachable
            await asyncio.wait_for(_ensure_db(), timeout=3.0)
            log_timing("Database initialized/migrated")
        except asyncio.TimeoutError:
            logger.warning("⚠️ Database initialization timed out at startup - continuing without DB")
            log_timing("Database init timed out - continuing")
        except Exception as _e:
            # Do NOT fail startup; log and continue so HTTP server binds
            logger.warning(f"⚠️ Database initialization failed at startup: {_e} - continuing without DB")
            log_timing(f"Database init failed - continuing: {_e}")
    
    log_timing("Logging system events")
    trading_logger.log_system_event("application_startup", {"version": "1.0.0"})
    trading_logger.log_system_event("database_initialized")
    app.state.market_stream_service = None
    
    # Start Telegram bot if configured (disabled in SAFE_MODE)
    log_timing("Starting Telegram bot initialization")
    app.state.telegram_bot = None
    try:
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        log_timing("Getting settings for Telegram")
        settings_for_telegram = get_settings()
        if (not SAFE_MODE) and telegram_token and telegram_chat_id and getattr(settings_for_telegram, "telegram_bot_enabled", False):
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

    # Start Market Data Stream listener (disabled in SAFE_MODE)
    log_timing("Starting Market Data Stream initialization")
    try:
        # Check if market stream is enabled
        log_timing("Getting settings for market stream")
        settings_for_stream = get_settings()
        enable_market_stream = getattr(settings_for_stream, "enable_market_stream", True)
        enable_market_stream = os.getenv("ENABLE_MARKET_STREAM", "true").lower() == "true" if enable_market_stream else False
        
        if SAFE_MODE or not enable_market_stream:
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
    
    # One-time daily refresh of portfolio and margin caches at startup 
    # (can be disabled with ENABLE_STARTUP_CACHE_WARMUP=false)
    if (not SAFE_MODE) and os.getenv("ENABLE_STARTUP_CACHE_WARMUP", "false").lower() == "true":
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
    else:
        log_timing("Startup cache warmup disabled by configuration")
    
    # Schedule daily housekeeping (log pruning) at 00:30) - disabled in SAFE_MODE
    log_timing("Starting scheduler initialization")
    try:
        log_timing("Getting settings for scheduler")
        settings = get_settings()
        if (not SAFE_MODE) and getattr(settings, "enable_scheduler", False):
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
                from datetime import datetime, timedelta
                # Start 5 minutes after app startup to avoid blocking
                start_time = datetime.now() + timedelta(minutes=5)
                scheduler.add_job(
                    lambda: asyncio.create_task(prefetch_watchlist_historical_data()),
                    IntervalTrigger(minutes=30, start_date=start_time),
                    name="prefetch_watchlist_historical_30m",
                    coalesce=True,
                    max_instances=1
                )
                logger.info(f"Scheduled 30-minute watchlist historical prefetch (starting at {start_time.strftime('%H:%M')})")
                log_timing("Watchlist historical data prefetch job added successfully")
            except Exception as e:
                logger.warning(f"Failed to schedule 30-minute historical prefetch: {str(e)}")
                log_timing(f"Watchlist historical prefetch scheduling failed: {str(e)}")

            log_timing("Starting main scheduler")
            scheduler.start()
            app.state.scheduler = scheduler
            logger.info("Scheduler started for housekeeping and screening tasks")
            log_timing("Main scheduler started successfully")

            # Start ONLY optimized scheduler (old scheduler disabled)
            log_timing("Starting OPTIMIZED trading strategy scheduler")

            # OLD scheduler is DISABLED
            # try:
            #     trading_scheduler = get_trading_scheduler()
            #     await trading_scheduler.start()
            #     app.state.trading_scheduler = trading_scheduler
            #     logger.info("🔵 OLD Trading strategy scheduler started successfully")
            # except Exception as e:
            #     logger.warning(f"Failed to start OLD trading strategy scheduler: {str(e)}")

            # Start optimized scheduler ONLY
            try:
                # Start optimized scheduler in background to avoid blocking startup
                async def _start_opt_sched_bg():
                    try:
                        await start_optimized_scheduler()
                        optimized_scheduler = get_optimized_scheduler()
                        app.state.optimized_scheduler = optimized_scheduler
                        logger.info("🟢 OPTIMIZED Trading strategy scheduler started (background)")
                    except Exception as _e:
                        logger.warning(f"Failed to start OPTIMIZED scheduler (bg): {_e}")

                asyncio.create_task(_start_opt_sched_bg())
                logger.info("⌛ OPTIMIZED Trading strategy scheduler starting in background")
                log_timing("OPTIMIZED trading strategy scheduler scheduled (background)")
            except Exception as e:
                logger.warning(f"Failed to schedule OPTIMIZED trading strategy scheduler: {str(e)}")
                log_timing(f"OPTIMIZED trading strategy scheduler schedule failed: {str(e)}")

            logger.info("🚀 PRODUCTION MODE: Optimized scheduler active (old scheduler disabled)")
            log_timing("PRODUCTION MODE: Optimized scheduler active")
        else:
            logger.info("Scheduler disabled by configuration or SAFE_MODE")
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
    
    # Close Redis connection
    try:
        from services.redis_service import close_redis_service
        await close_redis_service()
        logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")
    
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
    # OLD scheduler disabled - no need to stop
    # try:
    #     if getattr(app.state, "trading_scheduler", None):
    #         await app.state.trading_scheduler.stop()
    #         logger.info("🛑 OLD Trading strategy scheduler stopped")
    # except Exception as e:
    #     logger.error(f"Error stopping OLD trading scheduler: {str(e)}")
    try:
        if getattr(app.state, "optimized_scheduler", None):
            await stop_optimized_scheduler()
            logger.info("🛑 OPTIMIZED Trading strategy scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping OPTIMIZED trading scheduler: {str(e)}")
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
app.include_router(scheduler_comparison_router, prefix="/api", tags=["scheduler-comparison"])

# Lightweight health check for external monitors (e.g., production_health_check)
@app.get("/health")
async def health() -> dict:
    """Simple liveness probe that avoids any heavy dependencies."""
    return {"status": "ok", "timestamp": time.time()}

@app.get("/test")
async def test_endpoint():
    """Test endpoint to verify JSON responses work"""
    return {"message": "Test works!", "timestamp": time.time()}

# HTTP logging middleware - DISABLED due to hanging issues with HTML pages
# The middleware was causing timeouts on dashboard/homepage loads
# API endpoints have their own logging, so this is redundant
# 
# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     start = time.perf_counter()
#     
#     # Skip body reading for logging to avoid blocking - it causes hangs
#     # The actual endpoint will read the body if needed
#     request_body_to_log = None
#     
#     # Don't try to read request body in middleware as it can cause hangs
#     # if request.method in ("POST", "PUT", "PATCH"):
#     #     try:
#     #         body = await asyncio.wait_for(request.body(), timeout=1.0)
#     #         # ... body processing
#     #     except Exception as e:
#     #         logger.warning(f"Failed to read request body: {e}")
# 
#     try:
#         response = await call_next(request)
#         duration = time.perf_counter() - start
#         err: str = None
#         if response.status_code >= 500:
#             err = f"Server error {response.status_code}"
#         trading_logger.log_api_call(
#             endpoint=str(request.url.path),
#             method=request.method,
#             status_code=response.status_code,
#             response_time=duration,
#             error=err,
#             request_body=request_body_to_log
#         )
#         return response
#     except Exception as e:
#         duration = time.perf_counter() - start
#         trading_logger.log_api_call(
#             endpoint=str(request.url.path),
#             method=request.method,
#             status_code=500,
#             response_time=duration,
#             error=str(e),
#             request_body=request_body_to_log
#         )
#         trading_logger.log_error("api", e, {"path": str(request.url.path), "method": request.method})
#         raise

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# Templates
templates = Jinja2Templates(directory="templates")

# CRITICAL FIX: Jinja2 TemplateResponse is SYNCHRONOUS and blocks the async event loop
# Template rendering - use TemplateResponse directly (FastAPI handles it asynchronously)
async def render_template_async(template_name: str, request: Request, **kwargs):
    """Render template and return TemplateResponse"""
    context = {"request": request, **kwargs}
    # TemplateResponse is the proper way - FastAPI's StreamingResponse handles it async
    return templates.TemplateResponse(template_name, context)

@app.get("/")
async def dashboard(request: Request):
    """Main dashboard page"""
    return await render_template_async("dashboard.html", request)

@app.get("/reports")
async def reports_page(request: Request):
    """Reports listing page"""
    return await render_template_async("reports.html", request)

@app.get("/signals")
async def signals_page(request: Request):
    """Signals management page"""
    return await render_template_async("signals.html", request)

@app.get("/backtest")
async def backtest_page(request: Request):
    """Backtesting page"""
    return await render_template_async("backtest.html", request)

@app.get("/risk-monitor")
async def risk_monitor_page(request: Request):
    """Real-time risk monitoring page"""
    return await render_template_async("risk-monitor.html", request)

@app.get("/portfolio")
async def portfolio_page(request: Request):
    """Portfolio overview page"""
    return await render_template_async("portfolio.html", request)

@app.get("/settings")
async def settings_page(request: Request):
    """Settings configuration page"""
    return await render_template_async("settings.html", request)

@app.get("/watchlist")
async def watchlist_page(request: Request):
    """Watchlist management page"""
    return await render_template_async("watchlist.html", request)

@app.get("/auth")
async def auth_management_page(request: Request):
    """IIFL Authentication management page"""
    return await render_template_async("auth_management.html", request)

@app.get("/guide")
async def user_guide_page(request: Request):
    """Static user guide documentation page"""
    try:
        return await render_template_async("user_guide.html", request)
    except Exception:
        return await render_template_async("guide.html", request)

@app.get("/parallel-scheduler-test")
async def parallel_scheduler_dashboard(request: Request):
    """Parallel scheduler testing dashboard"""
    return await render_template_async("parallel_scheduler_dashboard.html", request)

if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )
