"""random - pseudo-random number generation.

MicroPython's `random` API is similar to CPython but may have a smaller feature
set.

Notes
-----
- The PRNG algorithm and entropy sources are port-dependent.
- `seed(None)` may seed from a system source (if available); otherwise you may
    need to provide your own seed for variability.

Example
-------
```python
    >>> import random
    >>> 
    >>> # Random integer
    >>> n = random.randint(1, 100)
    >>> 
    >>> # Random float [0, 1)
    >>> f = random.random()
    >>> 
    >>> # Random choice
    >>> item = random.choice([1, 2, 3, 4, 5])
```
"""

from typing import Any, Sequence, TypeVar

T = TypeVar('T')


def seed(n: int = None) -> None:
    """
    Initialize random number generator.

    :param n: Seed value (uses system source if None)

    Example
    -------
    ```python
        >>> import random
        >>> 
        >>> random.seed(42)  # Reproducible sequence
        >>> random.seed()    # Random seed from system
    ```
    """
    ...


def getrandbits(k: int) -> int:
    """
    Generate integer with k random bits.

    :param k: Number of bits

    :returns: Random integer with k bits

    Example
    -------
    ```python
        >>> import random
        >>> 
        >>> random.getrandbits(8)   # 0-255
        >>> random.getrandbits(16)  # 0-65535
    ```
    """
    ...


def randrange(start: int, stop: int = None, step: int = 1) -> int:
    """
    Random integer from range.

    :param start: Start (or stop if only arg)
    :param stop: End (exclusive)
    :param step: Step size

    :returns: Random integer

    Example
    -------
    ```python
        >>> import random
        >>> 
        >>> random.randrange(10)         # 0-9
        >>> random.randrange(5, 10)      # 5-9
        >>> random.randrange(0, 100, 5)  # 0, 5, 10, ..., 95
    ```
    """
    ...


def randint(a: int, b: int) -> int:
    """
    Random integer including endpoints.

    :param a: Minimum value
    :param b: Maximum value (inclusive)

    :returns: Random integer in [a, b]

    Example
    -------
    ```python
        >>> import random
        >>> 
        >>> random.randint(1, 6)    # Dice roll
        >>> random.randint(0, 100)  # 0-100 inclusive
    ```
    """
    ...


def random() -> float:
    """
    Random float in [0.0, 1.0).

    :returns: Random float

    Example
    -------
    ```python
        >>> import random
        >>> 
        >>> x = random.random()  # 0.0 <= x < 1.0
    ```
    """
    ...


def uniform(a: float, b: float) -> float:
    """
    Random float in [a, b].

    :param a: Minimum value
    :param b: Maximum value

    :returns: Random float in range

    Example
    -------
    ```python
        >>> import random
        >>> 
        >>> random.uniform(0, 10)    # 0.0-10.0
        >>> random.uniform(-1, 1)    # -1.0 to 1.0
    ```
    """
    ...


def choice(seq: Sequence[T]) -> T:
    """
    Random element from sequence.

    :param seq: Non-empty sequence

    :returns: Random element

    Example
    -------
    ```python
        >>> import random
        >>> 
        >>> random.choice([1, 2, 3, 4, 5])
        >>> random.choice('abcdef')
    ```
    """
    ...


def shuffle(x: list) -> None:
    """
    Shuffle list in place.

    :param x: List to shuffle

    Example
    -------
    ```python
        >>> import random
        >>> 
        >>> deck = [1, 2, 3, 4, 5]
        >>> random.shuffle(deck)
        >>> print(deck)  # Shuffled
    ```
    """
    ...
