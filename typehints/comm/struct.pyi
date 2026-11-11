"""
Pack and unpack binary data structures.

Example
-------
```python
    >>> import struct
    >>> 
    >>> # Pack values
    >>> data = struct.pack('<HH', 0x1234, 0x5678)
    >>> 
    >>> # Unpack values
    >>> x, y = struct.unpack('<HH', data)
```
"""

from typing import Any, Iterator, Union


def pack(fmt: str, *values: Any) -> bytes:
    """
    Pack values according to format string.

    Format characters:
    - b/B: signed/unsigned byte
    - h/H: signed/unsigned short (2 bytes)
    - i/I: signed/unsigned int (4 bytes)
    - l/L: signed/unsigned long (4 bytes)
    - q/Q: signed/unsigned long long (8 bytes)
    - f: float (4 bytes)
    - d: double (8 bytes)
    - s: bytes (preceded by length)

    Byte order:
    - < : little-endian
    - > : big-endian
    - @ : native

    :param fmt: Format string
    :param values: Values to pack

    :returns: Packed bytes

    Example
    -------
    ```python
        >>> import struct
        >>> 
        >>> # Little-endian uint16 + uint16
        >>> data = struct.pack('<HH', 0x1234, 0x5678)
        >>> 
        >>> # Float value
        >>> data = struct.pack('<f', 3.14159)
        >>> 
        >>> # String with length prefix
        >>> data = struct.pack('<H5s', 5, b'Hello')
    ```
    """
    ...


def unpack(fmt: str, buffer: Union[bytes, bytearray]) -> tuple:
    """
    Unpack values from buffer according to format.

    :param fmt: Format string
    :param buffer: Buffer to unpack from

    :returns: Tuple of unpacked values

    Example
    -------
    ```python
        >>> import struct
        >>> 
        >>> data = bytes([0x34, 0x12, 0x78, 0x56])
        >>> x, y = struct.unpack('<HH', data)
        >>> print(hex(x), hex(y))  # 0x1234 0x5678
    ```
    """
    ...


def unpack_from(fmt: str, buffer: Union[bytes, bytearray], offset: int = 0) -> tuple:
    """
    Unpack values from buffer at offset.

    :param fmt: Format string
    :param buffer: Buffer to unpack from
    :param offset: Byte offset to start at

    :returns: Tuple of unpacked values

    Example
    -------
    ```python
        >>> import struct
        >>> 
        >>> data = bytes([0x00, 0x00, 0x34, 0x12])
        >>> value, = struct.unpack_from('<H', data, 2)
        >>> print(hex(value))  # 0x1234
    ```
    """
    ...


def pack_into(fmt: str, buffer: bytearray, offset: int, *values: Any) -> None:
    """
    Pack values into buffer at offset.

    :param fmt: Format string
    :param buffer: Target buffer (must be bytearray)
    :param offset: Byte offset to write at
    :param values: Values to pack

    Example
    -------
    ```python
        >>> import struct
        >>> 
        >>> buf = bytearray(10)
        >>> struct.pack_into('<HH', buf, 2, 0x1234, 0x5678)
    ```
    """
    ...


def calcsize(fmt: str) -> int:
    """
    Calculate size of packed data.

    :param fmt: Format string

    :returns: Size in bytes

    Example
    -------
    ```python
        >>> import struct
        >>> 
        >>> size = struct.calcsize('<HHI')
        >>> print(size)  # 8 (2+2+4)
    ```
    """
    ...


def iter_unpack(fmt: str, buffer: Union[bytes, bytearray]) -> Iterator[tuple]:
    """
    Iteratively unpack from *buffer* according to format string *fmt*.

    Returns an iterator that yields successive tuples.  The buffer size must
    be a multiple of the size required by *fmt*.

    :param fmt: Pack format string (see ``pack()`` for format codes).
    :param buffer: Buffer to unpack from.
    :returns: Iterator of tuples.

    Example
    -------
    ```python
        >>> import struct
        >>> 
        >>> buf = struct.pack('<HH', 1, 2) + struct.pack('<HH', 3, 4)
        >>> for a, b in struct.iter_unpack('<HH', buf):
        ...     print(a, b)
        1 2
        3 4
    ```
    """
    ...


class Struct:
    """
    Pre-compiled struct format.

    Equivalent to calling ``struct.pack()`` / ``struct.unpack()`` with a
    fixed format string, but avoids re-parsing the format on every call.

    Example
    -------
    ```python
        >>> import struct
        >>> 
        >>> s = struct.Struct('<HI')
        >>> buf = s.pack(10, 200)
        >>> s.unpack(buf)
        (10, 200)
    ```
    """

    def __init__(self, fmt: str) -> None:
        """
        Create a ``Struct`` object for the given format string *fmt*.

        :param fmt: Pack format string.

        Example
        -------
        ```python
            >>> import struct
            >>> s = struct.Struct('>BH')
        ```
        """
        ...

    @property
    def format(self) -> str:
        """The format string passed to the constructor."""
        ...

    @property
    def size(self) -> int:
        """Byte size of the struct."""
        ...

    def pack(self, *values: Any) -> bytes:
        """
        Pack *values* according to this struct's format.

        :returns: Packed bytes.

        Example
        -------
        ```python
            >>> s = struct.Struct('<HI')
            >>> s.pack(1, 2)
            b'\\x01\\x00\\x02\\x00\\x00\\x00'
        ```
        """
        ...

    def pack_into(self, buffer: bytearray, offset: int, *values: Any) -> None:
        """
        Pack *values* into *buffer* at *offset*.

        :param buffer: Writable buffer.
        :param offset: Byte offset into the buffer.

        Example
        -------
        ```python
            >>> buf = bytearray(6)
            >>> s = struct.Struct('<HI')
            >>> s.pack_into(buf, 0, 1, 2)
        ```
        """
        ...

    def unpack(self, buffer: Union[bytes, bytearray]) -> tuple:
        """
        Unpack from *buffer*.

        :param buffer: Buffer containing packed data.
        :returns: Tuple of unpacked values.

        Example
        -------
        ```python
            >>> s = struct.Struct('<HI')
            >>> s.unpack(b'\\x01\\x00\\x02\\x00\\x00\\x00')
            (1, 2)
        ```
        """
        ...

    def unpack_from(self, buffer: Union[bytes, bytearray], offset: int = 0) -> tuple:
        """
        Unpack from *buffer* starting at *offset*.

        :param buffer: Buffer containing packed data.
        :param offset: Byte offset into the buffer.
        :returns: Tuple of unpacked values.

        Example
        -------
        ```python
            >>> s = struct.Struct('<HI')
            >>> s.unpack_from(b'\\x00' * 2 + b'\\x01\\x00\\x02\\x00\\x00\\x00', 2)
            (1, 2)
        ```
        """
        ...

    def iter_unpack(self, buffer: Union[bytes, bytearray]) -> Iterator[tuple]:
        """
        Iteratively unpack from *buffer*.

        :param buffer: Buffer to unpack from.
        :returns: Iterator of tuples.

        Example
        -------
        ```python
            >>> s = struct.Struct('<HH')
            >>> for a, b in s.iter_unpack(b'\\x01\\x00\\x02\\x00\\x03\\x00\\x04\\x00'):
            ...     print(a, b)
        ```
        """
        ...
