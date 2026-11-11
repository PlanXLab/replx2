"""
XBee3 Bluetooth Low Energy (BLE) module.

Provides API for controlling BLE functionality on XBee3 devices.

Key Features:
    - BLE enable/disable
    - GAP scanning and advertising
    - GATT client connection and data read/write
    - XBee BLE protocol connection

Note:
    This module is available on XBee3 Cellular, XBee3 Zigbee, XBee3 802.15.4,
    and XBee3 DigiMesh products.
"""

from typing import Any, Iterator, Optional, Callable, Union

try:
    from typing import TypedDict

    class _GAPScanDict(TypedDict):
        address: bytes
        addr_type: int
        connectable: int
        rssi: int
        payload: bytes
except ImportError:
    from typing import Dict
    _GAPScanDict = Dict

# Address types
ADDR_TYPE_PUBLIC: int = ...
"""Public BLE address type"""
ADDR_TYPE_RANDOM: int = ...
"""Random BLE address type"""

# Advertising payload property types
PROP_FLAGS: int = ...
"""BLE Flags AD type"""
PROP_16BIT_SERVICES_INCOMPLETE: int = ...
"""Incomplete list of 16-bit service UUIDs"""
PROP_16BIT_SERVICES_COMPLETE: int = ...
"""Complete list of 16-bit service UUIDs"""
PROP_32BIT_SERVICES_INCOMPLETE: int = ...
"""Incomplete list of 32-bit service UUIDs"""
PROP_32BIT_SERVICES_COMPLETE: int = ...
"""Complete list of 32-bit service UUIDs"""
PROP_128BIT_SERVICES_INCOMPLETE: int = ...
"""Incomplete list of 128-bit service UUIDs"""
PROP_128BIT_SERVICES_COMPLETE: int = ...
"""Complete list of 128-bit service UUIDs"""
PROP_NAME_COMPLETE: int = ...
"""Complete local name"""
PROP_NAME_SHORT: int = ...
"""Shortened local name"""
PROP_TX_POWER: int = ...
"""TX power level"""
PROP_16BIT_SERVICE_DATA: int = ...
"""Service data with 16-bit service UUID"""
PROP_32BIT_SERVICE_DATA: int = ...
"""Service data with 32-bit service UUID"""
PROP_128BIT_SERVICE_DATA: int = ...
"""Service data with 128-bit service UUID"""
PROP_APPEARANCE: int = ...
"""Device appearance"""
PROP_MANUFACTURER_DATA: int = ...
"""Manufacturer specific data"""

# Pairing modes
PAIRING_REQUIRE_MITM: int = ...
"""Require MITM (Man-In-The-Middle) protection"""
PAIRING_REQUIRE_BONDING: int = ...
"""Require bonding"""

# PHY types
BLE_1MBPS_PHY: int = ...
"""1 Mbps PHY"""
BLE_2MBPS_PHY: int = ...
"""2 Mbps PHY"""
BLE_CODED_PHY: int = ...
"""Coded PHY (Long Range)"""


def active(state: Optional[bool] = None) -> bool:
    """
    Enable/disable BLE functionality or query current state.

    :param state: Set to True to enable BLE, False to disable.
        If None, only returns current state.
    :return: BLE enabled state (True/False)

    Example:
        Check and change BLE enabled state::

            >>> from digi import ble
            >>> # Check current state
            >>> ble.active()
            False
            >>> # Enable BLE
            >>> ble.active(True)
            True
            >>> # Disable BLE
            >>> ble.active(False)
            False
    """
    ...


def config(**kwargs: Any) -> Any:
    """
    Query or change BLE configuration.

    Supported configuration keys:

    - ``mac``: (read-only) BLE MAC address (6-byte bytes)
    - ``name``: BLE device name (max 20 character string)
    - ``pairing``: Pairing mode (PAIRING_REQUIRE_MITM | PAIRING_REQUIRE_BONDING)

    :param kwargs: Configuration key (string) to query or key-value pairs to set
    :return: Value for single key query, None for multiple settings
    :raises ValueError: Invalid configuration key or value

    Example:
        Query and change BLE configuration::

            >>> from digi import ble
            >>> ble.active(True)
            >>> # Query MAC address
            >>> mac = ble.config("mac")
            >>> print(ble.format_address(mac))
            "00:13:A2:00:41:74:07:A6"
            >>> # Set device name
            >>> ble.config(name="MyXBee3")
            >>> # Query device name
            >>> ble.config("name")
            'MyXBee3'
    """
    ...


