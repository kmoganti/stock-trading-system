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
        # Tests often patch get_settings to return a plain dict
        if isinstance(settings, dict):
            s = settings
            current_settings = {
                "auto_trade": s.get("auto_trade", False),
                "signal_timeout": s.get("signal_timeout", 300),
                "risk_per_trade": s.get("risk_per_trade", 0.02),
                "max_positions": s.get("max_positions", 10),
                "max_daily_loss": s.get("max_daily_loss", None),
                "min_price": s.get("min_price", None),
                "min_liquidity": s.get("min_liquidity", None),
                "environment": s.get("environment", "dev")
            }
        else:
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
        env = settings.get("environment") if isinstance(settings, dict) else getattr(settings, "environment", "unknown")
        logger.info(f"Returning current settings for environment: {env}")
        return current_settings

    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.put("")
async def update_settings(
    settings_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
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
        
        # Ensure updated_keys is a string list - FastAPI/Pydantic response validators
        updated_keys = list(settings_data.keys())
        # FastAPI/pydantic in tests may expect string values for updated_keys
        updated_keys_str = [str(k) for k in updated_keys]
        return {
            "message": "Settings updated successfully",
            "updated_keys": updated_keys_str,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
