from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import logging
from models.database import get_db
from models.settings import Setting
from config import get_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)

@router.get("")
async def get_current_settings(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get current system settings"""
    logger.info("Request for current system settings.")
    try:
        settings = get_settings()
        
        current_settings = {
            "auto_trade": settings.auto_trade,
            "signal_timeout": settings.signal_timeout,
            "risk_per_trade": settings.risk_per_trade,
            "max_positions": settings.max_positions,
            "max_daily_loss": settings.max_daily_loss,
            "min_price": settings.min_price,
            "min_liquidity": settings.min_liquidity,
            "environment": settings.environment
        }
        logger.info(f"Returning current settings for environment: {settings.environment}")
        return current_settings
        
    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.put("")
async def update_settings(
    settings_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """Update system settings"""
    logger.info(f"Request to update settings with data: {settings_data}")
    try:
        from sqlalchemy import select
        
        # Update settings in database
        for key, value in settings_data.items():
            stmt = select(Setting).where(Setting.key == key)
            result = await db.execute(stmt)
            setting = result.scalar_one_or_none()
            
            if setting:
                setting.value = str(value)
            else:
                setting = Setting(key=key, value=str(value))
                db.add(setting)
        
        await db.commit()
        
        logger.info(f"Settings updated: {list(settings_data.keys())}")
        
        return {
            "message": "Settings updated successfully",
            "updated_keys": list(settings_data.keys())
        }
        
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
