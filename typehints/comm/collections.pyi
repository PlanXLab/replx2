"""collections - specialized container datatypes.

MicroPython usually provides a subset of CPython's `collections` module.
Container behaviour and API coverage can vary by port.

Notes
-----
- `deque` is commonly used as a fixed-size FIFO/ring buffer via `maxlen`.
- `OrderedDict` preserves insertion order; in newer Python versions regular
    dicts preserve insertion order too, but MicroPython behaviour depends on build.

Example
-------
```python
    >>> from collections import OrderedDict, namedtuple
    >>> 
    >>> # Ordered dictionary
    >>> od = OrderedDict()
    >>> od['first'] = 1
    >>> 
    >>> # Named tuple
    >>> Point = namedtuple('Point', ['x', 'y'])
    >>> p = Point(10, 20)
```
"""

from typing import Any, Callable, Iterator, Optional, TypeVar, Union

T = TypeVar('T')


class OrderedDict(dict):
    """
    Dictionary that remembers insertion order.

    Example
    -------
    ```python
        >>> from collections import OrderedDict
        >>> 
        >>> od = OrderedDict()
        >>> od['a'] = 1
        >>> od['b'] = 2
        >>> od['c'] = 3
        >>> 
        >>> for k, v in od.items():
        ...     print(k, v)  # Always in order
    ```
    """

    def __init__(self, *args, **kwargs) -> None:
        """Create new OrderedDict."""
        ...

    def popitem(self, last: bool = True) -> tuple:
        """
        Remove and return (key, value) pair.

        :param last: Remove last (True) or first (False)

        :returns: (key, value) tuple

        Example
        -------
        ```python
            >>> from collections import OrderedDict
            >>> 
            >>> od = OrderedDict([('a', 1), ('b', 2)])
            >>> od.popitem()      # ('b', 2)
            >>> od.popitem(False) # ('a', 1)
        ```
        """
        ...

    def move_to_end(self, key: Any, last: bool = True) -> None:
        """
        Move key to end of dictionary.

        :param key: Key to move
        :param last: Move to end (True) or beginning (False)

        Example
        -------
        ```python
            >>> from collections import OrderedDict
            >>> 
            >>> od = OrderedDict([('a', 1), ('b', 2), ('c', 3)])
            >>> od.move_to_end('a')
            >>> list(od.keys())  # ['b', 'c', 'a']
        ```
        """
        ...


def namedtuple(name: str, fields: Union[str, list[str]]) -> type:
    """
    Create a named tuple class.

    :param name: Class name for the tuple
    :param fields: Field names (space-separated string or list)

    :returns: New tuple class

    Example
    -------
    ```python
        >>> from collections import namedtuple
        >>> 
        >>> Point = namedtuple('Point', ['x', 'y'])
        >>> p = Point(10, 20)
        >>> print(p.x, p.y)  # 10 20
        >>> 
        >>> # Using string
        >>> Rect = namedtuple('Rect', 'x y w h')
        >>> r = Rect(0, 0, 100, 50)
    ```
    """
    ...


class deque:
    """
    Double-ended queue with maximum length.

    Example
    -------
    ```python
        >>> from collections import deque
        >>> 
        >>> # Fixed-size buffer
        >>> buf = deque((), 10)
        >>> buf.append(1)
        >>> buf.append(2)
        >>> 
        >>> # Get from left
        >>> x = buf.popleft()
    ```
    """

    def __init__(self, iterable: tuple = (), maxlen: int = ...) -> None:
        """
        Create new deque.

        :param iterable: Initial values (must be tuple)
        :param maxlen: Maximum length (unbounded if not set)

        Example
        -------
        ```python
            >>> from collections import deque
            >>> 
            >>> d = deque((), 100)  # Max 100 items
            >>> d = deque((1, 2, 3), 10)
        ```
        """
        ...

    def __len__(self) -> int:
        """Return number of elements."""
        ...

    def __iter__(self) -> Iterator:
        """Iterate over elements."""
        ...

    def __bool__(self) -> bool:
        """True if not empty."""
        ...

    def append(self, x: Any) -> None:
        """
        Add to right side.

        If maxlen reached, removes from left.

        :param x: Value to add

        Example
        -------
        ```python
            >>> from collections import deque
            >>> 
            >>> d = deque((), 3)
            >>> d.append(1)
            >>> d.append(2)
            >>> d.append(3)
            >>> d.append(4)  # 1 is removed
            >>> list(d)  # [2, 3, 4]
        ```
        """
        ...

    def appendleft(self, x: Any) -> None:
        """
        Add to left side.

        :param x: Value to add

        Example
        -------
        ```python
            >>> from collections import deque
            >>> 
            >>> d = deque((2, 3), 10)
            >>> d.appendleft(1)
            >>> list(d)  # [1, 2, 3]
        ```
        """
        ...

    def pop(self) -> Any:
        """
        Remove and return from right.

        :returns: Rightmost element

        Example
        -------
        ```python
            >>> from collections import deque
            >>> 
            >>> d = deque((1, 2, 3), 10)
            >>> d.pop()  # 3
        ```
        """
        ...

    def popleft(self) -> Any:
        """
        Remove and return from left.

        :returns: Leftmost element

        Example
        -------
        ```python
            >>> from collections import deque
            >>> 
            >>> d = deque((1, 2, 3), 10)
            >>> d.popleft()  # 1
        ```
        """
        ...
