"""aioble - high-level asynchronous BLE library.

`aioble` provides a higher-level, `uasyncio`-friendly API over the low-level
`bluetooth` module. It supports peripheral and central roles depending on the
port.

Notes
-----
- BLE operations are inherently asynchronous; most results arrive via events.
- Resource management matters on MicroPython: always close/release connections
    when finished.
- Cancellation/timeouts are normal patterns; be prepared to handle task
    cancellation and `TimeoutError`/`OSError` where applicable.

Example
-------
```python
    >>> import aioble
    >>> import asyncio
    >>> 
    >>> # BLE peripheral (server)
    >>> service = aioble.Service(aioble.UUID(0x181A))
    >>> char = aioble.Characteristic(service, aioble.UUID(0x2A6E), read=True, notify=True)
    >>> aioble.register_services(service)
    >>> 
    >>> async def advertise():
    ...     while True:
    ...         async with await aioble.advertise(
    ...             250_000,  # 250ms interval
    ...             name="MyDevice",
    ...             services=[service.uuid]
    ...         ) as connection:
    ...             print("Connected!")
    ...             await connection.disconnected()
```
"""

from typing import Any, Optional, Union

from .central import *
from .core import *
from .device import *
from .peripheral import *
from .server import *
from .client import *


class UUID:
    """
    Bluetooth UUID.

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> # 16-bit UUID
        >>> uuid16 = aioble.UUID(0x181A)
        >>> 
        >>> # 128-bit UUID
        >>> uuid128 = aioble.UUID("12345678-1234-1234-1234-123456789abc")
    ```
    """

    def __init__(self, value: Union[int, str, bytes]) -> None:
        """
        Create UUID.

        :param value: 16-bit int, UUID string, or 16-byte bytes

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> uuid = aioble.UUID(0x180F)  # Battery Service
            >>> uuid = aioble.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
        ```
        """
        ...


class Service:
    """
    GATT Service definition.

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> # Environmental Sensing Service
        >>> service = aioble.Service(aioble.UUID(0x181A))
        >>> temp_char = aioble.Characteristic(
        ...     service,
        ...     aioble.UUID(0x2A6E),
        ...     read=True, notify=True
        ... )
    ```
    """

    uuid: UUID
    """Service UUID."""

    def __init__(self, uuid: UUID, secondary: bool = False) -> None:
        """
        Create service.

        :param uuid: Service UUID
        :param secondary: Is secondary service

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> service = aioble.Service(aioble.UUID(0x181A))
        ```
        """
        ...


class Characteristic:
    """
    GATT Characteristic definition.

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> char = aioble.Characteristic(
        ...     service,
        ...     aioble.UUID(0x2A6E),
        ...     read=True,
        ...     notify=True
        ... )
        >>> 
        >>> # Set value
        >>> char.write(struct.pack('<h', temp * 100))
        >>> 
        >>> # Notify connected clients
        >>> char.notify(connection, data)
    ```
    """

    uuid: UUID
    """Characteristic UUID."""

    def __init__(
        self,
        service: Service,
        uuid: UUID,
        *,
        read: bool = False,
        write: bool = False,
        write_no_response: bool = False,
        notify: bool = False,
        indicate: bool = False,
        capture: bool = False
    ) -> None:
        """
        Create characteristic.

        :param service: Parent service
        :param uuid: Characteristic UUID
        :param read: Allow read
        :param write: Allow write with response
        :param write_no_response: Allow write without response
        :param notify: Allow notifications
        :param indicate: Allow indications
        :param capture: Capture writes to queue

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> char = aioble.Characteristic(
            ...     service,
            ...     aioble.UUID(0x2A6E),
            ...     read=True,
            ...     write=True,
            ...     notify=True
            ... )
        ```
        """
        ...

    def read(self) -> bytes:
        """
        Read characteristic value.

        :returns: Current value

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> value = char.read()
        ```
        """
        ...

    def write(self, data: bytes, send_update: bool = False) -> None:
        """
        Write characteristic value.

        :param data: Value to write
        :param send_update: Notify/indicate subscribers

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> char.write(b'\\x01\\x02\\x03')
            >>> char.write(data, send_update=True)
        ```
        """
        ...

    def notify(self, connection: 'DeviceConnection', data: bytes = None) -> None:
        """
        Send notification to client.

        :param connection: Client connection
        :param data: Data to send (None = current value)

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> char.notify(conn, new_data)
        ```
        """
        ...

    def indicate(self, connection: 'DeviceConnection', data: bytes = None) -> None:
        """
        Send indication to client.

        :param connection: Client connection
        :param data: Data to send

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> char.indicate(conn, data)
        ```
        """
        ...

    async def written(self, timeout_ms: int = None) -> 'DeviceConnection':
        """
        Wait for write from client.

        :param timeout_ms: Timeout in milliseconds

        :returns: Connection that wrote

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> conn = await char.written()
            >>> value = char.read()
        ```
        """
        ...


