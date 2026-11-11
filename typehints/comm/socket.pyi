"""
BSD socket interface.

Network socket operations.

This is a MicroPython subset of the CPython socket API. Supported features and
behaviour (especially around timeouts, DNS resolution, and IPv6) depend on the
port and the underlying network stack.

Example
-------
```python
    >>> import socket
    >>> 
    >>> # TCP client
    >>> s = socket.socket()
    >>> s.connect(('192.168.1.1', 80))
    >>> s.send(b'GET / HTTP/1.0\\r\\n\\r\\n')
    >>> data = s.recv(1024)
    >>> s.close()
```
"""

from typing import Optional, Tuple, Union


# Address family
AF_INET: int
"""IPv4 address family."""

AF_INET6: int
"""IPv6 address family."""

# Socket type
SOCK_STREAM: int
"""TCP socket."""

SOCK_DGRAM: int
"""UDP socket."""

SOCK_RAW: int
"""Raw socket."""

# Protocol
IPPROTO_TCP: int
"""TCP protocol."""

IPPROTO_UDP: int
"""UDP protocol."""

IPPROTO_IP: int
"""IP protocol."""

# Socket options
SOL_SOCKET: int
"""Socket level options."""

SO_REUSEADDR: int
"""Allow address reuse."""

SO_BROADCAST: int
"""Allow broadcast."""

SO_KEEPALIVE: int
"""Enable keep-alive."""

SO_RCVBUF: int
"""Receive buffer size."""

SO_SNDBUF: int
"""Send buffer size."""

# IP options
IP_ADD_MEMBERSHIP: int
"""Join multicast group."""


class socket:
    """
    Network socket.

    Sockets can be used directly via ``send``/``recv`` or as a stream using the
    ``read``/``write`` methods.

    Many operations can raise ``OSError`` (including timeout and connection
    errors). Error codes are port specific.

    Example
    -------
    ```python
        >>> import socket
        >>> 
        >>> # TCP client
        >>> s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        >>> s.connect(('example.com', 80))
        >>> s.send(b'GET / HTTP/1.1\\r\\nHost: example.com\\r\\n\\r\\n')
        >>> response = s.recv(4096)
        >>> s.close()
        >>> 
        >>> # UDP socket
        >>> s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        >>> s.sendto(b'Hello', ('192.168.1.100', 5000))
    ```
    """

    def __init__(
        self,
        af: int = AF_INET,
        type: int = SOCK_STREAM,
        proto: int = IPPROTO_TCP
    ) -> None:
        """
        Create socket.

        For UDP sockets use ``SOCK_DGRAM``. For TCP use ``SOCK_STREAM``.

        :param af: Address family (AF_INET, AF_INET6)
        :param type: Socket type (SOCK_STREAM, SOCK_DGRAM)
        :param proto: Protocol number

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> tcp = socket.socket()
            >>> udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ```
        """
        ...

    def connect(self, address: Tuple[str, int]) -> None:
        """
        Connect to remote address.

        This is usually a blocking call unless the socket is in non-blocking
        mode or has a timeout set.

        :param address: (host, port) tuple

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s = socket.socket()
            >>> s.connect(('192.168.1.1', 80))
        ```
        """
        ...

    def bind(self, address: Tuple[str, int]) -> None:
        """
        Bind to local address.

        For servers, bind to ``('0.0.0.0', port)`` to listen on all interfaces.

        :param address: (host, port) tuple

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s = socket.socket()
            >>> s.bind(('0.0.0.0', 8080))
        ```
        """
        ...

    def listen(self, backlog: int = 1) -> None:
        """
        Start listening for connections.

        Only valid for TCP sockets.

        :param backlog: Queue size for pending connections

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s = socket.socket()
            >>> s.bind(('0.0.0.0', 8080))
            >>> s.listen(5)
        ```
        """
        ...

    def accept(self) -> Tuple['socket', Tuple[str, int]]:
        """
        Accept incoming connection.

        Blocks until connection arrives.

        The returned socket represents the accepted client connection.

        :returns: (new_socket, (host, port)) tuple

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> server = socket.socket()
            >>> server.bind(('0.0.0.0', 8080))
            >>> server.listen(1)
            >>> 
            >>> client, addr = server.accept()
            >>> print(f"Connection from {addr}")
        ```
        """
        ...

    def send(self, data: bytes) -> int:
        """
        Send data on connected socket.

        ``send()`` may send fewer bytes than requested; handle the return value
        or use ``sendall()``.

        :param data: Data to send

        :returns: Number of bytes sent

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s.send(b'Hello, World!')
        ```
        """
        ...

    def sendall(self, data: bytes) -> None:
        """
        Send all data (blocking).

        Continues sending until all bytes are sent or an error occurs.

        :param data: Data to send

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s.sendall(b'Hello, World!')
        ```
        """
        ...

    def sendto(self, data: bytes, address: Tuple[str, int]) -> int:
        """
        Send data to address (UDP).

        This is typically used with ``SOCK_DGRAM`` sockets.

        :param data: Data to send
        :param address: (host, port) tuple

        :returns: Number of bytes sent

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            >>> s.sendto(b'Hello', ('192.168.1.100', 5000))
        ```
        """
        ...

    def recv(self, bufsize: int) -> bytes:
        """
        Receive data from socket.

        For TCP, an empty bytes object can indicate the connection was closed.

        :param bufsize: Maximum bytes to receive

        :returns: Received data

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> data = s.recv(1024)
            >>> print(data)
        ```
        """
        ...

    def recvfrom(self, bufsize: int) -> Tuple[bytes, Tuple[str, int]]:
        """
        Receive data and sender address (UDP).

        :param bufsize: Maximum bytes to receive

        :returns: (data, (host, port)) tuple

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> data, addr = s.recvfrom(1024)
            >>> print(f"From {addr}: {data}")
        ```
        """
        ...

    def read(self, size: int = -1) -> bytes:
        """
        Read data (stream interface).

        This is a convenience wrapper compatible with stream semantics.

        :param size: Bytes to read (-1 for available)

        :returns: Read data

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> data = s.read(100)
        ```
        """
        ...

    def readinto(self, buf: bytearray) -> int:
        """
        Read into pre-allocated buffer.

        Using a pre-allocated buffer can reduce heap allocations.

        :param buf: Target buffer

        :returns: Number of bytes read

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> buf = bytearray(1024)
            >>> n = s.readinto(buf)
        ```
        """
        ...

    def readline(self) -> bytes:
        """
        Read line from socket.

        Line endings are not translated; returned data includes the newline if
        present.

        :returns: Line including newline

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> line = s.readline()
        ```
        """
        ...

    def write(self, data: bytes) -> int:
        """
        Write data (stream interface).

        Like ``send()``, this may write fewer bytes than requested.

        :param data: Data to write

        :returns: Bytes written

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s.write(b'Hello')
        ```
        """
        ...

    def close(self) -> None:
        """
        Close socket.

        Always close sockets when done to free resources.

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s.close()
        ```
        """
        ...

    def settimeout(self, value: Optional[float]) -> None:
        """
        Set socket timeout.

        - ``None``: blocking mode (wait indefinitely)
        - ``0``: non-blocking mode
        - ``> 0``: timeout in seconds

        :param value: Timeout in seconds (None = blocking)

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s.settimeout(5.0)   # 5 second timeout
            >>> s.settimeout(None)  # Blocking
            >>> s.settimeout(0)     # Non-blocking
        ```
        """
        ...

    def setblocking(self, flag: bool) -> None:
        """
        Set blocking mode.

        Equivalent to calling ``settimeout(None)`` (blocking) or ``settimeout(0)``
        (non-blocking).

        :param flag: True for blocking

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s.setblocking(False)  # Non-blocking
        ```
        """
        ...

    def setsockopt(self, level: int, optname: int, value: Union[int, bytes]) -> None:
        """
        Set socket option.

        Supported options vary by port/stack.

        :param level: Option level (SOL_SOCKET, etc.)
        :param optname: Option name
        :param value: Option value

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ```
        """
        ...

    def makefile(self, mode: str = 'rb', buffering: int = 0) -> object:
        """
        Create file-like object from socket.

        This can be helpful for line-oriented protocols using ``readline()``.

        :param mode: File mode ('rb', 'wb', etc.)
        :param buffering: Buffer size

        :returns: File-like object

        Example
        -------
        ```python
            >>> import socket
            >>> 
            >>> f = s.makefile('rwb')
            >>> f.write(b'Hello\\n')
            >>> line = f.readline()
        ```
        """
        ...