def format_address(address: bytes) -> str:
    """
    Convert 6-byte BLE address to colon-separated hex string.

    :param address: 6-byte BLE address (bytes or bytearray)
    :return: String in "XX:XX:XX:XX:XX:XX" format

    Example:
        Convert BLE address format::

            >>> from digi import ble
            >>> addr = bytes([0x00, 0x13, 0xA2, 0x00, 0x41, 0x74])
            >>> ble.format_address(addr)
            '00:13:A2:00:41:74'
    """
    ...


def parse_address(address_string: str) -> bytes:
    """
    Convert colon-separated hex string to 6-byte BLE address.

    :param address_string: String in "XX:XX:XX:XX:XX:XX" format
    :return: 6-byte BLE address (bytes)
    :raises ValueError: Invalid address format

    Example:
        Convert string to BLE address::

            >>> from digi import ble
            >>> addr = ble.parse_address("00:13:A2:00:41:74")
            >>> addr
            b'\\x00\\x13\\xa2\\x00At'
    """
    ...


def gap_advertise(
    interval_us: int,
    adv_data: Optional[bytes] = None,
    *,
    resp_data: Optional[bytes] = None,
    connectable: bool = True
) -> None:
    """
    Start or stop BLE advertising.

    :param interval_us: Advertising interval (microseconds). 0 to stop advertising.
        Valid range: 20,000 ~ 10,240,000 us
    :param adv_data: Advertising data (max 31 bytes).
        None to keep previous data.
    :param resp_data: Scan response data (max 31 bytes).
        None to keep previous data.
    :param connectable: True for connectable advertising, False for non-connectable

    Example:
        Start and stop BLE advertising::

            >>> from digi import ble
            >>> ble.active(True)
            >>> # Create advertising data (Flags + Complete Local Name)
            >>> flags = bytes([0x02, 0x01, 0x06])  # Flags AD type
            >>> name = bytes([0x07, 0x09]) + b"XBee3"  # Complete Local Name
            >>> adv_data = flags + name
            >>> # Start advertising at 100ms interval
            >>> ble.gap_advertise(100000, adv_data, connectable=True)
            >>> # Stop advertising
            >>> ble.gap_advertise(0)
    """
    ...


class _gap_scan:
    """
    GAP scan result iterator class.

    This class cannot be instantiated directly; it is only returned
    from the gap_scan() function.

    Example:
        Process scan results::

            >>> from digi import ble
            >>> ble.active(True)
            >>> scanner = ble.gap_scan(duration_ms=3000)
            >>> while scanner.any():
            ...     if entry := scanner.get():
            ...         print(ble.format_address(entry['address']))
            >>> scanner.stop()
    """

    def get(self, timeout_ms: int = 0) -> Optional[_GAPScanDict]:
        """
        Get an advertising entry from the scan queue.

        :param timeout_ms: Maximum wait time (milliseconds).
            0 for immediate return, -1 for infinite wait.
        :return: Advertising data dictionary or None

            Dictionary keys:
            - ``address``: 6-byte BLE address
            - ``addr_type``: Address type (ADDR_TYPE_PUBLIC or ADDR_TYPE_RANDOM)
            - ``connectable``: Connectable flag (0 or 1)
            - ``rssi``: Received signal strength (dBm)
            - ``payload``: Advertising payload data

        Example:
            Get scan entry::

                >>> with ble.gap_scan(5000) as scanner:
                ...     entry = scanner.get(timeout_ms=1000)
                ...     if entry:
                ...         print(f"RSSI: {entry['rssi']} dBm")
        """
        ...

    def any(self) -> bool:
        """
        Check if there are pending items in the scan queue or scan is in progress.

        :return: True if items in queue or scan in progress

        Example:
            Check scan status::

                >>> with ble.gap_scan(3000) as scanner:
                ...     while scanner.any():
                ...         entry = scanner.get()
                ...         if entry:
                ...             print(entry['rssi'])
        """
        ...

    def stop(self) -> None:
        """
        Stop the ongoing scan.

        Example:
            Stop scan early::

                >>> scanner = ble.gap_scan(10000)
                >>> # Stop on first device found
                >>> if scanner.get(timeout_ms=1000):
                ...     scanner.stop()
        """
        ...

    def stopped(self) -> bool:
        """
        Check if scan has stopped.

        :return: True if scan has stopped

        Example:
            Check scan completion::

                >>> scanner = ble.gap_scan(1000)
                >>> import time
                >>> time.sleep(2)
                >>> scanner.stopped()
                True
        """
        ...

    def __enter__(self) -> "_gap_scan":
        """Context manager entry."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Auto-stop scan on context manager exit."""
        ...

    def __iter__(self) -> Iterator[_GAPScanDict]:
        """Return iterator."""
        ...

    def __next__(self) -> _GAPScanDict:
        """Return next scan entry."""
        ...


