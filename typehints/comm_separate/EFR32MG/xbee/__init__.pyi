"""
XBee-specific MicroPython module for Digi XBee devices.

Provides core XBee functionality: AT commands, message transmission/reception,
device discovery, power management, etc.

Key Features:
    - atcmd: AT command read/write
    - transmit/receive: Zigbee/802.15.4/DigiMesh message transmission/reception
    - discover: Network device discovery
    - XBee class: Hardware control (sleep, wake)

Note:
    Available features vary depending on XBee firmware type:
    - Zigbee, 802.15.4, DigiMesh: All features available
    - Cellular: AT commands, transmit/receive available
    - BLE: Refer to digi.ble module
"""

from typing import Any, Callable, Optional, Union

ADDR_BROADCAST: bytes = ...
"""64-bit broadcast address (0x000000000000FFFF)"""
ADDR_COORDINATOR: bytes = ...
"""64-bit coordinator address (0x0000000000000000)"""

ENDPOINT_DIGI_DATA: int = ...
"""Digi data endpoint (0xE8)"""
CLUSTER_DIGI_SERIAL_DATA: int = ...
"""Digi serial data cluster (0x0011)"""
PROFILE_DIGI_XBEE: int = ...
"""Digi XBee profile (0xC105)"""

PIN_WAKE: int = ...
"""Pin wake source (for XBee.wake_reason())"""
RTC_WAKE: int = ...
"""RTC wake source (for XBee.wake_reason())"""


def atcmd(
    cmd: str, 
    value: Optional[Any] = None
) -> Optional[Union[bytes, int, str, None]]:
    """
    Read or write AT command value.

    Executes immediately by adding local/remote flag and extra byte
    for register read command.

    :param cmd: Two-character AT command (e.g., "NI", "BD")
    :param value: Value to set. None or omitted to read current value.
        Integer, bytes, or string depending on command.
    :return: Current value on read; None on write.
        Return type varies by command (bytes, int, str).
    :raises KeyError: Unknown command
    :raises ValueError: Invalid value

    Example:
        Read/write AT command::

            >>> import xbee
            >>> 
            >>> # Read node identifier
            >>> ni = xbee.atcmd("NI")
            >>> print(f"Node ID: {ni}")
            >>> 
            >>> # Set node identifier
            >>> xbee.atcmd("NI", "MyXBee")
            >>> 
            >>> # Read serial number (as bytes)
            >>> sh = xbee.atcmd("SH")  # Serial High
            >>> sl = xbee.atcmd("SL")  # Serial Low
            >>> 
            >>> # Change baud rate
            >>> xbee.atcmd("BD", 115200)
            >>> 
            >>> # Save settings
            >>> xbee.atcmd("WR")
    """
    ...


def discover() -> Optional[dict]:
    """
    Discover XBee nodes in the network.

    Each call returns information about the next discovered node.
    Returns None when discovery is complete.

    Returned dictionary keys (vary by protocol):
        - ``sender_nwk``: 16-bit network address (Zigbee)
        - ``sender_eui64``: 64-bit address (bytes)
        - ``parent_nwk``: Parent network address (Zigbee)
        - ``node_id``: Node identifier string
        - ``node_type``: Node type (coordinator, router, end device)
        - ``device_type``: Device type identifier
        - ``rssi``: Last hop received signal strength (DigiMesh/802.15.4)

    :return: Dictionary with discovered node info, or None when complete.

    Note:
        Discovery time depends on NT (Node Discovery Timeout) AT parameter.
        Typical range is 6-60 seconds.

    Example:
        Discover devices on network::

            >>> import xbee
            >>> import time
            >>> 
            >>> print("Starting device discovery...")
            >>> devices = []
            >>> 
            >>> while True:
            ...     node = xbee.discover()
            ...     if node is None:
            ...         break
            ...     devices.append(node)
            ...     print(f"Found: {node.get('node_id', 'Unknown')}")
            ...     print(f"  Address: {node['sender_eui64'].hex()}")
            >>> 
            >>> print(f"\\nTotal {len(devices)} devices found")
    """
    ...


