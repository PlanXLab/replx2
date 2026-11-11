"""aioble.l2cap - L2CAP Connection-Oriented Channel (CoC) support.

Provides high-throughput, connection-oriented BLE channels that bypass the
ATT layer. Suitable for bulk data transfer and streaming.

Notes
-----
- Requires an established `DeviceConnection` before opening a channel.
- Only one L2CAP channel per connection is supported (NimBLE limitation).
- Once `accept()` starts listening, the stack listens forever.
- Auto-chunking by MTU is built into `send()`.

Example (Central / client side)
-------
```python
    >>> import aioble
    >>> import aioble.l2cap as l2cap
    >>> import asyncio
    >>> 
    >>> async def main():
    ...     device = aioble.Device(0, bytes.fromhex("aabbccddeeff"))
    ...     async with await device.connect() as conn:
    ...         ch = await conn.l2cap_connect(psm=0x70, mtu=512)
    ...         await ch.send(b"Hello over L2CAP")
    ...         buf = bytearray(512)
    ...         n = await ch.recvinto(buf)
    ...         print(buf[:n])
    ...         await ch.disconnect()
    >>> 
    >>> asyncio.run(main())
```

Example (Peripheral / server side)
-------
```python
    >>> async def server():
    ...     conn = await aioble.advertise(250_000, name="L2CAP-Dev")
    ...     ch = await conn.l2cap_accept(psm=0x70, mtu=512)
    ...     buf = bytearray(512)
    ...     n = await ch.recvinto(buf)
    ...     print(buf[:n])
    ...     await ch.send(b"Acknowledged")
    ...     await ch.disconnect()
```
"""

from typing import Optional


class L2CAPDisconnectedError(Exception):
    """Raised when the channel disconnects during an in-progress operation."""
    ...


class L2CAPConnectionError(Exception):
    """Raised when a connection attempt fails. Argument is the status code."""
    ...


class L2CAPChannel:
    """
    An L2CAP Connection-Oriented Channel.

    Obtained via `connection.l2cap_connect()` (Central) or
    `connection.l2cap_accept()` (Peripheral). Supports context manager usage
    for automatic disconnection.

    Example
    -------
    ```python
        >>> async with await conn.l2cap_connect(psm=0x70, mtu=512) as ch:
        ...     await ch.send(b"data")
        ...     buf = bytearray(512)
        ...     n = await ch.recvinto(buf)
    ```
    """

    our_mtu: int
    """Maximum payload the remote side can send to us."""

    peer_mtu: int
    """Maximum payload we can send to the remote side."""

    async def recvinto(self, buf: bytearray, timeout_ms: Optional[int] = None) -> int:
        """
        Receive data into *buf*.

        Waits until data is available, then copies up to ``len(buf)`` bytes.
        Returns the number of bytes written. If the channel buffer still has
        remaining data after this call, `available()` returns True.

        :param buf: Buffer to receive into
        :param timeout_ms: Timeout in milliseconds (None = wait forever)

        :returns: Number of bytes written to buf

        :raises L2CAPDisconnectedError: If channel disconnects while waiting

        Example
        -------
        ```python
            >>> buf = bytearray(512)
            >>> n = await ch.recvinto(buf, timeout_ms=5000)
            >>> print(buf[:n])
        ```
        """
        ...

    def available(self) -> bool:
        """
        Check synchronously whether received data is waiting in the buffer.

        :returns: True if data is ready

        Example
        -------
        ```python
            >>> if ch.available():
            ...     n = await ch.recvinto(buf)
        ```
        """
        ...

    async def send(
        self,
        buf: bytes,
        timeout_ms: Optional[int] = None,
        chunk_size: Optional[int] = None
    ) -> None:
        """
        Send *buf* over the channel.

        Automatically splits the buffer into chunks no larger than
        ``min(our_mtu * 2, peer_mtu)`` and waits for each chunk to be
        acknowledged before sending the next.

        :param buf: Data to send
        :param timeout_ms: Per-chunk flush timeout (None = wait forever)
        :param chunk_size: Override chunk size (default = peer_mtu)

        :raises L2CAPDisconnectedError: If channel disconnects while sending

        Example
        -------
        ```python
            >>> await ch.send(b"large payload", timeout_ms=10000)
        ```
        """
        ...

    async def flush(self, timeout_ms: Optional[int] = None) -> None:
        """
        Wait until all previously sent data has been acknowledged by the stack.

        :param timeout_ms: Timeout in milliseconds

        :raises L2CAPDisconnectedError: If channel disconnects while flushing

        Example
        -------
        ```python
            >>> await ch.flush(timeout_ms=3000)
        ```
        """
        ...

    async def disconnect(self, timeout_ms: int = 1000) -> None:
        """
        Disconnect the L2CAP channel.

        :param timeout_ms: Timeout waiting for disconnect confirmation

        Example
        -------
        ```python
            >>> await ch.disconnect()
        ```
        """
        ...

    async def disconnected(self, timeout_ms: int = 1000) -> None:
        """
        Wait until the channel is fully disconnected.

        :param timeout_ms: Timeout in milliseconds

        Example
        -------
        ```python
            >>> await ch.disconnected()
        ```
        """
        ...

    async def __aenter__(self) -> 'L2CAPChannel':
        """Context manager entry — returns self."""
        ...

    async def __aexit__(self, exc_type, exc_val, exc_traceback) -> None:
        """Context manager exit — calls disconnect()."""
        ...


async def accept(
    connection: object,
    psm: int,
    mtu: int,
    timeout_ms: Optional[int] = None
) -> L2CAPChannel:
    """
    Listen for an incoming L2CAP CoC connection (Peripheral / server side).

    Starts the BLE stack listening on *psm* (if not already) and waits for
    the remote Central to connect. Note: once listening has started, the stack
    continues listening for the lifetime of the application (NimBLE limitation).

    Prefer calling via ``connection.l2cap_accept(psm, mtu, timeout_ms)``
    rather than calling this directly.

    :param connection: Active `DeviceConnection`
    :param psm: Protocol/Service Multiplexer value (e.g. 0x70)
    :param mtu: Maximum Transmission Unit we advertise to the peer
    :param timeout_ms: How long to wait for an incoming connection

    :returns: Connected `L2CAPChannel`

    :raises ValueError: If connection is not active or already has a channel

    Example
    -------
    ```python
        >>> from aioble.l2cap import accept
        >>> ch = await accept(conn, psm=0x70, mtu=512, timeout_ms=10000)
    ```
    """
    ...


async def connect(
    connection: object,
    psm: int,
    mtu: int,
    timeout_ms: Optional[int] = None
) -> L2CAPChannel:
    """
    Open an L2CAP CoC connection to a Peripheral (Central / client side).

    Prefer calling via ``connection.l2cap_connect(psm, mtu, timeout_ms)``
    rather than calling this directly.

    :param connection: Active `DeviceConnection`
    :param psm: Protocol/Service Multiplexer to connect to
    :param mtu: Maximum Transmission Unit we advertise to the peer
    :param timeout_ms: Connection timeout

    :returns: Connected `L2CAPChannel`

    :raises ValueError: If already in listening mode or connection inactive
    :raises L2CAPConnectionError: If the remote side rejects the connection

    Example
    -------
    ```python
        >>> from aioble.l2cap import connect
        >>> ch = await connect(conn, psm=0x70, mtu=512, timeout_ms=5000)
    ```
    """
    ...