class Descriptor:
    """
    GATT Descriptor.

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> desc = aioble.Descriptor(
        ...     char,
        ...     aioble.UUID(0x2901),  # User Description
        ...     read=True
        ... )
        >>> desc.write(b"Temperature Sensor")
    ```
    """

    def __init__(
        self,
        characteristic: Characteristic,
        uuid: UUID,
        *,
        read: bool = False,
        write: bool = False
    ) -> None:
        """
        Create descriptor.

        :param characteristic: Parent characteristic
        :param uuid: Descriptor UUID
        :param read: Allow read
        :param write: Allow write

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> desc = aioble.Descriptor(char, aioble.UUID(0x2901), read=True)
        ```
        """
        ...

    def read(self) -> bytes:
        """Read descriptor value."""
        ...

    def write(self, data: bytes) -> None:
        """Write descriptor value."""
        ...


class DeviceConnection:
    """
    Connection to remote BLE device.

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> async with await aioble.advertise(250_000, name="Dev") as conn:
        ...     print(f"Connected: {conn.device}")
        ...     await conn.disconnected()
    ```
    """

    device: 'Device'
    """Remote device."""

    async def disconnect(self, timeout_ms: int = 2000) -> None:
        """
        Disconnect from device.

        :param timeout_ms: Timeout

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> await conn.disconnect()
        ```
        """
        ...

    async def disconnected(self, timeout_ms: int = None, disconnect: bool = False) -> None:
        """
        Wait for disconnection.

        :param timeout_ms: Timeout (None = forever)
        :param disconnect: Disconnect after timeout

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> await conn.disconnected()
            >>> print("Disconnected!")
        ```
        """
        ...

    def is_connected(self) -> bool:
        """
        Check if still connected.

        :returns: True if connected

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> if conn.is_connected():
            ...     print("Still connected")
        ```
        """
        ...

    async def pair(self, bond: bool = True, timeout_ms: int = 20000) -> None:
        """
        Pair with device.

        :param bond: Create bonding
        :param timeout_ms: Timeout

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> await conn.pair()
        ```
        """
        ...

    async def l2cap_connect(
        self,
        psm: int,
        mtu: int,
        timeout_ms: int = 5000
    ) -> 'aioble.l2cap.L2CAPChannel':
        """
        Open an L2CAP CoC channel to this device (Central role).

        :param psm: Protocol/Service Multiplexer value
        :param mtu: Our advertised MTU
        :param timeout_ms: Connection timeout

        :returns: Connected L2CAPChannel

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> ch = await conn.l2cap_connect(psm=0x70, mtu=512)
            >>> await ch.send(b"Hello")
            >>> await ch.disconnect()
        ```
        """
        ...

    async def l2cap_accept(
        self,
        psm: int,
        mtu: int,
        timeout_ms: int = None
    ) -> 'aioble.l2cap.L2CAPChannel':
        """
        Accept an incoming L2CAP CoC connection (Peripheral role).

        :param psm: Protocol/Service Multiplexer to listen on
        :param mtu: Our advertised MTU
        :param timeout_ms: How long to wait for a connection

        :returns: Connected L2CAPChannel

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> conn = await aioble.advertise(250_000, name="L2CAP-Dev")
            >>> ch = await conn.l2cap_accept(psm=0x70, mtu=512)
            >>> buf = bytearray(512)
            >>> n = await ch.recvinto(buf)
        ```
        """
        ...

    async def service(self, uuid: UUID, timeout_ms: int = 2000) -> 'ClientService':
        """
        Get remote service.

        :param uuid: Service UUID
        :param timeout_ms: Discovery timeout

        :returns: Client service object

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> svc = await conn.service(aioble.UUID(0x180F))
        ```
        """
        ...

    async def services(self, timeout_ms: int = 2000) -> list['ClientService']:
        """
        Discover all services.

        :param timeout_ms: Discovery timeout

        :returns: List of services

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> services = await conn.services()
            >>> for svc in services:
            ...     print(svc.uuid)
        ```
        """
        ...

    async def __aenter__(self) -> 'DeviceConnection':
        """Context manager entry."""
        ...

    async def __aexit__(self, *args) -> None:
        """Context manager exit."""
        ...


class Device:
    """
    Representation of a BLE device.

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> # From scan result
        >>> async for result in aioble.scan(5000):
        ...     print(result.device.addr_hex())
    ```
    """

    def addr_hex(self) -> str:
        """
        Get address as hex string.

        :returns: "AA:BB:CC:DD:EE:FF" format

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> addr = device.addr_hex()
        ```
        """
        ...

    async def connect(self, timeout_ms: int = 10000) -> DeviceConnection:
        """
        Connect to device.

        :param timeout_ms: Connection timeout

        :returns: Connection object

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> conn = await device.connect(timeout_ms=5000)
        ```
        """
        ...


