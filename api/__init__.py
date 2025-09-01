from .system import router as system_router
from .signals import router as signals_router
from .portfolio import router as portfolio_router
from .risk import router as risk_router
from .reports import router as reports_router
from .backtest import router as backtest_router
from .settings import router as settings_router

__all__ = [
    "system_router",
    "signals_router", 
    "portfolio_router",
    "risk_router",
    "reports_router",
    "backtest_router",
    "settings_router"
]
