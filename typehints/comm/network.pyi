"""
Network configuration.

Configure WiFi and Ethernet interfaces.

This module is highly port/board dependent: available interfaces, supported
security modes, and configuration options can vary.

Example
-------
```python
    >>> import network
    >>> 
    >>> # Connect to WiFi
    >>> wlan = network.WLAN(network.STA_IF)
    >>> wlan.active(True)
    >>> wlan.connect('MySSID', 'password')
    >>> 
    >>> # Wait for connection
    >>> while not wlan.isconnected():
    ...     pass
    >>> print(wlan.ifconfig())
```
"""

from typing import Any, Optional, Tuple, Union


# Interface modes
STA_IF: int
"""Station (client) interface."""

AP_IF: int
"""Access point interface."""

# Authentication modes
AUTH_OPEN: int
"""Open (no authentication)."""

AUTH_WEP: int
"""WEP authentication."""

AUTH_WPA_PSK: int
"""WPA-PSK authentication."""

AUTH_WPA2_PSK: int
"""WPA2-PSK authentication."""

AUTH_WPA_WPA2_PSK: int
"""WPA/WPA2-PSK mixed."""

# Status values
STAT_IDLE: int
"""Idle, not connected."""

STAT_CONNECTING: int
"""Connecting."""

STAT_WRONG_PASSWORD: int
"""Wrong password."""

STAT_NO_AP_FOUND: int
"""Access point not found."""

STAT_CONNECT_FAIL: int
"""Connection failed."""

STAT_GOT_IP: int
"""Connected, got IP."""


class WLAN:
    """
    WiFi interface controller.

    The WLAN interface is typically used in one of two modes:

    - Station mode (``STA_IF``): connect to an existing access point.
    - Access point mode (``AP_IF``): create an access point for other clients.

    Many operations may raise ``OSError`` if the underlying driver reports an
    error (e.g. authentication failure, unsupported configuration, etc.).

    Example
    -------
    ```python
        >>> import network
        >>> 
        >>> # Station mode (connect to AP)
        >>> wlan = network.WLAN(network.STA_IF)
        >>> wlan.active(True)
        >>> wlan.connect('MyNetwork', 'password')
        >>> 
        >>> while not wlan.isconnected():
        ...     pass
        >>> 
        >>> ip, subnet, gateway, dns = wlan.ifconfig()
        >>> print(f"IP: {ip}")
    ```
    """

    def __init__(self, interface_id: int) -> None:
        """
        Create WLAN interface.

        The returned object is usually a singleton per interface id.

        :param interface_id: STA_IF or AP_IF

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> sta = network.WLAN(network.STA_IF)
            >>> ap = network.WLAN(network.AP_IF)
        ```
        """
        ...

    def active(self, is_active: bool = None) -> Optional[bool]:
        """
        Get or set interface active state.

        An interface generally needs to be active before scanning, connecting,
        or creating an access point.

        :param is_active: True to activate (None to query)

        :returns: Current state if querying

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> wlan = network.WLAN(network.STA_IF)
            >>> wlan.active(True)   # Activate
            >>> wlan.active()       # Query: True
        ```
        """
        ...

    def connect(self, ssid: str, key: str = None, *, bssid: bytes = None) -> None:
        """
        Connect to WiFi network.

        Connection is usually asynchronous: after calling ``connect()``, poll
        ``isconnected()`` or check ``status()`` until the interface reports it
        is connected.

        :param ssid: Network name
        :param key: Password (None for open)
        :param bssid: Specific AP MAC address

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> wlan = network.WLAN(network.STA_IF)
            >>> wlan.active(True)
            >>> wlan.connect('MyNetwork', 'password123')
        ```
        """
        ...

    def disconnect(self) -> None:
        """
        Disconnect from network.

        This requests disconnection; depending on the port it may take a short
        time for the interface to actually drop the link.

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> wlan.disconnect()
        ```
        """
        ...

    def isconnected(self) -> bool:
        """
        Check connection status.

        In station mode this typically indicates both link + IP configuration.

        :returns: True if connected with IP

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> if wlan.isconnected():
            ...     print("Connected!")
        ```
        """
        ...

    def status(self, param: str = None) -> Union[int, str]:
        """
        Get connection status.

        Without arguments, returns a numeric status (often one of the
        ``STAT_*`` constants). Some ports support string parameters such as
        ``'rssi'``.

        :param param: Specific parameter (None for general status)

        :returns: Status value or parameter

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> status = wlan.status()
            >>> if status == network.STAT_GOT_IP:
            ...     print("Connected")
            >>> 
            >>> rssi = wlan.status('rssi')
            >>> print(f"Signal: {rssi} dBm")
        ```
        """
        ...

    def ifconfig(self, config: Tuple[str, str, str, str] = None) -> Optional[Tuple[str, str, str, str]]:
        """
        Get or set IP configuration.

        With no argument, returns a 4-tuple ``(ip, netmask, gateway, dns)``.
        Passing a tuple configures a static IP configuration.

        :param config: (ip, subnet, gateway, dns) tuple

        :returns: Current config if querying

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> # Get config
            >>> ip, subnet, gw, dns = wlan.ifconfig()
            >>> print(f"IP: {ip}")
            >>> 
            >>> # Set static IP
            >>> wlan.ifconfig(('192.168.1.100', '255.255.255.0', 
            ...                '192.168.1.1', '8.8.8.8'))
        ```
        """
        ...

    def config(self, **kwargs) -> Union[str, bytes, int, None]:
        """
        Get or set configuration parameters.

        Parameters: mac, ssid, channel, hidden, password,
                   authmode, hostname, txpower, pm

        Supported keys vary by port and by interface mode (STA vs AP). When
        requesting a value, some ports use ``wlan.config('param')``.

        :param kwargs: Parameters to set

        :returns: Parameter value if getting

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> # Get MAC address
            >>> mac = wlan.config('mac')
            >>> 
            >>> # Set hostname
            >>> wlan.config(hostname='my-pico')
            >>> 
            >>> # AP mode config
            >>> ap = network.WLAN(network.AP_IF)
            >>> ap.config(ssid='MyAP', password='12345678')
        ```
        """
        ...

    def scan(self) -> list[Tuple[bytes, bytes, int, int, int, bool]]:
        """
        Scan for WiFi networks.

        Returns a list of tuples containing:
        ``(ssid, bssid, channel, rssi, authmode, hidden)``.

        The SSID is returned as bytes; decode with ``ssid.decode()``.

        :returns: List of (ssid, bssid, channel, rssi, authmode, hidden)

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> wlan = network.WLAN(network.STA_IF)
            >>> wlan.active(True)
            >>> 
            >>> for ssid, bssid, ch, rssi, auth, hidden in wlan.scan():
            ...     print(f"{ssid.decode()}: {rssi}dBm")
        ```
        """
        ...


