"""
MicroPython-specific functions.

Memory and optimization utilities.

These APIs are specific to MicroPython and are primarily intended for embedded
use cases (interrupt safety, memory tuning, and performance).

Example
-------
```python
    >>> import micropython
    >>> 
    >>> # Memory info
    >>> micropython.mem_info()
    >>> 
    >>> # Emergency exception buffer
    >>> micropython.alloc_emergency_exception_buf(100)
```
"""

from typing import Any, Callable, Optional


def const(value: int) -> int:
    """
    Declare constant integer for optimization.

    Compiler will inline the value.

    ``const()`` is commonly used for module-level constants such as pins,
    register addresses, and bit masks.

    :param value: Constant value

    :returns: Same value

    Example
    -------
    ```python
        >>> from micropython import const
        >>> 
        >>> LED_PIN = const(25)
        >>> MAX_VALUE = const(255)
    ```
    """
    ...


def opt_level(level: int = None) -> Optional[int]:
    """
    Get or set optimization level.

    Levels:
    - 0: No optimization, assertions enabled
    - 1: Assertions removed
    - 2: Assertions and docstrings removed
    - 3: (same as 2)

    :param level: New level (None to query)

    Raising the optimization level may reduce memory usage at the cost of less
    debug information.

    :returns: Current level if querying

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> micropython.opt_level(2)
        >>> print(micropython.opt_level())
    ```
    """
    ...


def mem_info(verbose: bool = False) -> None:
    """
    Print memory usage information.

    :param verbose: Show detailed allocation info

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> micropython.mem_info()
        >>> micropython.mem_info(True)  # Detailed
    ```
    """
    ...


def qstr_info(verbose: bool = False) -> None:
    """
    Print interned string information.

    :param verbose: Show all strings

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> micropython.qstr_info()
    ```
    """
    ...


def stack_use() -> int:
    """
    Get current stack usage.

    :returns: Bytes of stack used

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> print(f"Stack: {micropython.stack_use()} bytes")
    ```
    """
    ...


def heap_lock() -> None:
    """
    Lock heap (prevent allocation).

    Use in critical sections.

    While the heap is locked, any operation that would allocate may raise an
    exception. This is useful in timing-critical code.

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> micropython.heap_lock()
        >>> # Critical code - no allocation allowed
        >>> micropython.heap_unlock()
    ```
    """
    ...


def heap_unlock() -> None:
    """
    Unlock heap (allow allocation).

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> micropython.heap_unlock()
    ```
    """
    ...


def heap_locked() -> bool:
    """
    Check if heap is locked.

    :returns: True if locked

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> if not micropython.heap_locked():
        ...     data = bytearray(100)
    ```
    """
    ...


def alloc_emergency_exception_buf(size: int) -> None:
    """
    Allocate buffer for exception in ISR.

    Allocate this early (before installing IRQ handlers) to allow printing
    tracebacks from hard interrupt context on ports that require it.

    Should be called early in program.

    :param size: Buffer size (100 is typical)

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> micropython.alloc_emergency_exception_buf(100)
    ```
    """
    ...


def kbd_intr(chr: int) -> None:
    """
    Set keyboard interrupt character.

    :param chr: ASCII code (-1 to disable)

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> micropython.kbd_intr(3)   # Ctrl+C (default)
        >>> micropython.kbd_intr(-1)  # Disable
    ```
    """
    ...


def schedule(func: Callable, arg: Any) -> None:
    """
    Schedule function to run soon.

    Safe to call from ISR.

    The scheduled function runs later in the VM context. The queue depth and
    overflow behaviour are port dependent.

    :param func: Function to call
    :param arg: Argument to pass

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> def handler(msg):
        ...     print(msg)
        >>> 
        >>> # In ISR:
        >>> micropython.schedule(handler, "Button pressed")
    ```
    """
    ...


def native(func: Callable) -> Callable:
    """
    Decorator for native code compilation.

    Native/Viper code generation is optional and can be disabled in some
    builds.

    :param func: Function to compile

    :returns: Native function

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> @micropython.native
        >>> def fast_add(a, b):
        ...     return a + b
    ```
    """
    ...


def viper(func: Callable) -> Callable:
    """
    Decorator for viper code compilation.

    Fastest but most restrictive.

    Viper mode supports typed pointers (e.g. ``ptr8``) and requires stricter
    code patterns. Incorrect use can crash the VM.

    :param func: Function to compile

    :returns: Viper function

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> @micropython.viper
        >>> def fast_fill(buf):
        ...     p = ptr8(buf)
        ...     for i in range(len(buf)):
        ...         p[i] = 0xFF
    ```
    """
    ...

