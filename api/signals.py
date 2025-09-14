from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
import logging
from models.database import get_db
from models.signals import Signal, SignalStatus
from services.order_manager import OrderManager
from services.iifl_api import IIFLAPIService
from services.risk import RiskService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from services.watchlist import WatchlistService

router = APIRouter(prefix="/api/signals", tags=["signals"])
logger = logging.getLogger(__name__)

async def get_order_manager(db: AsyncSession = Depends(get_db)) -> OrderManager:
    """Dependency to get OrderManager instance"""
    iifl = IIFLAPIService()
    data_fetcher = DataFetcher(iifl, db_session=db)
    risk_service = RiskService(data_fetcher, db)
    return OrderManager(iifl, risk_service, data_fetcher, db)

@router.get("")
async def get_signals(
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected, executed, expired, failed"),
    limit: int = Query(50, ge=1, le=200),
    order_manager: OrderManager = Depends(get_order_manager)
) -> List[Dict[str, Any]]:
    """Get signals with optional status filter"""
    logger.info(f"Request for signals with status='{status}' and limit={limit}")
    try:
        if status == "pending":
            signals = await order_manager.get_pending_signals(limit)
        else:
            signals = await order_manager.get_recent_signals(limit)
            
            # Filter by status if provided
            if status:
                signals = [s for s in signals if s.get('status') == status]
        
        logger.info(f"Found {len(signals)} signals.")
        return signals
        
    except Exception as e:
        logger.error(f"Error getting signals: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/intraday")
async def generate_intraday_signals(
    category: str = "day_trading",
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Generate intraday signals for all symbols in the given watchlist category."""
    try:
        iifl = IIFLAPIService()
        data_fetcher = DataFetcher(iifl, db_session=db)
        strategy = StrategyService(data_fetcher, db)
        symbols = await strategy.get_watchlist(category=category)
        generated: List[Dict[str, Any]] = []
        for symbol in symbols:
            sigs = await strategy.generate_signals(symbol)
            for ts in sigs:
                generated.append({
                    "symbol": ts.symbol,
                    "signal_type": ts.signal_type.value,
                    "entry_price": ts.entry_price,
                    "stop_loss": ts.stop_loss,
                    "target_price": ts.target_price,
                    "confidence": ts.confidence,
                    "strategy": ts.strategy,
                    "metadata": ts.metadata or {}
                })
        return {"count": len(generated), "signals": generated}
    except Exception as e:
        logger.error(f"Error generating intraday signals: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{signal_id}/approve")
async def approve_signal(
    signal_id: int,
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Approve a pending signal"""
    logger.info(f"Request to approve signal {signal_id}")
    try:
        result = await order_manager.approve_signal(signal_id)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving signal {signal_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{signal_id}/reject")
async def reject_signal(
    signal_id: int,
    reason: str = "Manual rejection",
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Reject a pending signal"""
    logger.info(f"Request to reject signal {signal_id} with reason: {reason}")
    try:
        result = await order_manager.reject_signal(signal_id, reason)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting signal {signal_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{signal_id}/expire")
async def expire_signal(
    signal_id: int,
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Manually expire a signal"""
    logger.info(f"Request to expire signal {signal_id}")
    try:
        result = await order_manager.cancel_pending_signal(signal_id)
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error expiring signal {signal_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{signal_id}")
async def get_signal_details(
    signal_id: int,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get detailed information about a specific signal"""
    logger.info(f"Request for details of signal {signal_id}")
    try:
        from sqlalchemy import select
        
        stmt = select(Signal).where(Signal.id == signal_id)
        result = await db.execute(stmt)
        signal = result.scalar_one_or_none()
        
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        return signal.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting signal details for {signal_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{signal_id}/order-status")
async def get_signal_order_status(
    signal_id: int,
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Get order status for an executed signal"""
    logger.info(f"Request for order status of signal {signal_id}")
    try:
        from sqlalchemy import select
        
        stmt = select(Signal).where(Signal.id == signal_id)
        result = await order_manager.db.execute(stmt)
        signal = result.scalar_one_or_none()
        
        if not signal:
            raise HTTPException(status_code=404, detail="Signal not found")
        
        if not signal.order_id:
            logger.warning(f"Signal {signal_id} has no associated order ID.")
            return {"message": "No order ID associated with this signal"}
        
        order_status = await order_manager.get_order_status(signal.order_id)
        
        if order_status:
            return {
                "signal_id": signal_id,
                "order_id": signal.order_id,
                "order_status": order_status
            }
        else:
            return {"message": "Order status not available"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order status for signal {signal_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
