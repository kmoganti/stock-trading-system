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

@router.post("")
async def create_signal(
    payload: Dict[str, Any],
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Create a signal and queue for approval (dry-run friendly).

    Expected payload keys: symbol, signal_type, entry_price/price, stop_loss, take_profit, reason, strategy, confidence
    """
    try:
        symbol = payload.get("symbol")
        signal_type = payload.get("signal_type")
        if not symbol or not signal_type:
            raise HTTPException(status_code=400, detail="symbol and signal_type are required")

        # Normalize fields
        entry_price = payload.get("entry_price", payload.get("price"))
        if entry_price is None:
            raise HTTPException(status_code=400, detail="entry_price (or price) is required")

        from models.signals import SignalType as ModelSignalType

        try:
            stype = ModelSignalType(signal_type.lower())
        except Exception:
            raise HTTPException(status_code=400, detail="invalid signal_type; expected buy/sell/exit")

        signal_data = {
            "symbol": symbol.upper(),
            "signal_type": stype,
            "entry_price": float(entry_price),
            "stop_loss": payload.get("stop_loss"),
            "take_profit": payload.get("take_profit"),
            "reason": payload.get("reason", "Manual/Backtest generated"),
            "strategy": payload.get("strategy", "manual"),
            "confidence": float(payload.get("confidence", 0.7)),
        }

        # Create DB record
        signal = await order_manager.create_signal(signal_data)
        if not signal:
            raise HTTPException(status_code=500, detail="Failed to create signal")

        # Keep pending for approval when auto_trade is False; otherwise process/exe
        await order_manager.process_signal(signal)

        return signal.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating signal: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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
    persist: bool = False,
    persisted: Optional[bool] = None,  # alias for persist (backward compatibility with clients)
    queue_for_approval: bool = True,
    db: AsyncSession = Depends(get_db),
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Generate intraday signals for all symbols in the given watchlist category.

    If persist is True, signals are saved as pending for approval (dry-run friendly).
    """
    try:
        # Support 'persisted=true' as an alias for 'persist=true'
        if persisted is not None:
            persist = bool(persist or persisted)

        iifl = IIFLAPIService()
        data_fetcher = DataFetcher(iifl, db_session=db)
        strategy = StrategyService(data_fetcher, db)
        symbols = await strategy.get_watchlist(category=category)
        generated: List[Dict[str, Any]] = []
        persisted: List[int] = []
        for symbol in symbols:
            sigs = await strategy.generate_signals(symbol)
            for ts in sigs:
                sig_dict = {
                    "symbol": ts.symbol,
                    "signal_type": ts.signal_type.value,
                    "entry_price": ts.entry_price,
                    "stop_loss": ts.stop_loss,
                    "target_price": ts.target_price,
                    "confidence": ts.confidence,
                    "strategy": ts.strategy,
                    "metadata": ts.metadata or {}
                }
                generated.append(sig_dict)
                if persist:
                    created = await order_manager.create_signal({
                        "symbol": ts.symbol,
                        "signal_type": ts.signal_type,
                        "entry_price": ts.entry_price,
                        "stop_loss": ts.stop_loss,
                        "take_profit": ts.target_price,
                        "reason": f"{ts.strategy} generated",
                        "strategy": ts.strategy,
                        "confidence": ts.confidence,
                    })
                    if created:
                        persisted.append(created.id)
                        if queue_for_approval:
                            await order_manager.process_signal(created)
        return {"count": len(generated), "signals": generated, "persisted_ids": persisted}
    except Exception as e:
        logger.error(f"Error generating intraday signals: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/historic")
async def generate_historic_signals(
    symbol: Optional[str] = None,
    category: Optional[str] = None,
    strategy_name: Optional[str] = None,
    persist: bool = True,
    persisted: Optional[bool] = None,  # alias for persist (backward compatibility with clients)
    queue_for_approval: bool = True,
    db: AsyncSession = Depends(get_db),
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Replay historical data to generate signals and optionally persist them as pending.

    If no symbol is provided, uses the watchlist for the given category.
    """
    try:
        # Support 'persisted=true' as an alias for 'persist=true'
        if persisted is not None:
            persist = bool(persist or persisted)

        iifl = IIFLAPIService()
        data_fetcher = DataFetcher(iifl, db_session=db)
        strategy = StrategyService(data_fetcher, db)

        symbols: List[str] = []
        if symbol:
            symbols = [symbol.upper()]
        else:
            symbols = await strategy.get_watchlist(category=category or "day_trading")

        generated: List[Dict[str, Any]] = []
        persisted: List[int] = []

        for sym in symbols:
            sigs = await strategy.generate_signals(sym)
            # Fallback to mock if nothing generated
            if not sigs:
                mock_sigs = await strategy._generate_mock_signals(sym)  # noqa: SLF001
                sigs = mock_sigs
            for ts in sigs:
                # Optional filter by strategy
                if strategy_name and ts.strategy != strategy_name:
                    continue
                sig_dict = {
                    "symbol": ts.symbol,
                    "signal_type": ts.signal_type.value,
                    "entry_price": ts.entry_price,
                    "stop_loss": ts.stop_loss,
                    "target_price": ts.target_price,
                    "confidence": ts.confidence,
                    "strategy": ts.strategy,
                    "metadata": ts.metadata or {}
                }
                generated.append(sig_dict)
                if persist:
                    created = await order_manager.create_signal({
                        "symbol": ts.symbol,
                        "signal_type": ts.signal_type,
                        "entry_price": ts.entry_price,
                        "stop_loss": ts.stop_loss,
                        "take_profit": ts.target_price,
                        "reason": f"Historic replay - {ts.strategy}",
                        "strategy": ts.strategy,
                        "confidence": ts.confidence,
                    })
                    if created:
                        persisted.append(created.id)
                        if queue_for_approval:
                            await order_manager.process_signal(created)

        return {"count": len(generated), "signals": generated, "persisted_ids": persisted}

    except Exception as e:
        logger.error(f"Error generating historic signals: {str(e)}", exc_info=True)
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