def register_services(*services: Service) -> None:
    """
    Register GATT services.

    :param services: Services to register

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> service1 = aioble.Service(aioble.UUID(0x181A))
        >>> service2 = aioble.Service(aioble.UUID(0x180F))
        >>> aioble.register_services(service1, service2)
    ```
    """
    ...


async def advertise(
    interval_us: int,
    name: str = None,
    services: list[UUID] = None,
    appearance: int = 0,
    manufacturer: tuple[int, bytes] = None,
    timeout_ms: int = None
) -> DeviceConnection:
    """
    Start advertising and wait for connection.

    :param interval_us: Advertising interval in microseconds
    :param name: Device name
    :param services: List of service UUIDs
    :param appearance: GAP appearance value
    :param manufacturer: (company_id, data) tuple
    :param timeout_ms: Advertising timeout

    :returns: Connection from connecting device

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> async def peripheral():
        ...     while True:
        ...         conn = await aioble.advertise(
        ...             250_000,  # 250ms
        ...             name="Pico-BLE",
        ...             services=[service.uuid]
        ...         )
        ...         print("Connected!")
        ...         await conn.disconnected()
    ```
    """
    ...


async def scan(
    duration_ms: int,
    interval_us: int = 30000,
    window_us: int = 30000,
    active: bool = False
):
    """
    Scan for BLE devices.

    :param duration_ms: Scan duration
    :param interval_us: Scan interval
    :param window_us: Scan window
    :param active: Request scan responses

    :returns: Async iterator of ScanResult

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> async for result in aioble.scan(5000):
        ...     if result.name() == "MyDevice":
        ...         device = result.device
        ...         break
    ```
    """
    ...


class ScanResult:
    """
    BLE scan result.

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> async for result in aioble.scan(5000):
        ...     print(result.name(), result.rssi)
    ```
    """

    device: Device
    """Scanned device."""

    rssi: int
    """Signal strength (dBm)."""

    def name(self) -> Optional[str]:
        """
        Get device name.

        :returns: Name or None

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> name = result.name()
        ```
        """
        ...

    def services(self) -> list[UUID]:
        """
        Get advertised service UUIDs.

        :returns: List of UUIDs

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> for uuid in result.services():
            ...     print(uuid)
        ```
        """
        ...

    def manufacturer(self) -> Optional[tuple[int, bytes]]:
        """
        Get manufacturer data.

        :returns: (company_id, data) or None

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> mfr = result.manufacturer()
            >>> if mfr:
            ...     company, data = mfr
        ```
        """
        ...


class ClientService:
    """
    Remote GATT service (client side).

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> svc = await conn.service(aioble.UUID(0x180F))
        >>> char = await svc.characteristic(aioble.UUID(0x2A19))
    ```
    """

    uuid: UUID
    """Service UUID."""

    async def characteristic(self, uuid: UUID) -> 'ClientCharacteristic':
        """
        Get characteristic.

        :param uuid: Characteristic UUID

        :returns: Client characteristic

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> char = await svc.characteristic(aioble.UUID(0x2A19))
        ```
        """
        ...

    async def characteristics(self) -> list['ClientCharacteristic']:
        """
        Get all characteristics.

        :returns: List of characteristics

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> chars = await svc.characteristics()
        ```
        """
        ...


class ClientCharacteristic:
    """
    Remote GATT characteristic (client side).

    Example
    -------
    ```python
        >>> import aioble
        >>> 
        >>> char = await svc.characteristic(aioble.UUID(0x2A19))
        >>> value = await char.read()
        >>> print(f"Battery: {value[0]}%")
    ```
    """

    uuid: UUID
    """Characteristic UUID."""

    async def read(self, timeout_ms: int = 1000) -> bytes:
        """
        Read characteristic value.

        :param timeout_ms: Read timeout

        :returns: Value bytes

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> value = await char.read()
        ```
        """
        ...

    async def write(self, data: bytes, response: bool = True, timeout_ms: int = 1000) -> None:
        """
        Write characteristic value.

        :param data: Value to write
        :param response: Wait for response
        :param timeout_ms: Write timeout

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> await char.write(b'\\x01')
        ```
        """
        ...

    async def subscribe(self, notify: bool = True, indicate: bool = False) -> None:
        """
        Subscribe to notifications/indications.

        :param notify: Enable notifications
        :param indicate: Enable indications

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> await char.subscribe(notify=True)
        ```
        """
        ...

    async def notified(self, timeout_ms: int = None) -> bytes:
        """
        Wait for notification.

        :param timeout_ms: Wait timeout

        :returns: Notification data

        Example
        -------
        ```python
            >>> import aioble
            >>> 
            >>> while True:
            ...     data = await char.notified()
            ...     print(f"Got: {data}")
        ```
        """
        ...
