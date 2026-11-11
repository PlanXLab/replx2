"""bluetooth - low-level BLE interface.

This module provides direct access to the Bluetooth Low Energy (BLE) stack.
It supports both peripheral (GATT server) and central (GATT client) roles.

Notes
-----
- Availability, feature set, and tuple formats can vary by port and firmware
    build options.
- IRQ callbacks run in a constrained context; keep handlers short and avoid
    allocating large objects. If you need to do substantial work, defer it to
    the scheduler or an `uasyncio` task.
- Many operations are asynchronous: results are delivered via the IRQ handler.

Example
-------
```python
    >>> import bluetooth
    >>> 
    >>> ble = bluetooth.BLE()
    >>> ble.active(True)
    >>> 
    >>> ble.gap_advertise(100_000, b'\\x02\\x01\\x06')
```
"""

from typing import Any, Callable, Optional, Tuple, Union


class UUID:
    """
    Bluetooth UUID.

    Example
    -------
    ```python
        >>> import bluetooth
        >>> 
        >>> # 16-bit
        >>> uuid16 = bluetooth.UUID(0x180F)
        >>> 
        >>> # 128-bit
        >>> uuid128 = bluetooth.UUID("12345678-1234-1234-1234-123456789abc")
    ```
    """

    def __init__(self, value: Union[int, str]) -> None:
        """
        Create UUID.

        :param value: 16/32-bit int or 128-bit string

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> uuid = bluetooth.UUID(0x2A19)
        ```
        """
        ...


