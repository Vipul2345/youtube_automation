"""Bounded retry with exponential backoff, jitter, and error classification.

Distinguishes transient (network, rate-limit, 5xx) from permanent
(auth, permission, schema, 4xx excluding 429) errors. Never retries
permanent failures. Uses bounded exponential backoff with full jitter.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


# Error classification markers — raised by adapters, caught by retry.


class TransientError(Exception):
    """A transient error that should be retried with backoff."""


class PermanentError(Exception):
    """A permanent error that must not be retried."""


class RateLimitError(TransientError):
    """HTTP 429 or similar rate-limiting response."""


async def retry_with_backoff(
    fn: Callable[..., Awaitable[Any]],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    **kwargs: Any,
) -> Any:
    """Execute *fn* with bounded exponential backoff.

    Args:
        fn: The async callable to invoke.
        max_attempts: Maximum number of attempts (1 = no retry).
        base_delay: Base delay in seconds for exponential calculation.
        max_delay: Cap for the exponential delay before jitter.
        jitter: Apply full jitter (random uniform between 0 and delay).

    Raises:
        PermanentError: Wrapped permanent failures are re-raised as-is.
        TransientError: If all attempts exhausted on a transient error.
        BaseException: Unexpected exceptions are not caught.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except PermanentError:
            raise
        except (TransientError, TimeoutError, ConnectionError, OSError) as exc:
            last_exc = exc
            if attempt < max_attempts:
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                if jitter:
                    delay = random.uniform(0, delay)
                logger.warning(
                    "Attempt %d/%d failed: %s. Retrying in %.2fs ...",
                    attempt,
                    max_attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "All %d attempts exhausted for transient error: %s",
                    max_attempts,
                    exc,
                )
    raise TransientError(f"Operation failed after {max_attempts} attempts") from last_exc


def classify_http_status(status: int, body: str = "") -> None:
    """Raise an appropriate error for an HTTP status code.

    Args:
        status: The HTTP status code.
        body: The response body text (used only for logging context).

    Raises:
        RateLimitError: For 429 responses.
        PermanentError: For 4xx (except 429) and some 5xx that should not be retried.
        TransientError: For other server/network-adjacent responses.
    """
    if status == 429:
        raise RateLimitError(f"Rate limited (429) — response: {body[:200]}")
    if status == 403:
        raise PermanentError(f"Permission denied (403) — response: {body[:200]}")
    if status == 401:
        raise PermanentError(f"Authentication failed (401) — response: {body[:200]}")
    if status == 404:
        raise PermanentError(f"Resource not found (404) — response: {body[:200]}")
    if status == 400:
        raise PermanentError(f"Bad request (400) — response: {body[:200]}")
    if 500 <= status <= 599:
        raise TransientError(f"Server error ({status}) — response: {body[:200]}")
    if 400 <= status <= 499:
        raise PermanentError(f"Client error ({status}) — response: {body[:200]}")


def exponential_backoff_delay(attempt: int, base: float = 2.0, max_delay: float = 30.0) -> float:
    """Return a jittered exponential backoff delay in seconds."""
    delay = min(base * (2 ** (attempt - 1)), max_delay)
    return random.uniform(0, delay)
