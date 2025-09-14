from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from typing import Dict, Any
from datetime import datetime
import logging
from models.database import get_db
from services.risk import RiskService
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService
from config import get_settings
from models.settings import Setting

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)

@router.get("/status")
async def get_system_status(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get system health and status"""
    logger.info("Request for system status.")
    try:
        settings = get_settings()
        
        # Resolve auto_trade preference: DB override wins over env config
        auto_trade_value = settings.auto_trade
        try:
            stmt = select(Setting).where(Setting.key == "auto_trade")
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()
            if row is not None:
                val = row.get_typed_value()
                if isinstance(val, bool):
                    auto_trade_value = val
                elif isinstance(val, str):
                    auto_trade_value = val.lower() == "true"
        except Exception as e:
            logger.warning(f"Failed to read auto_trade from DB: {str(e)}")

        # Basic system info
        status = {
            "environment": settings.environment,
            "auto_trade": auto_trade_value,
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
            await db.execute(text("SELECT 1"))
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
        # Persist auto_trade = false in settings table
        logger.critical("MANUAL TRADING HALT REQUESTED")
        try:
            stmt = select(Setting).where(Setting.key == "auto_trade")
            result = await db.execute(stmt)
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = "false"
            else:
                setting = Setting(key="auto_trade", value="false")
                db.add(setting)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to persist auto_trade halt: {str(e)}")
        
        return {"message": "Trading halted successfully", "status": "halted"}
        
    except Exception as e:
        logger.error(f"Error halting trading: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resume")
async def resume_trading(db: AsyncSession = Depends(get_db)) -> Dict[str, str]:
    """Resume trading after halt"""
    try:
        logger.info("MANUAL TRADING RESUME REQUESTED")
        # Persist auto_trade = true in settings table
        try:
            stmt = select(Setting).where(Setting.key == "auto_trade")
            result = await db.execute(stmt)
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = "true"
            else:
                setting = Setting(key="auto_trade", value="true")
                db.add(setting)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to persist auto_trade resume: {str(e)}")
        
        return {"message": "Trading resumed successfully", "status": "active"}
        
    except Exception as e:
        logger.error(f"Error resuming trading: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Simple health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
