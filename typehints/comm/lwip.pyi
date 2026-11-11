"""lwip - lwIP TCP/IP stack debug bindings.

This module exposes low-level hooks into the lwIP TCP/IP stack on ports that
use lwIP internally. It is primarily intended for debugging.

Most applications should use `network` and `socket` instead.

Example
-------
```python
    >>> import lwip
    >>> 
    >>> # Usually accessed via socket module
```
"""


def print_pcbs() -> None:
    """
    Print active protocol control blocks.

    Debug utility to show TCP/UDP connections.

    Example
    -------
    ```python
        >>> import lwip
        >>> 
        >>> lwip.print_pcbs()
    ```
    """
    ...


def reset() -> None:
    """Reset the lwIP stack.

    This is a disruptive operation intended for debugging/recovery.

    Example
    -------
    ```python
        >>> import lwip
        >>> 
        >>> lwip.reset()
    ```
    """
    ...
