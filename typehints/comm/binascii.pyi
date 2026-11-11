"""
Binary-to-text encoding functions.

Convert between binary and ASCII representations.

Example
-------
```python
    >>> import binascii
    >>> 
    >>> # Hex encoding
    >>> data = b'\\x01\\x02\\x03'
    >>> hex_str = binascii.hexlify(data)  # b'010203'
    >>> 
    >>> # Base64 encoding
    >>> b64 = binascii.b2a_base64(b'Hello')
```
"""

from typing import Union


def hexlify(data: Union[bytes, bytearray], sep: Union[str, bytes] = ...) -> bytes:
    """
    Convert binary data to hex representation.

    :param data: Binary data to convert
    :param sep: Separator between bytes (optional)

    :returns: Hex ASCII bytes

    Example
    -------
    ```python
        >>> import binascii
        >>> 
        >>> data = bytes([0x01, 0x02, 0xFF])
        >>> binascii.hexlify(data)  # b'0102ff'
        >>> 
        >>> # With separator
        >>> binascii.hexlify(data, ':')  # b'01:02:ff'
    ```
    """
    ...


def unhexlify(data: Union[str, bytes]) -> bytes:
    """
    Convert hex string to binary.

    :param data: Hex string or bytes

    :returns: Binary data

    Example
    -------
    ```python
        >>> import binascii
        >>> 
        >>> binascii.unhexlify('0102ff')  # b'\\x01\\x02\\xff'
        >>> binascii.unhexlify(b'48454c4c4f')  # b'HELLO'
    ```
    """
    ...


def b2a_base64(data: Union[bytes, bytearray], newline: bool = True) -> bytes:
    """
    Convert binary to base64.

    :param data: Binary data
    :param newline: Append newline (default True)

    :returns: Base64 encoded bytes

    Example
    -------
    ```python
        >>> import binascii
        >>> 
        >>> binascii.b2a_base64(b'Hello')
        ... # b'SGVsbG8=\\n'
        >>> 
        >>> binascii.b2a_base64(b'Hello', newline=False)
        ... # b'SGVsbG8='
    ```
    """
    ...


def a2b_base64(data: Union[str, bytes]) -> bytes:
    """
    Convert base64 to binary.

    :param data: Base64 encoded data

    :returns: Binary data

    Example
    -------
    ```python
        >>> import binascii
        >>> 
        >>> binascii.a2b_base64('SGVsbG8=')  # b'Hello'
    ```
    """
    ...


def crc32(data: Union[bytes, bytearray], value: int = 0) -> int:
    """
    Compute CRC-32 checksum.

    :param data: Data to checksum
    :param value: Initial CRC value (for chaining)

    :returns: 32-bit CRC value

    Example
    -------
    ```python
        >>> import binascii
        >>> 
        >>> crc = binascii.crc32(b'Hello World')
        >>> print(hex(crc))
        >>> 
        >>> # Incremental CRC
        >>> crc = binascii.crc32(b'Hello ')
        >>> crc = binascii.crc32(b'World', crc)
    ```
    """
    ...