class BLE:
    """
    BLE radio interface.

    Example
    -------
    ```python
        >>> import bluetooth
        >>> 
        >>> ble = bluetooth.BLE()
        >>> ble.active(True)
        >>> 
        >>> def handler(event, data):
        ...     if event == 1:  # CENTRAL_CONNECT
        ...         print("Connected!")
        >>> 
        >>> ble.irq(handler)
    ```
    """

    def __init__(self) -> None:
        """Create a BLE interface instance.

        The radio is usually disabled by default. Call `active(True)` to enable.
        """
        ...

    def active(self, active: bool = None) -> Optional[bool]:
        """
        Get or set BLE active state.

        :param active: True to enable

        :returns: Current state if querying

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble = bluetooth.BLE()
            >>> ble.active(True)
            >>> print(ble.active())  # True
        ```
        """
        ...

    def config(self, *args, **kwargs) -> Any:
        """Get or set BLE stack configuration.

        Common keys include (availability varies by port): ``mac``, ``addr_mode``,
        ``gap_name``, ``mtu``, ``bond``, ``mitm``, ``io``, ``le_secure``.

        Some values affect advertising, scanning, or the security manager and may
        only take effect when BLE is inactive.

        :returns: Value if getting

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> mac = ble.config('mac')
            >>> ble.config(gap_name='MyDevice')
        ```
        """
        ...

    def irq(self, handler: Callable[[int, tuple], None]) -> None:
        """Register a global BLE event (IRQ) handler.

        The handler is called as ``handler(event, data)`` where `event` is one
        of the ``_IRQ_*`` constants and `data` is an event-specific tuple.
        Tuple shapes are port dependent, but commonly include connection handles,
        addresses, value handles, and payload bytes.

        Events include (not exhaustive):
        - `_IRQ_CENTRAL_CONNECT`, `_IRQ_CENTRAL_DISCONNECT`
        - `_IRQ_GATTS_WRITE`, `_IRQ_GATTS_READ_REQUEST`
        - `_IRQ_SCAN_RESULT`, `_IRQ_SCAN_DONE`
        - `_IRQ_PERIPHERAL_CONNECT`, `_IRQ_PERIPHERAL_DISCONNECT`
        - `_IRQ_GATTC_*` discovery/read/write/notify/indicate

        Keep this callback fast; defer heavy work.

        :param handler: Callback(event, data)

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> def handler(event, data):
            ...     print(f"Event: {event}")
            >>> 
            >>> ble.irq(handler)
        ```
        """
        ...

    def gap_advertise(
        self,
        interval_us: int,
        adv_data: bytes = None,
        resp_data: bytes = None,
        connectable: bool = True
    ) -> None:
        """Start (or stop) advertising.

        :param interval_us: Advertising interval in microseconds. Some ports use
            ``None`` to stop advertising.
        :param adv_data: Raw advertising payload (up to 31 bytes on many stacks).
        :param resp_data: Optional scan response payload.
        :param connectable: Allow connections

        :raises OSError: If advertising cannot be started.

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> # Start advertising
            >>> adv = b'\\x02\\x01\\x06'  # Flags
            >>> ble.gap_advertise(100_000, adv)
            >>> 
            >>> # Stop advertising
            >>> ble.gap_advertise(None)
        ```
        """
        ...

    def gap_scan(
        self,
        duration_ms: int,
        interval_us: int = 1280000,
        window_us: int = 11250,
        active: bool = False
    ) -> None:
        """Start (or stop) a GAP scan.

        Scan results are delivered via `_IRQ_SCAN_RESULT` and `_IRQ_SCAN_DONE`.

        :param duration_ms: Scan duration. Some ports treat ``0`` as "scan until
            stopped" and ``None`` as "stop scanning".
        :param interval_us: Scan interval
        :param window_us: Scan window
        :param active: Request scan responses

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gap_scan(5000)  # Scan 5 seconds
            >>> ble.gap_scan(None)  # Stop scanning
        ```
        """
        ...

    def gap_connect(
        self,
        addr_type: int,
        addr: bytes,
        scan_duration_ms: int = 2000
    ) -> None:
        """Initiate a connection to a peripheral.

        The connection result is delivered asynchronously via IRQ (typically
        `_IRQ_PERIPHERAL_CONNECT` / `_IRQ_PERIPHERAL_DISCONNECT`).

        :param addr_type: Address type (0=public, 1=random)
        :param addr: 6-byte address
        :param scan_duration_ms: Connection timeout

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gap_connect(0, b'\\xaa\\xbb\\xcc\\xdd\\xee\\xff')
        ```
        """
        ...

    def gap_disconnect(self, conn_handle: int) -> bool:
        """Disconnect an existing connection.

        :param conn_handle: Connection handle

        :returns: True if a disconnect was initiated.

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gap_disconnect(conn_handle)
        ```
        """
        ...

    def gatts_register_services(self, services: tuple) -> tuple:
        """Register local GATT services (GATT server).

        The `services` definition is a nested tuple structure describing service
        UUIDs and characteristic UUIDs/flags. This is intentionally low-level.
        Higher-level helper libraries (e.g. `aioble`) can build on top.

        :param services: Service definitions

        :returns: Tuple of handles

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> UART_UUID = bluetooth.UUID("6E400001...")
            >>> TX_UUID = bluetooth.UUID("6E400002...")
            >>> RX_UUID = bluetooth.UUID("6E400003...")
            >>> 
            >>> services = (
            ...     (UART_UUID, (
            ...         (TX_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY),
            ...         (RX_UUID, bluetooth.FLAG_WRITE),
            ...     )),
            ... )
            >>> handles = ble.gatts_register_services(services)
        ```
        """
        ...

    def gatts_read(self, value_handle: int) -> bytes:
        """
        Read local characteristic value.

        :param value_handle: Value handle

        :returns: Current value

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> value = ble.gatts_read(tx_handle)
        ```
        """
        ...

    def gatts_write(self, value_handle: int, data: bytes, send_update: bool = False) -> None:
        """Update a local characteristic value.

        :param value_handle: Value handle
        :param data: Value to write
        :param send_update: When True, trigger an update to subscribed peers.
            Exact behaviour (notify vs indicate) is port-dependent.

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gatts_write(tx_handle, b'Hello')
        ```
        """
        ...

    def gatts_notify(self, conn_handle: int, value_handle: int, data: bytes = None) -> None:
        """Send a notification to a connected central.

        This is used for characteristics with `FLAG_NOTIFY`.

        :param conn_handle: Connection handle
        :param value_handle: Characteristic handle
        :param data: Data to send

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gatts_notify(conn, tx_handle, b'Update')
        ```
        """
        ...

    def gatts_indicate(self, conn_handle: int, value_handle: int, data: bytes = None) -> None:
        """Send an indication to a connected central.

        Indications are acknowledged by the peer when supported.

        :param conn_handle: Connection handle
        :param value_handle: Characteristic handle
        :param data: Data to send

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gatts_indicate(conn, tx_handle, b'Important')
        ```
        """
        ...

    def gatts_set_buffer(self, value_handle: int, len: int, append: bool = False) -> None:
        """Configure the internal buffer for a characteristic.

        This can be used to tune how incoming writes are buffered (e.g. for a RX
        characteristic in a UART-like service).

        :param value_handle: Value handle
        :param len: Buffer size
        :param append: Append mode

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gatts_set_buffer(rx_handle, 256)
        ```
        """
        ...

    def gattc_discover_services(self, conn_handle: int, uuid: UUID = None) -> None:
        """Discover services on a remote GATT server (GATT client).

        Results are delivered asynchronously via `_IRQ_GATTC_SERVICE_RESULT` and
        `_IRQ_GATTC_SERVICE_DONE`.

        :param conn_handle: Connection handle
        :param uuid: Specific UUID (None for all)

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gattc_discover_services(conn)
        ```
        """
        ...

    def gattc_discover_characteristics(
        self,
        conn_handle: int,
        start_handle: int,
        end_handle: int,
        uuid: UUID = None
    ) -> None:
        """Discover characteristics within a handle range.

        Results are delivered via `_IRQ_GATTC_CHARACTERISTIC_RESULT` and
        `_IRQ_GATTC_CHARACTERISTIC_DONE`.

        :param conn_handle: Connection handle
        :param start_handle: Start of range
        :param end_handle: End of range
        :param uuid: Specific UUID

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gattc_discover_characteristics(conn, svc_start, svc_end)
        ```
        """
        ...

    def gattc_read(self, conn_handle: int, value_handle: int) -> None:
        """Read a remote characteristic value.

        Result is delivered via `_IRQ_GATTC_READ_RESULT` / `_IRQ_GATTC_READ_DONE`.

        :param conn_handle: Connection handle
        :param value_handle: Value handle

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gattc_read(conn, char_handle)
        ```
        """
        ...

    def gattc_write(
        self,
        conn_handle: int,
        value_handle: int,
        data: bytes,
        mode: int = 0
    ) -> None:
        """Write a remote characteristic value.

        Completion is delivered via `_IRQ_GATTC_WRITE_DONE`.

        :param conn_handle: Connection handle
        :param value_handle: Value handle
        :param data: Data to write
        :param mode: 0=without response, 1=with response

        Example
        -------
        ```python
            >>> import bluetooth
            >>> 
            >>> ble.gattc_write(conn, char_handle, b'Hello')
        ```
        """
        ...


