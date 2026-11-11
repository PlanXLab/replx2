"""
Wait for I/O events on streams.

Provides poll/select functionality.

Example
-------
```python
    >>> import select
    >>> 
    >>> poll = select.poll()
    >>> poll.register(stream, select.POLLIN)
    >>> events = poll.poll(1000)  # Wait 1 second
```
"""

from typing import Any, Optional, Union


# Event constants
POLLIN: int
"""Data available to read."""

POLLOUT: int
"""Ready for writing."""

POLLERR: int
"""Error condition."""

POLLHUP: int
"""Hang up (peer closed)."""


class poll:
    """
    Polling object for waiting on I/O.

    Example
    -------
    ```python
        >>> import select
        >>> from machine import UART
        >>> 
        >>> uart = UART(0, 115200)
        >>> poll = select.poll()
        >>> poll.register(uart, select.POLLIN)
        >>> 
        >>> # Wait for data
        >>> events = poll.poll(1000)
        >>> for obj, event in events:
        ...     if event & select.POLLIN:
        ...         data = obj.read()
    ```
    """

    def __init__(self) -> None:
        """Create poll object."""
        ...

    def register(self, obj: Any, eventmask: int = POLLIN | POLLOUT) -> None:
        """
        Register stream for polling.

        :param obj: Stream object
        :param eventmask: Events to monitor

        Example
        -------
        ```python
            >>> import select
            >>> 
            >>> poll = select.poll()
            >>> poll.register(uart, select.POLLIN)
            >>> poll.register(socket, select.POLLIN | select.POLLOUT)
        ```
        """
        ...

    def unregister(self, obj: Any) -> None:
        """
        Unregister stream.

        :param obj: Stream object to remove

        Example
        -------
        ```python
            >>> import select
            >>> 
            >>> poll.unregister(uart)
        ```
        """
        ...

    def modify(self, obj: Any, eventmask: int) -> None:
        """
        Modify event mask for registered stream.

        :param obj: Registered stream
        :param eventmask: New event mask

        Example
        -------
        ```python
            >>> import select
            >>> 
            >>> poll.modify(socket, select.POLLIN)
        ```
        """
        ...

    def poll(self, timeout: int = -1) -> list[tuple[Any, int]]:
        """
        Wait for events.

        :param timeout: Timeout in ms (-1=forever, 0=non-blocking)

        :returns: List of (object, event) tuples

        Example
        -------
        ```python
            >>> import select
            >>> 
            >>> # Wait up to 1 second
            >>> events = poll.poll(1000)
            >>> 
            >>> for obj, event in events:
            ...     if event & select.POLLIN:
            ...         print("Data ready")
        ```
        """
        ...

    def ipoll(self, timeout: int = -1, flags: int = 0) -> Any:
        """
        Iterate over events (memory efficient).

        Like poll() but returns iterator.

        :param timeout: Timeout in ms
        :param flags: Flags (1 = one-shot)

        :returns: Iterator of (object, event) tuples

        Example
        -------
        ```python
            >>> import select
            >>> 
            >>> for obj, event in poll.ipoll(1000):
            ...     if event & select.POLLIN:
            ...         data = obj.read()
        ```
        """
        ...


def select(rlist: list, wlist: list, xlist: list, timeout: float = None) -> tuple:
    """
    Wait for I/O events (BSD-style).

    :param rlist: Wait for read
    :param wlist: Wait for write
    :param xlist: Wait for exceptions
    :param timeout: Timeout in seconds

    :returns: (readable, writable, errors) tuple

    Example
    -------
    ```python
        >>> import select
        >>> 
        >>> readable, _, _ = select.select([uart], [], [], 1.0)
        >>> if readable:
        ...     data = uart.read()
    ```
    """
    ...
