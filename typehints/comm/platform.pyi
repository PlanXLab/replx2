"""platform - platform identification helpers.

This module returns descriptive strings about the current MicroPython runtime.

Notes
-----
- Values are informational and may differ from CPython.
- For structured information, prefer `sys.implementation` and `os.uname()`.

Example
-------
```python
    >>> import platform
    >>> 
    >>> print(platform.platform())
    >>> print(platform.python_version())
```
"""


def platform() -> str:
    """
    Get platform description.

    :returns: Platform string

    Example
    -------
    ```python
        >>> import platform
        >>> 
        >>> print(platform.platform())
        ... # 'MicroPython-1.24.0-rp2-RP2350'
    ```
    """
    ...


def python_version() -> str:
    """
    Get Python version string.

    :returns: Version string

    Example
    -------
    ```python
        >>> import platform
        >>> 
        >>> print(platform.python_version())
        ... # '3.4.0'
    ```
    """
    ...


def libc_ver() -> tuple[str, str]:
    """
    Get libc version.

    :returns: (lib, version) tuple

    Example
    -------
    ```python
        >>> import platform
        >>> 
        >>> lib, ver = platform.libc_ver()
    ```
    """
    ...