def receive() -> Optional[dict]:
    """
    Receive XBee message from queue.

    Non-blocking call. Returns immediately without waiting.

    Returned dictionary keys (vary by protocol):
        - ``sender_nwk``: 16-bit network address (Zigbee)
        - ``sender_eui64``: 64-bit address (bytes)
        - ``source_ep``: Source endpoint
        - ``dest_ep``: Destination endpoint
        - ``cluster``: Cluster ID
        - ``profile``: Profile ID
        - ``broadcast``: Whether message was broadcast
        - ``payload``: Message payload (bytes)
        - ``rssi``: Received signal strength (802.15.4/DigiMesh)

    :return: Dictionary with received message, or None if queue is empty.

    Example:
        Receive and process messages::

            >>> import xbee
            >>> import time
            >>> 
            >>> # Message receive loop
            >>> while True:
            ...     msg = xbee.receive()
            ...     if msg:
            ...         sender = msg['sender_eui64'].hex()
            ...         payload = msg['payload'].decode('utf-8')
            ...         print(f"Message from {sender}: {payload}")
            ...         
            ...         # Echo response
            ...         xbee.transmit(msg['sender_eui64'], b"ACK")
            ...     else:
            ...         time.sleep(0.1)
    """
    ...


def transmit(
    dest: bytes, 
    payload: Union[bytes, str], 
    *,
    source_ep: int = ENDPOINT_DIGI_DATA,
    dest_ep: int = ENDPOINT_DIGI_DATA,
    cluster: int = CLUSTER_DIGI_SERIAL_DATA,
    profile: int = PROFILE_DIGI_XBEE,
    bcast_radius: int = 0,
    tx_options: int = 0
) -> None:
    """
    Send XBee message to specified destination.

    :param dest: Destination address (64-bit EUI64, or ADDR_BROADCAST, ADDR_COORDINATOR)
    :param payload: Data to transmit (bytes or str; str is encoded as UTF-8)
    :param source_ep: Source endpoint (default: ENDPOINT_DIGI_DATA)
    :param dest_ep: Destination endpoint (default: ENDPOINT_DIGI_DATA)
    :param cluster: Cluster ID (default: CLUSTER_DIGI_SERIAL_DATA)
    :param profile: Profile ID (default: PROFILE_DIGI_XBEE)
    :param bcast_radius: Broadcast hop limit (0 = maximum)
    :param tx_options: Transmit options bitmask
    :raises OSError: Send failed (network error, timeout, etc.)

    Example:
        Send message::

            >>> import xbee
            >>> 
            >>> # Broadcast message
            >>> xbee.transmit(xbee.ADDR_BROADCAST, "Hello everyone!")
            >>> 
            >>> # Send to specific device
            >>> dest_addr = bytes([0x00, 0x13, 0xA2, 0x00, 0x41, 0x23, 0x45, 0x67])
            >>> xbee.transmit(dest_addr, b"Hello specific device!")
            >>> 
            >>> # Send to coordinator
            >>> xbee.transmit(xbee.ADDR_COORDINATOR, b"Report to coordinator")
            >>> 
            >>> # Use custom endpoint/cluster
            >>> xbee.transmit(
            ...     dest_addr,
            ...     b"Custom data",
            ...     source_ep=0x54,
            ...     dest_ep=0x54,
            ...     cluster=0x0012
            ... )
    """
    ...


def idle_radio(flag: bool) -> bool:
    """
    Disable or re-enable radio network communication.

    While disabled, received frames are discarded and poll_now() cannot be used.

    Note:
        This command is only available in Micropython mode (AP=4).

    :param flag: True to disable network, False to re-enable
    :return: Previous flag value

    Example:
        Temporarily stop radio::

            >>> import xbee
            >>> 
            >>> # Disable radio
            >>> prev_state = xbee.idle_radio(True)
            >>> print(f"Previous state: {prev_state}")
            >>> 
            >>> # Perform operations
            >>> # ...
            >>> 
            >>> # Re-enable radio
            >>> xbee.idle_radio(False)
    """
    ...