def gap_scan(
    duration_ms: int,
    interval_us: int = 1280000,
    window_us: int = 11250,
    active: bool = False
) -> _gap_scan:
    """
    Start BLE GAP scan.

    :param duration_ms: Scan duration (milliseconds). 0 for infinite scan.
    :param interval_us: Scan interval (microseconds). Default 1.28 seconds.
    :param window_us: Scan window (microseconds). Default 11.25ms.
    :param active: True for active scan (send scan request), False for passive scan.
    :return: Scan result iterator object

    Example:
        Scan for nearby BLE devices::

            >>> from digi import ble
            >>> ble.active(True)
            >>> 
            >>> # Method 1: Using context manager
            >>> with ble.gap_scan(duration_ms=5000) as scanner:
            ...     for adv in scanner:
            ...         addr = ble.format_address(adv['address'])
            ...         rssi = adv['rssi']
            ...         print(f"Device: {addr}, RSSI: {rssi}")
            >>>
            >>> # Method 2: Manual control
            >>> scanner = ble.gap_scan(duration_ms=3000, active=True)
            >>> while not scanner.stopped():
            ...     entry = scanner.get(timeout_ms=100)
            ...     if entry and entry['connectable']:
            ...         print(f"Connectable: {ble.format_address(entry['address'])}")
            >>> scanner.stop()
    """
    ...


class UUID:
    """
    BLE UUID (Universally Unique Identifier) class.

    Represents 16-bit, 32-bit, or 128-bit UUID.

    Attributes:
        size: UUID size (in bytes: 2, 4, or 16)

    Example:
        Create and use UUID::

            >>> from digi import ble
            >>> # 16-bit UUID (Heart Rate Service)
            >>> hr_uuid = ble.UUID(0x180D)
            >>> hr_uuid.size
            2
            >>> # 128-bit UUID (string)
            >>> custom_uuid = ble.UUID("12345678-1234-5678-1234-567812345678")
            >>> custom_uuid.size
            16
            >>> # 128-bit UUID (bytes)
            >>> uuid_bytes = bytes(range(16))
            >>> raw_uuid = ble.UUID(uuid_bytes)
    """

    size: int

    def __init__(self, value: Union[int, str, bytes]) -> None:
        """
        Create UUID object.

        :param value: UUID value. Supported formats:
            - 16-bit integer (0x0000 ~ 0xFFFF)
            - 32-bit integer (0x00000000 ~ 0xFFFFFFFF)
            - 128-bit UUID string ("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
            - 16-byte bytes object
        :raises ValueError: Invalid UUID format

        Example:
            Create UUIDs in various formats::

                >>> # Standard 16-bit service UUID
                >>> battery_svc = ble.UUID(0x180F)  # Battery Service
                >>> # Custom 128-bit UUID
                >>> my_svc = ble.UUID("0000ffe0-0000-1000-8000-00805f9b34fb")
        """
        ...

    def __eq__(self, other: Any) -> bool:
        """UUID equality comparison."""
        ...

    def __hash__(self) -> int:
        """Return UUID hash value."""
        ...

    def __repr__(self) -> str:
        """UUID string representation."""
        ...


