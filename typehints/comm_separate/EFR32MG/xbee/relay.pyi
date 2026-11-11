"""
XBee User Data Relay Frame transmission/reception module.

Provides User Data Relay Frame communication functionality between
the Serial Port, Bluetooth interface, and MicroPython.

Key Features:
    - send: Send User Data Relay Frame
    - receive: Receive User Data Relay Frame
    - callback: Register reception callback

Note:
    User Data Relay is available on all XBee3 devices and is particularly
    useful for communication between interfaces.
"""

from typing import Any, Callable, Optional

try:
    from typing import TypedDict

    class _RelayDict(TypedDict):
        """User Data Relay Frame dictionary type."""
        message: bytes
        """Frame payload"""
        sender: int
        """Sender interface (SERIAL, BLUETOOTH, or MICROPYTHON)"""
except ImportError:
    from typing import Dict
    _RelayDict = Dict

SERIAL: int = ...
"""Serial interface constant (0)"""
BLUETOOTH: int = ...
"""Bluetooth interface constant (1)"""
MICROPYTHON: int = ...
"""MicroPython interface constant (2)"""
MAX_DATA_LENGTH: int = ...
"""Maximum payload length (can be read from ATRL)"""


def callback(func: Optional[Callable[[_RelayDict], Any]]) -> None:
    """
    Register callback for asynchronous User Data Relay Frame reception.

    The registered callback is called when a User Data Relay Frame is received
    from another interface (Serial, Bluetooth).

    :param func: Callback function to be called on frame reception.
        None to clear callback.

        Callback signature: ``func(relay_frame: _RelayDict) -> Any``

        relay_frame dictionary keys:
        - ``message``: Received payload (bytes)
        - ``sender``: Sender interface (SERIAL, BLUETOOTH, or MICROPYTHON)

    Note:
        - Do not perform blocking operations in callback
        - Exception raised in callback is printed but does not stop processing

    Example:
        Register relay callback::

            >>> from xbee import relay
            >>> 
            >>> def relay_handler(frame):
            ...     sender = frame['sender']
            ...     message = frame['message']
            ...     
            ...     if sender == relay.SERIAL:
            ...         print(f"From Serial: {message}")
            ...     elif sender == relay.BLUETOOTH:
            ...         print(f"From Bluetooth: {message}")
            ...         # Echo response
            ...         relay.send(relay.BLUETOOTH, b"Received: " + message)
            >>> 
            >>> # Register callback
            >>> relay.callback(relay_handler)
            >>> 
            >>> # Clear callback
            >>> # relay.callback(None)
    """
    ...


def receive() -> Optional[_RelayDict]:
    """
    Receive User Data Relay Frame synchronously.

    Non-blocking call. Returns immediately if queue is empty.

    :return: Dictionary containing received frame, or None if queue is empty.

        Dictionary keys:
        - ``message``: Received payload (bytes)
        - ``sender``: Sender interface (SERIAL, BLUETOOTH, or MICROPYTHON)

    Example:
        Polling receive loop::

            >>> from xbee import relay
            >>> import time
            >>> 
            >>> while True:
            ...     frame = relay.receive()
            ...     if frame:
            ...         sender = frame['sender']
            ...         data = frame['message']
            ...         
            ...         if sender == relay.SERIAL:
            ...             print(f"Serial -> MicroPython: {data}")
            ...         elif sender == relay.BLUETOOTH:
            ...             print(f"BLE -> MicroPython: {data}")
            ...         
            ...         # Response
            ...         relay.send(sender, b"ACK")
            ...     
            ...     time.sleep(0.1)
    """
    ...


def send(dest: int, data: bytes) -> None:
    """
    Send User Data Relay Frame to specified interface.

    :param dest: Destination interface:
        - ``relay.SERIAL``: Serial port
        - ``relay.BLUETOOTH``: Bluetooth (BLE)
        - ``relay.MICROPYTHON``: MicroPython (for test purposes)
    :param data: Payload to send (bytes, max length MAX_DATA_LENGTH)
    :raises ValueError: Invalid interface or data exceeds MAX_DATA_LENGTH
    :raises TypeError: data is not bytes type

    Example:
        Send data to various interfaces::

            >>> from xbee import relay
            >>> 
            >>> # Send to serial port
            >>> relay.send(relay.SERIAL, b"Hello Serial!\\r\\n")
            >>> 
            >>> # Send to Bluetooth interface
            >>> relay.send(relay.BLUETOOTH, b"Hello BLE!")
            >>> 
            >>> # Send sensor data in JSON format
            >>> import json
            >>> data = json.dumps({"temp": 25.5, "humidity": 60})
            >>> relay.send(relay.BLUETOOTH, data.encode())
            >>> 
            >>> # Large data transmission
            >>> large_data = b"x" * relay.MAX_DATA_LENGTH
            >>> relay.send(relay.SERIAL, large_data)
    """
    ...