def poll_now() -> None:
    """
    Request immediate polling for buffered data on parent device.

    Note:
        Only available for Zigbee End Devices (SM != 0).
        Must first set SP (Sleep Period) AT parameter.

    :raises OSError: ENOTSUP - SM is set to 0 (not an End Device)
    :raises OSError: ENOENT - SP value not set

    Example:
        Manually poll for data::

            >>> import xbee
            >>> 
            >>> # Poll for data from parent
            >>> try:
            ...     xbee.poll_now()
            ...     print("Poll request sent")
            ... except OSError as e:
            ...     print(f"Poll failed: {e}")
            >>> 
            >>> # Check for received data
            >>> msg = xbee.receive()
            >>> if msg:
            ...     print(f"Received: {msg['payload']}")
    """
    ...


class XBee:
    """
    Class for XBee hardware control.

    Provides hardware-level control functions such as sleep mode management
    and wake source information.

    Example:
        Basic sleep management::

            >>> import xbee
            >>> 
            >>> x = xbee.XBee()
            >>> 
            >>> # Check wake reason
            >>> reason = x.wake_reason()
            >>> if reason == xbee.PIN_WAKE:
            ...     print("Woke by pin")
            >>> elif reason == xbee.RTC_WAKE:
            ...     print("Woke by RTC")
            >>> 
            >>> # Enter sleep mode
            >>> x.sleep_now(10000)  # Sleep for 10 seconds
    """

    def __init__(self) -> None:
        """
        Create XBee hardware control object.

        Example:
            Initialize XBee object::

                >>> import xbee
                >>> x = xbee.XBee()
        """
        ...

    def atcmd(
        self, 
        cmd: str, 
        value: Optional[Any] = None
    ) -> Optional[Union[bytes, int, str, None]]:
        """
        Read or write AT command value.

        Same as xbee.atcmd() module function.

        :param cmd: Two-character AT command
        :param value: Value to set (None to read)
        :return: Current value on read; None on write

        Example:
            Read AT command with XBee object::

                >>> x = xbee.XBee()
                >>> ni = x.atcmd("NI")
                >>> print(f"Node ID: {ni}")
        """
        ...

    def sleep_now(
        self, 
        timeout_ms: int, 
        pin_wake: bool = False
    ) -> None:
        """
        Put XBee into low power sleep mode.

        Sleep duration is the shorter of timeout_ms and Sleep Period (SP * 10ms).
        After waking, the wake_reason() method can be used to determine the wake source.

        Note:
            Only available for End Devices (SM not 0) on Zigbee/DigiMesh networks.

        :param timeout_ms: Sleep timeout (milliseconds)
        :param pin_wake: True to enable pin wake (default False)

        Example:
            Enter sleep mode::

                >>> x = xbee.XBee()
                >>> 
                >>> # Sleep for 10 seconds
                >>> x.sleep_now(10000)
                >>> 
                >>> # Sleep with pin wake enabled
                >>> x.sleep_now(30000, pin_wake=True)
                >>> 
                >>> # Check wake source after waking
                >>> reason = x.wake_reason()
        """
        ...

    def wake_reason(self) -> int:
        """
        Return the most recent wake source.

        :return: Wake source:
            - ``xbee.PIN_WAKE``: Woke by external pin
            - ``xbee.RTC_WAKE``: Woke by internal RTC timer

        Example:
            Determine wake reason::

                >>> x = xbee.XBee()
                >>> 
                >>> reason = x.wake_reason()
                >>> if reason == xbee.PIN_WAKE:
                ...     print("Woke by pin interrupt")
                ...     # Process event
                >>> elif reason == xbee.RTC_WAKE:
                ...     print("Woke by scheduled timer")
                ...     # Perform periodic task
        """
        ...
