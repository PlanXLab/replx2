"""tls - TLS/SSL wrapper (alias of `ssl`).

Some MicroPython builds provide a `tls` module as a compatibility alias for the
`ssl` module. The public API is typically re-exported from `ssl`.

Notes
-----
- Availability and feature set are port-dependent.
- For details and supported arguments, refer to `ssl` in this typehint set.

Example
-------
```python
    >>> import tls
    >>> import socket
    >>> 
    >>> s = socket.socket()
    >>> s.connect(('www.example.com', 443))
    >>> 
    >>> ssl_sock = tls.wrap_socket(s)
    >>> ssl_sock.write(b'GET / HTTP/1.1\\r\\nHost: www.example.com\\r\\n\\r\\n')
```
"""

from ssl import *
