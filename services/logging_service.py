import logging
import logging.handlers
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import traceback
from pathlib import Path
import os
from datetime import timedelta
try:
    from config.settings import get_settings  # type: ignore
except Exception:
    def get_settings():
        class _S:
            log_retention_days = 14
        return _S()

class TradingLogger:
    """Centralized logging service for the trading system"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create different loggers for different components
        self.main_logger = self._setup_logger("main", "trading_system.log")
        self.trade_logger = self._setup_logger("trades", "trades.log")
        self.risk_logger = self._setup_logger("risk", "risk_events.log")
        self.api_logger = self._setup_logger("api", "api_calls.log")
        self.error_logger = self._setup_logger("errors", "errors.log", level=logging.ERROR)
        self._sentry_enabled = False
        self._telegram_notify = None
    
    def _setup_logger(self, name: str, filename: str, level: int = logging.INFO) -> logging.Logger:
        """Setup individual logger with rotating file handler"""
        logger = logging.getLogger(f"trading.{name}")
        logger.setLevel(level)
        
        # Remove existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / filename,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger

    def enable_sentry(self):
        self._sentry_enabled = True

    def set_telegram_notifier(self, notifier):
        self._telegram_notify = notifier
    
    def log_trade(self, signal_id: str, action: str, symbol: str, 
                  quantity: int, price: float, details: Dict[str, Any] = None):
        """Log trading activity"""
        trade_data = {
            "timestamp": datetime.now().isoformat(),
            "signal_id": signal_id,
            "action": action,
            "symbol": symbol,
            "quantity": quantity,
            "price": price,
            "details": details or {}
        }
        
        self.trade_logger.info(f"TRADE: {json.dumps(trade_data)}")
    
    def log_risk_event(self, event_type: str, severity: str, description: str, 
                      details: Dict[str, Any] = None):
        """Log risk management events"""
        risk_data = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "description": description,
            "details": details or {}
        }
        
        self.risk_logger.warning(f"RISK: {json.dumps(risk_data)}")
    
    def log_api_call(self, endpoint: str, method: str, status_code: int, 
                     response_time: float, error: str = None):
        """Log API calls"""
        api_data = {
            "timestamp": datetime.now().isoformat(),
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "response_time_ms": response_time * 1000,
            "error": error
        }
        
        level = logging.ERROR if error else logging.INFO
        self.api_logger.log(level, f"API: {json.dumps(api_data)}")
    
    def log_error(self, component: str, error: Exception, context: Dict[str, Any] = None):
        """Log errors with full context"""
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "component": component,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {}
        }
        
        self.error_logger.error(f"ERROR: {json.dumps(error_data, indent=2)}")
        try:
            if self._sentry_enabled:
                import sentry_sdk
                sentry_sdk.capture_exception(error)
        except Exception:
            pass
        try:
            if self._telegram_notify and isinstance(error, Exception):
                # only critical error notifications
                message = f"Critical error in {component}: {type(error).__name__} - {str(error)[:300]}"
                asyncio.create_task(self._telegram_notify(message))
        except Exception:
            pass
    
    def log_system_event(self, event: str, details: Dict[str, Any] = None):
        """Log system-level events"""
        event_data = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "details": details or {}
        }
        
        self.main_logger.info(f"SYSTEM: {json.dumps(event_data)}")

    def prune_old_logs(self, retention_days: int = 14) -> List[str]:
        """Delete log files older than retention_days; return list of removed files."""
        removed: List[str] = []
        try:
            cutoff = datetime.now() - timedelta(days=retention_days)
            for file in self.log_dir.glob("*.log"):
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(file))
                    if mtime < cutoff:
                        file.unlink(missing_ok=True)
                        removed.append(str(file))
                except Exception:
                    continue
        except Exception:
            pass
        return removed

    async def daily_housekeeping(self):
        """Run housekeeping tasks like pruning logs based on settings."""
        try:
            settings = get_settings()
            retention = getattr(settings, "log_retention_days", 14) or 14
            removed = self.prune_old_logs(retention)
            if removed:
                self.main_logger.info(f"Housekeeping pruned logs: {removed}")
        except Exception as e:
            self.error_logger.error(f"Housekeeping error: {str(e)}")

# Global logger instance
trading_logger = TradingLogger()

class ErrorHandler:
    """Centralized error handling with retry logic"""
    
    def __init__(self, logger: TradingLogger):
        self.logger = logger
    
    async def handle_with_retry(self, func, *args, max_retries: int = 3, 
                               delay: float = 1.0, component: str = "unknown", **kwargs):
        """Execute function with retry logic and error handling"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_error = e
                self.logger.log_error(
                    component, 
                    e, 
                    {
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "args": str(args)[:200],  # Truncate for logging
                        "kwargs": str(kwargs)[:200]
                    }
                )
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                else:
                    raise last_error
        
        raise last_error
    
    def safe_execute(self, func, *args, default_return=None, 
                    component: str = "unknown", **kwargs):
        """Execute function safely, returning default on error"""
        try:
            if asyncio.iscoroutinefunction(func):
                # For async functions, return a coroutine that handles the error
                async def async_wrapper():
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        self.logger.log_error(component, e, {
                            "function": func.__name__,
                            "args": str(args)[:200],
                            "kwargs": str(kwargs)[:200]
                        })
                        return default_return
                return async_wrapper()
            else:
                return func(*args, **kwargs)
                
        except Exception as e:
            self.logger.log_error(component, e, {
                "function": func.__name__,
                "args": str(args)[:200],
                "kwargs": str(kwargs)[:200]
            })
            return default_return

# Global error handler
error_handler = ErrorHandler(trading_logger)

def log_performance(component: str):
    """Decorator to log function performance"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = await func(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()
                
                trading_logger.main_logger.info(
                    f"PERFORMANCE: {component}.{func.__name__} "
                    f"executed in {execution_time:.3f}s"
                )
                return result
                
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                trading_logger.log_error(component, e, {
                    "function": func.__name__,
                    "execution_time": execution_time
                })
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()
                
                trading_logger.main_logger.info(
                    f"PERFORMANCE: {component}.{func.__name__} "
                    f"executed in {execution_time:.3f}s"
                )
                return result
                
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                trading_logger.log_error(component, e, {
                    "function": func.__name__,
                    "execution_time": execution_time
                })
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
