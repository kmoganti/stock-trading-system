import asyncio
import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import time
import json

from config.settings import get_settings
from models.database import init_db, close_db
from api import (
    system_router, signals_router, portfolio_router, 
    risk_router, reports_router, backtest_router, settings_router, events_router
)
from api.margin import router as margin_router
from api.auth_management import router as auth_router
from api.watchlist import router as watchlist_router

# Import and configure logging service
from services.logging_service import trading_logger
import os
from telegram_bot.bot import TelegramBot
from telegram_bot.handlers import setup_handlers
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.iifl_api import IIFLAPIService
from services.screener import ScreenerService
from services.watchlist import WatchlistService
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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
    logger.info("Starting Stock Trading System...")
    trading_logger.log_system_event("application_startup", {"version": "1.0.0"})
    trading_logger.log_system_event("database_initialized")
    app.state.market_stream_service = None
    
    # Start Telegram bot if configured
    app.state.telegram_bot = None
    try:
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if telegram_token and telegram_chat_id:
            bot = TelegramBot()
            await setup_handlers(bot)
            await bot.start()
            app.state.telegram_bot = bot
            logger.info("Telegram bot started")
        else:
            logger.warning("Telegram bot not started: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
    except Exception as e:
        logger.error(f"Failed to start Telegram bot: {str(e)}")

    # Start Market Data Stream listener
    try:
        from services.market_stream import MarketStreamService
        from models.database import AsyncSessionLocal

        # Authenticate first to get a token
        iifl_service = IIFLAPIService()
        if await iifl_service.authenticate() and not iifl_service.session_token.startswith("mock_"):
            async with AsyncSessionLocal() as session:
                watchlist_service = WatchlistService(session)
                screener_service = ScreenerService(watchlist_service)
                stream_service = MarketStreamService(iifl_service, screener_service)
                await stream_service.connect_and_subscribe()
                app.state.market_stream_service = stream_service
        else:
            logger.warning("Could not start market stream: IIFL authentication failed or using mock token.")
    except Exception as e:
        logger.error(f"Failed to start market data stream: {e}", exc_info=True)
    
    # Schedule daily housekeeping (log pruning) at 00:30
    # try:
    #     scheduler = AsyncIOScheduler()
    #     scheduler.add_job(
    #         lambda: asyncio.create_task(trading_logger.daily_housekeeping()),
    #         CronTrigger(hour=0, minute=30),
    #         name="daily_housekeeping"
    #     )
    #     # Prefetch watchlist historical data every 30 minutes
    #     try:
    #         from services.scheduler_tasks import build_daily_intraday_watchlist
    #         # Schedule to run every weekday at 9:00 AM
    #         scheduler.add_job(
    #             lambda: asyncio.create_task(build_daily_intraday_watchlist()),
    #             CronTrigger(day_of_week='mon-fri', hour=9, minute=0),
    #             name="build_intraday_watchlist"
    #         )
    #         logger.info("Scheduled daily intraday watchlist builder")
    #     except Exception as e:
    #         logger.warning(f"Failed to schedule intraday watchlist builder: {str(e)}")
    #     try:
    #         from services.scheduler_tasks import prefetch_watchlist_historical_data
    #         scheduler.add_job(
    #             lambda: asyncio.create_task(prefetch_watchlist_historical_data()),
    #             IntervalTrigger(minutes=30),
    #             name="prefetch_watchlist_historical_30m",
    #             coalesce=True,
    #             max_instances=1
    #         )
    #         logger.info("Scheduled 30-minute watchlist historical prefetch")
    #     except Exception as e:
    #         logger.warning(f"Failed to schedule 30-minute historical prefetch: {str(e)}")
    #     scheduler.start()
    #     app.state.scheduler = scheduler
    #     logger.info("Scheduler started for daily housekeeping")
    # except Exception as e:
    #     logger.warning(f"Failed to start scheduler: {str(e)}")

    yield
    
    # Shutdown
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

if __name__ == "__main__":
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )
