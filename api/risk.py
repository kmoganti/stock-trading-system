from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
from models.database import get_db
from models.risk_events import RiskEvent, RiskMetricsSnapshot, EmergencyAction, RiskEventType, RiskSeverity
from services.risk import RiskService
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService
from services.risk_monitor import risk_monitor
from services.logging_service import trading_logger

router = APIRouter(prefix="/api/risk", tags=["risk"])
logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class RiskStatusResponse(BaseModel):
    is_monitoring: bool
    emergency_halt: bool
    positions_count: int
    risk_metrics: Dict[str, Any]
    recent_events_count: int
    last_update: str

class PositionSummary(BaseModel):
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    pnl_percentage: float
    position_value: float
    stop_loss: float
    take_profit: float

class EmergencyActionRequest(BaseModel):
    action_type: str
    reason: str
    confirm: bool = False

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

# NEW REAL-TIME MONITORING ENDPOINTS

@router.get("/monitor/status", response_model=RiskStatusResponse)
async def get_realtime_risk_status():
    """Get real-time risk monitoring status"""
    try:
        status = risk_monitor.get_current_status()
        return RiskStatusResponse(**status)
    except Exception as e:
        logger.error(f"Error getting real-time risk status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/monitor/positions", response_model=List[PositionSummary])
async def get_realtime_positions():
    """Get real-time positions with risk metrics"""
    try:
        positions = risk_monitor.get_positions_summary()
        return [PositionSummary(**pos) for pos in positions]
    except Exception as e:
        logger.error(f"Error getting real-time positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/monitor/start")
async def start_realtime_monitoring(background_tasks: BackgroundTasks):
    """Start real-time risk monitoring"""
    try:
        if risk_monitor.is_monitoring:
            return {"message": "Real-time risk monitoring is already running", "success": True}
        
        background_tasks.add_task(risk_monitor.start_monitoring)
        
        trading_logger.log_system_event("realtime_risk_monitoring_started", {})
        
        return {"message": "Real-time risk monitoring started", "success": True}
    except Exception as e:
        logger.error(f"Error starting real-time risk monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/monitor/stop")
async def stop_realtime_monitoring():
    """Stop real-time risk monitoring"""
    try:
        await risk_monitor.stop_monitoring()
        
        trading_logger.log_system_event("realtime_risk_monitoring_stopped", {})
        
        return {"message": "Real-time risk monitoring stopped", "success": True}
    except Exception as e:
        logger.error(f"Error stopping real-time risk monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emergency/halt")
async def trigger_emergency_halt(request: EmergencyActionRequest):
    """Trigger emergency halt with position closure"""
    try:
        if not request.confirm:
            raise HTTPException(
                status_code=400, 
                detail="Emergency halt requires confirmation. Set 'confirm' to true."
            )
        
        # Import the enum from risk_monitor
        from services.risk_monitor import RiskEventType as MonitorRiskEventType
        
        # Trigger emergency halt
        await risk_monitor._trigger_emergency_halt(
            reason=request.reason,
            event_type=MonitorRiskEventType.EMERGENCY_HALT
        )
        
        trading_logger.log_system_event("emergency_halt_triggered", {
            "reason": request.reason,
            "action_type": request.action_type
        })
        
        return {
            "message": "Emergency halt triggered successfully",
            "success": True,
            "action_type": request.action_type,
            "reason": request.reason
        }
    except Exception as e:
        logger.error(f"Error triggering emergency halt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emergency/close-position/{symbol}")
async def close_position(symbol: str, reason: str = "Manual closure"):
    """Close a specific position immediately"""
    try:
        if symbol not in risk_monitor.positions:
            raise HTTPException(status_code=404, detail=f"Position {symbol} not found")
        
        position = risk_monitor.positions[symbol]
        
        # Execute position closure
        await risk_monitor._execute_stop_loss(position)
        
        trading_logger.log_system_event("manual_position_closure", {
            "symbol": symbol,
            "reason": reason,
            "position_pnl": position.unrealized_pnl
        })
        
        return {
            "message": f"Position {symbol} closed successfully",
            "success": True,
            "symbol": symbol,
            "pnl": position.unrealized_pnl
        }
    except Exception as e:
        logger.error(f"Error closing position {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emergency/close-all")
async def close_all_positions(reason: str = "Emergency closure"):
    """Close all open positions immediately"""
    try:
        positions_count = len(risk_monitor.positions)
        
        await risk_monitor._close_all_positions()
        
        trading_logger.log_system_event("emergency_close_all_positions", {
            "reason": reason,
            "positions_closed": positions_count
        })
        
        return {
            "message": f"All {positions_count} positions closed successfully",
            "success": True,
            "positions_closed": positions_count
        }
    except Exception as e:
        logger.error(f"Error closing all positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/emergency/clear")
async def clear_emergency_halt():
    """Clear emergency halt status to resume trading"""
    try:
        risk_monitor.emergency_halt = False
        
        trading_logger.log_system_event("emergency_halt_cleared", {})
        
        return {"message": "Emergency halt cleared - trading can resume", "success": True}
    except Exception as e:
        logger.error(f"Error clearing emergency halt: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/realtime")
async def get_realtime_risk_metrics():
    """Get current real-time risk metrics"""
    try:
        status = risk_monitor.get_current_status()
        return status["risk_metrics"]
    except Exception as e:
        logger.error(f"Error getting real-time risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts/live")
async def get_live_risk_alerts(limit: int = 20):
    """Get live risk alerts from monitoring system"""
    try:
        events = risk_monitor.get_recent_risk_events(limit)
        return events
    except Exception as e:
        logger.error(f"Error getting live risk alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health/monitor")
async def get_risk_monitor_health():
    """Get risk monitor health status"""
    try:
        health_status = {
            "status": "healthy" if risk_monitor.is_monitoring else "stopped",
            "monitoring_active": risk_monitor.is_monitoring,
            "emergency_halt": risk_monitor.emergency_halt,
            "last_position_update": risk_monitor.last_position_update.isoformat(),
            "positions_tracked": len(risk_monitor.positions),
            "recent_events": len(risk_monitor.recent_risk_events),
            "uptime_seconds": (datetime.now() - risk_monitor.last_position_update).total_seconds()
        }
        
        return health_status
    except Exception as e:
        logger.error(f"Error getting risk monitor health: {e}")
        raise HTTPException(status_code=500, detail=str(e))
