from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.ext.asyncio import AsyncSession 
from typing import Dict, Any, List, Optional, Literal
import asyncio
import logging
import os
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from models.database import get_db
from models.signals import Signal, SignalStatus
from services.order_manager import OrderManager
from services.iifl_api import IIFLAPIService
from services.risk import RiskService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from services.watchlist import WatchlistService
from .auth import get_api_key
from sqlalchemy import select, update
from services import progress as progress_service
from starlette.responses import StreamingResponse

router = APIRouter(prefix="/api/signals", tags=["signals"])
logger = logging.getLogger(__name__)

# Test mode - bypass IIFL calls
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
logger.info(f"🧪 Signals API initialized with TEST_MODE={TEST_MODE} (env={os.getenv('TEST_MODE', 'not set')})")

def _build_gemini_link(signal_payload: Dict[str, Any]) -> Dict[str, str]:
    """Construct a Gemini URL and prompt text for outside-of-system validation.

    Note: Gemini web may not prefill prompts via URL. We still include the
    prompt in the URL query for convenience and always return the plain text
    prompt so clients (UI/Telegram) can show/copy it.
    """
    try:
        symbol = signal_payload.get("symbol")
        stype = str(signal_payload.get("signal_type", "")).upper()
        entry = signal_payload.get("entry_price") or signal_payload.get("price")
        sl = signal_payload.get("stop_loss")
        tp = signal_payload.get("target_price") or signal_payload.get("take_profit")
        strategy = signal_payload.get("strategy")
        confidence = signal_payload.get("confidence")
        reason = signal_payload.get("reason")

        prompt = (
            "Review trading signal and assess risk. "
            f"Symbol: {symbol}. Type: {stype}. "
            f"Entry: {entry}. SL: {sl}. TP: {tp}. "
            f"Strategy: {strategy}. Confidence: {confidence}. "
            f"Reason: {reason}. "
            "List potential risks, market context to verify, and execution cautions."
        )
        import urllib.parse
        encoded = urllib.parse.quote(prompt)
        url = f"https://gemini.google.com/app?prompt={encoded}"
        return {"gemini_review_url": url, "gemini_prompt": prompt}
    except Exception:
        return {"gemini_review_url": None, "gemini_prompt": ""}

async def get_order_manager(db: AsyncSession = Depends(get_db)) -> OrderManager:
    """Dependency to get OrderManager instance"""
    iifl = IIFLAPIService()
    data_fetcher = DataFetcher(iifl, db_session=db)
    risk_service = RiskService(data_fetcher, db)
    return OrderManager(iifl, risk_service, data_fetcher, db)

class SignalCreationRequest(BaseModel):
    symbol: str = Field(..., description="Trading symbol, e.g., 'RELIANCE'")
    signal_type: Literal["buy", "sell", "exit"]
    entry_price: float = Field(..., gt=0, description="The price at which the signal is generated")
    stop_loss: Optional[float] = Field(None, gt=0)
    take_profit: Optional[float] = Field(None, gt=0)
    reason: str = "Manual/API generated"
    strategy: str = "manual"
    confidence: float = Field(0.7, ge=0, le=1)

    @model_validator(mode='after')
    def validate_sl_tp_relative_to_entry(self):
        """Validate that stop-loss and take-profit are logical relative to the entry price."""
        if self.entry_price is None:
            return self
        if self.signal_type == 'buy':
            if self.stop_loss is not None and self.stop_loss >= self.entry_price:
                raise ValueError('For a BUY signal, stop_loss must be below the entry_price.')
            if self.take_profit is not None and self.take_profit <= self.entry_price:
                raise ValueError('For a BUY signal, take_profit must be above the entry_price.')
        elif self.signal_type == 'sell':
            if self.stop_loss is not None and self.stop_loss <= self.entry_price:
                raise ValueError('For a SELL signal, stop_loss must be above the entry_price.')
            if self.take_profit is not None and self.take_profit >= self.entry_price:
                raise ValueError('For a SELL signal, take_profit must be below the entry_price.')
        return self

