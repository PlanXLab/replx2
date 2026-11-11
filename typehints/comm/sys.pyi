"""
System-specific parameters and functions.

Provides access to interpreter state, version info, and system control.

This is a MicroPython subset of CPython's ``sys`` module. Some attributes may
be missing or simplified depending on the build.

Example
-------
```python
    >>> import sys
    >>> 
    >>> print(sys.version)
    >>> print(sys.platform)
    >>> print(sys.implementation.name)
    >>> 
    >>> # Exit program
    >>> sys.exit(0)
```
"""

from typing import Any, NoReturn, TextIO


# Version information
version: str
"""Python version string.

This is typically the full version banner shown at the REPL.
"""

version_info: tuple[int, int, int]
"""Version as tuple (major, minor, micro)."""

implementation: Any
"""Implementation info (name, version, etc.).

Common fields include ``name`` and ``version``. Exact shape is implementation
defined.
"""

platform: str
"""Platform identifier (e.g., 'rp2')."""


# Module search path
path: list[str]
"""List of directories to search for modules.

This is consulted by the import system.
"""

modules: dict[str, Any]
"""Dictionary of loaded modules.

Maps module names to imported module objects.
"""


# Standard streams
stdin: TextIO
"""Standard input stream."""

stdout: TextIO
"""Standard output stream."""

stderr: TextIO
"""Standard error stream."""


# Size limits
maxsize: int
"""Maximum integer value (platform dependent)."""

byteorder: str
"""Native byte order ('little' or 'big')."""


def exit(retval: int = 0) -> NoReturn:
    """
    Exit the program with a return value.

    This raises ``SystemExit``.

    :param retval: Return value (0 = success)

    Example
    -------
    ```python
        >>> import sys
        >>> 
        >>> if error_condition:
        ...     sys.exit(1)
        >>> 
        >>> sys.exit(0)  # Success
    ```
    """
    ...


def print_exception(exc: BaseException, file: TextIO = None) -> None:
    """
    Print exception with traceback.

    This is a MicroPython helper similar to ``traceback.print_exception``.

    :param exc: Exception to print
    :param file: Output file (default: sys.stdout)

    Example
    -------
    ```python
        >>> import sys
        >>> 
        >>> try:
        ...     1 / 0
        ... except Exception as e:
        ...     sys.print_exception(e)
    ```
    """
    ...


def exc_info() -> tuple:
    """
    Get information about the current exception.

    Intended for use in ``except:`` blocks.

    :returns: Tuple (type, value, traceback)

    Example
    -------
    ```python
        >>> import sys
        >>> 
        >>> try:
        ...     raise ValueError("test")
        ... except:
        ...     exc_type, exc_val, exc_tb = sys.exc_info()
    ```
    """
    ...


def atexit(func: callable) -> callable:
    """
    Register a function to be called at interpreter exit.

    Registered functions are called during interpreter shutdown or soft reset
    (port dependent).

    :param func: Function to call (no arguments)

    :returns: The registered function

    Example
    -------
    ```python
        >>> import sys
        >>> 
        >>> def cleanup():
        ...     print("Cleaning up...")
        >>> 
        >>> sys.atexit(cleanup)
    ```
    """
    ...
