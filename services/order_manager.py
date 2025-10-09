import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models.signals import Signal, SignalType, SignalStatus
from models.risk_events import RiskEvent, RiskEventType
from .iifl_api import IIFLAPIService
from .risk import RiskService
from .data_fetcher import DataFetcher
from config import get_settings

logger = logging.getLogger(__name__)

class OrderManager:
    """Order Management System for executing trades"""
    
    def __init__(self, iifl_service: Optional[IIFLAPIService] = None, risk_service: Optional[RiskService] = None, 
                 data_fetcher: Optional[DataFetcher] = None, db_session: Optional[AsyncSession] = None):
        self.iifl = iifl_service or IIFLAPIService()
        self.risk = risk_service
        self.data_fetcher = data_fetcher
        self.db = db_session
        self.settings = get_settings()
        self.pending_orders: Dict[str, Dict] = {}
    
    async def create_signal(self, signal_data: Dict) -> Optional[Signal]:
        """Create a new trading signal in the database"""
        try:
            # Calculate expiry time
            expiry_time = datetime.now() + timedelta(seconds=self.settings.signal_timeout)
            
            # Normalize incoming signal_data: ensure entry_price exists (fallback to price)
            if 'entry_price' not in signal_data or signal_data.get('entry_price') is None:
                if 'price' in signal_data and signal_data.get('price') is not None:
                    signal_data['entry_price'] = signal_data['price']

            # Normalize signal_type: accept either enum or plain string
            raw_st = signal_data.get('signal_type')
            if raw_st and not hasattr(raw_st, 'value') and isinstance(raw_st, str):
                try:
                    # Try to map to SignalType enum if available
                    signal_data['signal_type'] = SignalType(raw_st.lower())
                except Exception:
                    # leave as-is; risk/other services accept string too
                    pass

            # Calculate required margin
            position_size = await self.risk.calculate_position_size(
                signal_data, 
                await self._get_available_capital()
            )
            
            required_margin_info = await self.data_fetcher.calculate_required_margin(
                signal_data['symbol'],
                position_size,
                signal_data['signal_type'].value if hasattr(signal_data.get('signal_type'), 'value') else signal_data.get('signal_type'),
                signal_data['entry_price']
            )
            # Normalize required margin to a float value
            if isinstance(required_margin_info, dict):
                required_margin_value = float(
                    required_margin_info.get("current_order_margin")
                    or required_margin_info.get("pre_order_margin")
                    or required_margin_info.get("post_order_margin")
                    or 0.0
                )
            else:
                # In some edge cases the API may return a primitive; coerce to float or 0.0
                try:
                    required_margin_value = float(required_margin_info) if required_margin_info is not None else 0.0
                except Exception:
                    required_margin_value = 0.0
            
            signal = Signal(
                symbol=signal_data['symbol'],
                signal_type=signal_data['signal_type'],
                reason=signal_data.get('reason', ''),
                stop_loss=signal_data.get('stop_loss'),
                take_profit=signal_data.get('take_profit'),
                margin_required=required_margin_value,
                status=SignalStatus.PENDING,
                expiry_time=expiry_time,
                quantity=position_size,
                price=signal_data.get('entry_price') if signal_data.get('entry_price') is not None else signal_data.get('price'),
                extras={
                    'confidence': signal_data.get('confidence', 0.5),
                    'strategy': signal_data.get('strategy', 'unknown')
                }
            )
            
            if self.db:
                self.db.add(signal)
                await self.db.commit()
                await self.db.refresh(signal)
            
            logger.info(f"Signal created: {signal.id} - {signal.symbol} {signal.signal_type.value}")
            return signal
            
        except Exception as e:
            logger.error(f"Error creating signal: {str(e)}")
            if self.db:
                await self.db.rollback()
            return None
    
    async def process_signal(self, signal: Signal) -> bool:
        """Process a signal - either execute automatically or queue for approval"""
        try:
            # Check if signal has expired
            if datetime.now() > signal.expiry_time:
                await self._expire_signal(signal)
                return False
            
            # Validate risk
            validation = await self.risk.validate_signal_risk(
                signal.to_dict(), signal.quantity or 1
            )
            
            if not validation['approved']:
                logger.warning(f"Signal {signal.id} failed risk validation: {validation['reasons']}")
                return False
            
            # Auto-execute if enabled, otherwise queue for approval
            if self.settings.auto_trade:
                return await self._execute_signal(signal)
            else:
                logger.info(f"Signal {signal.id} queued for manual approval")
                return True
                
        except Exception as e:
            logger.error(f"Error processing signal {signal.id}: {str(e)}")
            return False
    
    async def approve_signal(self, signal_id: int) -> Dict[str, Any]:
        """Approve and execute a pending signal"""
        try:
            # Get signal from database
            stmt = select(Signal).where(Signal.id == signal_id)
            result = await self.db.execute(stmt) if self.db else None
            signal = result.scalar_one_or_none() if result else None
            
            if not signal:
                return {"success": False, "message": "Signal not found"}
            
            if signal.status != SignalStatus.PENDING:
                return {"success": False, "message": f"Signal status is {signal.status.value}, cannot approve"}
            
            # Check if expired
            if datetime.now() > signal.expiry_time:
                await self._expire_signal(signal)
                return {"success": False, "message": "Signal has expired"}
            
            # Re-validate risk
            validation = await self.risk.validate_signal_risk(
                signal.to_dict(), signal.quantity or 1
            )
            
            if not validation['approved']:
                return {"success": False, "message": f"Risk validation failed: {validation['reasons']}"}
            
            # Execute the signal
            success = await self._execute_signal(signal)
            
            if success:
                signal.status = SignalStatus.APPROVED
                signal.approved_at = datetime.now()
                if self.db:
                    await self.db.commit()
                return {"success": True, "message": "Signal approved and executed"}
            else:
                return {"success": False, "message": "Signal execution failed"}
                
        except Exception as e:
            logger.error(f"Error approving signal {signal_id}: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    async def reject_signal(self, signal_id: int, reason: str = "Manual rejection") -> Dict[str, Any]:
        """Reject a pending signal"""
        try:
            stmt = select(Signal).where(Signal.id == signal_id)
            result = await self.db.execute(stmt) if self.db else None
            signal = result.scalar_one_or_none() if result else None
            
            if not signal:
                return {"success": False, "message": "Signal not found"}
            
            if signal.status != SignalStatus.PENDING:
                return {"success": False, "message": f"Signal status is {signal.status.value}, cannot reject"}
            
            signal.status = SignalStatus.REJECTED
            signal.extras = signal.extras or {}
            signal.extras['rejection_reason'] = reason
            
            if self.db:
                await self.db.commit()
            
            logger.info(f"Signal {signal_id} rejected: {reason}")
            return {"success": True, "message": "Signal rejected"}
            
        except Exception as e:
            logger.error(f"Error rejecting signal {signal_id}: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    async def _execute_signal(self, signal: Signal) -> bool:
        """Execute a trading signal by placing order with IIFL"""
        try:
            # In dry-run or non-production, simulate order execution without hitting broker API
            if getattr(self.settings, "dry_run", False) or self.settings.environment != "production":
                simulated_order_id = f"DRYRUN-{int(datetime.now().timestamp())}-{signal.id}"
                signal.status = SignalStatus.EXECUTED
                signal.executed_at = datetime.now()
                signal.order_id = simulated_order_id
            if self.db:
                await self.db.commit()
                logger.info(f"Simulated order execution for signal {signal.id} with id {simulated_order_id}")
                return True

            # Decide product based on signal type (short selling uses INTRADAY)
            tx_type = signal.signal_type.value
            if tx_type == "sell":
                # If we are already holding the stock (long), normal sell; otherwise short sell product
                # Lightweight check using cached portfolio (no forced refresh here)
                portfolio = await self.data_fetcher.get_portfolio_data()
                holdings = {h.get("symbol"): h.get("quantity", 0) for h in portfolio.get("holdings", [])}
                product = (
                    self.settings.default_sell_product
                    if holdings.get(signal.symbol, 0) > 0
                    else self.settings.short_sell_product
                )
            else:
                product = self.settings.default_buy_product

            # Prepare order data
            order_data = self.iifl.format_order_data(
                symbol=signal.symbol,
                transaction_type=tx_type,
                quantity=signal.quantity or 1,
                order_type="MARKET",
                price=signal.price,
                product=product,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit
            )
            
            # Place order with IIFL
            result = await self.iifl.place_order(order_data)
            
            if result and result.get("isSuccess"):
                order_id = result.get("resultData", {}).get("brokerOrderId")
                
                if order_id:
                    # Update signal with order details
                    signal.status = SignalStatus.EXECUTED
                    signal.executed_at = datetime.now()
                    signal.order_id = order_id
                    
                    if self.db:
                        await self.db.commit()
                    
                    # Track the order
                    self.pending_orders[order_id] = {
                        "signal_id": signal.id,
                        "symbol": signal.symbol,
                        "order_time": datetime.now()
                    }
                    
                    # After a successful order, refresh caches once to reflect latest positions/margin
                    try:
                        if self.data_fetcher:
                            await self.data_fetcher.get_portfolio_data(force_refresh=True)
                            await self.data_fetcher.get_margin_info(force_refresh=True)
                    except Exception:
                        pass
                    logger.info(f"Order executed: {order_id} for signal {signal.id}")
                    return True
                else:
                    logger.error(f"No order ID returned for signal {signal.id}")
                    return False
            else:
                error_msg = result.get("errorMessage", "Unknown error") if result else "No response"
                logger.error(f"Order execution failed for signal {signal.id}: {error_msg}")
                
                # Mark signal as failed
                signal.status = SignalStatus.FAILED
                signal.extras = signal.extras or {}
                signal.extras['error_message'] = error_msg
                if self.db:
                    await self.db.commit()
                
                return False
                
        except Exception as e:
            logger.error(f"Error executing signal {signal.id}: {str(e)}")
            
            # Mark signal as failed
            signal.status = SignalStatus.FAILED
            signal.extras = signal.extras or {}
            signal.extras['error_message'] = str(e)
            if self.db:
                await self.db.commit()
            
            return False
    
    async def _expire_signal(self, signal: Signal):
        """Mark a signal as expired"""
        try:
            signal.status = SignalStatus.EXPIRED
            await self.db.commit()
            logger.info(f"Signal {signal.id} expired")
            
        except Exception as e:
            logger.error(f"Error expiring signal {signal.id}: {str(e)}")
    
    async def check_expired_signals(self):
        """Check and expire old signals"""
        try:
            current_time = datetime.now()
            stmt = select(Signal).where(
                Signal.status == SignalStatus.PENDING,
                Signal.expiry_time <= current_time
            )
            
            result = await self.db.execute(stmt) if self.db else None
            expired_signals = result.scalars().all() if result else []
            
            for signal in expired_signals:
                await self._expire_signal(signal)
                
            if expired_signals:
                logger.info(f"Expired {len(expired_signals)} signals")
                
        except Exception as e:
            logger.error(f"Error checking expired signals: {str(e)}")
    
    async def monitor_orders(self):
        """Monitor pending orders and update their status"""
        try:
            if not self.pending_orders:
                return
            
            # Get all orders from IIFL
            orders_result = await self.iifl.get_orders()
            
            if not orders_result or not orders_result.get("isSuccess"):
                return
            
            iifl_orders = {order.get("brokerOrderId"): order for order in orders_result.get("resultData", [])}
            
            # Update order statuses
            for order_id, order_info in list(self.pending_orders.items()):
                if order_id in iifl_orders:
                    iifl_order = iifl_orders[order_id]
                    order_status = iifl_order.get("orderStatus", "").upper()
                    
                    # If order is filled, remove from pending and refresh caches once
                    if order_status in ["FILLED", "COMPLETE"]:
                        logger.info(f"Order {order_id} filled")
                        try:
                            await self.data_fetcher.get_portfolio_data(force_refresh=True)
                            await self.data_fetcher.get_margin_info(force_refresh=True)
                        except Exception:
                            pass
                        del self.pending_orders[order_id]
                    
                    # If order is cancelled or rejected
                    elif order_status in ["CANCELLED", "REJECTED"]:
                        logger.warning(f"Order {order_id} {order_status.lower()}")
                        
                        # Update signal status
                        signal_id = order_info["signal_id"]
                        stmt = select(Signal).where(Signal.id == signal_id)
                        result = await self.db.execute(stmt) if self.db else None
                        signal = result.scalar_one_or_none() if result else None
                        
                        if signal:
                            signal.status = SignalStatus.FAILED
                            signal.extras = signal.extras or {}
                            signal.extras['order_status'] = order_status
                            if self.db:
                                await self.db.commit()
                        
                        del self.pending_orders[order_id]
                
        except Exception as e:
            logger.error(f"Error monitoring orders: {str(e)}")
    
    async def get_pending_signals(self, limit: int = 50) -> List[Dict]:
        """Get pending signals for approval"""
        try:
            stmt = select(Signal).where(
                Signal.status == SignalStatus.PENDING,
                Signal.expiry_time > datetime.now()
            ).order_by(Signal.created_at.desc()).limit(limit)
            
            result = await self.db.execute(stmt) if self.db else None
            signals = result.scalars().all() if result else []
            
            return [signal.to_dict() for signal in signals]
            
        except Exception as e:
            logger.error(f"Error getting pending signals: {str(e)}")
            return []
    
    async def get_recent_signals(self, limit: int = 100) -> List[Dict]:
        """Get recent signals with all statuses"""
        try:
            stmt = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
            result = await self.db.execute(stmt) if self.db else None
            signals = result.scalars().all() if result else []
            
            return [signal.to_dict() for signal in signals]
            
        except Exception as e:
            logger.error(f"Error getting recent signals: {str(e)}")
            return []
    
    async def _get_available_capital(self) -> float:
        """Get available capital for trading"""
        try:
            margin_info = await self.data_fetcher.get_margin_info() if self.data_fetcher else None
            if margin_info:
                return float(margin_info.get('availableMargin', 0))
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting available capital: {str(e)}")
            return 0.0
    
    async def cancel_pending_signal(self, signal_id: int) -> Dict[str, Any]:
        """Cancel a pending signal"""
        try:
            stmt = select(Signal).where(Signal.id == signal_id)
            result = await self.db.execute(stmt)
            signal = result.scalar_one_or_none()
            
            if not signal:
                return {"success": False, "message": "Signal not found"}
            
            if signal.status != SignalStatus.PENDING:
                return {"success": False, "message": f"Cannot cancel signal with status {signal.status.value}"}
            
            signal.status = SignalStatus.REJECTED
            signal.extras = signal.extras or {}
            signal.extras['cancellation_reason'] = "Manual cancellation"
            
            await self.db.commit()
            
            return {"success": True, "message": "Signal cancelled"}
            
        except Exception as e:
            logger.error(f"Error cancelling signal {signal_id}: {str(e)}")
            return {"success": False, "message": f"Error: {str(e)}"}
    
    async def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get detailed status of an order"""
        try:
            result = await self.iifl.get_order_details(order_id)
            
            if result and result.get("isSuccess"):
                return result.get("resultData")
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting order status for {order_id}: {str(e)}")
            return None

    # Simple compat methods for tests
    async def place_order(self, signal: Dict) -> Dict:
        """Compat: Place order directly via IIFL for tests."""
        try:
            order_data = {
                "symbol": signal.get("symbol"),
                "quantity": signal.get("quantity", 1),
                "price": signal.get("price"),
                "order_type": "BUY" if (signal.get("signal_type") in ("buy", "BUY")) else "SELL"
            }
            result = await self.iifl.place_order(order_data)
            return result or {}
        except Exception as e:
            logger.error(f"Compat place_order failed: {str(e)}")
            return {}

    async def cancel_order(self, order_id: str) -> Dict:
        try:
            result = await self.iifl.cancel_order(order_id)
            return result or {"Success": False}
        except Exception as e:
            logger.error(f"Compat cancel_order failed: {str(e)}")
            return {"Success": False, "Message": str(e)}

    async def clear_all_signals(self) -> int:
        """Deletes all signals from the database. Returns the number of deleted signals."""
        try:
            from sqlalchemy import delete
            stmt = delete(Signal)
            result = await self.db.execute(stmt) if self.db else None
            if self.db:
                await self.db.commit()
            deleted_count = result.rowcount
            logger.info(f"Cleared {deleted_count} signals from the database.")
            return deleted_count
        except Exception as e:
            logger.error(f"Error clearing signals: {str(e)}")
            await self.db.rollback()
            return 0
