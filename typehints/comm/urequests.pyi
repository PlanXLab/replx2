"""
MicroPython HTTP requests library.

Lightweight HTTP client (urequests is an alias/predecessor of requests).

This module is designed to be small and allocation-friendly. It intentionally
implements only a subset of CPython's ``requests`` API. Keyword arguments and
TLS/certificate support vary by port and by the underlying socket/SSL stack.

Example
-------
```python
    >>> import urequests
    >>> 
    >>> r = urequests.get('http://example.com')
    >>> print(r.text)
    >>> r.close()
```
"""

from typing import Any, Optional, Union


class Response:
    """
    HTTP Response object.

    Always call ``close()`` when you are done to release the underlying socket.

    Example
    -------
    ```python
        >>> import urequests
        >>> 
        >>> r = urequests.get('http://example.com')
        >>> print(r.status_code)
        >>> print(r.text)
        >>> r.close()
    ```
    """

    status_code: int
    """HTTP status code."""

    reason: str
    """Status reason phrase."""

    @property
    def text(self) -> str:
        """
        Response content as string.

        The decoding used is implementation-defined; for binary payloads prefer
        ``content``.

        Example
        -------
        ```python
            >>> import urequests
            >>> 
            >>> r = urequests.get('http://example.com')
            >>> print(r.text)
        ```
        """
        ...

    @property
    def content(self) -> bytes:
        """
        Response content as bytes.

        Accessing ``content`` may read the full response body into memory.

        Example
        -------
        ```python
            >>> import urequests
            >>> 
            >>> r = urequests.get('http://example.com/data')
            >>> data = r.content
        ```
        """
        ...

    def json(self) -> Any:
        """
        Parse response as JSON.

        This is a convenience wrapper over ``json.loads()``.

        :returns: Parsed JSON data

        Example
        -------
        ```python
            >>> import urequests
            >>> 
            >>> r = urequests.get('http://api.example.com/data')
            >>> data = r.json()
        ```
        """
        ...

    def close(self) -> None:
        """
        Close response and release resources.

        Always call close() when done with the response.

        Example
        -------
        ```python
            >>> import urequests
            >>> 
            >>> r = urequests.get('http://example.com')
            >>> # ... use response ...
            >>> r.close()
        ```
        """
        ...


def get(url: str, **kwargs) -> Response:
    """
    Send GET request.

    Common keyword arguments include ``headers``, ``data``, ``json``, and
    timeouts, but supported kwargs are port dependent.

    :param url: Request URL

    :returns: Response object

    Example
    -------
    ```python
        >>> import urequests
        >>> 
        >>> r = urequests.get('http://example.com/api')
        >>> print(r.json())
        >>> r.close()
    ```
    """
    ...


def post(url: str, **kwargs) -> Response:
    """
    Send POST request.

    Payload may be provided via ``data=...`` or ``json=...`` (port dependent).

    :param url: Request URL

    :returns: Response object

    Example
    -------
    ```python
        >>> import urequests
        >>> 
        >>> r = urequests.post('http://api.example.com/data',
        ...                    json={'key': 'value'})
        >>> r.close()
    ```
    """
    ...


def put(url: str, **kwargs) -> Response:
    """
    Send PUT request.

    :param url: Request URL

    :returns: Response object

    Example
    -------
    ```python
        >>> import urequests
        >>> 
        >>> r = urequests.put('http://api.example.com/item/1',
        ...                   json={'updated': True})
        >>> r.close()
    ```
    """
    ...


def delete(url: str, **kwargs) -> Response:
    """
    Send DELETE request.

    :param url: Request URL

    :returns: Response object

    Example
    -------
    ```python
        >>> import urequests
        >>> 
        >>> r = urequests.delete('http://api.example.com/item/1')
        >>> print(r.status_code)
        >>> r.close()
    ```
    """
    ...


def head(url: str, **kwargs) -> Response:
    """
    Send HEAD request.

    :param url: Request URL

    :returns: Response object

    Example
    -------
    ```python
        >>> import urequests
        >>> 
        >>> r = urequests.head('http://example.com/file.zip')
        >>> print(r.status_code)
        >>> r.close()
    ```
    """
    ...


def patch(url: str, **kwargs) -> Response:
    """
    Send PATCH request.

    :param url: Request URL

    :returns: Response object

    Example
    -------
    ```python
        >>> import urequests
        >>> 
        >>> r = urequests.patch('http://api.example.com/item/1',
        ...                     json={'field': 'updated'})
        >>> r.close()
    ```
    """
    ...


def request(method: str, url: str, **kwargs) -> Response:
    """
    Send HTTP request.

    :param method: HTTP method
    :param url: Request URL

    :returns: Response object

    Example
    -------
    ```python
        >>> import urequests
        >>> 
        >>> r = urequests.request('OPTIONS', 'http://api.example.com/')
        >>> r.close()
    ```
    """
    ...
