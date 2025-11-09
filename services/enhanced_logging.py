"""
Enhanced logging configuration for comprehensive trading system monitoring.
"""
import logging
import logging.handlers
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from contextlib import contextmanager

class TradingSystemFormatter(logging.Formatter):
    """Custom formatter for structured logging with trading system context."""
    
    def __init__(self):
        super().__init__()
    
    def format(self, record):
        # Create structured log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "component": record.name.replace("trading.", "").replace("__main__", "main"),
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra context if available
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry)

class CriticalEventLogger:
    """Logger for critical trading system events that require monitoring."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup critical events logger
        self.critical_logger = self._setup_critical_logger()
        
    def _setup_critical_logger(self) -> logging.Logger:
        """Setup logger for critical events with immediate file writing."""
        logger = logging.getLogger("trading.critical")
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Critical events file handler - immediate flush
        critical_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "critical_events.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=10
        )
        critical_handler.setLevel(logging.INFO)
        critical_handler.setFormatter(TradingSystemFormatter())
        
        # Ensure immediate write for critical events
        class FlushingHandler(logging.handlers.RotatingFileHandler):
            def emit(self, record):
                super().emit(record)
                self.flush()
        
        critical_handler = FlushingHandler(
            self.log_dir / "critical_events.log",
            maxBytes=5*1024*1024,
            backupCount=10
        )
        critical_handler.setFormatter(TradingSystemFormatter())
        
        logger.addHandler(critical_handler)
        return logger
    
    def log_order_execution(self, order_id: str, symbol: str, side: str, 
                          quantity: int, price: float, status: str, **kwargs):
        """Log order execution events."""
        self.critical_logger.info(
            f"Order {status.upper()}: {side} {quantity} {symbol} @ ₹{price:.2f}",
            extra={
                'extra_data': {
                    'event_type': 'order_execution',
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'status': status,
                    'amount': quantity * price,
                    **kwargs
                }
            }
        )
    
    def log_signal_generation(self, signal_id: str, symbol: str, signal_type: str,
                            confidence: float, strategy: str, **kwargs):
        """Log trading signal generation."""
        self.critical_logger.info(
            f"Signal Generated: {signal_type.upper()} {symbol} (confidence: {confidence:.2f})",
            extra={
                'extra_data': {
                    'event_type': 'signal_generation',
                    'signal_id': signal_id,
                    'symbol': symbol,
                    'signal_type': signal_type,
                    'confidence': confidence,
                    'strategy': strategy,
                    **kwargs
                }
            }
        )
    
    def log_risk_violation(self, violation_type: str, description: str, 
                         severity: str, **kwargs):
        """Log risk management violations."""
        self.critical_logger.warning(
            f"Risk Violation: {violation_type} - {description}",
            extra={
                'extra_data': {
                    'event_type': 'risk_violation',
                    'violation_type': violation_type,
                    'description': description,
                    'severity': severity,
                    **kwargs
                }
            }
        )
    
    def log_pnl_update(self, date: str, daily_pnl: float, cumulative_pnl: float,
                      total_trades: int, **kwargs):
        """Log P&L updates."""
        self.critical_logger.info(
            f"P&L Update: Daily ₹{daily_pnl:,.2f}, Cumulative ₹{cumulative_pnl:,.2f}",
            extra={
                'extra_data': {
                    'event_type': 'pnl_update',
                    'date': date,
                    'daily_pnl': daily_pnl,
                    'cumulative_pnl': cumulative_pnl,
                    'total_trades': total_trades,
                    **kwargs
                }
            }
        )
    
    def log_system_state(self, component: str, state: str, **kwargs):
        """Log system state changes."""
        self.critical_logger.info(
            f"System State: {component} -> {state}",
            extra={
                'extra_data': {
                    'event_type': 'system_state',
                    'component': component,
                    'state': state,
                    **kwargs
                }
            }
        )
    
    def log_performance_metric(self, metric_name: str, value: float, 
                             unit: str = "", **kwargs):
        """Log performance metrics."""
        self.critical_logger.info(
            f"Performance: {metric_name} = {value}{unit}",
            extra={
                'extra_data': {
                    'event_type': 'performance_metric',
                    'metric_name': metric_name,
                    'value': value,
                    'unit': unit,
                    **kwargs
                }
            }
        )

# Global critical event logger
critical_events = CriticalEventLogger()

@contextmanager
def log_operation(operation_name: str, component: str = "system"):
    """Context manager for logging operation start/end with timing."""
    start_time = datetime.now()
    critical_events.critical_logger.info(
        f"Operation Started: {operation_name}",
        extra={
            'extra_data': {
                'event_type': 'operation_start',
                'operation': operation_name,
                'component': component,
                'start_time': start_time.isoformat()
            }
        }
    )
    
    try:
        yield
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        critical_events.critical_logger.info(
            f"Operation Completed: {operation_name} ({duration:.3f}s)",
            extra={
                'extra_data': {
                    'event_type': 'operation_complete',
                    'operation': operation_name,
                    'component': component,
                    'duration_seconds': duration,
                    'end_time': end_time.isoformat()
                }
            }
        )
    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        critical_events.critical_logger.error(
            f"Operation Failed: {operation_name} after {duration:.3f}s - {str(e)}",
            extra={
                'extra_data': {
                    'event_type': 'operation_failed',
                    'operation': operation_name,
                    'component': component,
                    'duration_seconds': duration,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'end_time': end_time.isoformat()
                }
            }
        )
        raise

def log_trade_execution(func):
    """Decorator for logging trade execution functions.

    Supports both sync and async functions without blocking the event loop.
    """
    import asyncio
    import functools

    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with log_operation(f"trade_execution_{func.__name__}", "order_manager"):
                return await func(*args, **kwargs)
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with log_operation(f"trade_execution_{func.__name__}", "order_manager"):
                return func(*args, **kwargs)
        return sync_wrapper

def log_signal_processing(func):
    """Decorator for logging signal processing functions.

    Works with both async and sync functions.
    """
    import asyncio
    import functools

    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with log_operation(f"signal_processing_{func.__name__}", "strategy"):
                return await func(*args, **kwargs)
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with log_operation(f"signal_processing_{func.__name__}", "strategy"):
                return func(*args, **kwargs)
        return sync_wrapper

def log_data_fetch(func):
    """Decorator for logging data fetching operations.

    Supports async and sync functions.
    """
    import asyncio
    import functools

    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with log_operation(f"data_fetch_{func.__name__}", "data_fetcher"):
                return await func(*args, **kwargs)
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with log_operation(f"data_fetch_{func.__name__}", "data_fetcher"):
                return func(*args, **kwargs)
        return sync_wrapper