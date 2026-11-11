"""
ESP-NOW wireless protocol support.

Connection-less wireless communication protocol for ESP32 and ESP8266.

ESP-NOW can operate alongside Wifi (``network.WLAN``), but a WLAN interface
(``IF_STA`` or ``IF_AP``) must be active before messages can be sent/received.

Example
-------
```python
    >>> import network
    >>> import espnow
    >>> 
    >>> # A WLAN interface must be active
    >>> sta = network.WLAN(network.WLAN.IF_STA)
    >>> sta.active(True)
    >>> 
    >>> e = espnow.ESPNow()
    >>> e.active(True)
    >>> peer = b'\\xbb\\xbb\\xbb\\xbb\\xbb\\xbb'
    >>> e.add_peer(peer)
    >>> e.send(peer, "Hello!")
```
"""

from typing import Any, Callable, Optional, Tuple, List, Iterator


# Constants
MAX_DATA_LEN: int = 250
"""Maximum message size in bytes."""

KEY_LEN: int = 16
"""Encryption key length in bytes."""

ADDR_LEN: int = 6
"""MAC address length in bytes."""

MAX_TOTAL_PEER_NUM: int = 20
"""Maximum number of registered peers."""

MAX_ENCRYPT_PEER_NUM: int = 6
"""Maximum number of encrypted peers."""

# Data rate constants (ESP32 only)
RATE_LORA_250K: int
"""Long range mode 250Kbps."""

RATE_LORA_500K: int
"""Long range mode 500Kbps."""

RATE_1M: int
"""1 Mbps data rate."""

RATE_2M: int
"""2 Mbps data rate."""

RATE_5M: int
"""5.5 Mbps data rate."""

RATE_6M: int
"""6 Mbps data rate."""

RATE_11M: int
"""11 Mbps data rate."""

RATE_12M: int
"""12 Mbps data rate."""

RATE_24M: int
"""24 Mbps data rate."""

RATE_54M: int
"""54 Mbps data rate."""


