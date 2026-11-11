"""vfs - virtual filesystem helpers.

This module provides filesystem driver classes and a small mounting API.
Most ports expose the same operations through the `os` module (e.g.
`os.mount`, `os.umount`, `os.VfsFat`, `os.VfsLfs2`). Some ports also keep a
separate `vfs` module for compatibility.

Notes
-----
- The concrete block device API is port-specific, but typically provides
    `readblocks`, `writeblocks`, and `ioctl`.
- `mkfs()` formats the underlying block device and will destroy existing data.
- Paths are interpreted by the VFS layer once mounted; relative paths are
    resolved against the current directory (`os.getcwd()` / `Vfs*.getcwd()`).

Example
-------
```python
        >>> import vfs
        >>>
        >>> # Create and mount a filesystem object at a mount point.
        >>> fs = vfs.VfsFat(bdev)
        >>> vfs.mount(fs, '/sd')
```
"""

from typing import Any, Optional, Union


class VfsFat:
    """
    FAT filesystem driver.

    Example
    -------
    ```python
        >>> import vfs
        >>> 
        >>> # Format and mount block device
        >>> vfs.VfsFat.mkfs(bdev)
        >>> fs = vfs.VfsFat(bdev)
        >>> vfs.mount(fs, '/flash')
    ```
    """

    def __init__(self, block_dev: Any) -> None:
        """
        Create FAT filesystem on block device.

        :param block_dev: Block device object

        Example
        -------
        ```python
            >>> import vfs
            >>> 
            >>> fs = vfs.VfsFat(sd_card)
        ```
        """
        ...

    @staticmethod
    def mkfs(block_dev: Any) -> None:
        """
        Format block device with FAT.

        :param block_dev: Block device to format

        Example
        -------
        ```python
            >>> import vfs
            >>> 
            >>> vfs.VfsFat.mkfs(sd_card)
        ```
        """
        ...

    def open(self, path: str, mode: str) -> Any:
        """Open a file on this filesystem.

        This mirrors `open()` from Python, but the exact set of supported modes
        and buffering behaviour is port-dependent.

        :param path: Path within this filesystem.
        :param mode: Mode string such as ``"r"``, ``"w"``, ``"a"``, ``"rb"``.

        :returns: A stream-like object supporting `read`/`write`/`close`.

        :raises OSError: For I/O errors, missing paths, permissions, etc.
        """
        ...

    def ilistdir(self, path: str) -> Any:
        """Iterate directory entries.

        This is the VFS equivalent of `os.ilistdir()`. Entries are typically
        tuples such as ``(name, type, inode[, size])`` but the exact shape is
        port/filesystem dependent.

        :param path: Directory path.
        :returns: An iterator of directory entries.
        """
        ...

    def mkdir(self, path: str) -> None:
        """Create a directory.

        :param path: Directory path.
        :raises OSError: If the directory exists or cannot be created.
        """
        ...

    def rmdir(self, path: str) -> None:
        """Remove an empty directory.

        :param path: Directory path.
        :raises OSError: If directory is not empty or cannot be removed.
        """
        ...

    def stat(self, path: str) -> tuple:
        """Get status for a path.

        The returned tuple matches `os.stat()` / `os.statvfs()` conventions as
        implemented by the port.

        :param path: Path to a file or directory.
        :returns: A stat tuple.
        """
        ...

    def statvfs(self, path: str) -> tuple:
        """Get filesystem statistics.

        :param path: Any path on the mounted filesystem.
        :returns: A statvfs tuple.
        """
        ...

    def remove(self, path: str) -> None:
        """Remove (unlink) a file.

        :param path: File path.
        :raises OSError: If the path does not exist or cannot be removed.
        """
        ...

    def rename(self, old: str, new: str) -> None:
        """Rename a file or directory.

        :param old: Existing path.
        :param new: New path.
        :raises OSError: If the operation fails.
        """
        ...

    def chdir(self, path: str) -> None:
        """Change the current directory for this VFS.

        This affects relative path resolution on this filesystem.
        """
        ...

    def getcwd(self) -> str:
        """Return the current directory for this VFS."""
        ...


