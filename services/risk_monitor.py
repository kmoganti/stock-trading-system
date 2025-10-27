"""
Real-Time Risk Monitoring System

This module provides comprehensive real-time risk monitoring for the trading system,
including position monitoring, P&L tracking, risk limit enforcement, and emergency controls.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from models.database import get_db
from services.iifl_api import IIFLAPIService
from services.logging_service import trading_logger
from services.telegram_notifier import TelegramNotifier
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class RiskEventType(Enum):
    """Types of risk events"""
    STOP_LOSS_HIT = "stop_loss_hit"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    POSITION_SIZE_EXCEEDED = "position_size_exceeded"
    MAX_POSITIONS_EXCEEDED = "max_positions_exceeded"
    MARGIN_SHORTAGE = "margin_shortage"
    API_FAILURE = "api_failure"
    UNUSUAL_MARKET_MOVEMENT = "unusual_market_movement"
    EMERGENCY_HALT = "emergency_halt"

class RiskSeverity(Enum):
    """Risk event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Position:
    """Position data structure"""
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    stop_loss: float
    take_profit: float
    product_type: str
    exchange: str
    instrument_id: str
    
    @property
    def pnl_percentage(self) -> float:
        """Calculate P&L percentage"""
        if self.entry_price == 0:
            return 0.0
        return (self.unrealized_pnl / (abs(self.quantity) * self.entry_price)) * 100

    @property
    def position_value(self) -> float:
        """Calculate position value"""
        return abs(self.quantity) * self.current_price

@dataclass
class RiskMetrics:
    """Current risk metrics"""
    total_portfolio_value: float
    available_margin: float
    used_margin: float
    daily_pnl: float
    daily_pnl_percentage: float
    unrealized_pnl: float
    realized_pnl: float
    open_positions_count: int
    max_single_position_risk: float
    portfolio_beta: float
    var_95: float  # Value at Risk 95%
    
