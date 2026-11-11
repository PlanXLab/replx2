"""heapq - heap queue algorithm (priority queue).

MicroPython typically provides a small subset of CPython's `heapq` module.
The heap is represented as a plain Python list.

Notes
-----
- This is a min-heap: the smallest item is always at index 0.
- To build a max-heap, store negated keys or use tuples like ``(-priority, item)``.

Example
-------
```python
    >>> import heapq
    >>> 
    >>> heap = []
    >>> heapq.heappush(heap, 3)
    >>> heapq.heappush(heap, 1)
    >>> heapq.heappush(heap, 2)
    >>> 
    >>> smallest = heapq.heappop(heap)  # 1
```
"""

from typing import Any, TypeVar

T = TypeVar('T')


def heappush(heap: list, item: Any) -> None:
    """
    Push item onto heap, maintaining heap property.

    :param heap: List to use as heap
    :param item: Item to push

    Example
    -------
    ```python
        >>> import heapq
        >>> 
        >>> heap = []
        >>> heapq.heappush(heap, (5, 'low'))
        >>> heapq.heappush(heap, (1, 'high'))
        >>> heapq.heappush(heap, (3, 'med'))
    ```
    """
    ...


def heappop(heap: list) -> Any:
    """
    Pop smallest item from heap.

    :param heap: Heap list

    :returns: Smallest item

    Example
    -------
    ```python
        >>> import heapq
        >>> 
        >>> heap = [1, 3, 5, 7]
        >>> smallest = heapq.heappop(heap)  # 1
    ```
    """
    ...


def heapify(x: list) -> None:
    """
    Transform list into heap in-place.

    :param x: List to heapify

    Example
    -------
    ```python
        >>> import heapq
        >>> 
        >>> data = [5, 3, 8, 1, 2]
        >>> heapq.heapify(data)
        >>> heapq.heappop(data)  # 1
    ```
    """
    ...