class LAN:
    """
    Ethernet LAN interface (if available).

    Availability and constructor parameters are port dependent.

    Example
    -------
    ```python
        >>> import network
        >>> 
        >>> lan = network.LAN()
        >>> lan.active(True)
        >>> 
        >>> while not lan.isconnected():
        ...     pass
        >>> print(lan.ifconfig())
    ```
    """

    def __init__(
        self,
        *,
        mdc: int = None,
        mdio: int = None,
        phy_type: int = None,
        phy_addr: int = None
    ) -> None:
        """
        Create LAN interface.

        :param mdc: MDC pin
        :param mdio: MDIO pin
        :param phy_type: PHY type
        :param phy_addr: PHY address

        Example
        -------
        ```python
            >>> import network
            >>> 
            >>> lan = network.LAN()
        ```
        """
        ...

    def active(self, is_active: bool = None) -> Optional[bool]:
        """Get or set active state.

        Activate the interface before attempting to use it.
        """
        ...

    def isconnected(self) -> bool:
        """Check if connected.

        Returns True if the link is up and the interface has network
        connectivity (exact semantics are port dependent).
        """
        ...

    def ifconfig(self, config: Tuple[str, str, str, str] = None) -> Optional[Tuple[str, str, str, str]]:
        """Get or set IP configuration.

        With no argument, returns ``(ip, netmask, gateway, dns)``.
        With a tuple argument, sets a static IP configuration.
        """
        ...

    def config(self, **kwargs) -> Union[str, bytes, int, None]:
        """Get or set parameters.

        Supported parameters vary by port.
        """
        ...


def hostname(name: str = None) -> Optional[str]:
    """
    Get or set system hostname.

    The hostname is used by some network stacks for DHCP and/or mDNS.

    :param name: New hostname (None to query)

    :returns: Current hostname if querying

    Example
    -------
    ```python
        >>> import network
        >>> 
        >>> network.hostname('my-pico')
        >>> print(network.hostname())  # 'my-pico'
    ```
    """
    ...


def country(code: str = None) -> Optional[str]:
    """
    Get or set WiFi country code.

    The country code affects regulatory settings such as allowed channels and
    transmit power. Support is port dependent.

    :param code: 2-letter country code

    :returns: Current code if querying

    Example
    -------
    ```python
        >>> import network
        >>> 
        >>> network.country('US')
        >>> network.country('KR')
    ```
    """
    ...


