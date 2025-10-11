"""
Optimized logging configuration for the trading system.
Dynamic configuration based on environment and performance requirements.
"""
import logging
import logging.handlers
import os
import json
import time
import socket
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from functools import wraps
import sys

class RateLimitedLogger:
    """Logger with rate limiting to prevent log flooding."""
    
    def __init__(self, logger: logging.Logger, max_messages_per_minute: int = 60):
        self.logger = logger
        self.max_messages = max_messages_per_minute
        self.message_counts = defaultdict(deque)
        self.lock = threading.Lock()
    
    def _should_log(self, message_key: str) -> bool:
        """Check if message should be logged based on rate limiting."""
        with self.lock:
            now = time.time()
            minute_ago = now - 60
            
            # Clean old entries
            message_queue = self.message_counts[message_key]
            while message_queue and message_queue[0] < minute_ago:
                message_queue.popleft()
            
            # Check rate limit
            if len(message_queue) >= self.max_messages:
                return False
            
            # Record this message
            message_queue.append(now)
            return True
    
    def log(self, level: int, msg: str, *args, **kwargs):
        """Rate-limited logging."""
        message_key = msg[:50]  # Use first 50 chars as key
        if self._should_log(message_key):
            self.logger.log(level, msg, *args, **kwargs)

class PerformanceFilter(logging.Filter):
    """Filter for performance-sensitive logging."""
    
    def __init__(self, threshold_ms: int = 1000):
        super().__init__()
        self.threshold_ms = threshold_ms
    
    def filter(self, record):
        """Only log if performance threshold is exceeded."""
        duration_ms = getattr(record, 'duration_ms', 0)
        return duration_ms >= self.threshold_ms

class ErrorAggregationHandler(logging.Handler):
    """Handler that aggregates similar errors to reduce noise."""
    
    def __init__(self, window_minutes: int = 5, max_detail_length: int = 2048):
        super().__init__()
        self.window_minutes = window_minutes
        self.max_detail_length = max_detail_length
        self.error_counts = defaultdict(int)
        self.last_logged = {}
        self.lock = threading.Lock()
    
    def emit(self, record):
        """Aggregate errors and emit summary when appropriate."""
        if record.levelno < logging.ERROR:
            return
        
        error_key = f"{record.module}:{record.funcName}:{record.getMessage()[:100]}"
        
        with self.lock:
            now = time.time()
            self.error_counts[error_key] += 1
            
            # Check if we should log this error
            last_log_time = self.last_logged.get(error_key, 0)
            window_seconds = self.window_minutes * 60
            
            if now - last_log_time >= window_seconds:
                count = self.error_counts[error_key]
                
                # Create aggregated record
                aggregated_record = logging.LogRecord(
                    name=record.name,
                    level=record.levelno,
                    pathname=record.pathname,
                    lineno=record.lineno,
                    msg=f"[Aggregated {count}x in {self.window_minutes}min] {record.getMessage()[:self.max_detail_length]}",
                    args=(),
                    exc_info=record.exc_info
                )
                
                # Log to next handler in chain
                for handler in logging.getLogger().handlers:
                    if handler != self:
                        handler.emit(aggregated_record)
                
                # Reset counters
                self.error_counts[error_key] = 0
                self.last_logged[error_key] = now

class OptimizedJSONFormatter(logging.Formatter):
    """High-performance JSON formatter with context injection."""
    
    def __init__(self, include_hostname=True, include_process_id=True, include_thread_id=False):
        super().__init__()
        self.hostname = socket.gethostname() if include_hostname else None
        self.process_id = os.getpid() if include_process_id else None
        self.include_thread_id = include_thread_id
        
        # Pre-compute static fields
        self.static_fields = {}
        if self.hostname:
            self.static_fields['hostname'] = self.hostname
        if self.process_id:
            self.static_fields['process_id'] = self.process_id
    
    def format(self, record):
        """Format log record as optimized JSON."""
        # Start with pre-computed static fields
        log_entry = dict(self.static_fields)
        
        # Add timestamp
        log_entry['timestamp'] = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        
        # Core log fields
        log_entry.update({
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        })
        
        # Optional thread ID
        if self.include_thread_id:
            log_entry['thread_id'] = record.thread
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra context
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName',
                          'processName', 'process', 'stack_info', 'exc_info', 'exc_text', 'message'}:
                extra_fields[key] = value
        
        if extra_fields:
            log_entry['extra'] = extra_fields
        
        return json.dumps(log_entry, default=str, separators=(',', ':'))

