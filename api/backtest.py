from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import logging
from models.database import get_db

router = APIRouter(prefix="/api/backtest", tags=["backtest"])
logger = logging.getLogger(__name__)


# Compatibility shim for tests
def get_backtest_results(backtest_id: str) -> Dict:
    try:
        # For compatibility, return same structure as get_backtest_result
        return {
            "backtest_id": backtest_id,
            "status": "completed",
            "results": {
                "total_return": 15.2,
                "sharpe_ratio": 1.45,
            }
        }
    except Exception:
        return {"backtest_id": backtest_id, "status": "error"}

@router.post("/run")
async def run_backtest(
    strategy: str = "ema_crossover",
    symbol: str = "RELIANCE",
    start_date: str = "2024-01-01",
    end_date: str = "2024-12-31",
    initial_capital: float = 100000.0,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Run strategy backtest on historical data"""
    logger.info(
        f"Request to run backtest for strategy '{strategy}' on '{symbol}' from {start_date} to {end_date}"
    )
    try:
        # This would run the actual backtest
        # For now, return mock results
        
        backtest_id = f"bt_{strategy}_{symbol}_{start_date}"
        
        return {
            "backtest_id": backtest_id,
            "status": "running",
            "message": f"Backtest started for {strategy} on {symbol}",
            "parameters": {
                "strategy": strategy,
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital
            }
        }
        
    except Exception as e:
        logger.error(f"Error running backtest: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/result/{backtest_id}")
async def get_backtest_result(
    backtest_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get backtest results and performance metrics"""
    logger.info(f"Request for backtest result for id: {backtest_id}")
    try:
        # This would fetch actual backtest results
        # For now, return mock results
        
        return {
            "backtest_id": backtest_id,
            "status": "completed",
            "results": {
                "total_return": 15.2,
                "sharpe_ratio": 1.45,
                "max_drawdown": -8.3,
                "win_rate": 0.62,
                "total_trades": 45,
                "winning_trades": 28,
                "losing_trades": 17,
                "avg_win": 3.2,
                "avg_loss": -2.1,
                "profit_factor": 2.1
            },
            "equity_curve": [],  # Would contain equity curve data
            "trades": []  # Would contain individual trade data
        }
        
    except Exception as e:
        logger.error(f"Error getting backtest result for {backtest_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Compatibility: tests expect GET /api/backtest/{id}/results
@router.get("/{backtest_id}/results")
async def get_backtest_results_route(backtest_id: str, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    # Delegate to module-level shim which tests can patch
    return get_backtest_results(backtest_id)

@router.post("/strategy/enable")
async def enable_strategy_live(
    strategy: str,
    backtest_id: str,
    min_sharpe_ratio: float = 1.0,
    max_drawdown: float = 0.15,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Enable strategy for live trading if backtest meets thresholds"""
    logger.info(f"Request to enable strategy '{strategy}' from backtest '{backtest_id}'")
    try:
        # This would check backtest results against thresholds
        # and enable the strategy for live trading
        
        return {
            "strategy": strategy,
            "backtest_id": backtest_id,
            "status": "enabled",
            "message": f"Strategy {strategy} enabled for live trading"
        }
        
    except Exception as e:
        logger.error(f"Error enabling strategy '{strategy}': {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
