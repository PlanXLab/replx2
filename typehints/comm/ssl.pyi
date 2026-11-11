"""
SSL/TLS wrapper for socket objects.

Secure socket layer encryption.

This module provides a small subset of CPython's ``ssl`` API. Feature support
and certificate handling are port dependent (e.g. availability of CA stores,
server-side TLS, and SNI).

Example
-------
```python
    >>> import ssl
    >>> import socket
    >>> 
    >>> s = socket.socket()
    >>> s.connect(('www.example.com', 443))
    >>> 
    >>> ssl_sock = ssl.wrap_socket(s)
    >>> ssl_sock.write(b'GET / HTTP/1.1\\r\\nHost: www.example.com\\r\\n\\r\\n')
    >>> data = ssl_sock.read(4096)
```
"""

from typing import Optional, Tuple, Union


# Protocol versions
PROTOCOL_TLS: int
"""Generic TLS protocol."""

PROTOCOL_TLS_CLIENT: int
"""TLS client protocol."""

PROTOCOL_TLS_SERVER: int
"""TLS server protocol."""

# Certificate requirements
CERT_NONE: int
"""No certificate required."""

CERT_OPTIONAL: int
"""Certificate optional."""

CERT_REQUIRED: int
"""Certificate required."""


class SSLContext:
    """
    SSL/TLS context for managing settings.

    Context objects hold shared TLS configuration such as certificate
    verification and loaded key/cert material.

    Example
    -------
    ```python
        >>> import ssl
        >>> 
        >>> ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        >>> ctx.verify_mode = ssl.CERT_REQUIRED
        >>> ctx.load_cert_chain('cert.pem', 'key.pem')
    ```
    """

    def __init__(self, protocol: int = PROTOCOL_TLS_CLIENT) -> None:
        """
        Create SSL context.

        The default protocol is typically the client-side TLS configuration.

        :param protocol: Protocol version

        Example
        -------
        ```python
            >>> import ssl
            >>> 
            >>> ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ```
        """
        ...

    verify_mode: int
    """Certificate verification mode."""

    def load_cert_chain(self, certfile: str, keyfile: str = None) -> None:
        """
        Load certificate chain.

        Used for server-side TLS and (where supported) client certificate
        authentication.

        :param certfile: Certificate file path
        :param keyfile: Key file path (optional)

        Example
        -------
        ```python
            >>> import ssl
            >>> 
            >>> ctx = ssl.SSLContext()
            >>> ctx.load_cert_chain('/certs/cert.pem', '/certs/key.pem')
        ```
        """
        ...

    def load_verify_locations(self, cafile: str = None, cadata: bytes = None) -> None:
        """
        Load CA certificates for verification.

        Some ports only support ``cadata`` or only support a single CA.

        :param cafile: CA file path
        :param cadata: CA certificate data

        Example
        -------
        ```python
            >>> import ssl
            >>> 
            >>> ctx = ssl.SSLContext()
            >>> ctx.load_verify_locations(cafile='/certs/ca.pem')
        ```
        """
        ...

    def wrap_socket(
        self,
        sock: object,
        server_side: bool = False,
        do_handshake_on_connect: bool = True,
        server_hostname: str = None
    ) -> 'SSLSocket':
        """
        Wrap socket with SSL.

        If ``do_handshake_on_connect`` is True, the TLS handshake is performed
        immediately. Otherwise, the handshake may be performed lazily on first
        I/O depending on the port.

        :param sock: Socket to wrap
        :param server_side: Server mode
        :param do_handshake_on_connect: Immediate handshake
        :param server_hostname: Server hostname for SNI

        :returns: SSL-wrapped socket

        Example
        -------
        ```python
            >>> import ssl
            >>> import socket
            >>> 
            >>> ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            >>> s = socket.socket()
            >>> s.connect(('example.com', 443))
            >>> ssl_sock = ctx.wrap_socket(s, server_hostname='example.com')
        ```
        """
        ...


class SSLSocket:
    """
    SSL-wrapped socket.

    Provides a file-like interface over the encrypted transport.

    Example
    -------
    ```python
        >>> import ssl
        >>> 
        >>> ssl_sock = ssl.wrap_socket(sock)
        >>> ssl_sock.write(b'Hello')
        >>> data = ssl_sock.read(1024)
    ```
    """

    def read(self, size: int = -1) -> bytes:
        """
        Read decrypted data.

        Returns decrypted application data. Behaviour for ``size=-1`` is
        port-specific.

        :param size: Max bytes to read

        :returns: Decrypted data

        Example
        -------
        ```python
            >>> import ssl
            >>> 
            >>> data = ssl_sock.read(1024)
        ```
        """
        ...

    def readinto(self, buf: bytearray) -> int:
        """
        Read into buffer.

        Using a pre-allocated buffer can reduce heap allocations.

        :param buf: Target buffer

        :returns: Bytes read

        Example
        -------
        ```python
            >>> import ssl
            >>> 
            >>> buf = bytearray(1024)
            >>> n = ssl_sock.readinto(buf)
        ```
        """
        ...

    def readline(self) -> bytes:
        """
        Read one line.

        :returns: Line data

        Example
        -------
        ```python
            >>> import ssl
            >>> 
            >>> line = ssl_sock.readline()
        ```
        """
        ...

    def write(self, data: bytes) -> int:
        """
        Write encrypted data.

        Returns the number of application bytes accepted for sending.

        :param data: Data to encrypt and send

        :returns: Bytes written

        Example
        -------
        ```python
            >>> import ssl
            >>> 
            >>> ssl_sock.write(b'GET / HTTP/1.1\\r\\n\\r\\n')
        ```
        """
        ...

    def close(self) -> None:
        """
        Close SSL connection.

        Example
        -------
        ```python
            >>> import ssl
            >>> 
            >>> ssl_sock.close()
        ```
        """
        ...

    def getpeercert(self, binary_form: bool = False) -> Union[dict, bytes, None]:
        """
        Get peer certificate.

        Support varies by port: some return ``None`` or a minimal dict.

        :param binary_form: Return as DER bytes

        :returns: Certificate dict or bytes

        Example
        -------
        ```python
            >>> import ssl
            >>> 
            >>> cert = ssl_sock.getpeercert()
            >>> print(cert)
        ```
        """
        ...


def wrap_socket(
    sock: object,
    server_side: bool = False,
    keyfile: str = None,
    certfile: str = None,
    cert_reqs: int = CERT_NONE,
    cadata: bytes = None,
    server_hostname: str = None,
    do_handshake_on_connect: bool = True
) -> SSLSocket:
    """
    Wrap socket with SSL/TLS.

    Convenience wrapper that creates an ``SSLContext`` under the hood.
    Prefer using ``SSLContext.wrap_socket`` when you need to reuse settings.

    :param sock: Socket to wrap
    :param server_side: Server mode
    :param keyfile: Private key file
    :param certfile: Certificate file
    :param cert_reqs: Certificate requirements
    :param cadata: CA certificate data
    :param server_hostname: Server hostname for SNI
    :param do_handshake_on_connect: Immediate handshake

    :returns: SSL-wrapped socket

    Example
    -------
    ```python
        >>> import ssl
        >>> import socket
        >>> 
        >>> s = socket.socket()
        >>> s.connect(('www.example.com', 443))
        >>> 
        >>> ssl_sock = ssl.wrap_socket(s, server_hostname='www.example.com')
        >>> ssl_sock.write(b'GET / HTTP/1.1\\r\\nHost: www.example.com\\r\\n\\r\\n')
    ```
    """
    ...
