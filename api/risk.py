from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List
import logging
from models.database import get_db
from services.risk import RiskService
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService

router = APIRouter(prefix="/api/risk", tags=["risk"])
logger = logging.getLogger(__name__)

# Centralized dependency for DataFetcher
def get_data_fetcher(db: AsyncSession = Depends(get_db)) -> DataFetcher:
    iifl = IIFLAPIService()
    return DataFetcher(iifl, db_session=db)

def get_risk_service(
    data_fetcher: DataFetcher = Depends(get_data_fetcher), 
    db: AsyncSession = Depends(get_db)
) -> RiskService:
    """Dependency to get RiskService instance"""
    return RiskService(data_fetcher, db)

@router.get("/events")
async def get_risk_events(
    limit: int = 50,
    risk_service: RiskService = Depends(get_risk_service)
) -> List[Dict[str, Any]]:
    """Get recent risk events"""
    logger.info(f"Request for recent risk events with limit: {limit}")
    try:
        events = await risk_service.get_recent_risk_events(limit)
        logger.info(f"Found {len(events)} risk events.")
        return events
        
    except Exception as e:
        logger.error(f"Error getting risk events: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary")
async def get_risk_summary(
    risk_service: RiskService = Depends(get_risk_service)
) -> Dict[str, Any]:
    """Get current risk summary"""
    logger.info("Request for risk summary.")
    try:
        summary = await risk_service.get_risk_summary()
        logger.info("Successfully generated risk summary.")
        return summary
        
    except Exception as e:
        logger.error(f"Error getting risk summary: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/halt")
async def trigger_risk_halt(
    reason: str = "Manual risk halt",
    risk_service: RiskService = Depends(get_risk_service)
) -> Dict[str, str]:
    """Manually trigger risk halt"""
    logger.warning(f"Manual risk halt triggered with reason: {reason}")
    try:
        from models.risk_events import RiskEventType
        
        await risk_service._trigger_risk_halt(
            RiskEventType.MANUAL_HALT,
            f"Manual halt triggered: {reason}",
            {"reason": reason}
        )
        
        return {"message": "Risk halt triggered", "status": "halted"}
        
    except Exception as e:
        logger.error(f"Error triggering risk halt: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/resume")
async def resume_from_risk_halt(
    reason: str = "Manual resume",
    risk_service: RiskService = Depends(get_risk_service)
) -> Dict[str, str]:
    """Resume trading from risk halt"""
    logger.info(f"Manual trading resume with reason: {reason}")
    try:
        await risk_service.resume_trading(reason)
        
        return {"message": "Trading resumed", "status": "active"}
        
    except Exception as e:
        logger.error(f"Error resuming from risk halt: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/position-monitoring")
async def get_position_risk_alerts(
    risk_service: RiskService = Depends(get_risk_service)
) -> List[Dict[str, Any]]:
    """Get current position risk alerts"""
    logger.info("Request for position risk alerts.")
    try:
        alerts = await risk_service.monitor_existing_positions()
        logger.info(f"Found {len(alerts)} position risk alerts.")
        return alerts
        
    except Exception as e:
        logger.error(f"Error getting position risk alerts: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
