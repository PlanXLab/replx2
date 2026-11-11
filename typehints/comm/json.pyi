"""
JSON encoder and decoder.

This is a MicroPython subset of CPython's ``json`` module. Supported types and
options are intentionally limited for use on embedded devices.

In general, JSON serialization supports standard JSON-compatible Python types:
dict, list/tuple, str, int/float, bool, and None.

Example
-------
```python
    >>> import json
    >>> 
    >>> # Encode to JSON
    >>> data = {'temp': 25.5, 'humid': 60}
    >>> text = json.dumps(data)
    >>> 
    >>> # Decode from JSON
    >>> obj = json.loads('{"x": 1, "y": 2}')
```
"""

from typing import Any, IO


def dumps(obj: Any) -> str:
    """
    Serialize object to JSON string.

    If an object contains unsupported types (e.g. bytes, set, custom classes),
    an exception may be raised.

    :param obj: Object to serialize (dict, list, str, int, float, bool, None)

    :returns: JSON string

    Example
    -------
    ```python
        >>> import json
        >>> 
        >>> data = {'sensor': 'DHT22', 'temp': 25.5}
        >>> text = json.dumps(data)
        >>> print(text)  # '{"sensor": "DHT22", "temp": 25.5}'
        >>> 
        >>> # List
        >>> json.dumps([1, 2, 3])  # '[1, 2, 3]'
    ```
    """
    ...


def dump(obj: Any, stream: IO[str]) -> None:
    """
    Serialize object to JSON and write to stream.

    The stream must be a text stream opened for writing.

    :param obj: Object to serialize
    :param stream: File-like object to write to

    Example
    -------
    ```python
        >>> import json
        >>> 
        >>> data = {'config': 'v1', 'enabled': True}
        >>> with open('/config.json', 'w') as f:
        ...     json.dump(data, f)
    ```
    """
    ...


def loads(s: str) -> Any:
    """
    Deserialize JSON string to object.

    Returns dicts/lists/strings/numbers/bools/None.

    :param s: JSON string

    :returns: Python object

    Example
    -------
    ```python
        >>> import json
        >>> 
        >>> obj = json.loads('{"x": 1, "y": 2}')
        >>> print(obj['x'])  # 1
        >>> 
        >>> arr = json.loads('[1, 2, 3]')
        >>> print(arr)  # [1, 2, 3]
    ```
    """
    ...


def load(stream: IO[str]) -> Any:
    """
    Deserialize JSON from stream.

    The stream must be a text stream opened for reading.

    :param stream: File-like object to read from

    :returns: Python object

    Example
    -------
    ```python
        >>> import json
        >>> 
        >>> with open('/config.json', 'r') as f:
        ...     config = json.load(f)
        >>> print(config)
    ```
    """
    ...
