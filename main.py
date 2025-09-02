import asyncio
import logging
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from config.settings import get_settings
from models.database import init_db, close_db
from api import (
    system_router, signals_router, portfolio_router, 
    risk_router, reports_router, backtest_router, settings_router
)
from api.margin import router as margin_router
from api.auth_management import router as auth_router

# Import and configure logging service
from services.logging_service import trading_logger
import os

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure root logger to use our trading logger with DEBUG level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/trading_system.log'),
        logging.StreamHandler()
    ]
)

# Suppress watchfiles logging spam
logging.getLogger('watchfiles').setLevel(logging.WARNING)
logging.getLogger('watchfiles.main').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Stock Trading System...")
    trading_logger.log_system_event("application_startup", {"version": "1.0.0"})
    await init_db()
    logger.info("Database initialized")
    trading_logger.log_system_event("database_initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Stock Trading System...")
    trading_logger.log_system_event("application_shutdown")
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

# Include API routers
app.include_router(system_router)
app.include_router(signals_router)
app.include_router(portfolio_router)
app.include_router(risk_router)
app.include_router(reports_router)
app.include_router(backtest_router)
app.include_router(settings_router)
app.include_router(auth_router)
app.include_router(margin_router, prefix="/api/margin", tags=["margin"])

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

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
