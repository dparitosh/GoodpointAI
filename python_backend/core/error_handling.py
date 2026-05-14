"""
Error Handling Framework - Retry logic, error classification, and recovery strategies

Provides:
- Error classification (transient vs permanent)
- Retry decorator with exponential backoff
- Fallback response generation
- Error context tracking and logging
"""

import asyncio
import logging
import time
from functools import wraps
from enum import Enum
from typing import Callable, TypeVar, Any, Optional, Dict, Coroutine
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorSeverity(str, Enum):
    """Error severity levels"""
    TRANSIENT = "transient"        # Retry-able error (timeout, connection, rate limit)
    RECOVERABLE = "recoverable"    # May succeed with fallback (service unavailable)
    PERMANENT = "permanent"        # Do not retry (invalid input, not found)


class ErrorCategory(str, Enum):
    """Error categories for specific handling"""
    AGENT_TIMEOUT = "agent_timeout"
    AGENT_UNAVAILABLE = "agent_unavailable"
    NETWORK_ERROR = "network_error"
    RATE_LIMITED = "rate_limited"
    INVALID_INPUT = "invalid_input"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    DATABASE_ERROR = "database_error"
    UNKNOWN = "unknown"


class ClassifiedError(Exception):
    """Error with classification and context"""
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity,
        category: ErrorCategory,
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None
    ):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.original_error = original_error
        self.context = context or {}
        self.retry_after = retry_after  # Seconds to wait before retry
        self.timestamp = datetime.utcnow()
    
    def should_retry(self) -> bool:
        """Determine if this error is retry-able"""
        return self.severity in [ErrorSeverity.TRANSIENT, ErrorSeverity.RECOVERABLE]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/response"""
        return {
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "context": self.context,
            "retry_after": self.retry_after,
            "timestamp": self.timestamp.isoformat()
        }


def classify_error(error: Exception) -> ClassifiedError:
    """
    Classify an exception and determine retry strategy
    
    Args:
        error: Exception to classify
        
    Returns:
        ClassifiedError with severity, category, and context
    """
    error_message = str(error)
    error_type = type(error).__name__
    
    # Timeout errors - TRANSIENT
    if isinstance(error, asyncio.TimeoutError) or "timeout" in error_message.lower():
        return ClassifiedError(
            message=f"Operation timed out: {error_message}",
            severity=ErrorSeverity.TRANSIENT,
            category=ErrorCategory.AGENT_TIMEOUT,
            original_error=error,
            retry_after=2
        )
    
    # Connection errors - TRANSIENT
    if isinstance(error, ConnectionError) or "connection" in error_message.lower():
        return ClassifiedError(
            message=f"Connection error: {error_message}",
            severity=ErrorSeverity.TRANSIENT,
            category=ErrorCategory.NETWORK_ERROR,
            original_error=error,
            retry_after=3
        )
    
    # Service unavailable errors - RECOVERABLE
    if "unavailable" in error_message.lower() or "service" in error_message.lower():
        return ClassifiedError(
            message=f"Service unavailable: {error_message}",
            severity=ErrorSeverity.RECOVERABLE,
            category=ErrorCategory.AGENT_UNAVAILABLE,
            original_error=error,
            retry_after=5
        )
    
    # Rate limit errors - TRANSIENT
    if "rate" in error_message.lower() or "throttl" in error_message.lower():
        return ClassifiedError(
            message=f"Rate limited: {error_message}",
            severity=ErrorSeverity.TRANSIENT,
            category=ErrorCategory.RATE_LIMITED,
            original_error=error,
            retry_after=10
        )
    
    # Resource exhausted - TRANSIENT
    if "resource" in error_message.lower() or "exhausted" in error_message.lower():
        return ClassifiedError(
            message=f"Resource exhausted: {error_message}",
            severity=ErrorSeverity.TRANSIENT,
            category=ErrorCategory.RESOURCE_EXHAUSTED,
            original_error=error,
            retry_after=5
        )
    
    # Input validation errors - PERMANENT
    if "invalid" in error_message.lower() or "valueerror" in error_type.lower():
        return ClassifiedError(
            message=f"Invalid input: {error_message}",
            severity=ErrorSeverity.PERMANENT,
            category=ErrorCategory.INVALID_INPUT,
            original_error=error
        )
    
    # Database errors - TRANSIENT or RECOVERABLE
    if "database" in error_message.lower() or "sql" in error_message.lower():
        return ClassifiedError(
            message=f"Database error: {error_message}",
            severity=ErrorSeverity.RECOVERABLE,
            category=ErrorCategory.DATABASE_ERROR,
            original_error=error,
            retry_after=3
        )
    
    # Unknown errors - RECOVERABLE
    return ClassifiedError(
        message=f"Unknown error: {error_message}",
        severity=ErrorSeverity.RECOVERABLE,
        category=ErrorCategory.UNKNOWN,
        original_error=error,
        retry_after=2
    )


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 32.0,
    exponential_base: float = 2.0
):
    """
    Decorator for async functions with exponential backoff retry logic
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff (e.g., 2 = double each time)
        
    Usage:
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        async def fetch_data():
            return await api.get()
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error: Optional[Exception] = None
            delay = initial_delay
            
            for attempt in range(max_retries + 1):  # +1 to include initial attempt
                try:
                    logger.debug(f"Attempt {attempt + 1}/{max_retries + 1} for {func.__name__}")
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    last_error = e
                    classified = classify_error(e)
                    
                    # Don't retry permanent errors
                    if classified.severity == ErrorSeverity.PERMANENT:
                        logger.error(
                            f"Permanent error in {func.__name__}: {classified.message}",
                            extra={"error_context": classified.to_dict()}
                        )
                        raise
                    
                    # Last attempt - raise error
                    if attempt >= max_retries:
                        logger.error(
                            f"Max retries exceeded for {func.__name__} after {max_retries} attempts",
                            extra={"error_context": classified.to_dict()}
                        )
                        raise
                    
                    # Calculate next delay with exponential backoff
                    next_delay = min(delay * exponential_base, max_delay)
                    
                    # Add jitter to prevent thundering herd
                    import random
                    jittered_delay = next_delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Retryable error in {func.__name__}, retrying in {jittered_delay:.2f}s. "
                        f"Attempt {attempt + 1}/{max_retries}. Error: {classified.message}",
                        extra={"error_context": classified.to_dict()}
                    )
                    
                    # Wait before retry
                    await asyncio.sleep(jittered_delay)
                    delay = next_delay
            
            # Should not reach here, but just in case
            if last_error:
                raise last_error
            raise RuntimeError("Retry decorator failed to complete")
            
        return wrapper
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for preventing cascading failures
    
    States:
    - CLOSED: Normal operation (requests go through)
    - OPEN: Service is failing (reject requests immediately)
    - HALF_OPEN: Testing if service recovered (allow limited requests)
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 60
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds
        
        # State tracking
        self.state = "CLOSED"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function through circuit breaker"""
        
        # OPEN state - reject requests
        if self.state == "OPEN":
            if self.last_failure_time is None:
                # First time opening circuit
                self.last_failure_time = datetime.utcnow()
                raise Exception(f"Circuit breaker {self.name} is OPEN. Service unavailable.")
            
            time_since_failure = (datetime.utcnow() - self.last_failure_time).total_seconds()
            
            # Check if timeout elapsed, transition to HALF_OPEN
            if time_since_failure > self.timeout_seconds:
                logger.info(f"Circuit breaker {self.name}: OPEN -> HALF_OPEN")
                self.state = "HALF_OPEN"
                self.success_count = 0
            else:
                raise Exception(
                    f"Circuit breaker {self.name} is OPEN. Service unavailable. "
                    f"Retry in {self.timeout_seconds - time_since_failure:.0f}s"
                )
        
        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise
    
    def _record_success(self):
        """Record successful call"""
        self.failure_count = 0
        
        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN -> CLOSED")
                self.state = "CLOSED"
                self.success_count = 0
    
    def _record_failure(self):
        """Record failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker {self.name}: CLOSED -> OPEN "
                f"(failures: {self.failure_count}/{self.failure_threshold})"
            )
            self.state = "OPEN"
        
        if self.state == "HALF_OPEN":
            # Failure in HALF_OPEN state - go back to OPEN
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN -> OPEN (recovery failed)")
            self.state = "OPEN"
            self.success_count = 0
    
    def record_success(self):
        """Public method: Record successful call"""
        self._record_success()
    
    def record_failure(self):
        """Public method: Record failed call"""
        self._record_failure()


# Global circuit breakers for different services
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Get or create circuit breaker for service"""
    if service_name not in _circuit_breakers:
        _circuit_breakers[service_name] = CircuitBreaker(
            name=service_name,
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=60
        )
    return _circuit_breakers[service_name]