# =============================================================================
# Viper Types (for use inside @viper decorated functions)
# =============================================================================

class int8:
    """Viper type: signed 8-bit integer."""
    def __init__(self, value: int) -> None: ...

class int16:
    """Viper type: signed 16-bit integer."""
    def __init__(self, value: int) -> None: ...

class int32:
    """Viper type: signed 32-bit integer."""
    def __init__(self, value: int) -> None: ...

class uint8:
    """Viper type: unsigned 8-bit integer."""
    def __init__(self, value: int) -> None: ...

class uint16:
    """Viper type: unsigned 16-bit integer."""
    def __init__(self, value: int) -> None: ...

class uint32:
    """Viper type: unsigned 32-bit integer."""
    def __init__(self, value: int) -> None: ...

class ptr:
    """
    Viper type: generic pointer.
    
    Use inside @micropython.viper decorated functions.
    """
    def __init__(self, buf: Any) -> None: ...
    def __getitem__(self, index: int) -> int: ...
    def __setitem__(self, index: int, value: int) -> None: ...


class RingIO:
    """
    A non-blocking ring buffer stream supporting the asyncio stream protocol.

    ``RingIO`` provides a FIFO buffer that can be used to pass data between
    coroutines or interrupt handlers without blocking.  It implements
    `asyncio.Stream`-compatible ``read``, ``readline``, ``write`` methods so
    it can be awaited with ``asyncio.StreamReader``/``StreamWriter``.

    Example
    -------
    ```python
        >>> import micropython
        >>> 
        >>> rio = micropython.RingIO(64)
        >>> rio.write(b"hello")
        5
        >>> rio.any()
        5
        >>> rio.read(5)
        b'hello'
    ```
    """

    def __init__(self, size: int) -> None:
        """
        Create a ``RingIO`` with a buffer of *size* bytes.

        :param size: Buffer size in bytes.

        Example
        -------
        ```python
            >>> import micropython
            >>> rio = micropython.RingIO(128)
        ```
        """
        ...

    def any(self) -> int:
        """
        Return the number of bytes available to read without blocking.

        :returns: Number of bytes ready in the buffer.

        Example
        -------
        ```python
            >>> rio.write(b"abc")
            >>> rio.any()
            3
        ```
        """
        ...

    def read(self, nbytes: Optional[int] = None) -> bytes:
        """
        Read and return up to *nbytes* bytes.  If *nbytes* is omitted,
        read as many bytes as are immediately available (non-blocking).

        :param nbytes: Maximum number of bytes to read.
        :returns: Bytes read from the buffer.

        Example
        -------
        ```python
            >>> rio.write(b"hello world")
            >>> rio.read(5)
            b'hello'
        ```
        """
        ...

    def readinto(self, buf: bytearray, nbytes: Optional[int] = None) -> int:
        """
        Read bytes into *buf*.  If *nbytes* is provided, read at most that
        many bytes.  Returns the number of bytes read.

        :param buf: Buffer to read data into.
        :param nbytes: Optional maximum number of bytes to read.
        :returns: Number of bytes actually read.

        Example
        -------
        ```python
            >>> buf = bytearray(8)
            >>> rio.write(b"data")
            >>> rio.readinto(buf, 4)
            4
        ```
        """
        ...

    def readline(self, nbytes: Optional[int] = None) -> bytes:
        """
        Read up to a newline character (``\\n``).  If *nbytes* is given,
        read at most that many bytes.  Returns bytes including the newline
        if found, otherwise all available bytes.

        :param nbytes: Optional maximum number of bytes to read.
        :returns: Bytes up to and including the newline.

        Example
        -------
        ```python
            >>> rio.write(b"line1\\nline2")
            >>> rio.readline()
            b'line1\\n'
        ```
        """
        ...

    def write(self, buf: bytes) -> int:
        """
        Write *buf* to the ring buffer.  Returns the number of bytes
        written, which may be less than ``len(buf)`` if the buffer is full.

        :param buf: Data to write.
        :returns: Number of bytes actually written.

        Example
        -------
        ```python
            >>> rio = micropython.RingIO(64)
            >>> rio.write(b"hello")
            5
        ```
        """
        ...

    def close(self) -> None:
        """
        Close the ``RingIO`` and release its buffer.

        Example
        -------
        ```python
            >>> rio = micropython.RingIO(64)
            >>> rio.close()
        ```
        """
        ...