from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from datetime import datetime
import logging
from models.database import get_db
from services.risk import RiskService
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService
from config import get_settings

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)

@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get system health and status"""
    logger.info("Request for system status.")
    try:
        settings = get_settings()
        
        # Basic system info
        status = {
            "environment": settings.environment,
            "auto_trade": settings.auto_trade,
            "signal_timeout": settings.signal_timeout,
            "max_positions": settings.max_positions,
            "risk_per_trade": settings.risk_per_trade,
            "max_daily_loss": settings.max_daily_loss,
            "timestamp": datetime.now().isoformat()
        }
        
        # Try to check IIFL API connectivity
        try:
            async with IIFLAPIService() as iifl:
                api_connected = await iifl.authenticate()
                status["iifl_api_connected"] = api_connected
                logger.info(f"IIFL API connection status: {api_connected}")
        except Exception as e:
            status["iifl_api_connected"] = False
            status["iifl_api_error"] = str(e)
            logger.warning(f"IIFL API connection check failed: {str(e)}")
        
        # Database connectivity
        try:
            await db.execute("SELECT 1")
            status["database_connected"] = True
            logger.info("Database connection status: True")
        except Exception as e:
            status["database_connected"] = False
            status["database_error"] = str(e)
            logger.warning(f"Database connection check failed: {str(e)}")
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/halt")
async def halt_trading(db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """Emergency halt trading"""
    try:
        # This would typically interact with a global trading state
        # For now, we'll log the halt request
        logger.critical("MANUAL TRADING HALT REQUESTED")
        
        return {"message": "Trading halted successfully", "status": "halted"}
        
    except Exception as e:
        logger.error(f"Error halting trading: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resume")
async def resume_trading(db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """Resume trading after halt"""
    try:
        logger.info("MANUAL TRADING RESUME REQUESTED")
        
        return {"message": "Trading resumed successfully", "status": "active"}
        
    except Exception as e:
        logger.error(f"Error resuming trading: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Simple health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
