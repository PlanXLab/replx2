"""deflate - DEFLATE/zlib/gzip compression.

This module provides streaming compression/decompression via `DeflateIO`.

Notes
-----
- Intended for use with stream-like objects (files, sockets, `io.BytesIO`).
- Memory usage depends on `wbits` and the implementation.
- If you wrap a stream, consider `close=True` to close the underlying stream
    when `DeflateIO` closes (where supported).

Example
-------
```python
    >>> import deflate
    >>> import io
    >>> 
    >>> # Compress data
    >>> compressed = io.BytesIO()
    >>> with deflate.DeflateIO(compressed, deflate.ZLIB) as d:
    ...     d.write(b'Hello World' * 100)
    >>> 
    >>> # Decompress
    >>> compressed.seek(0)
    >>> with deflate.DeflateIO(compressed, deflate.ZLIB) as d:
    ...     data = d.read()
```
"""

from typing import Optional, Union


# Format constants
RAW: int
"""Raw DEFLATE format.

No zlib/gzip header/trailer. Suitable when you control both ends.
"""

ZLIB: int
"""ZLIB format (zlib header/trailer)."""

GZIP: int
"""GZIP format (gzip header/trailer)."""


class DeflateIO:
    """
    Compression/decompression stream wrapper.

    Example
    -------
    ```python
        >>> import deflate
        >>> import io
        >>> 
        >>> # Compress to BytesIO
        >>> buf = io.BytesIO()
        >>> with deflate.DeflateIO(buf, deflate.ZLIB) as d:
        ...     d.write(b'Data to compress')
        >>> 
        >>> # Read compressed data
        >>> compressed = buf.getvalue()
    ```
    """

    def __init__(
        self,
        stream: object,
        format: int = RAW,
        wbits: int = 0,
        close: bool = False
    ) -> None:
        """
        Create compression/decompression stream.

        :param stream: Underlying stream
        :param format: RAW, ZLIB, or GZIP
        :param wbits: Window size (8-15, negative for raw)
        :param close: Close underlying stream on close

        Example
        -------
        ```python
            >>> import deflate
            >>> import io
            >>> 
            >>> buf = io.BytesIO()
            >>> d = deflate.DeflateIO(buf, deflate.GZIP)
        ```
        """
        ...

    def read(self, size: int = -1) -> bytes:
        """
        Read and decompress.

        :param size: Max bytes to read

        :returns: Decompressed data

        Example
        -------
        ```python
            >>> import deflate
            >>> 
            >>> data = d.read(1024)
        ```
        """
        ...

    def readinto(self, buf: bytearray) -> int:
        """
        Read into buffer.

        :param buf: Target buffer

        :returns: Bytes read

        Example
        -------
        ```python
            >>> import deflate
            >>> 
            >>> buf = bytearray(1024)
            >>> n = d.readinto(buf)
        ```
        """
        ...

    def readline(self) -> bytes:
        """
        Read one line.

        :returns: Line data

        Example
        -------
        ```python
            >>> import deflate
            >>> 
            >>> line = d.readline()
        ```
        """
        ...

    def write(self, data: Union[bytes, bytearray]) -> int:
        """
        Compress and write.

        :param data: Data to compress

        :returns: Bytes written (uncompressed)

        Example
        -------
        ```python
            >>> import deflate
            >>> 
            >>> d.write(b'Hello World')
        ```
        """
        ...

    def close(self) -> None:
        """
        Finish compression and close.

        Example
        -------
        ```python
            >>> import deflate
            >>> 
            >>> d.close()
        ```
        """
        ...

    def __enter__(self) -> 'DeflateIO':
        """Context manager entry."""
        ...

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        ...
