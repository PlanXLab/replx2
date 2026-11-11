"""math - mathematical functions.

MicroPython provides a set of math functions and constants. Availability and
floating-point precision can vary by port (some ports use single-precision).

Notes
-----
- Not every CPython `math` function is guaranteed to be available.
- Domain errors typically raise `ValueError` (e.g. `sqrt(-1)`).

Example
-------
```python
    >>> import math
    >>> 
    >>> x = math.sqrt(2)
    >>> angle = math.atan2(1, 1)
    >>> rad = math.radians(180)
```
"""


# Constants
e: float
"""Euler's number (2.718281...)."""

pi: float
"""Pi (3.141592...)."""

inf: float
"""Positive infinity."""

nan: float
"""Not a number (NaN)."""

tau: float
"""Tau (2*pi)."""


# Number theory
def ceil(x: float) -> int:
    """
    Ceiling of x (smallest integer >= x).

    :param x: Number

    :returns: Ceiling value

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.ceil(3.2)   # 4
        >>> math.ceil(-3.2)  # -3
    ```
    """
    ...


def floor(x: float) -> int:
    """
    Floor of x (largest integer <= x).

    :param x: Number

    :returns: Floor value

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.floor(3.8)   # 3
        >>> math.floor(-3.2)  # -4
    ```
    """
    ...


def trunc(x: float) -> int:
    """
    Truncate to integer (toward zero).

    :param x: Number

    :returns: Truncated value

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.trunc(3.8)   # 3
        >>> math.trunc(-3.8)  # -3
    ```
    """
    ...


def fabs(x: float) -> float:
    """
    Absolute value (float).

    :param x: Number

    :returns: Absolute value

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.fabs(-3.5)  # 3.5
    ```
    """
    ...


def fmod(x: float, y: float) -> float:
    """
    Floating-point modulo.

    :param x: Dividend
    :param y: Divisor

    :returns: Remainder

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.fmod(10.5, 3.0)  # 1.5
    ```
    """
    ...


def modf(x: float) -> tuple[float, float]:
    """
    Fractional and integer parts.

    :param x: Number

    :returns: (fractional, integer) tuple

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.modf(3.5)  # (0.5, 3.0)
    ```
    """
    ...


def frexp(x: float) -> tuple[float, int]:
    """
    Decompose to mantissa and exponent.

    :param x: Number

    :returns: (mantissa, exponent) where x = m * 2**e

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> m, e = math.frexp(8.0)  # (0.5, 4)
    ```
    """
    ...


def ldexp(x: float, i: int) -> float:
    """
    Compute x * 2**i.

    :param x: Mantissa
    :param i: Exponent

    :returns: x * 2**i

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.ldexp(0.5, 4)  # 8.0
    ```
    """
    ...


def copysign(x: float, y: float) -> float:
    """
    Copy sign of y to x.

    :param x: Magnitude
    :param y: Sign source

    :returns: |x| with sign of y

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.copysign(3.0, -1.0)  # -3.0
    ```
    """
    ...


# Power and logarithmic
def sqrt(x: float) -> float:
    """
    Square root.

    :param x: Non-negative number

    :returns: Square root

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.sqrt(2)  # 1.414...
        >>> math.sqrt(9)  # 3.0
    ```
    """
    ...


def pow(x: float, y: float) -> float:
    """
    Power function (x**y).

    :param x: Base
    :param y: Exponent

    :returns: x raised to power y

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.pow(2, 10)  # 1024.0
        >>> math.pow(2, 0.5) # 1.414...
    ```
    """
    ...


def exp(x: float) -> float:
    """
    Exponential (e**x).

    :param x: Exponent

    :returns: e raised to power x

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.exp(1)  # 2.718...
        >>> math.exp(0)  # 1.0
    ```
    """
    ...


def expm1(x: float) -> float:
    """
    Compute exp(x) - 1 accurately for small x.

    :param x: Exponent

    :returns: e**x - 1

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.expm1(1e-10)  # More accurate than exp(1e-10)-1
    ```
    """
    ...


def log(x: float, base: float = ...) -> float:
    """
    Logarithm (natural or specified base).

    :param x: Positive number
    :param base: Logarithm base (default: e)

    :returns: Logarithm value

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.log(math.e)     # 1.0
        >>> math.log(100, 10)    # 2.0
        >>> math.log(8, 2)       # 3.0
    ```
    """
    ...


def log2(x: float) -> float:
    """
    Base-2 logarithm.

    :param x: Positive number

    :returns: log2(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.log2(8)    # 3.0
        >>> math.log2(1024) # 10.0
    ```
    """
    ...


def log10(x: float) -> float:
    """
    Base-10 logarithm.

    :param x: Positive number

    :returns: log10(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.log10(100)  # 2.0
        >>> math.log10(1000) # 3.0
    ```
    """
    ...


def log1p(x: float) -> float:
    """
    Compute log(1+x) accurately for small x.

    :param x: Number > -1

    :returns: log(1+x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.log1p(1e-10)  # More accurate than log(1+1e-10)
    ```
    """
    ...