class VfsLfs2:
    """
    LittleFS v2 filesystem driver.

    Power-fail safe filesystem for flash.

    Example
    -------
    ```python
        >>> import vfs
        >>> 
        >>> # Format and mount
        >>> vfs.VfsLfs2.mkfs(bdev)
        >>> fs = vfs.VfsLfs2(bdev)
        >>> vfs.mount(fs, '/data')
    ```
    """

    def __init__(
        self,
        block_dev: Any,
        readsize: int = 32,
        progsize: int = 32,
        lookahead: int = 32,
        mtime: bool = True
    ) -> None:
        """
        Create LittleFS filesystem.

        :param block_dev: Block device
        :param readsize: Read size
        :param progsize: Program size
        :param lookahead: Lookahead size
        :param mtime: Track modification time

        Example
        -------
        ```python
            >>> import vfs
            >>> 
            >>> fs = vfs.VfsLfs2(flash)
        ```
        """
        ...

    @staticmethod
    def mkfs(
        block_dev: Any,
        readsize: int = 32,
        progsize: int = 32,
        lookahead: int = 32
    ) -> None:
        """
        Format block device with LittleFS.

        This erases any existing data. Use only on an uninitialized device or
        when you are prepared to lose stored files.

        :param block_dev: Block device
        :param readsize: Read size
        :param progsize: Program size
        :param lookahead: Lookahead size

        Example
        -------
        ```python
            >>> import vfs
            >>> 
            >>> vfs.VfsLfs2.mkfs(flash)
        ```
        """
        ...

    def open(self, path: str, mode: str) -> Any:
        """Open a file on this filesystem.

        :param path: Path within this filesystem.
        :param mode: Mode string such as ``"r"``/``"w"``/``"a"`` and binary
            variants (exact support is port-dependent).
        :returns: A stream-like object.
        """
        ...

    def ilistdir(self, path: str) -> Any:
        """Iterate directory entries (see `VfsFat.ilistdir`)."""
        ...

    def mkdir(self, path: str) -> None:
        """Create a directory."""
        ...

    def rmdir(self, path: str) -> None:
        """Remove an empty directory."""
        ...

    def stat(self, path: str) -> tuple:
        """Get status for a path."""
        ...

    def statvfs(self, path: str) -> tuple:
        """Get filesystem statistics."""
        ...

    def remove(self, path: str) -> None:
        """Remove (unlink) a file."""
        ...

    def rename(self, old: str, new: str) -> None:
        """Rename a file or directory."""
        ...


def mount(fsobj: Any, path: str, *, readonly: bool = False) -> None:
    """Mount a filesystem object at a mount point.

    After mounting, the mounted path becomes available through the global VFS
    (e.g. via `os` functions like `os.listdir('/sd')`).

    :param fsobj: A filesystem object such as `VfsFat` or `VfsLfs2`.
    :param path: Absolute mount point such as ``"/sd"``.
    :param readonly: Request a read-only mount when supported.

    :raises OSError: If mounting fails (invalid device, already mounted, etc.).

    Example
    -------
    ```python
        >>> import vfs
        >>> 
        >>> vfs.mount(vfs.VfsFat(sd), '/sd')
        >>> vfs.mount(vfs.VfsLfs2(flash), '/data', readonly=True)
    ```
    """
    ...


def umount(path: str) -> None:
    """Unmount a previously mounted filesystem.

    :param path: Mount point such as ``"/sd"``.
    :raises OSError: If the mount point does not exist or is busy.

    Example
    -------
    ```python
        >>> import vfs
        >>> 
        >>> vfs.umount('/sd')
    ```
    """
    ...


