"""
Time-related functions for MicroPython.

Provides sleep functions and tick counters for timing operations.

MicroPython provides two common time bases:

- An epoch-based wall clock (``time()``, ``localtime()``, ``gmtime()``), where
    the epoch is typically Jan 1, 2000.
- Monotonic tick counters (``ticks_ms()``, ``ticks_us()``, ``ticks_cpu()``)
    designed for measuring durations.

Example
-------
```python
    >>> import time
    >>> 
    >>> time.sleep(1)           # Sleep 1 second
    >>> time.sleep_ms(500)      # Sleep 500 milliseconds
    >>> time.sleep_us(100)      # Sleep 100 microseconds
    >>> 
    >>> # Measure elapsed time
    >>> start = time.ticks_ms()
    >>> # ... do work ...
    >>> elapsed = time.ticks_diff(time.ticks_ms(), start)
    >>> print(f"Took {elapsed}ms")
```
"""

from typing import Optional


def sleep(seconds: float) -> None:
    """
    Sleep for the given number of seconds.

    Accuracy and minimum sleep granularity are platform dependent.

    :param seconds: Time to sleep in seconds (can be float)

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> time.sleep(1)      # Sleep 1 second
        >>> time.sleep(0.5)    # Sleep 500ms
        >>> time.sleep(0.001)  # Sleep 1ms
    ```
    """
    ...


def sleep_ms(ms: int) -> None:
    """
    Sleep for the given number of milliseconds.

    :param ms: Time to sleep in milliseconds

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> time.sleep_ms(500)   # Sleep 500ms
        >>> time.sleep_ms(1000)  # Sleep 1 second
    ```
    """
    ...


def sleep_us(us: int) -> None:
    """
    Sleep for the given number of microseconds.

    :param us: Time to sleep in microseconds

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> time.sleep_us(100)   # Sleep 100 microseconds
        >>> time.sleep_us(1000)  # Sleep 1 millisecond
    ```
    """
    ...


def ticks_ms() -> int:
    """
    Return an increasing millisecond counter.

    The counter wraps around after some value, so always use
    ticks_diff() to compute differences.

    Use ``ticks_add()`` and ``ticks_diff()`` when implementing deadlines.

    :returns: Millisecond tick value

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> start = time.ticks_ms()
        >>> # ... do work ...
        >>> elapsed = time.ticks_diff(time.ticks_ms(), start)
    ```
    """
    ...


def ticks_us() -> int:
    """
    Return an increasing microsecond counter.

    The counter wraps around after some value, so always use
    ticks_diff() to compute differences.

    :returns: Microsecond tick value

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> start = time.ticks_us()
        >>> # ... do work ...
        >>> elapsed = time.ticks_diff(time.ticks_us(), start)
    ```
    """
    ...


def ticks_cpu() -> int:
    """
    Return a high-resolution CPU tick counter.

    Resolution is platform-dependent. Use for very short timing.

    :returns: CPU tick value

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> start = time.ticks_cpu()
        >>> # ... fast operation ...
        >>> elapsed = time.ticks_diff(time.ticks_cpu(), start)
    ```
    """
    ...


def ticks_diff(ticks1: int, ticks2: int) -> int:
    """
    Compute the signed difference between two tick values.

    Correctly handles counter wrap-around.

    :param ticks1: Later tick value
    :param ticks2: Earlier tick value

    :returns: Signed difference (ticks1 - ticks2)

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> start = time.ticks_ms()
        >>> time.sleep_ms(100)
        >>> elapsed = time.ticks_diff(time.ticks_ms(), start)
        >>> print(f"Elapsed: {elapsed}ms")  # ~100
    ```
    """
    ...


def ticks_add(ticks: int, delta: int) -> int:
    """
    Add a delta to a tick value, handling wrap-around.

    :param ticks: Base tick value
    :param delta: Value to add (can be negative)

    :returns: New tick value

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> # Calculate deadline 1 second from now
        >>> deadline = time.ticks_add(time.ticks_ms(), 1000)
        >>> 
        >>> while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        ...     # Wait until deadline
        ...     pass
    ```
    """
    ...


def time() -> int:
    """
    Return seconds since the Epoch (Jan 1, 2000 on MicroPython).

    The wall clock must be set by the port (e.g. via RTC or NTP) to be useful.

    :returns: Seconds since epoch

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> now = time.time()
        >>> print(f"Seconds since epoch: {now}")
    ```
    """
    ...


def time_ns() -> int:
    """
    Return nanoseconds since the Epoch.

    :returns: Nanoseconds since epoch

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> now_ns = time.time_ns()
    ```
    """
    ...


def gmtime(secs: Optional[int] = None) -> tuple:
    """
    Convert seconds to a time tuple (UTC).

    :param secs: Seconds since epoch (None = current time)

    :returns: Tuple (year, month, mday, hour, minute, second, weekday, yearday)

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> t = time.gmtime()
        >>> year, month, day, hour, minute, second, wd, yd = t
        >>> print(f"{year}-{month:02d}-{day:02d}")
    ```
    """
    ...


def localtime(secs: Optional[int] = None) -> tuple:
    """
    Convert seconds to a local time tuple.

    Some ports do not implement time zones; in that case ``localtime`` may be
    equivalent to ``gmtime``.

    :param secs: Seconds since epoch (None = current time)

    :returns: Tuple (year, month, mday, hour, minute, second, weekday, yearday)

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> t = time.localtime()
        >>> print(f"{t[3]:02d}:{t[4]:02d}:{t[5]:02d}")
    ```
    """
    ...


def mktime(t: tuple) -> int:
    """
    Convert a time tuple to seconds since epoch.

    This is the inverse of ``localtime()`` for ports that implement both.

    :param t: Time tuple (year, month, mday, hour, minute, second, weekday, yearday)

    :returns: Seconds since epoch

    Example
    -------
    ```python
        >>> import time
        >>> 
        >>> # January 7, 2026, 12:00:00
        >>> t = (2026, 1, 7, 12, 0, 0, 0, 0)
        >>> secs = time.mktime(t)
    ```
    """
    ...
