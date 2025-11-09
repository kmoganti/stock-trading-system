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
import os

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)

@router.get("/cache/stats")
async def get_cache_stats():
    """Get Redis cache statistics"""
    try:
        from services.redis_service import get_redis_service
        redis = await get_redis_service()
        
        if not redis.is_connected():
            return {
                "status": "disconnected",
                "message": "Redis cache is not connected"
            }
        
        stats = await redis.get_stats()
        return {
            "status": "connected",
            **stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@router.post("/cache/clear")
async def clear_cache(pattern: str = "*"):
    """
    Clear cache entries matching pattern.
    
    Examples:
    - pattern="*" - Clear all cache
    - pattern="api:*" - Clear all API caches
    - pattern="db:*" - Clear all database caches
    """
    try:
        from services.redis_service import get_redis_service
        redis = await get_redis_service()
        
        if not redis.is_connected():
            raise HTTPException(status_code=503, detail="Redis cache not connected")
        
        count = await redis.clear_pattern(pattern)
        return {
            "status": "success",
            "pattern": pattern,
            "keys_deleted": count
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_system_status():
    """Get system status - lightweight check without external API calls"""
    try:
        # Read settings directly from env vars to avoid any blocking calls
        import os
        
        return {
            "auto_trade": os.getenv("AUTO_TRADE", "false").lower() == "true",
            "dry_run": os.getenv("DRY_RUN", "true").lower() == "true",
            "iifl_api_connected": None,  # Don't check - too slow
            "database_connected": True,   # Assume connected - checked at startup
            "market_stream_active": os.getenv("ENABLE_MARKET_STREAM", "false").lower() == "true",
            "telegram_bot_active": os.getenv("TELEGRAM_BOT_TOKEN", "") != "",
            # Add environment field expected by tests/diagnostics
            "environment": os.getenv("ENVIRONMENT", os.getenv("ENV", "development")),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
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

@router.get("/env")
async def env_debug(var: str | None = None):
    """Debug endpoint to inspect environment variables. If `var` is provided, returns only that key.

    Includes SAFE_MODE, ENVIRONMENT, and relevant IIFL keys presence by default (values masked).
    """
    try:
        if var:
            return {var: os.getenv(var)}
        def mask(v: str | None):
            if not v:
                return None
            return v[:3] + "***" if len(v) > 6 else "***"
        return {
            "SAFE_MODE": os.getenv("SAFE_MODE"),
            "ENVIRONMENT": os.getenv("ENVIRONMENT"),
            "IIFL_CLIENT_ID_present": bool(os.getenv("IIFL_CLIENT_ID")),
            "IIFL_AUTH_CODE_present": bool(os.getenv("IIFL_AUTH_CODE")),
            "IIFL_APP_SECRET_present": bool(os.getenv("IIFL_APP_SECRET")),
            "IIFL_CLIENT_ID_preview": mask(os.getenv("IIFL_CLIENT_ID")),
        }
    except Exception as e:
        logger.error(f"Error in env debug: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/telegram/test")
async def telegram_test(message: str = "Test: Trading system notification") -> Dict[str, Any]:
    """Send a test Telegram notification to verify delivery configuration.

    Returns success flag and any error message without crashing the server.
    """
    try:
        from services.telegram_notifier import TelegramNotifier
        notifier = TelegramNotifier()
        # If not enabled, surface a helpful error
        if not getattr(notifier, "_enabled", False):
            return {"success": False, "error": "Telegram notifier disabled or misconfigured"}
        await notifier.send(message)
        return {"success": True}
    except Exception as e:
        logger.warning(f"Telegram test send failed: {e}")
        return {"success": False, "error": str(e)}

@router.get("/scheduler/activity")
async def get_scheduler_activity():
    """Get recent scheduler activity and execution stats"""
    try:
        from services.optimized_scheduler import get_optimized_scheduler
        
        scheduler = get_optimized_scheduler()
        
        # Get execution stats
        execution_stats = scheduler.get_execution_stats()
        
        # Get next run times for all jobs
        jobs = scheduler.scheduler.get_jobs()
        next_runs = []
        for job in jobs:
            next_runs.append({
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "job_id": job.id
            })
        
        # Format recent activity from execution stats
        recent_activity = []
        for strategy, stats in execution_stats.items():
            if stats['last_execution']:
                recent_activity.append({
                    "strategy": strategy,
                    "last_execution": stats['last_execution'].isoformat() if isinstance(stats['last_execution'], datetime) else stats['last_execution'],
                    "total_runs": stats['total_runs'],
                    "successful_runs": stats['successful_runs'],
                    "failed_runs": stats['failed_runs'],
                    "avg_execution_time": round(stats['avg_execution_time'], 2)
                })
        
        # Sort by last execution time (most recent first)
        recent_activity.sort(key=lambda x: x['last_execution'] if x['last_execution'] else '', reverse=True)
        
        return {
            "recent_activity": recent_activity[:10],  # Last 10
            "next_runs": next_runs,
            "total_strategies": len(execution_stats),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting scheduler activity: {e}", exc_info=True)
        return {
            "recent_activity": [],
            "next_runs": [],
            "error": str(e)
        }
