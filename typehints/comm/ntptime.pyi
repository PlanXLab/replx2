"""ntptime - simple NTP client.

This module can query an NTP server and optionally set the device's RTC.

Notes
-----
- Network connectivity must be configured before calling `settime()`.
- `settime()` typically sets the RTC to UTC.
- MicroPython's `time` module often uses a different epoch internally (commonly
    2000-01-01). `ntptime.time()` returns a Unix timestamp (1970-01-01) and
    `settime()` handles the conversion where applicable.

Example
-------
```python
    >>> import ntptime
    >>> import machine
    >>> 
    >>> ntptime.settime()
    >>> # RTC is now synced with NTP
```
"""


host: str
"""NTP server hostname (default: 'pool.ntp.org')."""

timeout: int
"""Request timeout in seconds."""


def time() -> int:
    """
    Get NTP time as Unix timestamp.

    :returns: Seconds since 1970-01-01

    Example
    -------
    ```python
        >>> import ntptime
        >>> 
        >>> timestamp = ntptime.time()
        >>> print(timestamp)
    ```
    """
    ...


def settime() -> None:
    """Synchronize the RTC to current NTP time.

    :raises OSError: On DNS lookup failure, UDP/socket errors, or timeouts.

    Example
    -------
    ```python
        >>> import ntptime
        >>> import network
        >>> 
        >>> # Connect to WiFi first
        >>> wlan = network.WLAN(network.STA_IF)
        >>> wlan.active(True)
        >>> wlan.connect('SSID', 'password')
        >>> while not wlan.isconnected():
        ...     pass
        >>> 
        >>> # Sync time
        >>> ntptime.settime()
        >>> 
        >>> # Now RTC is accurate
        >>> import time
        >>> print(time.localtime())
    ```
    """
    ...
