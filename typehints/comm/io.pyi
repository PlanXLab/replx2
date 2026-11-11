"""
I/O streams and file operations.

Provides stream classes and buffer operations.

Example
-------
```python
    >>> import io
    >>> 
    >>> # In-memory text buffer
    >>> buf = io.StringIO()
    >>> buf.write('Hello')
    >>> text = buf.getvalue()
    >>> 
    >>> # Binary buffer
    >>> bbuf = io.BytesIO(b'\\x01\\x02\\x03')
    >>> data = bbuf.read()
```
"""

from typing import Optional, Union


class StringIO:
    """
    In-memory text stream.

    Example
    -------
    ```python
        >>> import io
        >>> 
        >>> buf = io.StringIO()
        >>> buf.write('Hello, ')
        >>> buf.write('World!')
        >>> print(buf.getvalue())  # 'Hello, World!'
        >>> 
        >>> # Initialize with content
        >>> buf = io.StringIO('Initial text')
        >>> buf.read()  # 'Initial text'
    ```
    """

    def __init__(self, string: str = '') -> None:
        """
        Create StringIO buffer.

        :param string: Initial content

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.StringIO()
            >>> buf = io.StringIO('Hello')
        ```
        """
        ...

    def read(self, size: int = -1) -> str:
        """
        Read from buffer.

        :param size: Max characters (-1 for all)

        :returns: String data

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.StringIO('Hello World')
            >>> buf.read(5)   # 'Hello'
            >>> buf.read()    # ' World'
        ```
        """
        ...

    def readline(self) -> str:
        """
        Read one line.

        :returns: Line including newline

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.StringIO('Line1\\nLine2\\n')
            >>> buf.readline()  # 'Line1\\n'
        ```
        """
        ...

    def write(self, s: str) -> int:
        """
        Write string to buffer.

        :param s: String to write

        :returns: Number of characters written

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.StringIO()
            >>> buf.write('Hello')  # 5
        ```
        """
        ...

    def getvalue(self) -> str:
        """
        Get entire buffer content.

        :returns: Buffer content as string

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.StringIO()
            >>> buf.write('Test')
            >>> buf.getvalue()  # 'Test'
        ```
        """
        ...

    def seek(self, pos: int, whence: int = 0) -> int:
        """
        Move to position in buffer.

        :param pos: Position offset
        :param whence: 0=start, 1=current, 2=end

        :returns: New position

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.StringIO('Hello')
            >>> buf.seek(0)      # Back to start
            >>> buf.read()       # 'Hello'
        ```
        """
        ...

    def tell(self) -> int:
        """
        Get current position.

        :returns: Current position

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.StringIO('Hello')
            >>> buf.read(2)
            >>> buf.tell()  # 2
        ```
        """
        ...

    def close(self) -> None:
        """Close the buffer."""
        ...


class BytesIO:
    """
    In-memory binary stream.

    Example
    -------
    ```python
        >>> import io
        >>> 
        >>> buf = io.BytesIO()
        >>> buf.write(b'\\x01\\x02\\x03')
        >>> buf.seek(0)
        >>> data = buf.read()  # b'\\x01\\x02\\x03'
    ```
    """

    def __init__(self, initial_bytes: bytes = b'') -> None:
        """
        Create BytesIO buffer.

        :param initial_bytes: Initial content

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.BytesIO()
            >>> buf = io.BytesIO(b'Hello')
        ```
        """
        ...

    def read(self, size: int = -1) -> bytes:
        """
        Read from buffer.

        :param size: Max bytes (-1 for all)

        :returns: Bytes data

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.BytesIO(b'Hello')
            >>> buf.read(2)  # b'He'
            >>> buf.read()   # b'llo'
        ```
        """
        ...

    def readinto(self, b: bytearray) -> int:
        """
        Read into pre-allocated buffer.

        :param b: Target buffer

        :returns: Number of bytes read

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.BytesIO(b'Hello')
            >>> dest = bytearray(3)
            >>> buf.readinto(dest)  # 3
            >>> dest  # bytearray(b'Hel')
        ```
        """
        ...

    def readline(self) -> bytes:
        """
        Read one line.

        :returns: Line including newline

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.BytesIO(b'Line1\\nLine2\\n')
            >>> buf.readline()  # b'Line1\\n'
        ```
        """
        ...

    def write(self, b: Union[bytes, bytearray]) -> int:
        """
        Write bytes to buffer.

        :param b: Bytes to write

        :returns: Number of bytes written

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.BytesIO()
            >>> buf.write(b'Test')  # 4
        ```
        """
        ...

    def getvalue(self) -> bytes:
        """
        Get entire buffer content.

        :returns: Buffer content as bytes

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.BytesIO()
            >>> buf.write(b'Test')
            >>> buf.getvalue()  # b'Test'
        ```
        """
        ...

    def seek(self, pos: int, whence: int = 0) -> int:
        """
        Move to position in buffer.

        :param pos: Position offset
        :param whence: 0=start, 1=current, 2=end

        :returns: New position

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.BytesIO(b'Hello')
            >>> buf.seek(0)      # Back to start
            >>> buf.read()       # b'Hello'
        ```
        """
        ...

    def tell(self) -> int:
        """
        Get current position.

        :returns: Current position

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> buf = io.BytesIO(b'Hello')
            >>> buf.read(2)
            >>> buf.tell()  # 2
        ```
        """
        ...

    def close(self) -> None:
        """Close the buffer."""
        ...


class FileIO:
    """
    Raw file I/O.

    Low-level file operations.

    Example
    -------
    ```python
        >>> import io
        >>> 
        >>> f = io.FileIO('/data.bin', 'rb')
        >>> data = f.read()
        >>> f.close()
    ```
    """

    def __init__(self, name: str, mode: str = 'r') -> None:
        """
        Open file.

        :param name: File path
        :param mode: Open mode (r, w, rb, wb, etc.)

        Example
        -------
        ```python
            >>> import io
            >>> 
            >>> f = io.FileIO('/data.bin', 'wb')
        ```
        """
        ...

    def read(self, size: int = -1) -> bytes:
        """Read bytes from file."""
        ...

    def readinto(self, b: bytearray) -> int:
        """Read into buffer."""
        ...

    def write(self, b: Union[bytes, bytearray]) -> int:
        """Write bytes to file."""
        ...

    def seek(self, pos: int, whence: int = 0) -> int:
        """Seek to position."""
        ...

    def tell(self) -> int:
        """Get current position."""
        ...

    def flush(self) -> None:
        """Flush write buffers."""
        ...

    def close(self) -> None:
        """Close file."""
        ...


def open(name: str, mode: str = 'r', **kwargs) -> Union[FileIO, StringIO, BytesIO]:
    """
    Open a file.

    :param name: File path
    :param mode: Open mode

    :returns: File object

    Example
    -------
    ```python
        >>> import io
        >>> 
        >>> f = io.open('/test.txt', 'r')
        >>> content = f.read()
        >>> f.close()
    ```
    """
    ...