class ESPNow:
    """
    ESP-NOW protocol interface.

    Singleton class for ESP-NOW communication.

    All calls to ``espnow.ESPNow()`` return the same object.

    .. note::
        Some methods are available only on ESP32 (e.g. peer queries) due to
        code-size limits and Espressif API differences.

    Example
    -------
    ```python
        >>> import espnow
        >>> 
        >>> e = espnow.ESPNow()
        >>> e.active(True)
    ```
    """

    # Peer device table (ESP32 only)
    peers_table: dict
    """
    Dict of known peer devices and RSSI values.
    
    Format: {peer: [rssi, time_ms], ...}
    """

    def __init__(self) -> None:
        """
        Get singleton ESPNow instance.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> e = espnow.ESPNow()
        ```
        """
        ...

    def active(self, flag: bool = None) -> Optional[bool]:
        """
        Initialise or de-initialise ESP-NOW.

        :param flag:
            Any value convertible to bool.
            ``True`` prepares software/hardware (allocates buffers and registers
            callbacks). ``False`` de-initialises ESP-NOW and deregisters peers.

        :returns: Current status if flag not provided.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> e = espnow.ESPNow()
            >>> e.active(True)
            >>> print(e.active())  # Query status
        ```
        """
        ...

    def config(self, **kwargs) -> Optional[Any]:
        """
        Set (and on ESP32, get) configuration values.

                Keyword options:
                - ``rxbuf``: receive buffer size in bytes (default 526). Allocated by
                    ``active(True)``; changing it takes effect on next activation.
                - ``timeout_ms``: default receive timeout in ms (default 300000). Values
                    <0 mean “wait forever”.
                - ``rate``: transmission data rate (ESP32 only). This is effectively
                    write-only (ESP-IDF does not provide a query API).

                .. note::
                        The official API also supports ``config('param')`` queries on ESP32.
                        This stub only models the keyword form.

        :returns: ``None`` or the queried value (ESP32 only).

        :raises OSError: If ESP-NOW is not initialised.
        :raises ValueError: On invalid options or values.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> e.config(rxbuf=1024)
            >>> e.config(timeout_ms=5000)
            >>> e.config(rate=espnow.RATE_1M)  # ESP32
            >>> print(e.config('rxbuf'))  # Query (ESP32 only)
        ```
        """
        ...

    def send(self, mac: bytes, msg: bytes, sync: bool = True) -> bool:
        """
        Send a message to a peer (or to all peers on ESP32).

        :param mac:
            Peer MAC address (6 bytes). On ESP32, ``None`` sends to all registered
            peers except broadcast/multicast addresses.
        :param msg: Payload (string or bytes-like) up to ``MAX_DATA_LEN`` bytes.
        :param sync:
            If ``True`` (default), wait for peer response/ack. If ``False``, return
            immediately (responses are discarded).

        .. note::
            On ESP32, the documented API also supports ``send(msg)`` which is
            equivalent to ``send(None, msg, True)``.

        :returns: ``True`` if send succeeds (and for ``sync=True``, all peers respond).

        :raises OSError: For underlying ESP-NOW errors (e.g. NOT_INIT, NOT_FOUND, IF, NO_MEM).
        :raises ValueError: On invalid arguments.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> peer = b'\\xbb\\xbb\\xbb\\xbb\\xbb\\xbb'
            >>> e.send(peer, b'Hello!')
            >>> e.send(None, b'Broadcast')  # ESP32: send to all peers
        ```
        """
        ...

    def recv(self, timeout_ms: int = None) -> Tuple[Optional[bytes], Optional[bytes]]:
        """
        Receive a message.

        :param timeout_ms:
            ``None`` uses ``config(timeout_ms=...)``.
            ``0`` returns immediately.
            ``>0`` waits that many ms.
            ``<0`` waits forever.

        :returns: ``(mac, msg)`` or ``(None, None)`` on timeout.

        :raises OSError: If ESP-NOW is not initialised or WLAN is not active.
        :raises ValueError: On invalid timeout values.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> mac, msg = e.recv()
            >>> if mac:
            ...     print(f"From {mac}: {msg}")
        ```
        """
        ...

    def irecv(self, timeout_ms: int = None) -> Tuple[Optional[bytearray], Optional[bytearray]]:
        """
        Receive a message (allocation-free).

        Reuses internal bytearrays to reduce allocations/fragmentation.

        :param timeout_ms: Timeout in ms (see :meth:`recv`)

        :returns: ``(mac, msg)`` or ``(None, None)`` on timeout.

        .. note::
            On ESP8266, ``mac`` is also a bytearray.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> for mac, msg in e:  # Iteration uses irecv
            ...     print(mac, msg)
        ```
        """
        ...

    def recvinto(self, data: list, timeout_ms: int = None) -> int:
        """
        Low-level receive into provided buffers.

        :param data:
            List with at least two elements: ``[peer, msg]``.
            ``msg`` must be a bytearray large enough for 250 bytes.
            On ESP32, the ``peer`` element will be replaced with a reference to an
            entry in :attr:`peers_table`.

            On ESP32, if ``data`` has at least 4 elements, RSSI and timestamp will be
            stored in elements 3 and 4.

            On ESP8266, ``peer`` should be a 6-byte bytearray to receive the sender MAC.
        :param timeout_ms: Timeout in ms

        :returns: Message length in bytes, or 0 on timeout.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> data = [None, bytearray(250)]
            >>> length = e.recvinto(data)
        ```
        """
        ...

    def any(self) -> bool:
        """
        Check if a message is ready to be read.

        :returns: True if data available

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> if e.any():
            ...     mac, msg = e.recv()
        ```
        """
        ...

    def stats(self) -> Tuple[int, int, int, int, int]:
        """
        Get packet statistics (ESP32 only).

        :returns: (tx_pkts, tx_responses, tx_failures, rx_packets, rx_dropped)

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> tx, resp, fail, rx, drop = e.stats()
        ```
        """
        ...

    def set_pmk(self, pmk: bytes) -> None:
        """
        Set Primary Master Key (PMK) for encrypting peer LMKs.

        :param pmk: 16-byte key (``KEY_LEN``).

        :raises ValueError: On invalid PMK.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> e.set_pmk(b'0123456789abcdef')
        ```
        """
        ...

    def add_peer(
        self,
        mac: bytes,
        lmk: bytes = None,
        channel: int = None,
        ifidx: int = None,
        encrypt: bool = None
    ) -> None:
        """
        Register a peer device.

        :param mac: Peer MAC address (6 bytes).
        :param lmk:
            Local Master Key (LMK) for encryption (16 bytes), or a “falsey” value
            to disable encryption.
        :param channel:
            Wifi channel 0..14. ``0`` means “use current channel”. A non-zero
            value must match the currently configured WLAN channel.
        :param ifidx: Wifi interface index (ESP32 only): 0=STA, 1=AP.
        :param encrypt:
            Whether to encrypt traffic with this peer (ESP32 only). Defaults to
            True if LMK is a valid key.

        :raises OSError: For underlying ESP-NOW errors (e.g. NOT_INIT, EXIST, FULL, CHAN).
        :raises ValueError: On invalid arguments.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> peer = b'\\xbb\\xbb\\xbb\\xbb\\xbb\\xbb'
            >>> e.add_peer(peer)
            >>> e.add_peer(peer, lmk=b'secretkey1234567', encrypt=True)
        ```
        """
        ...

    def del_peer(self, mac: bytes) -> None:
        """
        Deregister a peer.

        :raises OSError: If not initialised or peer not found.
        :raises ValueError: On invalid MAC.

        :param mac: Peer MAC address

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> e.del_peer(peer)
        ```
        """
        ...

    def get_peer(self, mac: bytes) -> Tuple[bytes, bytes, int, int, bool]:
        """
        Get peer information (ESP32 only).

        :raises OSError: If not initialised or peer not found.
        :raises ValueError: On invalid MAC.

        :param mac: Peer MAC address

        :returns: (mac, lmk, channel, ifidx, encrypt)

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> info = e.get_peer(peer)
        ```
        """
        ...

    def peer_count(self) -> Tuple[int, int]:
        """
        Get peer count (ESP32 only).

        :returns: (peer_num, encrypt_num)

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> total, encrypted = e.peer_count()
        ```
        """
        ...

    def get_peers(self) -> Tuple[Tuple, ...]:
        """
        Get all peer info (ESP32 only).

        :returns: Tuple of peer info tuples

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> for peer_info in e.get_peers():
            ...     print(peer_info)
        ```
        """
        ...

    def mod_peer(
        self,
        mac: bytes,
        lmk: bytes = None,
        channel: int = None,
        ifidx: int = None,
        encrypt: bool = None
    ) -> None:
        """
        Modify peer parameters (ESP32 only).

        Any parameter left as ``None`` keeps its current value.

        :param mac: Peer MAC address
        :param lmk: New Local Master Key
        :param channel: New channel
        :param ifidx: New interface
        :param encrypt: New encryption setting

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> e.mod_peer(peer, channel=6)
        ```
        """
        ...

    def irq(self, callback: Callable[['ESPNow'], None]) -> None:
        """
        Set receive callback (ESP32 only).

        The callback is scheduled (not a hard IRQ). It should read out messages
        quickly (often with ``irecv(0)`` in a loop) to avoid buffer overflows.

        :param callback: Function called on message receive

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> def recv_cb(e):
            ...     while True:
            ...         mac, msg = e.irecv(0)
            ...         if mac is None:
            ...             return
            ...         print(mac, msg)
            >>> e.irq(recv_cb)
        ```
        """
        ...

    def __iter__(self) -> Iterator[Tuple[bytes, bytes]]:
        """
        Iterate over incoming messages.

        Example
        -------
        ```python
            >>> import espnow
            >>> 
            >>> for mac, msg in e:
            ...     print(mac, msg)
        ```
        """
        ...

    def __next__(self) -> Tuple[bytes, bytes]:
        """Get next message."""
        ...
