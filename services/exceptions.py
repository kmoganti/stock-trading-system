"""
Common exception handling utilities and custom exceptions for the trading system.
"""
import functools
import logging
from typing import Any, Callable, Optional, TypeVar, Union
from datetime import datetime

# Type variable for decorated functions
F = TypeVar('F', bound=Callable[..., Any])

class TradingSystemError(Exception):
    """Base exception for trading system errors."""
    pass

class APIError(TradingSystemError):
    """Exception raised for API-related errors."""
    pass

class DataFetchError(TradingSystemError):
    """Exception raised for data fetching errors."""
    pass

class RiskManagementError(TradingSystemError):
    """Exception raised for risk management violations."""
    pass

class AuthenticationError(TradingSystemError):
    """Exception raised for authentication failures."""
    pass

class ValidationError(TradingSystemError):
    """Exception raised for validation failures."""
    pass


def handle_exceptions(
    logger: Optional[logging.Logger] = None,
    default_return: Any = None,
    re_raise: bool = False,
    log_level: int = logging.ERROR
):
    """
    Decorator for standardized exception handling across services.
    
    Args:
        logger: Logger instance to use for error logging
        default_return: Default value to return on exception
        re_raise: Whether to re-raise the exception after logging
        log_level: Logging level to use for the error message
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if logger:
                    logger.log(log_level, f"Error in {func.__name__}: {str(e)}")
                if re_raise:
                    raise
                return default_return
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if logger:
                    logger.log(log_level, f"Error in {func.__name__}: {str(e)}")
                if re_raise:
                    raise
                return default_return
        
        # Return the appropriate wrapper based on function type
        if hasattr(func, '__code__') and 'async' in str(func.__code__):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def log_and_return(
    logger: logging.Logger,
    error_msg: str,
    exception: Exception,
    default_return: Any = None,
    log_level: int = logging.ERROR
) -> Any:
    """
    Standard error logging and return pattern.
    
    Args:
        logger: Logger instance
        error_msg: Custom error message
        exception: The caught exception
        default_return: Value to return
        log_level: Logging level
    
    Returns:
        The default_return value
    """
    logger.log(log_level, f"{error_msg}: {str(exception)}")
    return default_return


def safe_execute(
    func: Callable,
    *args,
    logger: Optional[logging.Logger] = None,
    error_msg: str = "Operation failed",
    default_return: Any = None,
    **kwargs
) -> Any:
    """
    Safely execute a function with standardized error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        logger: Logger instance for error logging
        error_msg: Custom error message prefix
        default_return: Value to return on error
        **kwargs: Keyword arguments for the function
    
    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if logger:
            logger.error(f"{error_msg}: {str(e)}")
        return default_return


async def safe_execute_async(
    func: Callable,
    *args,
    logger: Optional[logging.Logger] = None,
    error_msg: str = "Async operation failed",
    default_return: Any = None,
    **kwargs
) -> Any:
    """
    Safely execute an async function with standardized error handling.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for the function
        logger: Logger instance for error logging
        error_msg: Custom error message prefix
        default_return: Value to return on error
        **kwargs: Keyword arguments for the function
    
    Returns:
        Function result or default_return on error
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        if logger:
            logger.error(f"{error_msg}: {str(e)}")
        return default_return