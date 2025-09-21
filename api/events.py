from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import logging
import asyncio

from models.database import get_db
from services.risk import RiskService
from services.order_manager import OrderManager
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService

router = APIRouter(prefix="/api/events", tags=["events"])
logger = logging.getLogger(__name__)

def get_data_fetcher(db: AsyncSession = Depends(get_db)) -> DataFetcher:
    iifl = IIFLAPIService()
    return DataFetcher(iifl, db_session=db)

def get_risk_service(
    data_fetcher: DataFetcher = Depends(get_data_fetcher), 
    db: AsyncSession = Depends(get_db)
) -> RiskService:
    return RiskService(data_fetcher, db)

def get_order_manager(
    data_fetcher: DataFetcher = Depends(get_data_fetcher),
    risk_service: RiskService = Depends(get_risk_service),
    db: AsyncSession = Depends(get_db)
) -> OrderManager:
    iifl = IIFLAPIService()
    return OrderManager(iifl, risk_service, data_fetcher, db)

@router.get("")
async def get_all_events(
    limit: int = 20,
    risk_service: RiskService = Depends(get_risk_service),
    order_manager: OrderManager = Depends(get_order_manager)
) -> List[Dict[str, Any]]:
    """Get a combined list of recent activities (signals, executions, risk events)."""
    try:
        # Fetch signals (pending, executed) and risk events in parallel
        signals_task = order_manager.get_recent_signals(limit=limit)
        risk_events_task = risk_service.get_recent_risk_events(limit=limit)
        
        all_signals, risk_events = await asyncio.gather(signals_task, risk_events_task)
        
        events = []
        
        # Process signals
        for signal in all_signals:
            event_type = "execution" if signal.get('status') == 'executed' else "signal"
            events.append({
                "type": event_type,
                "message": f"{signal.get('signal_type', '').upper()} signal for {signal.get('symbol')}",
                "timestamp": signal.get('created_at'),
                "details": signal
            })
            
        # Process risk events
        for risk_event in risk_events:
            events.append({
                "type": "risk",
                "message": risk_event.get('description'),
                "timestamp": risk_event.get('timestamp'),
                "details": risk_event
            })
            
        # Sort events by timestamp descending
        events.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Limit the total number of events
        return events[:limit]
        
    except Exception as e:
        logger.error(f"Error fetching combined events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch recent activity")