class AbstractBlockDev:
    """
    Abstract base class for block device drivers.

    To implement a block device, subclass this and override
    ``readblocks()``, ``writeblocks()``, and ``ioctl()``.
    Instances can be passed to ``vfs.mount()`` to create a filesystem.

    Example
    -------
    ```python
        >>> import vfs
        >>> 
        >>> class MyFlash(vfs.AbstractBlockDev):
        ...     def readblocks(self, block, buf, offset=0): ...
        ...     def writeblocks(self, block, buf, offset=0): ...
        ...     def ioctl(self, op, arg): ...
        >>> 
        >>> fs = MyFlash()
        >>> vfs.mount(vfs.VfsLfs2(fs), '/flash')
    ```
    """

    def readblocks(self, block_num: int, buf: bytearray, offset: int = 0) -> None:
        """
        Read blocks from the device into *buf*.

        The first form (no *offset*) reads whole, aligned blocks.
        The second form (with *offset*) allows reading at arbitrary byte
        offsets within a block.

        :param block_num: Starting block index.
        :param buf: Buffer to read into (length must be a multiple of block size
            for the aligned form).
        :param offset: Byte offset within the starting block.

        Example
        -------
        ```python
            >>> buf = bytearray(512)
            >>> dev.readblocks(0, buf)          # aligned, one block
            >>> dev.readblocks(0, buf[:10], 6)  # 10 bytes at offset 6
        ```
        """
        ...

    def writeblocks(self, block_num: int, buf: Union[bytes, bytearray], offset: int = 0) -> None:
        """
        Write *buf* to the device starting at *block_num*.

        The first form (no *offset*) writes whole, aligned blocks and the
        driver must erase before writing if required.
        The second form (with *offset*) writes at an arbitrary byte offset;
        the caller is responsible for erasing via ``ioctl`` first.

        :param block_num: Starting block index.
        :param buf: Data to write.
        :param offset: Byte offset within the starting block.

        Example
        -------
        ```python
            >>> dev.writeblocks(0, b'\\xff' * 512)       # aligned, one block
            >>> dev.writeblocks(0, b'hello', 0)          # 5 bytes at offset 0
        ```
        """
        ...

    def ioctl(self, op: int, arg: int = 0) -> Optional[int]:
        """
        Control the block device and query its parameters.

        *op* values:

        * ``1`` – Initialise the device.
        * ``2`` – Shutdown the device.
        * ``3`` – Sync / flush the device.
        * ``4`` – Return the total number of blocks (required).
        * ``5`` – Return the block size in bytes (``None`` → 512).
        * ``6`` – Erase block *arg* (required by littlefs).

        :param op: Operation code.
        :param arg: Operation argument (block number for op 6, unused otherwise).
        :returns: Integer result for ops 4 and 5; ``None`` or 0 otherwise.

        Example
        -------
        ```python
            >>> dev.ioctl(4, 0)    # total block count
            2048
            >>> dev.ioctl(5, 0)    # block size
            512
            >>> dev.ioctl(6, 10)   # erase block 10
        ```
        """
        ...


def rom_ioctl(op: int, arg: int = 0, length: int = 0, buf: Optional[bytes] = None) -> Any:
    """
    Perform an I/O control operation on the internal ROM/flash device.

    This is a low-level function for querying or operating on the built-in
    read-only memory.  The overloads accepted are:

    * ``rom_ioctl(op)``
    * ``rom_ioctl(op, arg)``
    * ``rom_ioctl(op, arg, length)``
    * ``rom_ioctl(op, arg, offset, buf)``

    :param op: Operation code.
    :param arg: Optional integer argument.
    :param length: Optional length argument.
    :param buf: Optional buffer argument.
    :returns: Result depending on *op*.

    Example
    -------
    ```python
        >>> import vfs
        >>> 
        >>> vfs.rom_ioctl(4)   # query total block count of ROM
    ```
    """
    ...