class LoggingOptimizer:
    """Centralized logging configuration and optimization."""
    
    def __init__(self, settings):
        self.settings = settings
        self.loggers = {}
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        
    def setup_optimized_logging(self) -> Dict[str, logging.Logger]:
        """Setup optimized logging configuration."""
        
        # Create formatters
        if self.settings.log_format == "json":
            formatter = OptimizedJSONFormatter(
                include_hostname=self.settings.log_include_hostname,
                include_process_id=self.settings.log_include_process_id,
                include_thread_id=self.settings.log_include_thread_id
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # Setup component loggers
        logger_configs = {
            'trading.main': {
                'level': self.settings.log_level,
                'file': 'trading_system.log',
                'rate_limit': None
            },
            'trading.trades': {
                'level': self.settings.log_level_trades,
                'file': 'trades.log',
                'rate_limit': None
            },
            'trading.api': {
                'level': self.settings.log_level_api,
                'file': 'api_calls.log',
                'rate_limit': self.settings.api_log_rate_limit
            },
            'trading.risk': {
                'level': self.settings.log_level_risk,
                'file': 'risk_events.log',
                'rate_limit': None
            },
            'trading.strategy': {
                'level': self.settings.log_level_strategy,
                'file': 'strategy.log',
                'rate_limit': None
            },
            'trading.data': {
                'level': self.settings.log_level_data,
                'file': 'data_fetcher.log',
                'rate_limit': 200  # Limit data fetcher logs
            },
            'trading.performance': {
                'level': 'INFO',
                'file': 'performance.log',
                'rate_limit': None
            }
        }
        
        # Critical events logger with special handling
        if self.settings.enable_critical_events:
            logger_configs['trading.critical'] = {
                'level': 'INFO',
                'file': 'critical_events.log',
                'rate_limit': None,
                'immediate_flush': self.settings.critical_events_immediate_flush,
                'max_size_mb': self.settings.critical_events_max_size_mb
            }
        
        # Create loggers
        for name, config in logger_configs.items():
            logger = self._create_optimized_logger(name, config, formatter)
            self.loggers[name] = logger
        
        # Setup root logger
        self._setup_root_logger(formatter)
        
        # Setup error aggregation if enabled
        if self.settings.enable_error_aggregation:
            self._setup_error_aggregation()
        
        return self.loggers
    
    def _create_optimized_logger(self, name: str, config: Dict[str, Any], formatter: logging.Formatter) -> logging.Logger:
        """Create optimized logger with specified configuration."""
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, config['level'].upper()))
        
        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # File handler with rotation
        log_file = self.log_dir / config['file']
        max_size_mb = config.get('max_size_mb', self.settings.log_max_file_size_mb)
        
        if config.get('immediate_flush', False):
            # Special handler for critical events
            class FlushingRotatingFileHandler(logging.handlers.RotatingFileHandler):
                def emit(self, record):
                    super().emit(record)
                    self.flush()
            
            file_handler = FlushingRotatingFileHandler(
                log_file,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=self.settings.log_backup_count
            )
        else:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=self.settings.log_backup_count
            )
        
        file_handler.setFormatter(formatter)
        
        # Add performance filter if enabled
        if config.get('performance_filter', False):
            file_handler.addFilter(
                PerformanceFilter(self.settings.performance_threshold_ms)
            )
        
        logger.addHandler(file_handler)
        
        # Console handler (if enabled)
        if self.settings.log_console_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # Rate limiting wrapper
        rate_limit = config.get('rate_limit')
        if rate_limit:
            return RateLimitedLogger(logger, rate_limit)
        
        return logger
    
    def _setup_root_logger(self, formatter: logging.Formatter):
        """Setup root logger configuration."""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.settings.log_level.upper()))
        
        # Remove default handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
    
    def _setup_error_aggregation(self):
        """Setup error aggregation handler."""
        aggregation_handler = ErrorAggregationHandler(
            window_minutes=self.settings.error_aggregation_window_minutes,
            max_detail_length=self.settings.max_error_details_length
        )
        
        # Add to root logger to catch all errors
        logging.getLogger().addHandler(aggregation_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get optimized logger by name."""
        return self.loggers.get(f'trading.{name}', logging.getLogger(name))
    
    def log_performance_metric(self, metric_name: str, value: float, unit: str = "", **context):
        """Log performance metric with optimization."""
        if not self.settings.enable_performance_logging:
            return
        
        perf_logger = self.get_logger('performance')
        perf_logger.info(
            f"Performance: {metric_name} = {value}{unit}",
            extra={
                'metric_name': metric_name,
                'metric_value': value,
                'metric_unit': unit,
                **context
            }
        )
    
    def configure_sampling(self):
        """Configure log sampling if enabled."""
        if not self.settings.enable_log_sampling:
            return
        
        class SamplingFilter(logging.Filter):
            def __init__(self, sample_rate: float):
                super().__init__()
                self.sample_rate = sample_rate
                import random
                self.random = random.Random()
            
            def filter(self, record):
                return self.random.random() < self.sample_rate
        
        # Apply sampling to high-volume loggers
        sampling_filter = SamplingFilter(self.settings.log_sample_rate)
        
        for logger_name in ['trading.api', 'trading.data']:
            logger = self.loggers.get(logger_name)
            if logger:
                for handler in logger.handlers:
                    handler.addFilter(sampling_filter)

def setup_optimized_logging(settings) -> Dict[str, logging.Logger]:
    """Setup optimized logging configuration."""
    optimizer = LoggingOptimizer(settings)
    loggers = optimizer.setup_optimized_logging()
    
    # Configure sampling if enabled
    optimizer.configure_sampling()
    
    return loggers

# Performance monitoring decorator
def log_performance(logger_name: str = 'performance'):
    """Decorator to log function performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger = logging.getLogger(f'trading.{logger_name}')
                logger.info(
                    f"Function {func.__name__} completed in {duration_ms:.2f}ms",
                    extra={
                        'function_name': func.__name__,
                        'duration_ms': duration_ms,
                        'success': True
                    }
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger = logging.getLogger(f'trading.{logger_name}')
                logger.error(
                    f"Function {func.__name__} failed after {duration_ms:.2f}ms: {str(e)}",
                    extra={
                        'function_name': func.__name__,
                        'duration_ms': duration_ms,
                        'success': False,
                        'error': str(e)
                    }
                )
                raise
        return wrapper
    return decorator

# Async version of performance decorator
def log_async_performance(logger_name: str = 'performance'):
    """Decorator to log async function performance."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                logger = logging.getLogger(f'trading.{logger_name}')
                logger.info(
                    f"Async function {func.__name__} completed in {duration_ms:.2f}ms",
                    extra={
                        'function_name': func.__name__,
                        'duration_ms': duration_ms,
                        'success': True,
                        'async': True
                    }
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger = logging.getLogger(f'trading.{logger_name}')
                logger.error(
                    f"Async function {func.__name__} failed after {duration_ms:.2f}ms: {str(e)}",
                    extra={
                        'function_name': func.__name__,
                        'duration_ms': duration_ms,
                        'success': False,
                        'error': str(e),
                        'async': True
                    }
                )
                raise
        return wrapper
    return decorator