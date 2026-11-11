"""
Operating system interface for MicroPython.

Provides filesystem operations and system information.

This is a MicroPython subset of CPython's ``os`` module, focused on embedded
filesystems. Available functions and the exact semantics depend on the port and
the configured VFS (e.g. FAT, LittleFS).

Example
-------
```python
    >>> import os
    >>> 
    >>> # List files
    >>> files = os.listdir('/')
    >>> print(files)
    >>> 
    >>> # Create directory
    >>> os.mkdir('/data')
    >>> 
    >>> # Get filesystem info
    >>> stat = os.statvfs('/')
    >>> free = stat[0] * stat[3]
```
"""

from typing import Iterator, Optional, Union


def listdir(dir: str = '.') -> list[str]:
    """
    List directory contents.

    :param dir: Directory path (default: current directory)

    :returns: List of filenames (without path)

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> files = os.listdir('/')
        >>> files = os.listdir('/lib')
        >>> 
        >>> for f in os.listdir():
        ...     print(f)
    ```
    """
    ...


def ilistdir(dir: str = '.') -> Iterator[tuple]:
    """
    Return an iterator of directory entries.

    Memory-efficient alternative to listdir().

    The yielded tuple format is VFS dependent, but commonly includes at least
    a name and a type. Do not rely on platform-specific ``type`` constants
    unless you control the target port.

    :param dir: Directory path

    :returns: Iterator yielding (name, type, inode, size) tuples

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> for name, type_, inode, size in os.ilistdir('/'):
        ...     kind = 'dir' if type_ == 0x4000 else 'file'
        ...     print(f"{name}: {kind}, {size} bytes")
    ```
    """
    ...


def mkdir(path: str) -> None:
    """
    Create a directory.

    :param path: Directory path to create

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> os.mkdir('/data')
        >>> os.mkdir('/data/logs')
    ```
    """
    ...


def rmdir(path: str) -> None:
    """
    Remove an empty directory.

    :param path: Directory path to remove

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> os.rmdir('/data/logs')
    ```
    """
    ...


def remove(path: str) -> None:
    """
    Remove a file.

    :param path: File path to remove

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> os.remove('/data/old.txt')
    ```
    """
    ...


def rename(old_path: str, new_path: str) -> None:
    """
    Rename a file or directory.

    :param old_path: Current path
    :param new_path: New path

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> os.rename('/old.txt', '/new.txt')
        >>> os.rename('/data', '/backup')
    ```
    """
    ...


def stat(path: str) -> tuple:
    """
    Get file or directory status.

    :param path: Path to check

    :returns: Tuple (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime)

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> st = os.stat('/main.py')
        >>> size = st[6]
        >>> print(f"Size: {size} bytes")
    ```
    """
    ...


def statvfs(path: str) -> tuple:
    """
    Get filesystem statistics.

    The return value matches the POSIX-like ``statvfs`` layout used by
    MicroPython VFS implementations. Fields are integers.

    :param path: Path on filesystem to check

    :returns: Tuple (bsize, frsize, blocks, bfree, bavail, files, ffree, favail, flag, namemax)

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> st = os.statvfs('/')
        >>> block_size = st[0]
        >>> total_blocks = st[2]
        >>> free_blocks = st[3]
        >>> 
        >>> total = block_size * total_blocks
        >>> free = block_size * free_blocks
        >>> print(f"Free: {free // 1024} KB")
    ```
    """
    ...


def getcwd() -> str:
    """
    Get current working directory.

    :returns: Current directory path

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> cwd = os.getcwd()
        >>> print(cwd)
    ```
    """
    ...


def chdir(path: str) -> None:
    """
    Change current working directory.

    :param path: New directory path

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> os.chdir('/lib')
        >>> print(os.getcwd())  # '/lib'
    ```
    """
    ...


def sync() -> None:
    """
    Sync all filesystems.

    Ensures all pending writes are flushed to storage.

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> # After writing important data
        >>> os.sync()
    ```
    """
    ...


def uname() -> tuple:
    """
    Get system information.

    The returned object is a tuple-like structure with attribute access on many
    ports (e.g. ``info.release``, ``info.machine``).

    :returns: Tuple (sysname, nodename, release, version, machine)

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> info = os.uname()
        >>> print(info.machine)    # e.g., 'Raspberry Pi Pico 2'
        >>> print(info.release)    # e.g., '1.24.0'
    ```
    """
    ...


def urandom(n: int) -> bytes:
    """
    Generate n random bytes.

    Uses hardware random number generator if available.

    :param n: Number of random bytes

    :returns: Random bytes

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> key = os.urandom(16)
        >>> print(key.hex())
    ```
    """
    ...


def dupterm(stream: Optional[object], index: int = 0) -> Optional[object]:
    """
    Duplicate or set terminal stream.

    This is commonly used to redirect or duplicate the REPL over UART, USB, or
    another stream. Passing ``stream=None`` can be used to query the current
    stream or disable duplication (port dependent).

    :param stream: Stream object (or None to get current)
    :param index: Terminal index (0 or 1)

    :returns: Previous stream if setting

    Example
    -------
    ```python
        >>> import os
        >>> from machine import UART
        >>> 
        >>> uart = UART(0, 115200)
        >>> os.dupterm(uart)  # Duplicate REPL to UART
    ```
    """
    ...


# VFS mount operations
def mount(fsobj: object, mount_point: str, *, readonly: bool = False) -> None:
    """
    Mount a filesystem object.

    ``fsobj`` is usually a VFS instance or a block device wrapped by a VFS
    class. Available VFS types are port dependent.

    :param fsobj: Filesystem object (VfsFat, VfsLfs2, etc.)
    :param mount_point: Mount point path
    :param readonly: Mount as read-only

    Example
    -------
    ```python
        >>> import os
        >>> from machine import SDCard
        >>> 
        >>> sd = SDCard()
        >>> os.mount(sd, '/sd')
    ```
    """
    ...


def umount(mount_point: str) -> None:
    """
    Unmount a filesystem.

    Open files under the mount point may prevent unmounting (port dependent).

    :param mount_point: Mount point path

    Example
    -------
    ```python
        >>> import os
        >>> 
        >>> os.umount('/sd')
    ```
    """
    ...


# Path separator
sep: str
"""Path separator ('/')."""