class _gap_connect:
    """
    GAP connection class.

    Manages connection to a remote BLE device as a GATT client.
    This class cannot be instantiated directly; it is only returned
    from the gap_connect() function.

    Example:
        BLE device connection and GATT operations::

            >>> from digi import ble
            >>> ble.active(True)
            >>> 
            >>> target = bytes([0x01, 0x02, 0x03, 0x04, 0x05, 0x06])
            >>> with ble.gap_connect(ble.ADDR_TYPE_PUBLIC, target) as conn:
            ...     # Discover services
            ...     for svc in conn.gattc_services():
            ...         print(f"Service: {svc['uuid']}")
            ...         # Discover characteristics
            ...         for char in conn.gattc_characteristics(svc):
            ...             print(f"  Char: {char['uuid']}")
    """

    def addr(self) -> bytes:
        """
        Return the BLE address of the connected device.

        :return: 6-byte BLE address

        Example:
            Check connected device address::

                >>> with ble.gap_connect(addr_type, address) as conn:
                ...     print(ble.format_address(conn.addr()))
        """
        ...

    def close(self) -> None:
        """
        Terminate the BLE connection.

        Example:
            Manual connection termination::

                >>> conn = ble.gap_connect(addr_type, address)
                >>> # ... perform operations ...
                >>> conn.close()
        """
        ...

    def config(self, **kwargs: Any) -> Any:
        """
        Query or change connection settings.

        Supported settings:
        - ``interval``: Connection interval (1.25ms units)
        - ``timeout``: Connection timeout (10ms units)
        - ``latency``: Slave latency

        :param kwargs: Configuration key to query or key-value pairs to set
        :return: Value for single key query

        Example:
            Query connection parameters::

                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     interval = conn.config("interval")
                ...     print(f"Connection interval: {interval * 1.25}ms")
        """
        ...

    def phyconfig(self, **kwargs: Any) -> Any:
        """
        Query or change PHY settings.

        Supported settings:
        - ``tx_phy``: TX PHY (BLE_1MBPS_PHY, BLE_2MBPS_PHY, BLE_CODED_PHY)
        - ``rx_phy``: RX PHY

        :param kwargs: Configuration key to query or key-value pairs to set
        :return: Value for single key query

        Example:
            Change PHY settings::

                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     # Change to 2Mbps PHY
                ...     conn.phyconfig(tx_phy=ble.BLE_2MBPS_PHY)
        """
        ...

    def disconnect_code(self) -> Optional[int]:
        """
        Return the disconnect code.

        :return: Disconnect reason code or None if still connected

        Example:
            Check disconnect reason::

                >>> conn = ble.gap_connect(addr_type, addr)
                >>> # ... after connection terminates ...
                >>> code = conn.disconnect_code()
                >>> if code:
                ...     print(f"Disconnect reason: 0x{code:02X}")
        """
        ...

    def gattc_services(
        self, 
        uuid: Optional[UUID] = None
    ) -> Iterator[dict]:
        """
        Discover GATT services on the remote device.

        :param uuid: Search for specific UUID only. None for all services.
        :return: Service dictionary iterator

            Dictionary keys:
            - ``uuid``: Service UUID (UUID object)
            - ``start_handle``: Start handle
            - ``end_handle``: End handle

        Example:
            Discover GATT services::

                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     for service in conn.gattc_services():
                ...         print(f"UUID: {service['uuid']}")
                ...         print(f"Handles: {service['start_handle']}-{service['end_handle']}")
        """
        ...

    def gattc_characteristics(
        self, 
        service: Optional[dict] = None,
        uuid: Optional[UUID] = None
    ) -> Iterator[dict]:
        """
        Discover GATT characteristics.

        :param service: Service dictionary (from gattc_services()).
            None for characteristics from all services.
        :param uuid: Search for specific UUID only.
        :return: Characteristic dictionary iterator

            Dictionary keys:
            - ``uuid``: Characteristic UUID
            - ``handle``: Characteristic handle
            - ``value_handle``: Value handle
            - ``properties``: Characteristic properties bitmask

        Example:
            Discover characteristics and check properties::

                >>> CHAR_PROP_READ = 0x02
                >>> CHAR_PROP_NOTIFY = 0x10
                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     for svc in conn.gattc_services():
                ...         for char in conn.gattc_characteristics(svc):
                ...             props = char['properties']
                ...             if props & CHAR_PROP_READ:
                ...                 print(f"Readable: {char['uuid']}")
        """
        ...

    def gattc_descriptors(
        self, 
        characteristic: dict
    ) -> Iterator[dict]:
        """
        Discover GATT descriptors.

        :param characteristic: Characteristic dictionary (from gattc_characteristics())
        :return: Descriptor dictionary iterator

            Dictionary keys:
            - ``uuid``: Descriptor UUID
            - ``handle``: Descriptor handle

        Example:
            Find CCCD (Client Characteristic Configuration Descriptor)::

                >>> CCCD_UUID = ble.UUID(0x2902)
                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     for svc in conn.gattc_services():
                ...         for char in conn.gattc_characteristics(svc):
                ...             for desc in conn.gattc_descriptors(char):
                ...                 if desc['uuid'] == CCCD_UUID:
                ...                     print(f"CCCD handle: {desc['handle']}")
        """
        ...

    def gattc_read_characteristic(
        self, 
        characteristic: dict
    ) -> bytes:
        """
        Read characteristic value.

        :param characteristic: Characteristic dictionary (from gattc_characteristics())
        :return: Characteristic value (bytes)
        :raises OSError: Read failed

        Example:
            Read battery level::

                >>> BATTERY_LEVEL_UUID = ble.UUID(0x2A19)
                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     for svc in conn.gattc_services(ble.UUID(0x180F)):
                ...         for char in conn.gattc_characteristics(svc, BATTERY_LEVEL_UUID):
                ...             level = conn.gattc_read_characteristic(char)
                ...             print(f"Battery: {level[0]}%")
        """
        ...

    def gattc_read_descriptor(
        self, 
        descriptor: dict
    ) -> bytes:
        """
        Read descriptor value.

        :param descriptor: Descriptor dictionary (from gattc_descriptors())
        :return: Descriptor value (bytes)
        :raises OSError: Read failed

        Example:
            Read CCCD state::

                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     # ... after finding characteristic/descriptor ...
                ...     cccd_value = conn.gattc_read_descriptor(cccd_desc)
                ...     notifications_enabled = (cccd_value[0] & 0x01) != 0
        """
        ...

    def gattc_write_characteristic(
        self, 
        characteristic: dict,
        data: bytes,
        response: bool = True
    ) -> None:
        """
        Write characteristic value.

        :param characteristic: Characteristic dictionary
        :param data: Data to write (bytes)
        :param response: True to wait for response (Write Request),
            False for write without response (Write Command)
        :raises OSError: Write failed

        Example:
            Write to LED control characteristic::

                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     # Find LED characteristic
                ...     for svc in conn.gattc_services():
                ...         for char in conn.gattc_characteristics(svc, led_uuid):
                ...             # Turn LED on
                ...             conn.gattc_write_characteristic(char, b'\\x01')
        """
        ...

    def gattc_write_descriptor(
        self, 
        descriptor: dict,
        data: bytes
    ) -> None:
        """
        Write descriptor value.

        :param descriptor: Descriptor dictionary
        :param data: Data to write (bytes)
        :raises OSError: Write failed

        Example:
            Enable notifications::

                >>> CCCD_ENABLE_NOTIFY = b'\\x01\\x00'
                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     # ... after finding CCCD descriptor ...
                ...     conn.gattc_write_descriptor(cccd_desc, CCCD_ENABLE_NOTIFY)
        """
        ...

    def gattc_configure(
        self, 
        characteristic: dict,
        callback: Optional[Callable[[bytes], Any]]
    ) -> None:
        """
        Set notification/indication callback for characteristic.

        :param characteristic: Characteristic dictionary
        :param callback: Callback function to call on notification/indication.
            Callback receives bytes argument. None to unregister callback.

        Example:
            Receive Heart Rate notifications::

                >>> def on_heart_rate(data):
                ...     hr = data[1]  # Heart rate value
                ...     print(f"Heart Rate: {hr} BPM")
                >>>
                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     hr_char = ...  # Heart Rate Measurement characteristic
                ...     cccd = ...     # CCCD descriptor
                ...     # Register callback
                ...     conn.gattc_configure(hr_char, on_heart_rate)
                ...     # Enable notifications
                ...     conn.gattc_write_descriptor(cccd, b'\\x01\\x00')
                ...     # Wait for notifications
                ...     import time
                ...     time.sleep(10)
        """
        ...

    def isconnected(self) -> bool:
        """
        Check connection status.

        :return: True if connected, False otherwise

        Example:
            Monitor connection status::

                >>> conn = ble.gap_connect(addr_type, addr)
                >>> while conn.isconnected():
                ...     # Work while connected
                ...     data = conn.gattc_read_characteristic(char)
                ...     time.sleep(1)
                >>> print("Connection lost")
        """
        ...

    def secure(self, mode: int = 0) -> bool:
        """
        Upgrade connection to secure connection.

        :param mode: Security mode.
            0 for encryption only, PAIRING_REQUIRE_MITM | PAIRING_REQUIRE_BONDING combinations.
        :return: True on successful secure connection

        Example:
            Set up secure connection::

                >>> with ble.gap_connect(addr_type, addr) as conn:
                ...     # Request MITM protection and bonding
                ...     mode = ble.PAIRING_REQUIRE_MITM | ble.PAIRING_REQUIRE_BONDING
                ...     if conn.secure(mode):
                ...         print("Secure connection established")
        """
        ...

    def __enter__(self) -> "_gap_connect":
        """Context manager entry."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Auto-close connection on context manager exit."""
        ...