def getaddrinfo(
    host: str,
    port: int,
    af: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0
) -> list:
    """
    Resolve host name to address.

    Some ports only support a subset of arguments. The returned sockaddr is
    suitable to pass to ``connect()``/``sendto()``.

    :param host: Host name or IP
    :param port: Port number
    :param af: Address family filter
    :param type: Socket type filter
    :param proto: Protocol filter
    :param flags: Resolver flags

    :returns: List of (family, type, proto, canonname, sockaddr) tuples

    Example
    -------
    ```python
        >>> import socket
        >>> 
        >>> info = socket.getaddrinfo('example.com', 80)
        >>> family, type, proto, canon, sockaddr = info[0]
        >>> 
        >>> s = socket.socket(family, type, proto)
        >>> s.connect(sockaddr)
    ```
    """
    ...


def inet_aton(ip_string: str) -> bytes:
    """
    Convert IP string to 4 bytes.

    Only supports IPv4 dotted-quad strings.

    :param ip_string: IP address string

    :returns: 4-byte address

    Example
    -------
    ```python
        >>> import socket
        >>> 
        >>> socket.inet_aton('192.168.1.1')
        ... # b'\\xc0\\xa8\\x01\\x01'
    ```
    """
    ...


def inet_ntoa(packed_ip: bytes) -> str:
    """
    Convert 4 bytes to IP string.

    Only supports IPv4 packed addresses.

    :param packed_ip: 4-byte address

    :returns: IP string

    Example
    -------
    ```python
        >>> import socket
        >>> 
        >>> socket.inet_ntoa(b'\\xc0\\xa8\\x01\\x01')
        ... # '192.168.1.1'
    ```
    """
    ...
