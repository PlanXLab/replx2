"""
i.MXRT (MIMXRT) specific functions.

This module provides access to flash storage on i.MXRT-based boards
such as Teensy 4.0/4.1 and MIMXRT10xx-EVK boards.

Example
-------
```python
    >>> import mimxrt
    >>> 
    >>> # Access flash storage
    >>> flash = mimxrt.Flash()
    >>> buf = bytearray(4096)
    >>> flash.readblocks(0, buf)
```
"""

from typing import Optional


class Flash:
    """
    Access to built-in flash storage.

    This class gives access to the internal flash memory via the standard
    MicroPython block-device protocol.

    In most cases you should use the mounted filesystem via Python's standard
    file API instead of accessing the block device directly.

    Used by the VfsLfs2 filesystem at boot:
    
    Example
    -------
    ```python
        >>> import vfs
        >>> import mimxrt
        >>> 
        >>> bdev = mimxrt.Flash()
        >>> fs = vfs.VfsLfs2(bdev, progsize=256)
        >>> vfs.mount(fs, "/flash")
    ```
    """

    def __init__(self) -> None:
        """
        Create and return a block device for flash access.

        Returns a singleton object for accessing the internal
        flash storage.

        Example
        -------
        ```python
            >>> import mimxrt
            >>> 
            >>> flash = mimxrt.Flash()
        ```
        """
        ...

    def readblocks(self, block_num: int, buf: bytearray, offset: int = None) -> None:
        """
        Read blocks from flash.

        :param block_num: Starting block number
        :param buf: Buffer to read into
        :param offset: Optional byte offset within block (extended protocol)

        Implements the simple and extended block protocol defined by
        ``vfs.AbstractBlockDev``.

        Example
        -------
        ```python
            >>> import mimxrt
            >>> 
            >>> flash = mimxrt.Flash()
            >>> buf = bytearray(4096)
            >>> flash.readblocks(0, buf)
        ```
        """
        ...

    def writeblocks(self, block_num: int, buf: bytes, offset: int = None) -> None:
        """
        Write blocks to flash.

        When called without offset (simple protocol), the block is
        erased first. When called with offset (extended protocol),
        no erase is performed - requires prior erase operation.

        :param block_num: Starting block number
        :param buf: Data to write
        :param offset: Optional byte offset within block (extended protocol)

        Implements the simple and extended block protocol defined by
        ``vfs.AbstractBlockDev``.

        Example
        -------
        ```python
            >>> import mimxrt
            >>> 
            >>> flash = mimxrt.Flash()
            >>> data = b'\\x00' * 4096
            >>> flash.writeblocks(0, data)
        ```
        """
        ...

    def ioctl(self, cmd: int, arg: int) -> Optional[int]:
        """
        Control flash device.

        Implements the block device protocol defined by ``vfs.AbstractBlockDev``.

        Supported commands:
        - 1 (INIT): Initialize device, returns 0
        - 2 (DEINIT): Deinitialize device, returns 0
        - 3 (SYNC): Sync device, returns 0
        - 4 (BLOCK_COUNT): Get number of blocks
        - 5 (BLOCK_SIZE): Get block size (4096 bytes)
        - 6 (BLOCK_ERASE): Erase block at arg

        :param cmd: Control command
        :param arg: Command argument

        :returns: Command result or None

        Example
        -------
        ```python
            >>> import mimxrt
            >>> 
            >>> flash = mimxrt.Flash()
            >>> blocks = flash.ioctl(4, 0)  # Get block count
            >>> size = flash.ioctl(5, 0)    # Get block size
        ```
        """
        ...


# USB Mass Storage support flag
# Only present if compiled with MICROPY_HW_USB_MSC=1
MSC: bool
"""True if USB Mass Storage is supported (compile-time option)."""
