"""requests - higher-level HTTP client (MicroPython).

This module is a (usually small) convenience wrapper around the lower-level
socket/network stack, similar to `urequests`. Compared to CPython `requests`,
feature coverage is limited and varies by port.

Notes
-----
- Always call `Response.close()` when you are done to release the underlying
    socket and free buffers. Not closing responses can leak resources.
- HTTPS/TLS support depends on the `ssl` module and the port's TLS stack.
- Some keyword arguments may be accepted but ignored depending on the build.

Example
-------
```python
    >>> import requests
    >>> 
    >>> # GET request
    >>> r = requests.get('http://example.com/api')
    >>> print(r.status_code)
    >>> print(r.json())
    >>> 
    >>> # POST request
    >>> r = requests.post('http://example.com/api', json={'key': 'value'})
```
"""

from typing import Any, Optional, Union


class Response:
    """
    HTTP Response object.

    Example
    -------
    ```python
        >>> import requests
        >>> 
        >>> r = requests.get('http://example.com')
        >>> print(r.status_code)  # 200
        >>> print(r.text)         # HTML content
        >>> print(r.headers)      # Response headers
    ```
    """

    status_code: int
    """HTTP status code."""

    reason: str
    """Status reason phrase."""

    headers: dict
    """Response headers."""

    encoding: str
    """Response encoding."""

    @property
    def text(self) -> str:
        """
        Response content as string.

        Example
        -------
        ```python
            >>> import requests
            >>> 
            >>> r = requests.get('http://example.com')
            >>> html = r.text
        ```
        """
        ...

    @property
    def content(self) -> bytes:
        """
        Response content as bytes.

        Example
        -------
        ```python
            >>> import requests
            >>> 
            >>> r = requests.get('http://example.com/image.png')
            >>> data = r.content
        ```
        """
        ...

    def json(self) -> Any:
        """
        Parse response as JSON.

        :returns: Parsed JSON data

        Example
        -------
        ```python
            >>> import requests
            >>> 
            >>> r = requests.get('http://api.example.com/data')
            >>> data = r.json()
            >>> print(data['key'])
        ```
        """
        ...

    def close(self) -> None:
        """Close the response and release resources.

        In MicroPython this is often essential to return the socket to the system.
        Prefer using a `try/finally` when reading a response.

        Example
        -------
        ```python
            >>> import requests
            >>> 
            >>> r = requests.get('http://example.com')
            >>> # ... use response ...
            >>> r.close()
        ```
        """
        ...


def get(
    url: str,
    headers: dict = None,
    params: dict = None,
    timeout: float = None,
    **kwargs
) -> Response:
    """
    Send GET request.

    :param url: Request URL
    :param headers: Custom headers
    :param params: URL query parameters
    :param timeout: Request timeout

    :returns: Response object

    Example
    -------
    ```python
        >>> import requests
        >>> 
        >>> r = requests.get('http://example.com/api')
        >>> print(r.json())
        >>> 
        >>> # With parameters
        >>> r = requests.get('http://api.example.com/search',
        ...                  params={'q': 'micropython'})
        >>> 
        >>> # With headers
        >>> r = requests.get('http://api.example.com/data',
        ...                  headers={'Authorization': 'Bearer token'})
    ```
    """
    ...


def post(
    url: str,
    data: Union[bytes, str, dict] = None,
    json: Any = None,
    headers: dict = None,
    timeout: float = None,
    **kwargs
) -> Response:
    """
    Send POST request.

    :param url: Request URL
    :param data: Form data or body
    :param json: JSON data (auto-serialized)
    :param headers: Custom headers
    :param timeout: Request timeout

    :returns: Response object

    Example
    -------
    ```python
        >>> import requests
        >>> 
        >>> # JSON POST
        >>> r = requests.post('http://api.example.com/data',
        ...                   json={'name': 'value'})
        >>> 
        >>> # Form POST
        >>> r = requests.post('http://example.com/login',
        ...                   data={'user': 'admin', 'pass': 'secret'})
    ```
    """
    ...


def put(
    url: str,
    data: Union[bytes, str, dict] = None,
    json: Any = None,
    headers: dict = None,
    timeout: float = None,
    **kwargs
) -> Response:
    """
    Send PUT request.

    :param url: Request URL
    :param data: Body data
    :param json: JSON data
    :param headers: Custom headers
    :param timeout: Request timeout

    :returns: Response object

    Example
    -------
    ```python
        >>> import requests
        >>> 
        >>> r = requests.put('http://api.example.com/item/1',
        ...                  json={'name': 'updated'})
    ```
    """
    ...


def delete(
    url: str,
    headers: dict = None,
    timeout: float = None,
    **kwargs
) -> Response:
    """
    Send DELETE request.

    :param url: Request URL
    :param headers: Custom headers
    :param timeout: Request timeout

    :returns: Response object

    Example
    -------
    ```python
        >>> import requests
        >>> 
        >>> r = requests.delete('http://api.example.com/item/1')
        >>> print(r.status_code)  # 204
    ```
    """
    ...


def head(
    url: str,
    headers: dict = None,
    timeout: float = None,
    **kwargs
) -> Response:
    """
    Send HEAD request.

    :param url: Request URL
    :param headers: Custom headers
    :param timeout: Request timeout

    :returns: Response object

    Example
    -------
    ```python
        >>> import requests
        >>> 
        >>> r = requests.head('http://example.com/file.zip')
        >>> size = r.headers.get('Content-Length')
    ```
    """
    ...


def patch(
    url: str,
    data: Union[bytes, str, dict] = None,
    json: Any = None,
    headers: dict = None,
    timeout: float = None,
    **kwargs
) -> Response:
    """
    Send PATCH request.

    :param url: Request URL
    :param data: Body data
    :param json: JSON data
    :param headers: Custom headers
    :param timeout: Request timeout

    :returns: Response object

    Example
    -------
    ```python
        >>> import requests
        >>> 
        >>> r = requests.patch('http://api.example.com/item/1',
        ...                    json={'field': 'new_value'})
    ```
    """
    ...


def request(
    method: str,
    url: str,
    data: Union[bytes, str, dict] = None,
    json: Any = None,
    headers: dict = None,
    timeout: float = None,
    **kwargs
) -> Response:
    """
    Send HTTP request.

    :param method: HTTP method
    :param url: Request URL
    :param data: Body data
    :param json: JSON data
    :param headers: Custom headers
    :param timeout: Request timeout

    :returns: Response object

    Example
    -------
    ```python
        >>> import requests
        >>> 
        >>> r = requests.request('OPTIONS', 'http://api.example.com/')
    ```
    """
    ...