# IRQ event constants
_IRQ_CENTRAL_CONNECT: int
"""A central connected to this device (peripheral role).

The `data` tuple typically contains ``(conn_handle, addr_type, addr)``.
"""

_IRQ_CENTRAL_DISCONNECT: int
"""A central disconnected (peripheral role).

The `data` tuple typically contains ``(conn_handle, addr_type, addr)``.
"""

_IRQ_GATTS_WRITE: int
"""A remote client wrote to a local characteristic (GATT server).

The `data` tuple typically contains ``(conn_handle, value_handle)``.
Use `gatts_read(value_handle)` to retrieve the current value.
"""

_IRQ_GATTS_READ_REQUEST: int
"""A remote client requested a read (GATT server).

The `data` tuple often contains ``(conn_handle, value_handle)``. Some ports
use this for access control decisions.
"""

_IRQ_SCAN_RESULT: int
"""A scan result is available (central role).

The `data` tuple typically contains address info, advertising type/RSSI, and
payload bytes. Exact ordering is port-dependent.
"""

_IRQ_SCAN_DONE: int
"""Scanning completed or was stopped."""

_IRQ_PERIPHERAL_CONNECT: int
"""Connected to a peripheral (central role).

The `data` tuple typically contains ``(conn_handle, addr_type, addr)``.
"""

_IRQ_PERIPHERAL_DISCONNECT: int
"""Disconnected from a peripheral (central role)."""

_IRQ_GATTC_SERVICE_RESULT: int
"""A service discovery result.

The `data` tuple usually includes the discovered service's handle range and UUID.
"""

_IRQ_GATTC_SERVICE_DONE: int
"""Service discovery completed."""

_IRQ_GATTC_CHARACTERISTIC_RESULT: int
"""A characteristic discovery result.

The `data` tuple typically includes handles/properties and the characteristic UUID.
"""

_IRQ_GATTC_CHARACTERISTIC_DONE: int
"""Characteristic discovery completed."""

_IRQ_GATTC_READ_RESULT: int
"""A partial/complete read result.

Some stacks may deliver data in multiple chunks; use `_IRQ_GATTC_READ_DONE` to
detect completion.
"""

_IRQ_GATTC_READ_DONE: int
"""Read operation completed."""

_IRQ_GATTC_WRITE_DONE: int
"""Write operation completed."""

_IRQ_GATTC_NOTIFY: int
"""A notification was received from the peer."""

_IRQ_GATTC_INDICATE: int
"""An indication was received from the peer."""

# Characteristic flags
FLAG_READ: int
"""Characteristic is readable."""

FLAG_WRITE: int
"""Characteristic is writable (with response)."""

FLAG_WRITE_NO_RESPONSE: int
"""Characteristic is writable (no response)."""

FLAG_NOTIFY: int
"""Characteristic supports notifications."""

FLAG_INDICATE: int
"""Characteristic supports indications."""
