"""
Threading support.

Multi-core threading on RP2.

Threading support is highly port dependent. Some ports implement true
multi-threading, while others may provide only limited primitives.

Be careful with shared mutable state: use locks to protect critical sections.

Example
-------
```python
    >>> import _thread
    >>> 
    >>> def task():
    ...     while True:
    ...         print("Thread running")
    ...         time.sleep(1)
    >>> 
    >>> _thread.start_new_thread(task, ())
```
"""

from typing import Any, Callable, Optional, Tuple


def start_new_thread(function: Callable, args: Tuple, kwargs: dict = None) -> int:
    """
    Start new thread.

    On RP2, runs on second core.

    The new thread starts executing ``function(*args, **kwargs)``.
    Behaviour of return values and exceptions in the new thread is
    implementation-defined.

    :param function: Function to run
    :param args: Positional arguments
    :param kwargs: Keyword arguments

    :returns: Thread identifier

    Example
    -------
    ```python
        >>> import _thread
        >>> 
        >>> def worker(name):
        ...     print(f"Hello from {name}")
        >>> 
        >>> _thread.start_new_thread(worker, ("Core1",))
    ```
    """
    ...


def exit() -> None:
    """
    Exit current thread.

    This terminates the calling thread.

    Example
    -------
    ```python
        >>> import _thread
        >>> 
        >>> def worker():
        ...     # Do work
        ...     _thread.exit()
    ```
    """
    ...


def allocate_lock() -> 'LockType':
    """
    Create new lock.

    Locks are used to synchronize access to shared resources.

    :returns: Lock object

    Example
    -------
    ```python
        >>> import _thread
        >>> 
        >>> lock = _thread.allocate_lock()
    ```
    """
    ...


def get_ident() -> int:
    """
    Get current thread identifier.

    :returns: Thread ID

    Example
    -------
    ```python
        >>> import _thread
        >>> 
        >>> tid = _thread.get_ident()
        >>> print(f"Thread: {tid}")
    ```
    """
    ...


def stack_size(size: int = None) -> int:
    """
    Get or set stack size for new threads.

    Stack sizing support varies by port. A too-small stack can cause crashes.

    :param size: New stack size

    :returns: Current/previous size

    Example
    -------
    ```python
        >>> import _thread
        >>> 
        >>> _thread.stack_size(8192)
    ```
    """
    ...


class LockType:
    """
    Thread lock for synchronization.

    Supports the context manager protocol (``with lock: ...``).

    Example
    -------
    ```python
        >>> import _thread
        >>> 
        >>> lock = _thread.allocate_lock()
        >>> 
        >>> lock.acquire()
        >>> try:
        ...     # Critical section
        ...     pass
        >>> finally:
        ...     lock.release()
    ```
    """

    def acquire(self, waitflag: int = 1, timeout: float = -1) -> bool:
        """
        Acquire lock.

        If ``waitflag`` is 0, returns immediately.
        If ``timeout`` is provided, waits up to that many seconds (port
        dependent).

        :param waitflag: Block if locked (1) or return (0)
        :param timeout: Wait timeout (-1 = forever)

        :returns: True if acquired

        Example
        -------
        ```python
            >>> import _thread
            >>> 
            >>> lock.acquire()
            >>> lock.acquire(0)  # Non-blocking
            >>> lock.acquire(1, 5.0)  # 5 second timeout
        ```
        """
        ...

    def release(self) -> None:
        """
        Release lock.

        Example
        -------
        ```python
            >>> import _thread
            >>> 
            >>> lock.release()
        ```
        """
        ...

    def locked(self) -> bool:
        """
        Check if lock is held.

        :returns: True if locked

        Example
        -------
        ```python
            >>> import _thread
            >>> 
            >>> if lock.locked():
            ...     print("Busy")
        ```
        """
        ...

    def __enter__(self) -> bool:
        """Context manager entry."""
        ...

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        ...