def gap_connect(
    addr_type: int,
    address: bytes,
    timeout_ms: int = 10000,
    interval_us: int = 50000,
    window_us: int = 50000
) -> _gap_connect:
    """
    Connect to a remote BLE device.

    :param addr_type: Address type (ADDR_TYPE_PUBLIC or ADDR_TYPE_RANDOM)
    :param address: 6-byte BLE address
    :param timeout_ms: Connection timeout (milliseconds). Default 10 seconds.
    :param interval_us: Scan interval (microseconds). Default 50ms.
    :param window_us: Scan window (microseconds). Default 50ms.
    :return: Connection object
    :raises OSError: Connection failed

    Example:
        Connect to BLE device::

            >>> from digi import ble
            >>> ble.active(True)
            >>> 
            >>> # Find device by scanning
            >>> target_addr = None
            >>> with ble.gap_scan(5000) as scanner:
            ...     for adv in scanner:
            ...         if adv['connectable']:
            ...             target_addr = adv['address']
            ...             addr_type = adv['addr_type']
            ...             break
            >>>
            >>> # Connect to found device
            >>> if target_addr:
            ...     with ble.gap_connect(addr_type, target_addr, timeout_ms=5000) as conn:
            ...         print(f"Connected to {ble.format_address(conn.addr())}")
            ...         # Perform GATT operations
            ...         for svc in conn.gattc_services():
            ...             print(f"Service: {svc['uuid']}")
    """
    ...


