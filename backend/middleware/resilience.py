"""
Resilience patterns for SmartPlayFPL API.

Implements:
- Circuit Breaker: Prevents cascading failures when external services are down
- Retry with exponential backoff: Automatic retries for transient failures
- Request timeout wrapper: Ensures operations don't hang indefinitely
"""

import asyncio
import functools
import logging
import time
from datetime import datetime
from enum import Enum
from typing import Callable, Optional, TypeVar, Any
from dataclasses import dataclass, field

logger = logging.getLogger("smartplayfpl.resilience")

T = TypeVar("T")


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStats:
    """Statistics for circuit breaker monitoring."""
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0
    total_blocked: int = 0


@dataclass
class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls.

    Usage:
        cb = CircuitBreaker(name="fpl_api", failure_threshold=5)

        async with cb:
            result = await fetch_from_fpl()

    Or as decorator:
        @cb.protect
        async def fetch_from_fpl():
            ...
    """
    name: str
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_requests: int = 3

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failures: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0, init=False)
    _half_open_successes: int = field(default=0, init=False)
    _stats: CircuitStats = field(default_factory=CircuitStats, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current state, checking for automatic recovery."""
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state

    @property
    def is_available(self) -> bool:
        """Check if requests can proceed."""
        return self.state != CircuitState.OPEN

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._stats.state_changes += 1

        if new_state == CircuitState.HALF_OPEN:
            self._half_open_successes = 0
        elif new_state == CircuitState.CLOSED:
            self._failures = 0

        logger.info(f"Circuit '{self.name}': {old_state.value} -> {new_state.value}")

    def record_success(self) -> None:
        """Record a successful call."""
        self._stats.successes += 1
        self._stats.last_success_time = datetime.utcnow()

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.half_open_requests:
                self._transition_to(CircuitState.CLOSED)

    def record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        self._failures += 1
        self._last_failure_time = time.time()
        self._stats.failures += 1
        self._stats.last_failure_time = datetime.utcnow()

        logger.warning(f"Circuit '{self.name}': failure #{self._failures} - {type(error).__name__}: {error}")

        if self._state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self._failures >= self.failure_threshold:
            self._transition_to(CircuitState.OPEN)

    async def __aenter__(self):
        """Async context manager entry."""
        if not self.is_available:
            self._stats.total_blocked += 1
            raise CircuitOpenError(f"Circuit '{self.name}' is open")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure(exc_val)
        return False  # Don't suppress exceptions

    def protect(self, func: Callable) -> Callable:
        """Decorator to protect a function with circuit breaker."""
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with self:
                return await func(*args, **kwargs)
        return wrapper

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self._stats.failures,
            "successes": self._stats.successes,
            "blocked": self._stats.total_blocked,
            "state_changes": self._stats.state_changes,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


class CircuitOpenError(Exception):
    """Raised when a circuit breaker is open."""
    pass


# =============================================================================
# CIRCUIT BREAKER REGISTRY
# =============================================================================

class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    _instance: Optional["CircuitBreakerRegistry"] = None
    _breakers: dict[str, CircuitBreaker] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._breakers = {}
        return cls._instance

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_requests: int = 3,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_requests=half_open_requests,
            )
        return self._breakers[name]

    def get_all_stats(self) -> dict[str, dict]:
        """Get statistics for all circuit breakers."""
        return {name: cb.get_stats() for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers to closed state."""
        for cb in self._breakers.values():
            cb._transition_to(CircuitState.CLOSED)


# Global registry instance
circuit_registry = CircuitBreakerRegistry()


# =============================================================================
# RETRY WITH BACKOFF
# =============================================================================

async def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> T:
    """
    Execute a function with exponential backoff retry.

    Args:
        func: Async function to execute
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exceptions that trigger retry
        on_retry: Optional callback called on each retry (attempt, exception)

    Returns:
        Result of successful function execution

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except retryable_exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(f"All {max_retries} retries exhausted: {e}")
                raise

            delay = min(initial_delay * (exponential_base ** attempt), max_delay)

            if on_retry:
                on_retry(attempt + 1, e)

            logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay:.1f}s: {e}")
            await asyncio.sleep(delay)

    raise last_exception


def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    retryable_exceptions: tuple = (Exception,),
) -> Callable:
    """Decorator for automatic retry with backoff."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                lambda: func(*args, **kwargs),
                max_retries=max_retries,
                initial_delay=initial_delay,
                retryable_exceptions=retryable_exceptions,
            )
        return wrapper
    return decorator


# =============================================================================
# TIMEOUT WRAPPER
# =============================================================================

async def with_timeout(
    coro,
    timeout: float,
    timeout_message: Optional[str] = None,
) -> Any:
    """
    Execute a coroutine with a timeout.

    Args:
        coro: Coroutine to execute
        timeout: Timeout in seconds
        timeout_message: Custom message for timeout error

    Returns:
        Result of coroutine

    Raises:
        asyncio.TimeoutError: If operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        msg = timeout_message or f"Operation timed out after {timeout}s"
        logger.warning(msg)
        raise asyncio.TimeoutError(msg)


def timeout_decorator(seconds: float) -> Callable:
    """Decorator to add timeout to async function."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await with_timeout(
                func(*args, **kwargs),
                timeout=seconds,
                timeout_message=f"{func.__name__} timed out after {seconds}s"
            )
        return wrapper
    return decorator


# =============================================================================
# PRE-CONFIGURED CIRCUIT BREAKERS
# =============================================================================

# FPL API circuit breaker
fpl_circuit = circuit_registry.get_or_create(
    name="fpl_api",
    failure_threshold=5,
    recovery_timeout=60,
    half_open_requests=3,
)

# Claude AI circuit breaker (more lenient due to longer operations)
claude_circuit = circuit_registry.get_or_create(
    name="claude_ai",
    failure_threshold=3,
    recovery_timeout=120,
    half_open_requests=2,
)
