"""
Asyncio support for ESP-NOW.

Provides async methods for ESP-NOW communication.

Example
-------
```python
    >>> import network
    >>> import aioespnow
    >>> import asyncio
    >>> 
    >>> network.WLAN(network.WLAN.IF_STA).active(True)
    >>> 
    >>> e = aioespnow.AIOESPNow()
    >>> e.active(True)
    >>> 
    >>> async def main():
    ...     peer = b'\\xbb\\xbb\\xbb\\xbb\\xbb\\xbb'
    ...     e.add_peer(peer)
    ...     await e.asend(peer, b'Hello!')
    >>> 
    >>> asyncio.run(main())
```
"""

from typing import Any, Optional, Tuple, AsyncIterator
from espnow import ESPNow


class AIOESPNow(ESPNow):
    """
    Async ESP-NOW interface.

    Inherits all methods from :class:`espnow.ESPNow` and adds async support.

    .. note::
        The async receive helpers do not take a timeout argument.

    Example
    -------
    ```python
        >>> import aioespnow
        >>> 
        >>> e = aioespnow.AIOESPNow()
        >>> e.active(True)
    ```
    """

    async def arecv(self) -> Tuple[Optional[bytes], Optional[bytes]]:
        """
        Async receive message.

        Asyncio equivalent of ``ESPNow.recv()``.

        :returns: (mac, msg) tuple

        Example
        -------
        ```python
            >>> import aioespnow
            >>> import asyncio
            >>> 
            >>> async def receiver(e):
            ...     mac, msg = await e.arecv()
            ...     print(f"From {mac}: {msg}")
        ```
        """
        ...

    async def airecv(self) -> Tuple[Optional[bytearray], Optional[bytearray]]:
        """
        Async receive message (allocation-free).

        Asyncio equivalent of ``ESPNow.irecv()``.

        :returns: (mac, msg) tuple

        Example
        -------
        ```python
            >>> import aioespnow
            >>> import asyncio
            >>> 
            >>> async def receiver(e):
            ...     mac, msg = await e.airecv()
            ...     print(f"From {mac}: {msg}")
        ```
        """
        ...

    async def asend(self, mac: bytes, msg: bytes, sync: bool = True) -> bool:
        """
        Async send message.

        Asyncio equivalent of ``ESPNow.send()``.

        :param mac: Peer MAC address or None for all peers
        :param msg: Message to send
        :param sync: Wait for response

        :returns: True if successful

        Example
        -------
        ```python
            >>> import aioespnow
            >>> import asyncio
            >>> 
            >>> async def sender(e, peer):
            ...     await e.asend(peer, b'Hello!')
        ```
        """
        ...

    def __aiter__(self) -> AsyncIterator[Tuple[bytes, bytes]]:
        """
        Async iterate over messages.

        Example
        -------
        ```python
            >>> import aioespnow
            >>> import asyncio
            >>> 
            >>> async def receiver(e):
            ...     async for mac, msg in e:
            ...         print(mac, msg)
            ...         if msg == b'halt':
            ...             break
        ```
        """
        ...

    async def __anext__(self) -> Tuple[bytes, bytes]:
        """Get next message asynchronously."""
        ...
