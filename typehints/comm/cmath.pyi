"""cmath - complex number mathematics.

MicroPython provides a subset of `cmath` for complex arithmetic.

Notes
-----
- Complex support may be optional or limited on some ports.
- Branch cuts and floating-point precision follow the port's implementation.

Example
-------
```python
    >>> import cmath
    >>> 
    >>> z = complex(3, 4)
    >>> r = cmath.sqrt(z)
    >>> phase = cmath.phase(z)
```
"""


# Constants
e: float
"""Euler's number (2.718281...)."""

pi: float
"""Pi (3.141592...)."""

inf: float
"""Positive infinity."""

infj: complex
"""Complex infinity (0+inf*j)."""

nan: float
"""Not a number (NaN)."""

nanj: complex
"""Complex NaN (0+nan*j)."""


def cos(z: complex) -> complex:
    """
    Complex cosine.

    :param z: Complex number

    :returns: cos(z)

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> z = complex(1, 2)
        >>> cmath.cos(z)
    ```
    """
    ...


def sin(z: complex) -> complex:
    """
    Complex sine.

    :param z: Complex number

    :returns: sin(z)

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> z = complex(1, 2)
        >>> cmath.sin(z)
    ```
    """
    ...


def exp(z: complex) -> complex:
    """
    Complex exponential.

    :param z: Complex number

    :returns: e**z

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> cmath.exp(complex(0, cmath.pi))  # ~-1
    ```
    """
    ...


def log(z: complex) -> complex:
    """
    Complex natural logarithm.

    :param z: Complex number

    :returns: ln(z)

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> cmath.log(complex(1, 0))  # 0
    ```
    """
    ...


def log10(z: complex) -> complex:
    """
    Complex base-10 logarithm.

    :param z: Complex number

    :returns: log10(z)

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> cmath.log10(complex(100, 0))  # 2
    ```
    """
    ...


def sqrt(z: complex) -> complex:
    """
    Complex square root.

    :param z: Complex number

    :returns: sqrt(z)

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> cmath.sqrt(complex(-1, 0))  # 1j
        >>> cmath.sqrt(complex(3, 4))   # 2+1j
    ```
    """
    ...


def phase(z: complex) -> float:
    """
    Phase (argument) of complex number.

    :param z: Complex number

    :returns: Phase in radians (-pi to pi)

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> z = complex(1, 1)
        >>> cmath.phase(z)  # pi/4
        >>> 
        >>> cmath.phase(complex(0, 1))  # pi/2
    ```
    """
    ...


def polar(z: complex) -> tuple[float, float]:
    """
    Convert to polar coordinates.

    :param z: Complex number

    :returns: (magnitude, phase) tuple

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> z = complex(3, 4)
        >>> r, phi = cmath.polar(z)
        >>> print(r)  # 5.0
    ```
    """
    ...


def rect(r: float, phi: float) -> complex:
    """
    Convert from polar to rectangular.

    :param r: Magnitude
    :param phi: Phase in radians

    :returns: Complex number

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> z = cmath.rect(5, cmath.pi/4)  # ~3.5+3.5j
    ```
    """
    ...


def isfinite(z: complex) -> bool:
    """
    Check if both parts are finite.

    :param z: Complex number

    :returns: True if finite

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> cmath.isfinite(complex(1, 2))  # True
        >>> cmath.isfinite(cmath.infj)     # False
    ```
    """
    ...


def isinf(z: complex) -> bool:
    """
    Check if either part is infinite.

    :param z: Complex number

    :returns: True if infinite

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> cmath.isinf(cmath.infj)      # True
        >>> cmath.isinf(complex(1, 2))   # False
    ```
    """
    ...


def isnan(z: complex) -> bool:
    """
    Check if either part is NaN.

    :param z: Complex number

    :returns: True if NaN

    Example
    -------
    ```python
        >>> import cmath
        >>> 
        >>> cmath.isnan(cmath.nanj)      # True
        >>> cmath.isnan(complex(1, 2))   # False
    ```
    """
    ...
