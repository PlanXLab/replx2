"""
Secure hash algorithms.

Generate cryptographic hash digests.

Example
-------
```python
    >>> import hashlib
    >>> 
    >>> # SHA-256 hash
    >>> h = hashlib.sha256()
    >>> h.update(b'Hello')
    >>> h.update(b' World')
    >>> digest = h.digest()
    >>> print(digest.hex())
```
"""

from typing import Union


class sha256:
    """
    SHA-256 hash object.

    Example
    -------
    ```python
        >>> import hashlib
        >>> 
        >>> h = hashlib.sha256()
        >>> h.update(b'Hello World')
        >>> digest = h.digest()
        >>> print(digest.hex())
        >>> 
        >>> # One-shot
        >>> h = hashlib.sha256(b'Hello World')
        >>> print(h.digest().hex())
    ```
    """

    def __init__(self, data: bytes = None) -> None:
        """
        Create SHA-256 hash object.

        :param data: Initial data to hash

        Example
        -------
        ```python
            >>> import hashlib
            >>> 
            >>> h = hashlib.sha256()
            >>> h = hashlib.sha256(b'Initial data')
        ```
        """
        ...

    def update(self, data: Union[bytes, bytearray]) -> None:
        """
        Add data to hash.

        :param data: Data to hash

        Example
        -------
        ```python
            >>> import hashlib
            >>> 
            >>> h = hashlib.sha256()
            >>> h.update(b'Part 1')
            >>> h.update(b'Part 2')
        ```
        """
        ...

    def digest(self) -> bytes:
        """
        Get hash digest.

        :returns: 32-byte hash

        Example
        -------
        ```python
            >>> import hashlib
            >>> 
            >>> h = hashlib.sha256(b'Hello')
            >>> digest = h.digest()  # 32 bytes
        ```
        """
        ...

    def hexdigest(self) -> str:
        """
        Get hex-encoded digest.

        :returns: 64-character hex string

        Example
        -------
        ```python
            >>> import hashlib
            >>> 
            >>> h = hashlib.sha256(b'Hello')
            >>> print(h.hexdigest())
        ```
        """
        ...

    def copy(self) -> 'sha256':
        """
        Copy hash state.

        :returns: New hash object

        Example
        -------
        ```python
            >>> import hashlib
            >>> 
            >>> h = hashlib.sha256(b'Start')
            >>> h2 = h.copy()
            >>> h.update(b'A')
            >>> h2.update(b'B')
        ```
        """
        ...


class sha1:
    """
    SHA-1 hash object.

    Note: SHA-1 is deprecated for security applications.

    Example
    -------
    ```python
        >>> import hashlib
        >>> 
        >>> h = hashlib.sha1()
        >>> h.update(b'Hello World')
        >>> print(h.hexdigest())
    ```
    """

    def __init__(self, data: bytes = None) -> None:
        """Create SHA-1 hash object."""
        ...

    def update(self, data: Union[bytes, bytearray]) -> None:
        """Add data to hash."""
        ...

    def digest(self) -> bytes:
        """Get 20-byte digest."""
        ...

    def hexdigest(self) -> str:
        """Get hex digest."""
        ...

    def copy(self) -> 'sha1':
        """Copy hash state."""
        ...


class md5:
    """
    MD5 hash object.

    Note: MD5 is deprecated for security applications.

    Example
    -------
    ```python
        >>> import hashlib
        >>> 
        >>> h = hashlib.md5()
        >>> h.update(b'Hello World')
        >>> print(h.hexdigest())
    ```
    """

    def __init__(self, data: bytes = None) -> None:
        """Create MD5 hash object."""
        ...

    def update(self, data: Union[bytes, bytearray]) -> None:
        """Add data to hash."""
        ...

    def digest(self) -> bytes:
        """Get 16-byte digest."""
        ...

    def hexdigest(self) -> str:
        """Get hex digest."""
        ...

    def copy(self) -> 'md5':
        """Copy hash state."""
        ...
