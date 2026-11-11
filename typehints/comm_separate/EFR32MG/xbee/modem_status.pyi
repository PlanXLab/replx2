# Copyright (c) 2019, Digi International, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
XBee Modem Status callback module.

Provides the ability to register callbacks to receive 0x8A Modem Status
frames generated from the XBee module. These status frames indicate
events such as power-on, network joining/leaving, and configuration changes.

Key Features:
    - callback: Register status callback
    - receive: Synchronous polling receive

Note:
    Modem Status codes vary by XBee firmware type. Refer to product manual
    for complete status code listing.

Common status codes:
    - 0x00: Hardware reset or power on
    - 0x01: Watchdog timer reset
    - 0x02: Joined network (Zigbee)
    - 0x03: Left network (Zigbee)
    - 0x06: Coordinator started (Zigbee)
    - 0x0B: Network key updated (Zigbee)
"""

from typing import Any, Callable, Optional


def callback(func: Optional[Callable[[int], Any]]) -> None:
    """
    Register callback for asynchronous Modem Status frame reception.

    The callback is invoked each time a 0x8A Modem Status frame is
    received from the XBee module.

    :param func: Callback function called with status code.
        None to clear callback.

        Callback signature: ``func(status: int) -> Any``

    Note:
        - Do not perform blocking operations in callback
        - Exception raised in callback is printed but does not stop processing

    Example:
        Register modem status callback::

            >>> from xbee import modem_status
            >>> 
            >>> def status_handler(status):
            ...     status_names = {
            ...         0x00: "Hardware reset",
            ...         0x01: "Watchdog reset",
            ...         0x02: "Joined network",
            ...         0x03: "Left network",
            ...         0x06: "Coordinator started",
            ...         0x0B: "Network key updated",
            ...     }
            ...     name = status_names.get(status, f"Unknown (0x{status:02X})")
            ...     print(f"Modem status: {name}")
            >>> 
            >>> # Register callback
            >>> modem_status.callback(status_handler)
            >>> 
            >>> # Clear callback later
            >>> # modem_status.callback(None)
    """
    ...


def receive() -> Optional[int]:
    """
    Receive Modem Status frame synchronously.

    Non-blocking call. Returns immediately if queue is empty.

    :return: Modem status code (int), or None if queue is empty.

    Example:
        Polling receive loop::

            >>> from xbee import modem_status
            >>> import time
            >>> 
            >>> while True:
            ...     status = modem_status.receive()
            ...     if status is not None:
            ...         print(f"Modem status received: 0x{status:02X}")
            ...         
            ...         if status == 0x02:
            ...             print("Network joined - ready to communicate")
            ...         elif status == 0x03:
            ...             print("Network left - attempting rejoin...")
            ...     
            ...     time.sleep(0.5)
    """
    ...