@router.post("")
async def create_signal(
    payload: SignalCreationRequest,
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Create a signal and queue for approval (dry-run friendly)."""
    try:
        from models.signals import SignalType as ModelSignalType
        signal_data = payload.model_dump()
        signal_data["signal_type"] = ModelSignalType(payload.signal_type)

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
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get signals with optional status filter - reads directly from database"""
    logger.info(f"Request for signals with status='{status}' and limit={limit}")
    
    try:
        # In SAFE_MODE, avoid touching the database entirely to prevent hangs
        if os.getenv("SAFE_MODE", "false").lower() == "true":
            logger.warning("SAFE_MODE=true - returning empty signals list without DB access")
            return []

        from models.signals import Signal, SignalStatus
        from sqlalchemy import select
        
        # Build query
        query = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
        
        # Filter by status if provided
        if status:
            try:
                status_enum = SignalStatus(status.lower())
                query = query.where(Signal.status == status_enum)
            except ValueError:
                logger.warning(f"Invalid status value: {status}")
        
        # Execute query with a strict timeout to avoid blocking the event loop
        try:
            result = await asyncio.wait_for(db.execute(query), timeout=1.5)
        except asyncio.TimeoutError:
            logger.warning("Timeout while fetching signals from DB - returning empty list")
            return []
        signals = result.scalars().all()
        
        # Convert to dict
        signals_dict = [sig.to_dict() for sig in signals]
        
        logger.info(f"Found {len(signals_dict)} signals.")
        return signals_dict
        
    except Exception as e:
        logger.error(f"Error getting signals: {str(e)}", exc_info=True)
        # On DB errors, fail safe with empty list to keep UI responsive
        return []

@router.get("/progress")
async def get_generation_progress() -> Dict[str, Any]:
    """Return current server-side signal generation progress state."""
    try:
        return await progress_service.get_state()
    except Exception as e:
        logger.error(f"Error getting progress state: {str(e)}", exc_info=True)
        # Return a safe default state
        return {
            "in_progress": False,
            "task": None,
            "phase": None,
            "current_symbol": None,
            "processed": 0,
            "total": 0,
            "percentage": 0,
            "started_at": None,
            "last_update": None,
        }

@router.get("/progress/stream")
async def stream_generation_progress():
    """Server-Sent Events stream that pushes progress updates periodically."""
    async def event_generator():
        try:
            while True:
                state = await progress_service.get_state()
                import json
                payload = f"data: {json.dumps(state)}\n\n"
                yield payload
                # Yield periodically; keep interval short for responsiveness
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            # Client disconnected
            return

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/generate/intraday")
async def generate_intraday_signals(
    category: str = "day_trading",
    persist: bool = False,
    persisted: Optional[bool] = None,  # alias for persist (backward compatibility with clients)
    queue_for_approval: bool = True,
    use_batch: bool = True,  # new: prefer batched data fetch to avoid long blocking
    validate: bool = False,   # ignored; server-side validation removed
    max_concurrency: int = 4,  # new: limit concurrent processing
    interval: Optional[str] = None,  # new: override interval
    days: Optional[int] = None,      # new: override days window
    db: AsyncSession = Depends(get_db),
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Generate intraday signals for all symbols in the given watchlist category.

    Optimized to batch-fetch historical data and process symbols concurrently to prevent request hangs.
    If persist is True, signals are saved as pending for approval (dry-run friendly).
    """
    try:
        # Support 'persisted=true' as an alias for 'persist=true'
        if persisted is not None:
            persist = bool(persist or persisted)

        iifl = IIFLAPIService()
        data_fetcher = DataFetcher(iifl, db_session=db)
        strategy = StrategyService(data_fetcher, db)

        # Load symbols from watchlist for the category
        symbols = await strategy.get_watchlist(category=category)
        await progress_service.start(task="intraday", total=len(symbols), phase="initializing")

        if not symbols:
            await progress_service.finish()
            return {"count": 0, "signals": [], "persisted_ids": []}

        # Decide interval/days similar to StrategyService defaults
        eff_interval = interval or ("5m" if category == "day_trading" else "1D")
        eff_days = (
            days if days is not None else (2 if category == "day_trading" else (250 if category == "long_term" else 100))
        )

        generated: List[Dict[str, Any]] = []
        persisted_ids: List[int] = []

        if use_batch:
            # Batch historical fetch to minimize network overhead and avoid sequential blocking
            await progress_service.update(phase="fetching")
            hist_map = await data_fetcher.get_historical_data_many(
                symbols, interval=eff_interval, days=eff_days, max_concurrency=max_concurrency
            )

            # Process signals concurrently with a semaphore
            await progress_service.update(phase="scanning")
            sem = asyncio.Semaphore(max_concurrency)
            lock = asyncio.Lock()  # protect shared lists

            async def process_symbol(sym: str, data):
                async with sem:
                    try:
                        sigs = await strategy.generate_signals_from_data(sym, data, strategy_name=None, validate=validate)
                        if not sigs:
                            return
                        # Convert and optionally persist
                        to_add: List[Dict[str, Any]] = []
                        for ts in sigs:
                            sig_dict = {
                                "symbol": ts.symbol,
                                "signal_type": ts.signal_type.value,
                                "entry_price": ts.entry_price,
                                "stop_loss": ts.stop_loss,
                                "target_price": ts.target_price,
                                "confidence": ts.confidence,
                                "strategy": ts.strategy,
                                "metadata": ts.metadata or {},
                            }
                            sig_dict.update(_build_gemini_link(sig_dict))
                            to_add.append(sig_dict)
                        async with lock:
                            generated.extend(to_add)
                        if persist:
                            for ts in sigs:
                                created = await order_manager.create_signal({
                                    "symbol": ts.symbol,
                                    "signal_type": ts.signal_type,
                                    "entry_price": ts.entry_price,
                                    "stop_loss": ts.stop_loss,
                                    "take_profit": ts.target_price,
                                    "reason": f"{ts.strategy} generated",
                                    "strategy": ts.strategy,
                                    "confidence": ts.confidence,
                                    "gemini_review_url": _build_gemini_link({
                                        "symbol": ts.symbol,
                                        "signal_type": ts.signal_type.value,
                                        "entry_price": ts.entry_price,
                                        "stop_loss": ts.stop_loss,
                                        "target_price": ts.target_price,
                                        "strategy": ts.strategy,
                                        "confidence": ts.confidence,
                                        "reason": f"{ts.strategy} generated",
                                    })["gemini_review_url"],
                                })
                                if created:
                                    if queue_for_approval:
                                        await order_manager.process_signal(created)
                                    async with lock:
                                        persisted_ids.append(created.id)
                    finally:
                        # Update progress per symbol processed
                        try:
                            idx = (len(generated) or 0)
                            await progress_service.update(current_symbol=sym, processed=idx)
                        except Exception:
                            pass

            tasks: List[Any] = []
            for sym, data in hist_map.items():
                tasks.append(process_symbol(sym, data))
            if tasks:
                await asyncio.gather(*tasks)
        else:
            # Fallback to original sequential flow (not recommended for large lists)
            await progress_service.update(phase="scanning")
            for idx, symbol in enumerate(symbols, start=1):
                await progress_service.update(current_symbol=symbol, processed=idx)
                try:
                    sigs = await asyncio.wait_for(
                        strategy.generate_signals(symbol),
                        timeout=30.0  # 30-second timeout per symbol
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout generating intraday signals for {symbol}, skipping.")
                    continue  # Move to the next symbol
                except Exception as e:
                    logger.error(f"Error generating intraday signals for {symbol}: {e}")
                    continue
                await asyncio.sleep(0)
                for ts in sigs:
                    sig_dict = {
                        "symbol": ts.symbol,
                        "signal_type": ts.signal_type.value,
                        "entry_price": ts.entry_price,
                        "stop_loss": ts.stop_loss,
                        "target_price": ts.target_price,
                        "confidence": ts.confidence,
                        "strategy": ts.strategy,
                        "metadata": ts.metadata or {},
                    }
                    sig_dict.update(_build_gemini_link(sig_dict))
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
                            "gemini_review_url": _build_gemini_link(sig_dict)["gemini_review_url"],
                        })
                        if created:
                            persisted_ids.append(created.id)
                            if queue_for_approval:
                                await order_manager.process_signal(created)

        await progress_service.finish()
        return {"count": len(generated), "signals": generated, "persisted_ids": persisted_ids}
    except Exception as e:
        logger.error(f"Error generating intraday signals: {str(e)}", exc_info=True)
        await progress_service.clear()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/live")
async def generate_live_signals(
    scan_type: str = "long_term",
    market_cap: str = "large", 
    persist: bool = True,
    queue_for_approval: bool = True,
    db: AsyncSession = Depends(get_db),
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """Generate live market signals using real-time analysis"""
    try:
        # Import our live scanner
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        from live_long_term_scan import LiveLongTermScanner
        import asyncio
        
        scanner = LiveLongTermScanner()
        
        # Define symbol sets based on market cap
        if market_cap == "large":
            symbols = [
                "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK",
                "BAJFINANCE", "BHARTIARTL", "ITC", "HINDUNILVR", "ASIANPAINT", "MARUTI",
                "SUNPHARMA", "LTIM", "TITAN", "NESTLEIND", "ULTRACEMCO", "TECHM",
                "ADANIPORTS", "POWERGRID", "NTPC", "COALINDIA", "ONGC"
            ]
        elif market_cap == "mid":
            symbols = [
                "ADANIENSOL", "ADANIGREEN", "CHOLAFIN", "BEL", "HAL", "SIEMENS", 
                "ABB", "BOSCHLTD", "HAVELLS", "PIDILITIND", "GODREJCP", "DABUR"
            ]
        else:  # all or small
            symbols = [
                "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK",
                "BAJFINANCE", "BHARTIARTL", "ITC", "HINDUNILVR", "ASIANPAINT", "MARUTI",
                "SUNPHARMA", "LTIM", "TITAN", "NESTLEIND", "ULTRACEMCO", "TECHM",
                "ADANIPORTS", "POWERGRID", "NTPC", "COALINDIA", "ONGC", "TATASTEEL",
                "JSWSTEEL", "HINDALCO", "VEDL", "GRASIM", "CIPLA", "DRREDDY",
                "BAJAJ-AUTO", "M&M", "EICHERMOT", "BOSCHLTD", "HAVELLS", "SIEMENS", "ABB"
            ]
        
        # Initialize progress
        await progress_service.start(task="live", total=len(symbols), phase="scanning")

        # Run the live scan
        results = await scanner.scan_watchlist(symbols)
        
        generated_signals = []
        persisted_ids = []
        
        for opportunity in results["opportunities"]:
            for signal in opportunity["signals"]:
                # Convert to our signal format
                signal_data = {
                    "symbol": opportunity["symbol"],
                    "signal_type": signal["type"].lower(),
                    "entry_price": signal["entry"],
                    "stop_loss": signal["stop_loss"],
                    "take_profit": signal["target"],
                    "reason": f"Live scan: {signal['reason']}",
                    "strategy": signal["strategy"],
                    "confidence": opportunity["confidence"],
                }
                # Attach Gemini review URL
                signal_data.update(_build_gemini_link(signal_data))
                generated_signals.append(signal_data)
                
                if persist:
                    from models.signals import SignalType as ModelSignalType
                    created = await order_manager.create_signal({
                        "symbol": opportunity["symbol"],
                        "signal_type": ModelSignalType(signal["type"].lower()),
                        "entry_price": signal["entry"],
                        "stop_loss": signal["stop_loss"],
                        "take_profit": signal["target"],
                        "reason": f"Live scan: {signal['reason']}",
                        "strategy": signal["strategy"],
                        "confidence": opportunity["confidence"],
                        "gemini_review_url": signal_data.get("gemini_review_url")
                    })
                    if created:
                        persisted_ids.append(created.id)
                        if queue_for_approval:
                            await order_manager.process_signal(created)
        
        await progress_service.finish()
        return {
            "count": len(generated_signals),
            "signals": generated_signals,
            "persisted_ids": persisted_ids,
            "symbols_analyzed": len(symbols),
            "opportunities_found": len(results["opportunities"])
        }
        
    except Exception as e:
        logger.error(f"Error generating live signals: {str(e)}", exc_info=True)
        await progress_service.clear()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate/historic")
async def generate_historic_signals(
    symbol: Optional[str] = None,
    symbols: Optional[List[str]] = None,  # Support multiple symbols
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

        symbol_list: List[str] = []
        if symbol:
            symbol_list = [symbol.upper()]
        elif symbols:
            symbol_list = [s.upper() for s in symbols]
        else:
            symbol_list = await strategy.get_watchlist(category=category or "day_trading")

        generated: List[Dict[str, Any]] = []
        persisted: List[int] = []

        await progress_service.start(task="historic", total=len(symbol_list), phase="scanning")

        for idx, sym in enumerate(symbol_list, start=1):
            await progress_service.update(current_symbol=sym, processed=idx)
            try:
                sigs = await asyncio.wait_for(
                    strategy.generate_signals(sym),
                    timeout=30.0  # 30-second timeout per symbol
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout generating historic signals for {sym}, skipping.")
                continue
            except Exception as e:
                logger.error(f"Error generating historic signals for {sym}: {e}")
                continue
            # yield control to keep loop responsive
            await asyncio.sleep(0)
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
                sig_dict.update(_build_gemini_link(sig_dict))
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
                        "gemini_review_url": sig_dict.get("gemini_review_url")
                    })
                    if created:
                        persisted.append(created.id)
                        if queue_for_approval:
                            await order_manager.process_signal(created)

        await progress_service.finish()
        return {"count": len(generated), "signals": generated, "persisted_ids": persisted}

    except Exception as e:
        logger.error(f"Error generating historic signals: {str(e)}", exc_info=True)
        await progress_service.clear()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{signal_id}/approve")
async def approve_signal(
    signal_id: int,
    api_key: str = Security(get_api_key),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Approve a pending signal"""
    logger.info(f"Request to approve signal {signal_id} (TEST_MODE={TEST_MODE})")
    
    try:
        if TEST_MODE:
            # Test mode: Update signal directly without calling IIFL
            logger.info(f"TEST_MODE: Approving signal {signal_id} without IIFL calls")
            
            stmt = update(Signal).where(Signal.id == signal_id).values(
                status=SignalStatus.APPROVED,
                approved_at=datetime.now()
            )
            await db.execute(stmt)
            await db.commit()
            
            # Fetch updated signal
            result = await db.execute(select(Signal).where(Signal.id == signal_id))
            signal = result.scalar_one_or_none()
            
            if not signal:
                raise HTTPException(status_code=404, detail="Signal not found")
            
            return {
                "success": True,
                "message": f"Signal {signal_id} approved (TEST MODE)",
                "signal": signal.to_dict()
            }
        
        # Production mode: Use order_manager with timeout
        order_manager = await get_order_manager(db)
        result = await asyncio.wait_for(
            order_manager.approve_signal(signal_id),
            timeout=8.0
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout approving signal {signal_id}")
        raise HTTPException(status_code=504, detail="Signal approval timed out - signal may still be processing")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving signal {signal_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{signal_id}/reject")
async def reject_signal(
    signal_id: int,
    reason: str = "Manual rejection",
    api_key: str = Security(get_api_key),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Reject a pending signal"""
    logger.info(f"Request to reject signal {signal_id} with reason: {reason} (TEST_MODE={TEST_MODE})")
    
    try:
        if TEST_MODE:
            # Test mode: Update signal directly without calling IIFL
            logger.info(f"TEST_MODE: Rejecting signal {signal_id} without IIFL calls")
            
            stmt = update(Signal).where(Signal.id == signal_id).values(
                status=SignalStatus.REJECTED,
                extras={"rejection_reason": reason, "rejected_at": datetime.now().isoformat()}
            )
            await db.execute(stmt)
            await db.commit()
            
            # Fetch updated signal
            result = await db.execute(select(Signal).where(Signal.id == signal_id))
            signal = result.scalar_one_or_none()
            
            if not signal:
                raise HTTPException(status_code=404, detail="Signal not found")
            
            return {
                "success": True,
                "message": f"Signal {signal_id} rejected (TEST MODE): {reason}",
                "signal": signal.to_dict()
            }
        
        # Production mode: Use order_manager with timeout
        order_manager = await get_order_manager(db)
        result = await asyncio.wait_for(
            order_manager.reject_signal(signal_id, reason),
            timeout=8.0
        )
        
        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])
        
        return result
        
    except asyncio.TimeoutError:
        logger.warning(f"Timeout rejecting signal {signal_id}")
        raise HTTPException(status_code=504, detail="Signal rejection timed out - signal may still be processing")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting signal {signal_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{signal_id}/expire")
async def expire_signal(
    signal_id: int,
    api_key: str = Security(get_api_key),
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

@router.delete("/all", dependencies=[Security(get_api_key)])
async def clear_all_signals(
    order_manager: OrderManager = Depends(get_order_manager)
) -> Dict[str, Any]:
    """
    Deletes all signals from the database. This is a destructive operation.
    """
    try:
        deleted_count = await order_manager.clear_all_signals()
        return {"success": True, "message": f"Cleared {deleted_count} signals.", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Error clearing all signals via API: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while clearing signals.")


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

# Validation endpoints removed – external review via Gemini links replaces server-side LLM validation.