def ipconfig(*args: Any, **kwargs: Any) -> Any:
    """
    Get or set global IP-configuration parameters.

    Supported parameters:

    * ``dns`` – Get/set DNS server (supports IPv4 and IPv6 addresses).
    * ``prefer`` (``4`` or ``6``) – Specify which address family to return
      when a domain name has both A and AAAA records.

    :returns: Parameter value when called as getter, ``None`` when setting.

    Example
    -------
    ```python
        >>> import network
        >>> 
        >>> # Get current DNS server
        >>> network.ipconfig('dns')
        '8.8.8.8'
        >>> # Set DNS server
        >>> network.ipconfig(dns='8.8.4.4')
        >>> # Prefer IPv4 when both A and AAAA records exist
        >>> network.ipconfig(prefer=4)
    ```
    """
    ...


def route(*args: Any, **kwargs: Any) -> Any:
    """
    Get or set entries in the routing table.

    When called with no arguments, returns the current routing table.

    Example
    -------
    ```python
        >>> import network
        >>> 
        >>> network.route()
    ```
    """
    ...


class AbstractNIC:
    """
    Abstract base class for network interface objects.

    Provides the common interface that all MicroPython network drivers
    must implement (``WLAN``, ``LAN``, etc.).

    Example
    -------
    ```python
        >>> import network
        >>> 
        >>> nic = network.WLAN(network.STA_IF)  # concrete subclass
        >>> nic.active(True)
        >>> nic.connect('ssid', 'password')
    ```
    """

    def active(self, is_active: Optional[bool] = None) -> Optional[bool]:
        """
        Activate or deactivate the interface.  Without arguments, query
        the current state.

        :param is_active: ``True`` to activate, ``False`` to deactivate.
        :returns: Current state when called with no arguments.

        Example
        -------
        ```python
            >>> nic.active(True)
            >>> nic.active()
            True
        ```
        """
        ...

    def connect(self, service_id: Any = None, key: Optional[str] = None, **kwargs: Any) -> None:
        """
        Connect to a network.  Optional on always-connected interfaces.

        :param service_id: Network identifier (e.g. SSID).
        :param key: Authentication credential (e.g. password).

        Example
        -------
        ```python
            >>> nic.connect('MySSID', 'password')
        ```
        """
        ...

    def disconnect(self) -> None:
        """
        Disconnect from the current network.

        Example
        -------
        ```python
            >>> nic.disconnect()
        ```
        """
        ...

    def isconnected(self) -> bool:
        """
        Return ``True`` if connected to a network.

        :returns: Connection state.

        Example
        -------
        ```python
            >>> while not nic.isconnected():
            ...     pass
        ```
        """
        ...

    def status(self, param: Optional[str] = None) -> Any:
        """
        Query dynamic status of the interface.  With no argument, return
        the network link status.  Pass a string parameter name for specific
        values (e.g. ``'rssi'``, ``'stations'``).

        :param param: Optional status parameter name.
        :returns: Status value.

        Example
        -------
        ```python
            >>> nic.status('rssi')
            -55
        ```
        """
        ...

    def ifconfig(self, ip_mask_gw_dns: Optional[Tuple[str, str, str, str]] = None) -> Optional[Tuple[str, str, str, str]]:
        """
        Get or set IP-level parameters (IP, subnet mask, gateway, DNS).
        Deprecated – prefer ``ipconfig()``.

        :param ip_mask_gw_dns: 4-tuple to set, omit to get.
        :returns: Current IP configuration 4-tuple when called with no args.

        Example
        -------
        ```python
            >>> nic.ifconfig()
            ('192.168.1.5', '255.255.255.0', '192.168.1.1', '8.8.8.8')
            >>> nic.ifconfig(('192.168.1.10', '255.255.255.0', '192.168.1.1', '8.8.8.8'))
        ```
        """
        ...

    def ipconfig(self, *args: Any, **kwargs: Any) -> Any:
        """
        Get or set interface-level IP-configuration parameters.

        :returns: Parameter value when used as getter.

        Example
        -------
        ```python
            >>> nic.ipconfig('addr4')
            ('192.168.1.5', 24)
        ```
        """
        ...

    def config(self, param: Optional[str] = None, **kwargs: Any) -> Any:
        """
        Get or set general network interface parameters.

        :param param: Parameter name string to query.
        :returns: Parameter value when called as getter.

        Example
        -------
        ```python
            >>> nic.config('mac')
            b'\\xde\\xad\\xbe\\xef\\x00\\x01'
            >>> nic.config(txpower=20)
        ```
        """
        ...