class _xbee_connect:
    """
    XBee BLE connection class.

    Communicates with other XBee devices using XBee-specific BLE protocol.
    This class cannot be instantiated directly; it is only returned
    from the xbee_connect() function.

    Example:
        XBee BLE connection::

            >>> from digi import ble
            >>> ble.active(True)
            >>> 
            >>> # Connect to XBee device (password authentication)
            >>> target = bytes([0x00, 0x13, 0xA2, 0x00, 0x41, 0x74, 0x07, 0xA6])
            >>> with ble.xbee_connect(target, "password123") as conn:
            ...     # Execute AT command
            ...     ni = conn.atcmd("NI")
            ...     print(f"Node ID: {ni}")
    """

    def addr(self) -> bytes:
        """
        Return the address of the connected XBee device.

        :return: 8-byte 64-bit address or 6-byte BLE address

        Example:
            Check connected device address::

                >>> with ble.xbee_connect(target, password) as conn:
                ...     addr = conn.addr()
                ...     print(f"Connected to: {addr.hex()}")
        """
        ...

    def close(self) -> None:
        """
        Terminate the XBee BLE connection.

        Example:
            Manual connection termination::

                >>> conn = ble.xbee_connect(target, password)
                >>> ni = conn.atcmd("NI")
                >>> conn.close()
        """
        ...

    def atcmd(
        self, 
        cmd: str, 
        value: Optional[Any] = None
    ) -> Optional[Any]:
        """
        Execute AT command on the connected XBee device.

        :param cmd: 2-character AT command (e.g., "NI", "VR", "SH")
        :param value: Value to set. None to query current value.
        :return: Command result on query, None on set
        :raises OSError: Command failed

        Example:
            Execute remote XBee AT commands::

                >>> with ble.xbee_connect(target, password) as conn:
                ...     # Query Node Identifier
                ...     ni = conn.atcmd("NI")
                ...     print(f"Node ID: {ni}")
                ...     # Query firmware version
                ...     vr = conn.atcmd("VR")
                ...     print(f"Firmware: {vr:04X}")
                ...     # Change Node ID
                ...     conn.atcmd("NI", "NewName")
                ...     conn.atcmd("WR")  # Save changes
        """
        ...

    def relay(self, data: bytes) -> bytes:
        """
        Send and receive data via relay frame.

        :param data: Data to transmit (bytes)
        :return: Received response data (bytes)
        :raises OSError: Communication failed

        Example:
            Relay frame communication::

                >>> with ble.xbee_connect(target, password) as conn:
                ...     # Send custom data and receive response
                ...     response = conn.relay(b"Hello XBee!")
                ...     print(f"Response: {response}")
        """
        ...

    def isconnected(self) -> bool:
        """
        Check connection status.

        :return: True if connected

        Example:
            Check connection status::

                >>> conn = ble.xbee_connect(target, password)
                >>> while conn.isconnected():
                ...     data = conn.relay(b"ping")
                ...     time.sleep(1)
        """
        ...

    def __enter__(self) -> "_xbee_connect":
        """Context manager entry."""
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Auto-close connection on context manager exit."""
        ...


def xbee_connect(
    address: Union[bytes, str],
    password: str,
    timeout_ms: int = 10000,
    addr_type: Optional[int] = None
) -> _xbee_connect:
    """
    Connect to another XBee device using XBee BLE protocol.

    :param address: Target XBee address.
        8-byte 64-bit address or 6-byte BLE address,
        or colon-separated string ("XX:XX:XX:XX:XX:XX")
    :param password: BLE connection password (target device's BL setting)
    :param timeout_ms: Connection timeout (milliseconds). Default 10 seconds.
    :param addr_type: Address type. None for 64-bit address.
    :return: XBee connection object
    :raises OSError: Connection failed

    Example:
        XBee BLE connection::

            >>> from digi import ble
            >>> import time
            >>> ble.active(True)
            >>> 
            >>> # Connect with 64-bit address
            >>> target_64bit = bytes([0x00, 0x13, 0xA2, 0x00, 0x41, 0x74, 0x07, 0xA6])
            >>> password = "mypassword"
            >>> 
            >>> with ble.xbee_connect(target_64bit, password) as conn:
            ...     # Query remote device info
            ...     ni = conn.atcmd("NI")
            ...     vr = conn.atcmd("VR")
            ...     print(f"Connected to: {ni}")
            ...     print(f"Firmware version: {vr:04X}")
            ...     
            ...     # Relay frame communication
            ...     response = conn.relay(b"Hello from MicroPython!")
            ...     print(f"Response: {response}")
    """
    ...


def delete_bondings() -> None:
    """
    Delete all saved bonding information.

    Removes key information for all previously paired devices.

    Example:
        Initialize bonding information::

            >>> from digi import ble
            >>> ble.active(True)
            >>> # Delete all bonding information
            >>> ble.delete_bondings()
            >>> print("All bonding information cleared")
    """
    ...


def io_callbacks(
    callback: Optional[Callable[[int, int], Any]]
) -> None:
    """
    Register BLE security I/O callback.

    Called when display/input capability is required during pairing.

    :param callback: I/O callback function. Receives two integer arguments:
        (io_type, value). None to unregister callback.

    Example:
        Register security I/O callback::

            >>> from digi import ble
            >>> 
            >>> def on_io_request(io_type, value):
            ...     print(f"IO request: type={io_type}, value={value}")
            >>>
            >>> ble.io_callbacks(on_io_request)
    """
    ...


def passkey_confirm(confirm: bool) -> None:
    """
    Respond to passkey confirmation request.

    Used in Numeric Comparison pairing.

    :param confirm: True to confirm passkey match, False to reject

    Example:
        Passkey confirmation::

            >>> from digi import ble
            >>> 
            >>> displayed_passkey = 123456
            >>> # Request user confirmation for displayed passkey
            >>> user_confirmed = True  # User confirmation
            >>> ble.passkey_confirm(user_confirmed)
    """
    ...


def passkey_enter(passkey: int) -> None:
    """
    Enter passkey.

    Used in Passkey Entry pairing.

    :param passkey: 6-digit passkey (0 ~ 999999)

    Example:
        Enter passkey::

            >>> from digi import ble
            >>> 
            >>> # Enter passkey displayed on remote device
            >>> displayed_passkey = 123456
            >>> ble.passkey_enter(displayed_passkey)
    """
    ...
