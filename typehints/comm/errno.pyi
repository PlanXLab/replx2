"""
System error numbers.

Standard POSIX error codes.

Example
-------
```python
    >>> import errno
    >>> 
    >>> try:
    ...     open('/nonexistent')
    >>> except OSError as e:
    ...     if e.errno == errno.ENOENT:
    ...         print("File not found")
```
"""


# Error constants
ENOENT: int
"""No such file or directory."""

EIO: int
"""I/O error."""

EBADF: int
"""Bad file descriptor."""

EAGAIN: int
"""Resource temporarily unavailable."""

ENOMEM: int
"""Out of memory."""

EACCES: int
"""Permission denied."""

EEXIST: int
"""File exists."""

ENODEV: int
"""No such device."""

ENOTDIR: int
"""Not a directory."""

EISDIR: int
"""Is a directory."""

EINVAL: int
"""Invalid argument."""

ENOSPC: int
"""No space left on device."""

ECONNABORTED: int
"""Connection aborted."""

ECONNRESET: int
"""Connection reset by peer."""

ENOBUFS: int
"""No buffer space available."""

ENOTCONN: int
"""Not connected."""

ETIMEDOUT: int
"""Connection timed out."""

ECONNREFUSED: int
"""Connection refused."""

EHOSTUNREACH: int
"""Host unreachable."""

EALREADY: int
"""Operation already in progress."""

EINPROGRESS: int
"""Operation in progress."""


# Error name dictionary
errorcode: dict[int, str]
"""Mapping of error numbers to names.

Example
-------
```python
    >>> import errno
    >>> 
    >>> errno.errorcode[errno.ENOENT]  # 'ENOENT'
```
"""