# Trigonometric
def sin(x: float) -> float:
    """
    Sine of x (radians).

    :param x: Angle in radians

    :returns: Sine value

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.sin(0)           # 0.0
        >>> math.sin(math.pi/2)   # 1.0
    ```
    """
    ...


def cos(x: float) -> float:
    """
    Cosine of x (radians).

    :param x: Angle in radians

    :returns: Cosine value

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.cos(0)        # 1.0
        >>> math.cos(math.pi)  # -1.0
    ```
    """
    ...


def tan(x: float) -> float:
    """
    Tangent of x (radians).

    :param x: Angle in radians

    :returns: Tangent value

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.tan(0)           # 0.0
        >>> math.tan(math.pi/4)   # 1.0
    ```
    """
    ...


def asin(x: float) -> float:
    """
    Arc sine.

    :param x: Value in [-1, 1]

    :returns: Angle in radians

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.asin(0)    # 0.0
        >>> math.asin(1)    # pi/2
    ```
    """
    ...


def acos(x: float) -> float:
    """
    Arc cosine.

    :param x: Value in [-1, 1]

    :returns: Angle in radians

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.acos(1)    # 0.0
        >>> math.acos(0)    # pi/2
    ```
    """
    ...


def atan(x: float) -> float:
    """
    Arc tangent.

    :param x: Value

    :returns: Angle in radians

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.atan(0)    # 0.0
        >>> math.atan(1)    # pi/4
    ```
    """
    ...


def atan2(y: float, x: float) -> float:
    """
    Arc tangent of y/x with quadrant handling.

    :param y: Y coordinate
    :param x: X coordinate

    :returns: Angle in radians

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.atan2(1, 1)   # pi/4
        >>> math.atan2(-1, -1) # -3*pi/4
    ```
    """
    ...


# Hyperbolic
def sinh(x: float) -> float:
    """
    Hyperbolic sine.

    :param x: Value

    :returns: sinh(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.sinh(0)  # 0.0
        >>> math.sinh(1)  # 1.175...
    ```
    """
    ...


def cosh(x: float) -> float:
    """
    Hyperbolic cosine.

    :param x: Value

    :returns: cosh(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.cosh(0)  # 1.0
    ```
    """
    ...


def tanh(x: float) -> float:
    """
    Hyperbolic tangent.

    :param x: Value

    :returns: tanh(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.tanh(0)    # 0.0
        >>> math.tanh(100)  # ~1.0
    ```
    """
    ...


def asinh(x: float) -> float:
    """
    Inverse hyperbolic sine.

    :param x: Value

    :returns: asinh(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.asinh(0)  # 0.0
    ```
    """
    ...


def acosh(x: float) -> float:
    """
    Inverse hyperbolic cosine.

    :param x: Value >= 1

    :returns: acosh(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.acosh(1)  # 0.0
    ```
    """
    ...


def atanh(x: float) -> float:
    """
    Inverse hyperbolic tangent.

    :param x: Value in (-1, 1)

    :returns: atanh(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.atanh(0)  # 0.0
    ```
    """
    ...


# Angular conversion
def degrees(x: float) -> float:
    """
    Convert radians to degrees.

    :param x: Angle in radians

    :returns: Angle in degrees

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.degrees(math.pi)    # 180.0
        >>> math.degrees(math.pi/2)  # 90.0
    ```
    """
    ...


def radians(x: float) -> float:
    """
    Convert degrees to radians.

    :param x: Angle in degrees

    :returns: Angle in radians

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.radians(180)  # pi
        >>> math.radians(90)   # pi/2
    ```
    """
    ...


# Special functions
def gamma(x: float) -> float:
    """
    Gamma function.

    :param x: Value

    :returns: Gamma(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.gamma(5)  # 24.0 (4!)
    ```
    """
    ...


def lgamma(x: float) -> float:
    """
    Natural log of gamma function.

    :param x: Value

    :returns: log(Gamma(x))

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.lgamma(5)  # log(24)
    ```
    """
    ...


def erf(x: float) -> float:
    """
    Error function.

    :param x: Value

    :returns: erf(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.erf(0)  # 0.0
        >>> math.erf(1)  # 0.842...
    ```
    """
    ...


def erfc(x: float) -> float:
    """
    Complementary error function (1 - erf(x)).

    :param x: Value

    :returns: erfc(x)

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.erfc(0)  # 1.0
    ```
    """
    ...


# Classification
def isfinite(x: float) -> bool:
    """
    Check if x is finite.

    :param x: Value

    :returns: True if finite

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.isfinite(1.0)      # True
        >>> math.isfinite(math.inf) # False
    ```
    """
    ...


def isinf(x: float) -> bool:
    """
    Check if x is infinite.

    :param x: Value

    :returns: True if infinite

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.isinf(math.inf)  # True
        >>> math.isinf(1.0)       # False
    ```
    """
    ...


def isnan(x: float) -> bool:
    """
    Check if x is NaN.

    :param x: Value

    :returns: True if NaN

    Example
    -------
    ```python
        >>> import math
        >>> 
        >>> math.isnan(math.nan)  # True
        >>> math.isnan(1.0)       # False
    ```
    """
    ...
