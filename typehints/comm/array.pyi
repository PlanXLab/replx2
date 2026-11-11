"""array - efficient arrays of basic numeric types.

MicroPython's `array` provides compact storage for homogeneous numeric values.
It is commonly used for binary protocols and buffers.

Notes
-----
- Endianness and binary layout follow the machine's native representation.
    Use `struct` for portable binary packing.
- Some type codes may be missing or mapped differently depending on the port.
- Arrays support the buffer protocol for many use cases (`bytearray`-like for
    ``'b'``/``'B'``).

Example
-------
```python
    >>> import array
    >>> 
    >>> # Create array of signed integers
    >>> a = array.array('i', [1, 2, 3, 4, 5])
    >>> print(a[0])
    >>> 
    >>> # Byte array for buffers
    >>> buf = array.array('B', [0] * 100)
```
"""

from typing import Iterable, Iterator, Union, overload


class array:
    """
    Array of homogeneous numeric values.

    Type codes:
    - 'b': signed byte (1)
    - 'B': unsigned byte (1)
    - 'h': signed short (2)
    - 'H': unsigned short (2)
    - 'i': signed int (4)
    - 'I': unsigned int (4)
    - 'l': signed long (4)
    - 'L': unsigned long (4)
    - 'q': signed long long (8)
    - 'Q': unsigned long long (8)
    - 'f': float (4)
    - 'd': double (8)

    Example
    -------
    ```python
        >>> import array
        >>> 
        >>> # Integer array
        >>> a = array.array('i', [1, 2, 3])
        >>> a.append(4)
        >>> 
        >>> # Byte buffer
        >>> buf = array.array('B', [0] * 256)
        >>> 
        >>> # Float array
        >>> samples = array.array('f', [0.0] * 1000)
    ```
    """

    def __init__(self, typecode: str, iterable: Iterable = ...) -> None:
        """
        Create new array.

        :param typecode: Type code character
        :param iterable: Initial values (optional)

        Example
        -------
        ```python
            >>> import array
            >>> 
            >>> a = array.array('H')  # Empty uint16 array
            >>> b = array.array('f', [1.0, 2.0, 3.0])
        ```
        """
        ...

    @overload
    def __getitem__(self, index: int) -> Union[int, float]: ...
    @overload
    def __getitem__(self, index: slice) -> 'array': ...

    def __getitem__(self, index):
        """Get an element or slice.

        Indexing returns a Python number (int/float). Slicing returns a new
        `array` with the same typecode.
        """
        ...

    def __setitem__(self, index: int, value: Union[int, float]) -> None:
        """Set an element value."""
        ...

    def __len__(self) -> int:
        """Return number of elements."""
        ...

    def __iter__(self) -> Iterator:
        """Iterate over elements."""
        ...

    def __contains__(self, value: Union[int, float]) -> bool:
        """Check if value in array."""
        ...

    def __add__(self, other: 'array') -> 'array':
        """Concatenate arrays."""
        ...

    def __iadd__(self, other: 'array') -> 'array':
        """Extend array in place."""
        ...

    def append(self, value: Union[int, float]) -> None:
        """
        Append value to end.

        :param value: Value to append

        Example
        -------
        ```python
            >>> import array
            >>> 
            >>> a = array.array('i', [1, 2])
            >>> a.append(3)
            >>> print(list(a))  # [1, 2, 3]
        ```
        """
        ...

    def extend(self, iterable: Iterable) -> None:
        """
        Extend array with values.

        :param iterable: Values to add

        Example
        -------
        ```python
            >>> import array
            >>> 
            >>> a = array.array('i', [1, 2])
            >>> a.extend([3, 4, 5])
        ```
        """
        ...

    def decode(self) -> str:
        """
        Decode byte array as UTF-8 string.

        Only for 'b' and 'B' type arrays.

        :returns: Decoded string

        Example
        -------
        ```python
            >>> import array
            >>> 
            >>> a = array.array('B', [72, 101, 108, 108, 111])
            >>> s = a.decode()  # 'Hello'
        ```
        """
        ...

    @property
    def typecode(self) -> str:
        """Type code character."""
        ...

    @property
    def itemsize(self) -> int:
        """Size of one element in bytes."""
        ...
