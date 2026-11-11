"""
Low-level C structure access.

Access structured data in memory with C-like definitions.

Example
-------
```python
    >>> import uctypes
    >>> 
    >>> # Define a structure
    >>> HEADER = {
    ...     'magic': uctypes.UINT32 | 0,
    ...     'size': uctypes.UINT16 | 4,
    ...     'flags': uctypes.UINT8 | 6,
    ... }
    >>> 
    >>> buf = bytearray(8)
    >>> s = uctypes.struct(uctypes.addressof(buf), HEADER)
    >>> s.magic = 0xDEADBEEF
```
"""

from typing import Any, Union


# Type constants - scalar types
INT8: int
"""Signed 8-bit integer."""

UINT8: int
"""Unsigned 8-bit integer."""

INT16: int
"""Signed 16-bit integer."""

UINT16: int
"""Unsigned 16-bit integer."""

INT32: int
"""Signed 32-bit integer."""

UINT32: int
"""Unsigned 32-bit integer."""

INT64: int
"""Signed 64-bit integer."""

UINT64: int
"""Unsigned 64-bit integer."""

FLOAT32: int
"""32-bit float."""

FLOAT64: int
"""64-bit float (double)."""

# Special types
VOID: int
"""Void pointer type."""

PTR: int
"""Pointer type indicator."""

ARRAY: int
"""Array type indicator."""

# Byte order constants
NATIVE: int
"""Native byte order and alignment."""

LITTLE_ENDIAN: int
"""Little-endian byte order."""

BIG_ENDIAN: int
"""Big-endian byte order."""


def struct(addr: int, descriptor: dict, layout_type: int = NATIVE) -> Any:
    """
    Create structure object at memory address.

    :param addr: Memory address
    :param descriptor: Structure descriptor dictionary
    :param layout_type: Byte order (NATIVE, LITTLE_ENDIAN, BIG_ENDIAN)

    :returns: Structure accessor object

    Example
    -------
    ```python
        >>> import uctypes
        >>> 
        >>> # Define register layout
        >>> GPIO_REGS = {
        ...     'OUT': uctypes.UINT32 | 0,
        ...     'OE': uctypes.UINT32 | 4,
        ...     'IN': uctypes.UINT32 | 8,
        ... }
        >>> 
        >>> buf = bytearray(12)
        >>> gpio = uctypes.struct(uctypes.addressof(buf), GPIO_REGS)
        >>> gpio.OUT = 0xFF
    ```
    """
    ...


def addressof(obj: Any) -> int:
    """
    Get memory address of object.

    :param obj: Object (usually bytearray or array)

    :returns: Memory address

    Example
    -------
    ```python
        >>> import uctypes
        >>> 
        >>> buf = bytearray(100)
        >>> addr = uctypes.addressof(buf)
        >>> print(hex(addr))
    ```
    """
    ...


def sizeof(obj: Union[dict, Any], layout_type: int = NATIVE) -> int:
    """
    Calculate size of structure.

    :param obj: Structure descriptor or instance
    :param layout_type: Byte order for descriptors

    :returns: Size in bytes

    Example
    -------
    ```python
        >>> import uctypes
        >>> 
        >>> HEADER = {
        ...     'magic': uctypes.UINT32 | 0,
        ...     'size': uctypes.UINT16 | 4,
        ... }
        >>> 
        >>> size = uctypes.sizeof(HEADER)  # 6
    ```
    """
    ...


def bytes_at(addr: int, size: int) -> bytes:
    """
    Read bytes from memory address.

    :param addr: Memory address
    :param size: Number of bytes to read

    :returns: Bytes read from memory

    Example
    -------
    ```python
        >>> import uctypes
        >>> 
        >>> # Read from memory-mapped register
        >>> data = uctypes.bytes_at(0x40000000, 16)
    ```
    """
    ...


def bytearray_at(addr: int, size: int) -> bytearray:
    """
    Create bytearray view of memory.

    Changes to bytearray modify underlying memory.

    :param addr: Memory address
    :param size: Size of view

    :returns: Bytearray view

    Example
    -------
    ```python
        >>> import uctypes
        >>> 
        >>> buf = bytearray(100)
        >>> addr = uctypes.addressof(buf)
        >>> 
        >>> # Create view of first 10 bytes
        >>> view = uctypes.bytearray_at(addr, 10)
        >>> view[0] = 0xFF  # Modifies buf[0]
    ```
    """
    ...
