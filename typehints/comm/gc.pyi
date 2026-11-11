"""
Garbage collector control for MicroPython.

Provides memory management and statistics.

Use this module to inspect heap usage and to control when GC runs. This can be
useful on memory-constrained devices or in timing-sensitive code.

Example
-------
```python
    >>> import gc
    >>> 
    >>> # Get memory info
    >>> free = gc.mem_free()
    >>> used = gc.mem_alloc()
    >>> print(f"Free: {free}, Used: {used}")
    >>> 
    >>> # Force collection
    >>> gc.collect()
```
"""

from typing import Optional


def enable() -> None:
    """
    Enable automatic garbage collection.

    When enabled, GC will run automatically based on allocation heuristics.

    Example
    -------
    ```python
        >>> import gc
        >>> 
        >>> gc.enable()
    ```
    """
    ...


def disable() -> None:
    """
    Disable automatic garbage collection.

    Manual gc.collect() calls still work.

    Disabling GC can reduce latency jitter, but can also increase peak memory
    usage.

    Example
    -------
    ```python
        >>> import gc
        >>> 
        >>> gc.disable()  # For timing-critical code
        >>> # ... do work ...
        >>> gc.collect()  # Manual collection
        >>> gc.enable()
    ```
    """
    ...


def collect() -> int:
    """
    Run a garbage collection cycle.

    Frees unreferenced memory.

    :returns: Amount of memory freed (bytes) on ports that report it.

    Example
    -------
    ```python
        >>> import gc
        >>> 
        >>> freed = gc.collect()
        >>> print(f"Freed {freed} bytes")
    ```
    """
    ...


def mem_alloc() -> int:
    """
    Get amount of heap RAM currently allocated.

    :returns: Allocated bytes

    Example
    -------
    ```python
        >>> import gc
        >>> 
        >>> used = gc.mem_alloc()
        >>> print(f"Used: {used} bytes")
    ```
    """
    ...


def mem_free() -> int:
    """
    Get amount of heap RAM available.

    :returns: Free bytes

    Example
    -------
    ```python
        >>> import gc
        >>> 
        >>> free = gc.mem_free()
        >>> print(f"Free: {free // 1024} KB")
    ```
    """
    ...


def threshold(amount: Optional[int] = None) -> Optional[int]:
    """
    Get or set GC allocation threshold.

    When amount bytes are allocated, GC triggers automatically.

    Passing a negative value may disable threshold-triggered GC on some ports.

    :param amount: Threshold in bytes (None to query)

    :returns: Current threshold if querying

    Example
    -------
    ```python
        >>> import gc
        >>> 
        >>> # Get current threshold
        >>> t = gc.threshold()
        >>> 
        >>> # Set threshold to 50KB
        >>> gc.threshold(50 * 1024)
        >>> 
        >>> # Disable threshold-based GC
        >>> gc.threshold(-1)
    ```
    """
    ...


def isenabled() -> bool:
    """
    Check if automatic GC is enabled.

    :returns: True if enabled

    Example
    -------
    ```python
        >>> import gc
        >>> 
        >>> if gc.isenabled():
        ...     print("GC is automatic")
    ```
    """
    ...