class WLANWiPy:
    """
    WiPy-specific WLAN class.

    Provides the WLAN interface for WiPy boards with WiPy-specific extensions.

    Example
    -------
    ```python
        >>> import network
        >>> 
        >>> wlan = network.WLANWiPy(network.STA_IF)
        >>> wlan.active(True)
        >>> wlan.connect('MySSID', auth=(network.WPA2, 'password'))
    ```
    """

    STA: int
    AP: int
    WEP: int
    WPA: int
    WPA2: int
    INT_ANT: int
    EXT_ANT: int

    def __init__(self, mode: int, *, ssid: Optional[str] = None, auth: Optional[tuple] = None,
                 channel: int = 1, antenna: int = 0) -> None:
        """
        Create a WLANWiPy object.

        :param mode: ``STA`` or ``AP``.
        :param ssid: SSID for AP mode.
        :param auth: Authentication tuple ``(security, password)``.
        :param channel: WiFi channel (AP mode).
        :param antenna: Antenna selection.

        Example
        -------
        ```python
            >>> wlan = network.WLANWiPy(network.STA_IF)
        ```
        """
        ...

    def active(self, is_active: Optional[bool] = None) -> Optional[bool]:
        """
        Activate or deactivate the WLAN interface.

        Example
        -------
        ```python
            >>> wlan.active(True)
        ```
        """
        ...

    def connect(self, ssid: str, *, auth: Optional[tuple] = None,
                bssid: Optional[bytes] = None, timeout: Optional[int] = None) -> None:
        """
        Connect to a WiFi network.

        :param ssid: Network SSID.
        :param auth: Authentication tuple ``(security, password)``.
        :param bssid: Target AP MAC address.
        :param timeout: Connection timeout in milliseconds.

        Example
        -------
        ```python
            >>> wlan.connect('MySSID', auth=(network.WPA2, 'password'))
        ```
        """
        ...

    def disconnect(self) -> None:
        """
        Disconnect from the current network.

        Example
        -------
        ```python
            >>> wlan.disconnect()
        ```
        """
        ...

    def isconnected(self) -> bool:
        """
        Return ``True`` if connected to an AP.

        :returns: Connection state.

        Example
        -------
        ```python
            >>> wlan.isconnected()
            True
        ```
        """
        ...

    def ifconfig(self, config: Optional[Any] = None) -> Optional[tuple]:
        """
        Get or set IP configuration.

        :param config: ``'dhcp'`` or 4-tuple ``(ip, mask, gw, dns)``.
        :returns: Current configuration tuple when called with no args.

        Example
        -------
        ```python
            >>> wlan.ifconfig()
            ('192.168.1.5', '255.255.255.0', '192.168.1.1', '8.8.8.8')
        ```
        """
        ...

    def mode(self, mode: Optional[int] = None) -> Optional[int]:
        """
        Get or set the WLAN mode.

        :param mode: ``STA`` or ``AP``.
        :returns: Current mode when called with no args.

        Example
        -------
        ```python
            >>> wlan.mode(network.STA_IF)
        ```
        """
        ...

    def ssid(self, ssid: Optional[str] = None) -> Optional[str]:
        """
        Get or set the SSID.

        Example
        -------
        ```python
            >>> wlan.ssid()
            'MySSID'
        ```
        """
        ...

    def auth(self, auth: Optional[tuple] = None) -> Optional[tuple]:
        """
        Get or set the authentication configuration.

        :param auth: Authentication tuple ``(security, password)``.
        :returns: Current auth tuple when called with no args.

        Example
        -------
        ```python
            >>> wlan.auth()
            (3, 'password')
        ```
        """
        ...

    def channel(self, channel: Optional[int] = None) -> Optional[int]:
        """
        Get or set the WiFi channel.

        Example
        -------
        ```python
            >>> wlan.channel(6)
        ```
        """
        ...

    def antenna(self, antenna: Optional[int] = None) -> Optional[int]:
        """
        Get or set the antenna selection.

        Example
        -------
        ```python
            >>> wlan.antenna(network.EXT_ANT)
        ```
        """
        ...

    def mac(self) -> bytes:
        """
        Return the MAC address as a 6-byte bytes object.

        :returns: MAC address.

        Example
        -------
        ```python
            >>> wlan.mac()
            b'\\xde\\xad\\xbe\\xef\\x00\\x01'
        ```
        """
        ...

    def scan(self) -> list:
        """
        Scan for available networks.

        :returns: List of tuples ``(ssid, bssid, channel, rssi, security)``.

        Example
        -------
        ```python
            >>> for net in wlan.scan():
            ...     print(net)
        ```
        """
        ...