class RealTimeRiskMonitor:
    """
    Real-time risk monitoring system that continuously monitors positions,
    P&L, and enforces risk limits with emergency controls.
    """
    
    def __init__(self):
        self.iifl_service = IIFLAPIService()
        self.telegram_service = TelegramNotifier()
        self.positions: Dict[str, Position] = {}
        self.risk_metrics = RiskMetrics(
            total_portfolio_value=0.0,
            available_margin=0.0,
            used_margin=0.0,
            daily_pnl=0.0,
            daily_pnl_percentage=0.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            open_positions_count=0,
            max_single_position_risk=0.0,
            portfolio_beta=0.0,
            var_95=0.0
        )
        
        # Risk limits from settings
        self.max_daily_loss_pct = float(settings.MAX_DAILY_LOSS)
        self.max_daily_loss_amount = 0.0  # Will be calculated based on portfolio value
        self.max_position_size = float(settings.MAX_POSITION_SIZE)
        self.max_positions = int(settings.MAX_POSITIONS)
        self.risk_per_trade_pct = float(settings.RISK_PER_TRADE)
        
        # Monitoring state
        self.is_monitoring = False
        self.emergency_halt = False
        self.last_position_update = datetime.now()
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # Risk events tracking
        self.recent_risk_events: List[Dict] = []
        self.alert_cooldown: Dict[str, datetime] = {}
        
        logger.info("RealTimeRiskMonitor initialized")

    async def start_monitoring(self):
        """Start real-time risk monitoring"""
        if self.is_monitoring:
            logger.warning("Risk monitoring is already running")
            return
            
        self.is_monitoring = True
        self.emergency_halt = False
        
        logger.info("🚨 Starting real-time risk monitoring")
        trading_logger.log_system_event("risk_monitor_started", {
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_positions": self.max_positions,
            "max_position_size": self.max_position_size
        })
        
        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Also start separate tasks for different monitoring aspects
        asyncio.create_task(self._position_monitoring_loop())
        asyncio.create_task(self._risk_metrics_update_loop())
        
        await self._send_alert("Risk monitoring started", RiskSeverity.LOW)

    async def stop_monitoring(self):
        """Stop risk monitoring"""
        self.is_monitoring = False
        
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            
        logger.info("🛑 Risk monitoring stopped")
        trading_logger.log_system_event("risk_monitor_stopped", {})
        
        await self._send_alert("Risk monitoring stopped", RiskSeverity.MEDIUM)

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                # Skip monitoring if emergency halt is active
                if self.emergency_halt:
                    await asyncio.sleep(10)
                    continue
                
                # Update positions and risk metrics
                await self._update_positions()
                await self._update_risk_metrics()
                
                # Perform risk checks
                await self._check_daily_loss_limits()
                await self._check_position_limits()
                await self._check_stop_losses()
                await self._check_margin_requirements()
                
                # Clean up old events
                self._cleanup_old_events()
                
                # Wait before next check (configurable)
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in risk monitoring loop: {e}")
                trading_logger.log_error("risk_monitor", e, {
                    "loop": "main_monitoring",
                    "positions_count": len(self.positions)
                })
                await asyncio.sleep(10)  # Wait longer on error

    async def _position_monitoring_loop(self):
        """Dedicated position monitoring loop"""
        while self.is_monitoring:
            try:
                if not self.emergency_halt:
                    # Check individual positions for stop losses and take profits
                    for symbol, position in self.positions.items():
                        await self._monitor_individual_position(position)
                
                await asyncio.sleep(2)  # Check positions every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in position monitoring: {e}")
                await asyncio.sleep(5)

    async def _risk_metrics_update_loop(self):
        """Update risk metrics periodically"""
        while self.is_monitoring:
            try:
                if not self.emergency_halt:
                    await self._calculate_advanced_risk_metrics()
                
                await asyncio.sleep(30)  # Update advanced metrics every 30 seconds
                
            except Exception as e:
                logger.error(f"Error updating risk metrics: {e}")
                await asyncio.sleep(60)

    async def _update_positions(self):
        """Update current positions from IIFL API"""
        try:
            # Get positions from IIFL API
            positions_response = await self.iifl_service.get_positions()
            
            if not positions_response or positions_response.get('status') != 'Ok':
                logger.warning("Failed to get positions from IIFL API")
                return
            
            positions_data = positions_response.get('result', [])
            updated_positions = {}
            
            for pos_data in positions_data:
                if pos_data.get('quantity', 0) == 0:
                    continue  # Skip closed positions
                    
                symbol = pos_data.get('tradingSymbol', '')
                
                # Get current price (this would need market data integration)
                current_price = await self._get_current_price(symbol)
                
                position = Position(
                    symbol=symbol,
                    quantity=int(pos_data.get('quantity', 0)),
                    entry_price=float(pos_data.get('buyAveragePrice', 0) or pos_data.get('sellAveragePrice', 0)),
                    current_price=current_price,
                    unrealized_pnl=float(pos_data.get('unrealizedPnL', 0)),
                    realized_pnl=float(pos_data.get('realizedPnL', 0)),
                    stop_loss=await self._calculate_stop_loss(pos_data),
                    take_profit=await self._calculate_take_profit(pos_data),
                    product_type=pos_data.get('product', ''),
                    exchange=pos_data.get('exchange', ''),
                    instrument_id=pos_data.get('instrumentId', '')
                )
                
                updated_positions[symbol] = position
            
            self.positions = updated_positions
            self.last_position_update = datetime.now()
            
            logger.debug(f"Updated {len(self.positions)} positions")
            
        except Exception as e:
            logger.error(f"Error updating positions: {e}")
            await self._log_risk_event(RiskEventType.API_FAILURE, RiskSeverity.HIGH, {
                "error": str(e),
                "function": "_update_positions"
            })

    async def _update_risk_metrics(self):
        """Update current risk metrics"""
        try:
            # Get margin and portfolio info
            margin_response = await self.iifl_service.get_margin_info()
            
            if margin_response and margin_response.get('status') == 'Ok':
                margin_data = margin_response.get('result', {})
                
                self.risk_metrics.available_margin = float(margin_data.get('availableMargin', 0))
                self.risk_metrics.used_margin = float(margin_data.get('usedMargin', 0))
                self.risk_metrics.total_portfolio_value = self.risk_metrics.available_margin + self.risk_metrics.used_margin
            
            # Calculate daily P&L
            daily_pnl = sum(pos.unrealized_pnl + pos.realized_pnl for pos in self.positions.values())
            self.risk_metrics.daily_pnl = daily_pnl
            
            if self.risk_metrics.total_portfolio_value > 0:
                self.risk_metrics.daily_pnl_percentage = (daily_pnl / self.risk_metrics.total_portfolio_value) * 100
                self.max_daily_loss_amount = self.risk_metrics.total_portfolio_value * self.max_daily_loss_pct
            
            # Update position counts
            self.risk_metrics.open_positions_count = len(self.positions)
            
            # Calculate max single position risk
            if self.positions:
                max_risk = max(abs(pos.unrealized_pnl) for pos in self.positions.values())
                self.risk_metrics.max_single_position_risk = max_risk
            
            logger.debug(f"Risk metrics updated - P&L: ₹{daily_pnl:.2f}, Positions: {len(self.positions)}")
            
        except Exception as e:
            logger.error(f"Error updating risk metrics: {e}")

    async def _check_daily_loss_limits(self):
        """Check if daily loss limits are exceeded"""
        if self.risk_metrics.daily_pnl < -self.max_daily_loss_amount:
            await self._trigger_emergency_halt(
                reason=f"Daily loss limit exceeded: ₹{self.risk_metrics.daily_pnl:.2f} (limit: ₹{-self.max_daily_loss_amount:.2f})",
                event_type=RiskEventType.DAILY_LOSS_LIMIT
            )

    async def _check_position_limits(self):
        """Check position count and size limits"""
        # Check position count
        if len(self.positions) > self.max_positions:
            await self._log_risk_event(RiskEventType.MAX_POSITIONS_EXCEEDED, RiskSeverity.HIGH, {
                "current_positions": len(self.positions),
                "max_positions": self.max_positions
            })
        
        # Check individual position sizes
        for symbol, position in self.positions.items():
            if position.position_value > self.max_position_size:
                await self._log_risk_event(RiskEventType.POSITION_SIZE_EXCEEDED, RiskSeverity.HIGH, {
                    "symbol": symbol,
                    "position_value": position.position_value,
                    "max_position_size": self.max_position_size
                })

    async def _check_stop_losses(self):
        """Check if any positions hit stop losses"""
        for symbol, position in self.positions.items():
            if position.quantity > 0:  # Long position
                if position.current_price <= position.stop_loss:
                    await self._execute_stop_loss(position)
            elif position.quantity < 0:  # Short position
                if position.current_price >= position.stop_loss:
                    await self._execute_stop_loss(position)

    async def _check_margin_requirements(self):
        """Check margin requirements"""
        if self.risk_metrics.available_margin < (self.risk_metrics.used_margin * 0.1):  # 10% buffer
            await self._log_risk_event(RiskEventType.MARGIN_SHORTAGE, RiskSeverity.HIGH, {
                "available_margin": self.risk_metrics.available_margin,
                "used_margin": self.risk_metrics.used_margin
            })

    async def _monitor_individual_position(self, position: Position):
        """Monitor individual position for risk events"""
        # Check for unusual price movements
        if abs(position.pnl_percentage) > 10:  # 10% move
            await self._log_risk_event(RiskEventType.UNUSUAL_MARKET_MOVEMENT, RiskSeverity.MEDIUM, {
                "symbol": position.symbol,
                "pnl_percentage": position.pnl_percentage,
                "current_price": position.current_price,
                "entry_price": position.entry_price
            })

    async def _execute_stop_loss(self, position: Position):
        """Execute stop loss for a position"""
        try:
            logger.warning(f"🚨 STOP LOSS HIT: {position.symbol} at ₹{position.current_price}")
            
            # Execute market order to close position
            order_response = await self.iifl_service.place_order(
                instrument_id=position.instrument_id,
                quantity=abs(position.quantity),
                price=0,  # Market order
                order_type="MARKET",
                side="SELL" if position.quantity > 0 else "BUY",
                product=position.product_type,
                exchange=position.exchange,
                validity="DAY"
            )
            
            await self._log_risk_event(RiskEventType.STOP_LOSS_HIT, RiskSeverity.HIGH, {
                "symbol": position.symbol,
                "stop_loss_price": position.stop_loss,
                "current_price": position.current_price,
                "pnl": position.unrealized_pnl,
                "order_response": order_response
            })
            
            await self._send_alert(
                f"🚨 STOP LOSS EXECUTED: {position.symbol}\n"
                f"Price: ₹{position.current_price:.2f}\n"
                f"Loss: ₹{position.unrealized_pnl:.2f}\n"
                f"Quantity: {position.quantity}",
                RiskSeverity.HIGH
            )
            
        except Exception as e:
            logger.error(f"Failed to execute stop loss for {position.symbol}: {e}")

    async def _trigger_emergency_halt(self, reason: str, event_type: RiskEventType):
        """Trigger emergency trading halt"""
        self.emergency_halt = True
        
        logger.critical(f"🚨 EMERGENCY HALT TRIGGERED: {reason}")
        
        try:
            # Close all positions
            await self._close_all_positions()
            
            # Log the emergency event
            await self._log_risk_event(event_type, RiskSeverity.CRITICAL, {
                "reason": reason,
                "positions_count": len(self.positions),
                "daily_pnl": self.risk_metrics.daily_pnl
            })
            
            # Send critical alert
            await self._send_alert(
                f"🚨 EMERGENCY HALT TRIGGERED\n"
                f"Reason: {reason}\n"
                f"All positions being closed\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                RiskSeverity.CRITICAL
            )
            
        except Exception as e:
            logger.error(f"Error during emergency halt: {e}")

    async def _close_all_positions(self):
        """Close all open positions"""
        logger.warning("🚨 Closing all positions due to emergency halt")
        
        for symbol, position in self.positions.items():
            try:
                await self.iifl_service.place_order(
                    instrument_id=position.instrument_id,
                    quantity=abs(position.quantity),
                    price=0,  # Market order
                    order_type="MARKET",
                    side="SELL" if position.quantity > 0 else "BUY",
                    product=position.product_type,
                    exchange=position.exchange,
                    validity="DAY"
                )
                
                logger.info(f"Closed position: {symbol}")
                
            except Exception as e:
                logger.error(f"Failed to close position {symbol}: {e}")

    async def _get_current_price(self, symbol: str) -> float:
        """Get current market price for symbol"""
        # This would integrate with market data feed
        # For now, return a placeholder
        return 0.0

    async def _calculate_stop_loss(self, position_data: Dict) -> float:
        """Calculate stop loss price for position"""
        entry_price = float(position_data.get('buyAveragePrice', 0) or position_data.get('sellAveragePrice', 0))
        quantity = int(position_data.get('quantity', 0))
        
        if quantity > 0:  # Long position
            return entry_price * (1 - float(settings.STOP_LOSS_PERCENT))
        else:  # Short position
            return entry_price * (1 + float(settings.STOP_LOSS_PERCENT))

    async def _calculate_take_profit(self, position_data: Dict) -> float:
        """Calculate take profit price for position"""
        entry_price = float(position_data.get('buyAveragePrice', 0) or position_data.get('sellAveragePrice', 0))
        quantity = int(position_data.get('quantity', 0))
        
        if quantity > 0:  # Long position
            return entry_price * (1 + float(settings.TAKE_PROFIT_PERCENT))
        else:  # Short position
            return entry_price * (1 - float(settings.TAKE_PROFIT_PERCENT))

    async def _calculate_advanced_risk_metrics(self):
        """Calculate advanced risk metrics like VaR, Beta, etc."""
        # Placeholder for advanced risk calculations
        # Would integrate with historical data and statistical models
        pass

    async def _log_risk_event(self, event_type: RiskEventType, severity: RiskSeverity, details: Dict):
        """Log a risk event"""
        event = {
            "timestamp": datetime.now(),
            "event_type": event_type.value,
            "severity": severity.value,
            "details": details
        }
        
        self.recent_risk_events.append(event)
        
        trading_logger.log_system_event("risk_event", {
            "event_type": event_type.value,
            "severity": severity.value,
            "details": details
        })
        
        logger.warning(f"Risk event: {event_type.value} - {severity.value}")
        
        # Send alert based on severity
        if severity in [RiskSeverity.HIGH, RiskSeverity.CRITICAL]:
            await self._send_alert(
                f"Risk Event: {event_type.value}\nSeverity: {severity.value}\nDetails: {json.dumps(details, indent=2)}",
                severity
            )

    async def _send_alert(self, message: str, severity: RiskSeverity):
        """Send risk alert via configured channels"""
        try:
            # Check cooldown to avoid spam
            alert_key = f"{severity.value}_{hash(message)}"
            if alert_key in self.alert_cooldown:
                if datetime.now() - self.alert_cooldown[alert_key] < timedelta(minutes=5):
                    return  # Skip if same alert sent within 5 minutes
            
            self.alert_cooldown[alert_key] = datetime.now()
            
            # Send via Telegram
            if settings.TELEGRAM_NOTIFICATIONS_ENABLED:
                await self.telegram_service.send_message(f"🚨 RISK ALERT\n\n{message}")
            
            # Log the alert
            logger.warning(f"Risk alert sent: {message}")
            
        except Exception as e:
            logger.error(f"Failed to send risk alert: {e}")

    def _cleanup_old_events(self):
        """Clean up old risk events"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.recent_risk_events = [
            event for event in self.recent_risk_events
            if event["timestamp"] > cutoff_time
        ]
        
        # Clean up alert cooldown
        cutoff_cooldown = datetime.now() - timedelta(hours=1)
        self.alert_cooldown = {
            key: timestamp for key, timestamp in self.alert_cooldown.items()
            if timestamp > cutoff_cooldown
        }

    def get_current_status(self) -> Dict[str, Any]:
        """Get current risk monitoring status"""
        return {
            "is_monitoring": self.is_monitoring,
            "emergency_halt": self.emergency_halt,
            "positions_count": len(self.positions),
            "risk_metrics": {
                "daily_pnl": self.risk_metrics.daily_pnl,
                "daily_pnl_percentage": self.risk_metrics.daily_pnl_percentage,
                "available_margin": self.risk_metrics.available_margin,
                "used_margin": self.risk_metrics.used_margin,
                "total_portfolio_value": self.risk_metrics.total_portfolio_value,
                "open_positions_count": self.risk_metrics.open_positions_count
            },
            "recent_events_count": len(self.recent_risk_events),
            "last_update": self.last_position_update.isoformat()
        }

    def get_positions_summary(self) -> List[Dict]:
        """Get summary of current positions"""
        return [
            {
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "pnl_percentage": pos.pnl_percentage,
                "position_value": pos.position_value,
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit
            }
            for pos in self.positions.values()
        ]

    def get_recent_risk_events(self, limit: int = 50) -> List[Dict]:
        """Get recent risk events"""
        return sorted(
            self.recent_risk_events,
            key=lambda x: x["timestamp"],
            reverse=True
        )[:limit]

# Global risk monitor instance
risk_monitor = RealTimeRiskMonitor()