"""
ulab module type hints for MicroPython.

Provides a NumPy/SciPy-like API optimized for microcontrollers.
The top-level module exposes `numpy`, `scipy`, `utils`, and `user` submodules,
as well as `ndarray` and `dtype` support.

Example
-------
```python
    >>> from ulab import numpy as np
    >>> from ulab import scipy as spy
    >>>
    >>> x = np.array([1.0, 2.0, 3.0])
    >>> y = np.sin(x)
    >>> print(np.mean(y))
    >>>
    >>> z = spy.special.erf(x)
```
"""

from typing import Any, Callable, Iterable, Optional, Protocol, Sequence, Union


_ArrayLike = Union["ndarray", Sequence[Any], Iterable[Any]]
_Number = Union[int, float, bool]


class flatiter:
    """Iterator over ndarray elements in flattened (C-order) traversal."""

    def __iter__(self) -> "flatiter":
        """
        Return the iterator object itself.

        :returns: This ``flatiter`` instance.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> for v in a.flat:
            ...     print(v)
        ```
        """
        ...

    def __next__(self) -> Any:
        """
        Return the next scalar element in flattened order.

        :returns: The next element.

        :raises StopIteration: When all elements have been consumed.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> it = iter(a.flat)
            >>> print(next(it))  # 1
        ```
        """
        ...


class dtype:
    """NumPy-like dtype descriptor used by ulab ndarray objects."""


class ndarray:
    """
    N-dimensional numeric array type for MicroPython ulab.

    Supports 1-D to 4-D arrays (firmware-dependent), arithmetic and
    broadcast-style operations, slicing, and dense/strided views.
    """

    dtype: Any
    itemsize: int
    ndim: int
    shape: tuple[int, ...]
    size: int
    strides: tuple[int, ...]
    flat: flatiter
    T: "ndarray"
    real: "ndarray"
    imag: "ndarray"

    def __len__(self) -> int:
        """
        Return the number of elements in the leading dimension.

        :returns: Length of the first axis.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> print(len(a))  # 3
        ```
        """
        ...

    def __iter__(self) -> flatiter:
        """
        Return an iterator over first-axis slices.

        :returns: Iterator yielding rows, or scalars for 1-D arrays.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([10, 20, 30])
            >>> for v in a:
            ...     print(v)
        ```
        """
        ...

    def __getitem__(self, key: Any) -> Any:
        """
        Return an element or sub-array selected by index or slice.

        :param key: Integer index, slice, or tuple thereof.

        :returns: Scalar value or ndarray view.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([10, 20, 30])
            >>> print(a[1])    # 20
            >>> print(a[0:2])  # array([10, 20])
        ```
        """
        ...

    def __setitem__(self, key: Any, value: Any) -> None:
        """
        Set an element or sub-array selected by index or slice.

        :param key: Integer index, slice, or tuple thereof.
        :param value: Scalar or array-like values to assign.

        :returns: None.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> a[1] = 99
            >>> print(a)  # array([1, 99, 3])
        ```
        """
        ...

    def __abs__(self) -> "ndarray":
        """
        Return element-wise absolute values.

        :returns: New ndarray of absolute values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([-1, -2, 3])
            >>> print(abs(a))  # array([1, 2, 3])
        ```
        """
        ...

    def __neg__(self) -> "ndarray":
        """
        Return element-wise negation.

        :returns: New ndarray with all values negated.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> print(-a)  # array([-1, -2, -3])
        ```
        """
        ...

    def __pos__(self) -> "ndarray":
        """
        Return the array unchanged (unary +).

        :returns: This ndarray or a copy.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> print(+a)
        ```
        """
        ...

    def __invert__(self) -> "ndarray":
        """
        Return element-wise bitwise NOT. Integer arrays only.

        :returns: New ndarray with all bits inverted.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0, 1, 0xFF], dtype=np.uint8)
            >>> print(~a)
        ```
        """
        ...

    def __add__(self, other: Any) -> "ndarray":
        """
        Return element-wise sum ``self + other``.

        :param other: Scalar or array to add.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> print(a + 10)  # array([11, 12, 13])
        ```
        """
        ...

    def __radd__(self, other: Any) -> "ndarray":
        """
        Return element-wise sum ``other + self``.

        :param other: Scalar or array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> print(10 + a)  # array([11, 12, 13])
        ```
        """
        ...

    def __sub__(self, other: Any) -> "ndarray":
        """
        Return element-wise difference ``self - other``.

        :param other: Scalar or array to subtract.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([10, 20, 30])
            >>> print(a - 5)  # array([5, 15, 25])
        ```
        """
        ...

    def __rsub__(self, other: Any) -> "ndarray":
        """
        Return element-wise difference ``other - self``.

        :param other: Scalar or array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> print(100 - a)  # array([99, 98, 97])
        ```
        """
        ...

    def __mul__(self, other: Any) -> "ndarray":
        """
        Return element-wise product ``self * other``.

        :param other: Scalar or array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> print(a * 2)  # array([2, 4, 6])
        ```
        """
        ...

    def __rmul__(self, other: Any) -> "ndarray":
        """
        Return element-wise product ``other * self``.

        :param other: Scalar or array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> print(2 * a)  # array([2, 4, 6])
        ```
        """
        ...

    def __truediv__(self, other: Any) -> "ndarray":
        """
        Return element-wise true division ``self / other``.

        :param other: Scalar or array divisor.

        :returns: Result ndarray of floats.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([4.0, 6.0, 8.0])
            >>> print(a / 2.0)  # array([2.0, 3.0, 4.0])
        ```
        """
        ...

    def __rtruediv__(self, other: Any) -> "ndarray":
        """
        Return element-wise true division ``other / self``.

        :param other: Scalar or array numerator.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([2.0, 4.0, 8.0])
            >>> print(1.0 / a)  # array([0.5, 0.25, 0.125])
        ```
        """
        ...

    def __floordiv__(self, other: Any) -> "ndarray":
        """
        Return element-wise floor division ``self // other``.

        :param other: Scalar or array divisor.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([7, 8, 9])
            >>> print(a // 3)  # array([2, 2, 3])
        ```
        """
        ...

    def __rfloordiv__(self, other: Any) -> "ndarray":
        """
        Return element-wise floor division ``other // self``.

        :param other: Scalar or array numerator.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([2, 3, 4])
            >>> print(24 // a)  # array([12, 8, 6])
        ```
        """
        ...

    def __pow__(self, other: Any) -> "ndarray":
        """
        Return element-wise power ``self ** other``.

        :param other: Scalar or array exponent.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([2, 3, 4])
            >>> print(a ** 2)  # array([4, 9, 16])
        ```
        """
        ...

    def __rpow__(self, other: Any) -> "ndarray":
        """
        Return element-wise power ``other ** self``.

        :param other: Scalar or array base.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([2, 3, 4])
            >>> print(2 ** a)  # array([4, 8, 16])
        ```
        """
        ...

    def __and__(self, other: Any) -> "ndarray":
        """
        Return element-wise bitwise AND. Integer arrays only.

        :param other: Scalar or integer array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0b1010, 0b1100], dtype=np.uint8)
            >>> print(a & 0b1000)
        ```
        """
        ...

    def __rand__(self, other: Any) -> "ndarray":
        """
        Return element-wise bitwise AND ``other & self``. Integer arrays only.

        :param other: Scalar or integer array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0b1010, 0b1100], dtype=np.uint8)
            >>> print(0b1000 & a)
        ```
        """
        ...

    def __or__(self, other: Any) -> "ndarray":
        """
        Return element-wise bitwise OR. Integer arrays only.

        :param other: Scalar or integer array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0b0010, 0b0100], dtype=np.uint8)
            >>> print(a | 0b0001)
        ```
        """
        ...

    def __ror__(self, other: Any) -> "ndarray":
        """
        Return element-wise bitwise OR ``other | self``. Integer arrays only.

        :param other: Scalar or integer array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0b0010, 0b0100], dtype=np.uint8)
            >>> print(0b0001 | a)
        ```
        """
        ...

    def __xor__(self, other: Any) -> "ndarray":
        """
        Return element-wise bitwise XOR. Integer arrays only.

        :param other: Scalar or integer array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0b1010, 0b0101], dtype=np.uint8)
            >>> print(a ^ 0b1111)
        ```
        """
        ...

    def __rxor__(self, other: Any) -> "ndarray":
        """
        Return element-wise bitwise XOR ``other ^ self``. Integer arrays only.

        :param other: Scalar or integer array.

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0b1010, 0b0101], dtype=np.uint8)
            >>> print(0b1111 ^ a)
        ```
        """
        ...

    def __lshift__(self, other: Any) -> "ndarray":
        """
        Return element-wise left bit shift ``self << other``.

        :param other: Shift amount (scalar or array).

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 4], dtype=np.uint8)
            >>> print(a << 1)  # array([2, 4, 8])
        ```
        """
        ...

    def __rshift__(self, other: Any) -> "ndarray":
        """
        Return element-wise right bit shift ``self >> other``.

        :param other: Shift amount (scalar or array).

        :returns: Result ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([8, 16, 32], dtype=np.uint8)
            >>> print(a >> 1)  # array([4, 8, 16])
        ```
        """
        ...

    def reshape(self, shape: Union[int, tuple[int, ...]]) -> "ndarray":
        """
        Return a new view of the array with a different shape.

        The total number of elements must remain unchanged.

        :param shape: New shape as an integer or tuple of integers.

        :returns: ndarray view with the requested shape.

        :raises ValueError: If the total size would change.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3, 4, 5, 6])
            >>> b = a.reshape((2, 3))
            >>> print(b.shape)  # (2, 3)
        ```
        """
        ...

    def transpose(self, *axes: int) -> "ndarray":
        """
        Return a view with the array's axes permuted.

        :param axes: Optional permutation of axis indices. If omitted, all
            axes are reversed (equivalent to ``.T``).

        :returns: ndarray view with transposed axes.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[1, 2, 3], [4, 5, 6]])
            >>> print(a.transpose().shape)  # (3, 2)
        ```
        """
        ...

    def byteswap(self, inplace: bool = False) -> "ndarray":
        """
        Swap the byte order of every element in the array.

        :param inplace: If ``True``, modify this array in-place and return
            it. Otherwise return a new array.

        :returns: Array with swapped bytes (``self`` when ``inplace=True``).

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0x0102], dtype=np.uint16)
            >>> b = a.byteswap()
            >>> print(hex(int(b[0])))  # 0x201
        ```
        """
        ...

    def copy(self) -> "ndarray":
        """
        Return an independent copy of this array.

        Modifications to the copy do not affect the original.

        :returns: New ndarray with the same data, dtype, and shape.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> b = a.copy()
            >>> b[0] = 99
            >>> print(a[0])  # 1 — original unchanged
        ```
        """
        ...

    def flatten(self) -> "ndarray":
        """
        Return a 1-D copy of the array in C-order (row-major).

        :returns: 1-D ndarray containing all elements.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[1, 2], [3, 4]])
            >>> print(a.flatten())  # array([1, 2, 3, 4])
        ```
        """
        ...

    def tobytes(self) -> bytes:
        """
        Serialize the array's raw memory to a Python ``bytes`` object.

        :returns: Raw bytes of the array data in its native byte order.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3], dtype=np.uint8)
            >>> print(a.tobytes())  # b'\x01\x02\x03'
        ```
        """
        ...

    def tolist(self) -> list[Any]:
        """
        Convert the array to a nested Python list.

        :returns: Python list (nested for multi-dimensional arrays).

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 2.0, 3.0])
            >>> print(a.tolist())  # [1.0, 2.0, 3.0]
        ```
        """
        ...

    def sort(self, axis: int = -1) -> Optional["ndarray"]:
        """
        Sort array elements in-place along the specified axis.

        :param axis: Axis to sort along. Defaults to ``-1`` (last axis).

        :returns: ``None`` (sort is in-place on most firmware builds).

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([3, 1, 2])
            >>> a.sort()
            >>> print(a)  # array([1, 2, 3])
        ```
        """
        ...


class FFTModule(Protocol):
    """ulab.numpy.fft — discrete Fourier transform routines."""

    def fft(self, x: ndarray, y: Optional[ndarray] = None) -> Any:
        """
        Compute the 1-D discrete Fourier Transform.

        Returns a tuple ``(real, imag)`` of ndarrays each with the same
        length as the input.

        :param x: Input signal array (real part).
        :param y: Optional imaginary part. Omit for a purely real input.

        :returns: Tuple ``(real, imag)`` — FFT result split into components.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> x = np.array([1.0, 2.0, 3.0, 4.0])
            >>> real, imag = np.fft.fft(x)
            >>> print(real)
        ```
        """
        ...

    def ifft(self, x: ndarray, y: Optional[ndarray] = None) -> Any:
        """
        Compute the 1-D inverse discrete Fourier Transform.

        Returns a tuple ``(real, imag)`` representing the reconstructed
        time-domain signal.

        :param x: Real part of the frequency-domain input.
        :param y: Imaginary part of the frequency-domain input.

        :returns: Tuple ``(real, imag)`` — IFFT result.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> x = np.array([1.0, 2.0, 3.0, 4.0])
            >>> fr, fi = np.fft.fft(x)
            >>> tr, ti = np.fft.ifft(fr, fi)
            >>> print(tr)
        ```
        """
        ...


class LinalgModule(Protocol):
    """ulab.numpy.linalg — linear algebra routines."""

    def cholesky(self, a: ndarray) -> ndarray:
        """
        Return the lower-triangular Cholesky factor of a positive-definite matrix.

        :param a: Symmetric positive-definite 2-D square matrix.

        :returns: Lower-triangular ndarray ``L`` such that ``a == L @ L.T``.

        :raises ValueError: If ``a`` is not positive-definite.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[4.0, 2.0], [2.0, 3.0]])
            >>> L = np.linalg.cholesky(a)
            >>> print(L)
        ```
        """
        ...

    def det(self, a: ndarray) -> _Number:
        """
        Compute the determinant of a square matrix.

        :param a: 2-D square ndarray.

        :returns: Scalar determinant value.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[1.0, 2.0], [3.0, 4.0]])
            >>> print(np.linalg.det(a))  # -2.0
        ```
        """
        ...

    def eig(self, a: ndarray) -> Any:
        """
        Compute the eigenvalues and right eigenvectors of a square matrix.

        :param a: 2-D square ndarray. Real symmetric matrices recommended
            on MicroPython to guarantee real results.

        :returns: Tuple ``(eigenvalues, eigenvectors)`` where each column of
            ``eigenvectors`` is a normalized eigenvector.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[2.0, 1.0], [1.0, 2.0]])
            >>> vals, vecs = np.linalg.eig(a)
            >>> print(vals)
        ```
        """
        ...

    def inv(self, a: ndarray) -> ndarray:
        """
        Compute the inverse of a square matrix.

        :param a: Invertible 2-D square ndarray.

        :returns: Matrix inverse of ``a``.

        :raises ValueError: If ``a`` is singular or not square.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[1.0, 2.0], [3.0, 4.0]])
            >>> print(np.linalg.inv(a))
        ```
        """
        ...

    def norm(self, a: ndarray, ord: Optional[int] = None, axis: Optional[int] = None) -> Any:
        """
        Compute a matrix or vector norm.

        :param a: Input matrix or vector.
        :param ord: Norm order. ``None`` uses Frobenius for matrices and
            Euclidean (L2) for vectors.
        :param axis: Axis along which to compute the norm.

        :returns: Scalar or ndarray of norm values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> v = np.array([3.0, 4.0])
            >>> print(np.linalg.norm(v))  # 5.0
        ```
        """
        ...

    def qr(self, a: ndarray, mode: str = "reduced") -> Any:
        """
        Compute the QR factorization of a matrix.

        :param a: 2-D ndarray to decompose.
        :param mode: Factorization mode. ``"reduced"`` returns economy-size Q
            and R.

        :returns: Tuple ``(Q, R)`` — orthogonal Q and upper-triangular R.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
            >>> Q, R = np.linalg.qr(a)
            >>> print(Q.shape, R.shape)
        ```
        """
        ...


class Generator:
    """Pseudo-random number generator for ulab.numpy.random."""

    def random(self, size: Optional[Union[int, tuple[int, ...]]] = None, out: Optional[ndarray] = None) -> Any:
        """
        Draw uniform random floats from the half-open interval [0.0, 1.0).

        :param size: Output shape. If ``None`` returns a single float.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of the requested shape, or a scalar float.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> gen = np.random.Generator()
            >>> values = gen.random(size=5)
            >>> print(values)
        ```
        """
        ...

    def normal(
        self,
        loc: float = 0.0,
        scale: float = 1.0,
        size: Optional[Union[int, tuple[int, ...]]] = None,
        out: Optional[ndarray] = None,
    ) -> Any:
        """
        Draw samples from a normal (Gaussian) distribution.

        :param loc: Mean of the distribution.
        :param scale: Standard deviation of the distribution.
        :param size: Output shape. If ``None`` returns a single sample.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of samples, or a scalar float.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> gen = np.random.Generator()
            >>> samples = gen.normal(loc=0.0, scale=1.0, size=10)
            >>> print(np.mean(samples))
        ```
        """
        ...

    def uniform(
        self,
        low: float = 0.0,
        high: float = 1.0,
        size: Optional[Union[int, tuple[int, ...]]] = None,
        out: Optional[ndarray] = None,
    ) -> Any:
        """
        Draw samples from a uniform distribution over [low, high).

        :param low: Lower boundary of the output interval.
        :param high: Upper boundary of the output interval (exclusive).
        :param size: Output shape. If ``None`` returns a single sample.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of samples, or a scalar float.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> gen = np.random.Generator()
            >>> samples = gen.uniform(low=0.0, high=10.0, size=5)
            >>> print(samples)
        ```
        """
        ...


class RandomModule(Protocol):
    """ulab.numpy.random — random number generation."""

    Generator: type[Generator]

    def random(self, size: Optional[Union[int, tuple[int, ...]]] = None, out: Optional[ndarray] = None) -> Any:
        """
        Draw uniform random floats from [0.0, 1.0).

        :param size: Output shape. Omit for a single scalar float.
        :param out: Optional pre-allocated output array.

        :returns: ndarray or scalar float.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> vals = np.random.random(size=4)
            >>> print(vals)
        ```
        """
        ...

    def normal(
        self,
        loc: float = 0.0,
        scale: float = 1.0,
        size: Optional[Union[int, tuple[int, ...]]] = None,
        out: Optional[ndarray] = None,
    ) -> Any:
        """
        Draw samples from a normal distribution.

        :param loc: Mean (centre) of the distribution.
        :param scale: Standard deviation (spread) of the distribution.
        :param size: Output shape.
        :param out: Optional pre-allocated output array.

        :returns: ndarray or scalar float.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> samples = np.random.normal(loc=0.0, scale=1.0, size=10)
            >>> print(np.mean(samples))
        ```
        """
        ...

    def uniform(
        self,
        low: float = 0.0,
        high: float = 1.0,
        size: Optional[Union[int, tuple[int, ...]]] = None,
        out: Optional[ndarray] = None,
    ) -> Any:
        """
        Draw samples from a uniform distribution over [low, high).

        :param low: Lower boundary of the interval.
        :param high: Upper boundary of the interval (exclusive).
        :param size: Output shape.
        :param out: Optional pre-allocated output array.

        :returns: ndarray or scalar float.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> samples = np.random.uniform(low=1.0, high=5.0, size=6)
            >>> print(samples)
        ```
        """
        ...


class NumpyModule(Protocol):
    """ulab.numpy — NumPy-compatible numerical computing for MicroPython."""

    __name__: str

    ndarray: type[ndarray]

    bool: int
    uint8: int
    int8: int
    uint16: int
    int16: int
    float: int
    complex: int

    e: float
    inf: float
    nan: float
    pi: float

    fft: FFTModule
    linalg: LinalgModule
    random: RandomModule

    def set_printoptions(self, threshold: Optional[int] = None, edgeitems: Optional[int] = None) -> None:
        """
        Configure how arrays are printed.

        :param threshold: Total element count above which printing is
            abbreviated. Pass ``None`` to leave unchanged.
        :param edgeitems: Number of edge items shown when abbreviated.

        :returns: None.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> np.set_printoptions(threshold=10, edgeitems=3)
        ```
        """
        ...

    def get_printoptions(self) -> dict[str, int]:
        """
        Return the current array printing options.

        :returns: Dictionary with keys ``"threshold"`` and ``"edgeitems"``.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> opts = np.get_printoptions()
            >>> print(opts)  # {'threshold': 10, 'edgeitems': 3}
        ```
        """
        ...

    def ndinfo(self, array: ndarray) -> None:
        """
        Print shape, strides, dtype, and element count of an array.

        Useful for quick debugging of array metadata.

        :param array: The ndarray to inspect.

        :returns: None.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[1, 2, 3], [4, 5, 6]])
            >>> np.ndinfo(a)
        ```
        """
        ...

    def array(self, values: _ArrayLike, *, dtype: Any = ...) -> ndarray:
        """
        Create an ndarray from a list, tuple, or other iterable.

        :param values: Input data — list, tuple, ndarray, or iterable.
        :param dtype: Desired element type (e.g. ``np.float``, ``np.uint8``).
            Inferred from the data when omitted.

        :returns: New ndarray containing the supplied values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 2.0, 3.0], dtype=np.float)
            >>> print(a)
        ```
        """
        ...

    def asarray(self, values: _ArrayLike, *, dtype: Any = ...) -> ndarray:
        """
        Convert the input to an ndarray, copying only when necessary.

        If the input is already an ndarray with the correct dtype, no copy is
        made and the original is returned.

        :param values: Input data.
        :param dtype: Target element type.

        :returns: ndarray view or copy of the input.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.asarray([1, 2, 3], dtype=np.float)
            >>> print(a)
        ```
        """
        ...

    def frombuffer(self, buffer: Any, *, dtype: Any = ..., count: int = -1, offset: int = 0) -> ndarray:
        """
        Create a 1-D ndarray backed by an existing buffer object.

        :param buffer: Any object that exposes the buffer protocol
            (``bytes``, ``bytearray``, ``memoryview``, etc.).
        :param dtype: Element type. Defaults to ``np.uint8``.
        :param count: Number of elements to read. ``-1`` reads all available.
        :param offset: Byte offset into the buffer.

        :returns: 1-D ndarray sharing memory with the buffer.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> buf = bytearray([10, 20, 30, 40])
            >>> a = np.frombuffer(buf, dtype=np.uint8)
            >>> print(a)  # array([10, 20, 30, 40])
        ```
        """
        ...

    def arange(self, *args: Any, dtype: Any = ...) -> ndarray:
        """
        Return evenly-spaced values within a given interval.

        Call forms: ``arange(stop)``, ``arange(start, stop)``, or
        ``arange(start, stop, step)``.

        :param args: Stop value, or start + stop, or start + stop + step.
        :param dtype: Desired element type. Inferred when omitted.

        :returns: 1-D ndarray of evenly-spaced values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> print(np.arange(5))          # array([0, 1, 2, 3, 4])
            >>> print(np.arange(1, 4))       # array([1, 2, 3])
            >>> print(np.arange(0, 1, 0.25)) # array([0.0, 0.25, 0.5, 0.75])
        ```
        """
        ...

    def compress(self, condition: _ArrayLike, a: _ArrayLike, axis: Optional[int] = None) -> ndarray:
        """
        Return selected slices of an array where ``condition`` is True.

        :param condition: 1-D boolean array selecting the slices to keep.
        :param a: Input array.
        :param axis: Axis along which to compress. If ``None``, the array is
            flattened first.

        :returns: Compressed ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([10, 20, 30, 40])
            >>> mask = np.array([True, False, True, False])
            >>> print(np.compress(mask, a))  # array([10, 30])
        ```
        """
        ...

    def concatenate(self, arrays: Sequence[_ArrayLike], axis: int = 0) -> ndarray:
        """
        Join a sequence of arrays along an existing axis.

        :param arrays: Sequence of arrays. All shapes must match except along
            ``axis``.
        :param axis: Axis along which to concatenate. Default ``0``.

        :returns: Concatenated ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> b = np.array([4, 5, 6])
            >>> print(np.concatenate([a, b]))  # array([1, 2, 3, 4, 5, 6])
        ```
        """
        ...

    def delete(self, a: _ArrayLike, obj: Any, axis: Optional[int] = None) -> ndarray:
        """
        Return a new array with specified sub-arrays removed.

        :param a: Input array.
        :param obj: Integer index or slice of elements to remove.
        :param axis: Axis along which to delete. Flattens if ``None``.

        :returns: New ndarray with specified elements removed.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3, 4])
            >>> print(np.delete(a, 1))  # array([1, 3, 4])
        ```
        """
        ...

    def diag(self, v: _ArrayLike, k: int = 0) -> ndarray:
        """
        Extract a diagonal or construct a diagonal matrix.

        When ``v`` is 1-D, returns a 2-D array with ``v`` on diagonal ``k``.
        When ``v`` is 2-D, extracts the diagonal as a 1-D array.

        :param v: Input array.
        :param k: Diagonal offset. ``0`` is the main diagonal; positive values
            refer to upper diagonals; negative values to lower.

        :returns: Diagonal ndarray or diagonal matrix.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> print(np.diag(np.array([1, 2, 3])))
            >>> m = np.array([[1, 2], [3, 4]])
            >>> print(np.diag(m))  # array([1, 4])
        ```
        """
        ...

    def empty(self, shape: Union[int, tuple[int, ...]], dtype: Any = ...) -> ndarray:
        """
        Create an uninitialized array with the given shape.

        Contents are undefined. Use when you will immediately write all values.

        :param shape: Integer or tuple defining the array dimensions.
        :param dtype: Element type. Defaults to ``np.float``.

        :returns: Uninitialized ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.empty((3, 3), dtype=np.float)
            >>> print(a.shape)  # (3, 3)
        ```
        """
        ...

    def eye(self, n: int, m: Optional[int] = None, k: int = 0, dtype: Any = ...) -> ndarray:
        """
        Return a 2-D array with ones on a diagonal and zeros elsewhere.

        :param n: Number of rows.
        :param m: Number of columns. Defaults to ``n``.
        :param k: Diagonal offset. ``0`` is the main diagonal.
        :param dtype: Element type. Defaults to ``np.float``.

        :returns: 2-D identity-like ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> print(np.eye(3))
            >>> print(np.eye(3, k=1))
        ```
        """
        ...

    def full(self, shape: Union[int, tuple[int, ...]], fill_value: Any, dtype: Any = ...) -> ndarray:
        """
        Return an array of the given shape filled with a constant value.

        :param shape: Integer or tuple defining the array dimensions.
        :param fill_value: Scalar value to fill every element.
        :param dtype: Element type. Inferred from ``fill_value`` when omitted.

        :returns: ndarray filled with ``fill_value``.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.full((2, 3), 7.0)
            >>> print(a)
        ```
        """
        ...

    def linspace(self, start: _Number, stop: _Number, num: int = 50, endpoint: bool = True, dtype: Any = ...) -> ndarray:
        """
        Return ``num`` evenly-spaced numbers over [start, stop].

        :param start: Start of the interval.
        :param stop: End of the interval.
        :param num: Number of samples to generate. Default ``50``.
        :param endpoint: If ``True`` (default), ``stop`` is the last sample.
        :param dtype: Element type. Defaults to ``np.float``.

        :returns: 1-D ndarray of evenly-spaced values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> x = np.linspace(0, 1, num=5)
            >>> print(x)  # array([0.0, 0.25, 0.5, 0.75, 1.0])
        ```
        """
        ...

    def logspace(self, start: _Number, stop: _Number, num: int = 50, endpoint: bool = True, base: _Number = 10.0, dtype: Any = ...) -> ndarray:
        """
        Return numbers spaced evenly on a logarithmic scale.

        The interval spans ``[base**start, base**stop]``.

        :param start: Exponent for the first value.
        :param stop: Exponent for the last value.
        :param num: Number of samples. Default ``50``.
        :param endpoint: Whether ``base**stop`` is included as the last value.
        :param base: Logarithm base. Default ``10``.
        :param dtype: Element type.

        :returns: 1-D ndarray of log-spaced values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> x = np.logspace(0, 2, num=5)
            >>> print(x)  # array([1.0, 3.16..., 10.0, 31.6..., 100.0])
        ```
        """
        ...

    def meshgrid(self, *arrays: _ArrayLike) -> Any:
        """
        Return coordinate matrices from 1-D coordinate vectors.

        :param arrays: 1-D coordinate arrays, one per output dimension.

        :returns: List of ndarrays forming the coordinate grids.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> x = np.array([0, 1, 2])
            >>> y = np.array([0, 1])
            >>> xx, yy = np.meshgrid(x, y)
            >>> print(xx.shape)  # (2, 3)
        ```
        """
        ...

    def ones(self, shape: Union[int, tuple[int, ...]], dtype: Any = ...) -> ndarray:
        """
        Return an array of the given shape filled with ones.

        :param shape: Integer or tuple defining the array dimensions.
        :param dtype: Element type. Defaults to ``np.float``.

        :returns: ndarray of ones.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.ones((2, 3))
            >>> print(a)
        ```
        """
        ...

    def zeros(self, shape: Union[int, tuple[int, ...]], dtype: Any = ...) -> ndarray:
        """
        Return an array of the given shape filled with zeros.

        :param shape: Integer or tuple defining the array dimensions.
        :param dtype: Element type. Defaults to ``np.float``.

        :returns: ndarray of zeros.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.zeros(5)
            >>> print(a)  # array([0.0, 0.0, 0.0, 0.0, 0.0])
        ```
        """
        ...

    def take(self, a: _ArrayLike, indices: _ArrayLike, axis: Optional[int] = None) -> ndarray:
        """
        Take elements from an array along an axis using an index array.

        :param a: Source array.
        :param indices: 1-D integer array of positions to select.
        :param axis: Axis along which to take. Flattens if ``None``.

        :returns: ndarray of the selected elements.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([10, 20, 30, 40])
            >>> idx = np.array([0, 2])
            >>> print(np.take(a, idx))  # array([10, 30])
        ```
        """
        ...

    def bincount(self, a: _ArrayLike, weights: Optional[_ArrayLike] = None, minlength: int = 0) -> ndarray:
        """
        Count occurrences of each non-negative integer value in ``a``.

        :param a: 1-D array of non-negative integers.
        :param weights: Optional weight per element. Each integer contributes
            its weight instead of 1.
        :param minlength: Minimum number of bins in the output array.

        :returns: 1-D ndarray of counts (or weighted sums).

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0, 1, 1, 2, 0], dtype=np.int16)
            >>> print(np.bincount(a))  # array([2, 2, 1])
        ```
        """
        ...

    def clip(self, a: _ArrayLike, a_min: Optional[_Number], a_max: Optional[_Number], out: Optional[ndarray] = None) -> ndarray:
        """
        Clip array values to the interval [a_min, a_max].

        Values below ``a_min`` become ``a_min``; values above ``a_max``
        become ``a_max``.

        :param a: Input array.
        :param a_min: Lower bound. Pass ``None`` to skip lower clipping.
        :param a_max: Upper bound. Pass ``None`` to skip upper clipping.
        :param out: Optional pre-allocated output array.

        :returns: Clipped ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([-2.0, 0.5, 3.0])
            >>> print(np.clip(a, 0.0, 2.0))  # array([0.0, 0.5, 2.0])
        ```
        """
        ...

    def equal(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Return element-wise ``True`` where ``x1 == x2``.

        :param x1: First operand.
        :param x2: Second operand.
        :param out: Optional pre-allocated boolean output array.

        :returns: Boolean ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> b = np.array([1, 0, 3])
            >>> print(np.equal(a, b))  # array([True, False, True])
        ```
        """
        ...

    def not_equal(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Return element-wise ``True`` where ``x1 != x2``.

        :param x1: First operand.
        :param x2: Second operand.
        :param out: Optional pre-allocated boolean output array.

        :returns: Boolean ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> b = np.array([1, 0, 3])
            >>> print(np.not_equal(a, b))  # array([False, True, False])
        ```
        """
        ...

    def isfinite(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Test element-wise for finite values (not inf, not nan).

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: Boolean ndarray, ``True`` where values are finite.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, np.inf, np.nan])
            >>> print(np.isfinite(a))  # array([True, False, False])
        ```
        """
        ...

    def isinf(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Test element-wise for positive or negative infinity.

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: Boolean ndarray, ``True`` where values are infinite.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, np.inf, -np.inf])
            >>> print(np.isinf(a))  # array([False, True, True])
        ```
        """
        ...

    def maximum(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Return element-wise maximum of two arrays.

        Propagates NaN when either input is NaN.

        :param x1: First input array.
        :param x2: Second input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of element-wise maxima.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 5, 3])
            >>> b = np.array([4, 2, 6])
            >>> print(np.maximum(a, b))  # array([4, 5, 6])
        ```
        """
        ...

    def minimum(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Return element-wise minimum of two arrays.

        Propagates NaN when either input is NaN.

        :param x1: First input array.
        :param x2: Second input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of element-wise minima.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 5, 3])
            >>> b = np.array([4, 2, 6])
            >>> print(np.minimum(a, b))  # array([1, 2, 3])
        ```
        """
        ...

    def nonzero(self, a: _ArrayLike) -> Any:
        """
        Return the indices of non-zero (truthy) elements.

        :param a: Input array.

        :returns: Tuple of index arrays, one per dimension.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0, 3, 0, 5, 0])
            >>> print(np.nonzero(a))  # (array([1, 3]),)
        ```
        """
        ...

    def where(self, condition: _ArrayLike, x: Optional[_ArrayLike] = None, y: Optional[_ArrayLike] = None) -> Any:
        """
        Return elements from ``x`` or ``y`` depending on ``condition``.

        When called with only ``condition``, equivalent to
        ``np.nonzero(condition)``.

        :param condition: Boolean array selecting values.
        :param x: Values used where ``condition`` is True.
        :param y: Values used where ``condition`` is False.

        :returns: ndarray of selected values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, -2, 3, -4])
            >>> print(np.where(a > 0, a, 0))  # array([1, 0, 3, 0])
        ```
        """
        ...

    def bitwise_and(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise bitwise AND of two integer arrays.

        :param x1: First integer array.
        :param x2: Second integer array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of bitwise AND results.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0b1010, 0b1100], dtype=np.uint8)
            >>> b = np.array([0b1100, 0b1010], dtype=np.uint8)
            >>> print(np.bitwise_and(a, b))
        ```
        """
        ...

    def bitwise_or(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise bitwise OR of two integer arrays.

        :param x1: First integer array.
        :param x2: Second integer array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of bitwise OR results.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0b0010, 0b0100], dtype=np.uint8)
            >>> b = np.array([0b0001, 0b0010], dtype=np.uint8)
            >>> print(np.bitwise_or(a, b))
        ```
        """
        ...

    def bitwise_xor(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise bitwise XOR of two integer arrays.

        :param x1: First integer array.
        :param x2: Second integer array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of bitwise XOR results.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0b1010, 0b0101], dtype=np.uint8)
            >>> b = np.array([0b1111, 0b1111], dtype=np.uint8)
            >>> print(np.bitwise_xor(a, b))
        ```
        """
        ...

    def left_shift(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Shift the bits of ``x1`` left by the amounts in ``x2``.

        :param x1: Integer array to shift.
        :param x2: Number of bit positions to shift left (per element).
        :param out: Optional pre-allocated output array.

        :returns: ndarray with bits shifted left.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 4], dtype=np.uint8)
            >>> print(np.left_shift(a, 1))  # array([2, 4, 8])
        ```
        """
        ...

    def right_shift(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Shift the bits of ``x1`` right by the amounts in ``x2``.

        :param x1: Integer array to shift.
        :param x2: Number of bit positions to shift right (per element).
        :param out: Optional pre-allocated output array.

        :returns: ndarray with bits shifted right.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([8, 16, 32], dtype=np.uint8)
            >>> print(np.right_shift(a, 2))  # array([2, 4, 8])
        ```
        """
        ...

    def convolve(self, a: _ArrayLike, v: _ArrayLike, mode: str = "full") -> ndarray:
        """
        Compute the discrete linear convolution of two 1-D arrays.

        :param a: First input (signal).
        :param v: Second input (filter kernel).
        :param mode: Output size mode — ``"full"`` (default), ``"same"``,
            or ``"valid"``.

        :returns: 1-D ndarray of convolution output.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> signal = np.array([1.0, 2.0, 3.0])
            >>> kernel = np.array([0.5, 0.5])
            >>> print(np.convolve(signal, kernel, mode="same"))
        ```
        """
        ...

    def all(self, a: _ArrayLike, axis: Optional[int] = None) -> Any:
        """
        Return ``True`` only if all elements evaluate to ``True`` (non-zero).

        :param a: Input array.
        :param axis: Axis to reduce over. Tests the whole array if ``None``.

        :returns: Boolean scalar or ndarray of booleans.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> print(np.all(a))   # True
            >>> print(np.all(np.array([1, 0, 1])))  # False
        ```
        """
        ...

    def any(self, a: _ArrayLike, axis: Optional[int] = None) -> Any:
        """
        Return ``True`` if at least one element evaluates to ``True``.

        :param a: Input array.
        :param axis: Axis to reduce over. Tests the whole array if ``None``.

        :returns: Boolean scalar or ndarray of booleans.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0, 0, 1])
            >>> print(np.any(a))  # True
        ```
        """
        ...

    def argmax(self, a: _ArrayLike, axis: Optional[int] = None) -> Any:
        """
        Return the index of the maximum value.

        :param a: Input array.
        :param axis: Axis to search along. Flattens if ``None``.

        :returns: Integer index or ndarray of indices.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([3, 1, 4, 1, 5])
            >>> print(np.argmax(a))  # 4
        ```
        """
        ...

    def argmin(self, a: _ArrayLike, axis: Optional[int] = None) -> Any:
        """
        Return the index of the minimum value.

        :param a: Input array.
        :param axis: Axis to search along. Flattens if ``None``.

        :returns: Integer index or ndarray of indices.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([3, 1, 4, 1, 5])
            >>> print(np.argmin(a))  # 1
        ```
        """
        ...

    def argsort(self, a: _ArrayLike, axis: int = -1) -> ndarray:
        """
        Return the indices that would sort the array.

        The original array is not modified; use ``a[np.argsort(a)]`` to
        retrieve the sorted values.

        :param a: Input array.
        :param axis: Axis to sort along. Default ``-1`` (last axis).

        :returns: Integer ndarray of indices.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([3, 1, 2])
            >>> idx = np.argsort(a)
            >>> print(idx)    # array([1, 2, 0])
            >>> print(a[idx]) # array([1, 2, 3])
        ```
        """
        ...

    def cross(self, a: _ArrayLike, b: _ArrayLike) -> ndarray:
        """
        Compute the cross product of two 3-element 1-D vectors.

        :param a: First vector (must have exactly 3 elements).
        :param b: Second vector (must have exactly 3 elements).

        :returns: 1-D ndarray of 3 elements representing the cross product.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 0, 0])
            >>> b = np.array([0, 1, 0])
            >>> print(np.cross(a, b))  # array([0, 0, 1])
        ```
        """
        ...

    def diff(self, a: _ArrayLike, n: int = 1, axis: int = -1) -> ndarray:
        """
        Compute the n-th discrete difference along the given axis.

        :param a: Input array.
        :param n: Number of times differencing is applied. Default ``1``.
        :param axis: Axis to differentiate along. Default ``-1``.

        :returns: ndarray of differences (length reduced by ``n`` on the axis).

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 3, 6, 10])
            >>> print(np.diff(a))       # array([2, 3, 4])
            >>> print(np.diff(a, n=2))  # array([1, 1])
        ```
        """
        ...

    def dot(self, a: _ArrayLike, b: _ArrayLike) -> Any:
        """
        Compute the dot product of two arrays.

        For 1-D inputs this is the inner (scalar) product. For 2-D inputs
        this is matrix multiplication.

        :param a: First input array.
        :param b: Second input array.

        :returns: Scalar or ndarray dot product result.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3])
            >>> b = np.array([4, 5, 6])
            >>> print(np.dot(a, b))  # 32.0
        ```
        """
        ...

    def trace(self, a: _ArrayLike, offset: int = 0) -> Any:
        """
        Return the sum along the diagonals of a 2-D array.

        :param a: 2-D input array.
        :param offset: Diagonal index. ``0`` is the main diagonal; positive
            values refer to upper diagonals; negative to lower.

        :returns: Scalar sum of the selected diagonal.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[1, 2], [3, 4]])
            >>> print(np.trace(a))  # 5.0
        ```
        """
        ...

    def flip(self, m: _ArrayLike, axis: Optional[int] = None) -> ndarray:
        """
        Reverse the order of elements along the given axis.

        :param m: Input array.
        :param axis: Axis to reverse. Reverses all axes if ``None``.

        :returns: ndarray with elements reversed.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3, 4])
            >>> print(np.flip(a))  # array([4, 3, 2, 1])
        ```
        """
        ...

    def load(self, file: Any) -> ndarray:
        """
        Load an ndarray from a NumPy ``.npy`` file.

        :param file: File path string or file-like object to read from.

        :returns: ndarray stored in the file.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.load("sensor_data.npy")
            >>> print(a.shape)
        ```
        """
        ...

    def loadtxt(
        self,
        file: Any,
        *,
        delimiter: Optional[str] = None,
        comments: Optional[str] = None,
        max_rows: int = -1,
        usecols: Optional[Any] = None,
        dtype: Any = ...,
        skiprows: int = 0,
    ) -> ndarray:
        """
        Load data from a plain-text file into an ndarray.

        :param file: File path string or file-like object.
        :param delimiter: Column separator. Defaults to any whitespace.
        :param comments: Character that marks comment lines (e.g. ``"#"``).
        :param max_rows: Maximum number of rows to read. ``-1`` reads all.
        :param usecols: Column indices to load (integer or tuple).
        :param dtype: Element type of the output array.
        :param skiprows: Number of header rows to skip.

        :returns: 2-D (or 1-D) ndarray of parsed values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> data = np.loadtxt("readings.csv", delimiter=",", skiprows=1)
            >>> print(data.shape)
        ```
        """
        ...

    def save(self, file: Any, array: _ArrayLike) -> None:
        """
        Save an ndarray to a NumPy ``.npy`` file.

        :param file: Destination file path string or file-like object.
        :param array: Array to save.

        :returns: None.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 2.0, 3.0])
            >>> np.save("data.npy", a)
        ```
        """
        ...

    def savetxt(self, file: Any, array: _ArrayLike, delimiter: str = " ") -> None:
        """
        Save an ndarray to a plain-text file.

        :param file: Destination file path string or file-like object.
        :param array: Array to write.
        :param delimiter: String placed between columns. Defaults to a space.

        :returns: None.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 2.0, 3.0])
            >>> np.savetxt("data.csv", a, delimiter=",")
        ```
        """
        ...

    def max(self, array: _ArrayLike, *, axis: Optional[int] = None) -> Any:
        """
        Return the maximum element, optionally along an axis.

        :param array: Input array.
        :param axis: Axis to reduce over. Returns global max if ``None``.

        :returns: Scalar or ndarray of maxima.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([3, 1, 4, 1, 5])
            >>> print(np.max(a))  # 5.0
        ```
        """
        ...

    def mean(self, array: _ArrayLike, *, axis: Optional[int] = None, keepdims: bool = False) -> Any:
        """
        Compute the arithmetic mean.

        :param array: Input array.
        :param axis: Axis to average over. Returns global mean if ``None``.
        :param keepdims: If ``True``, preserve the reduced axis as a
            length-1 dimension.

        :returns: Scalar or ndarray of means.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 2.0, 3.0, 4.0])
            >>> print(np.mean(a))  # 2.5
        ```
        """
        ...

    def median(self, array: _ArrayLike, *, axis: Optional[int] = None) -> Any:
        """
        Compute the median value.

        :param array: Input array.
        :param axis: Axis to compute the median over. Global median if ``None``.

        :returns: Scalar or ndarray of medians.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 3, 2])
            >>> print(np.median(a))  # 2.0
        ```
        """
        ...

    def min(self, array: _ArrayLike, *, axis: Optional[int] = None) -> Any:
        """
        Return the minimum element, optionally along an axis.

        :param array: Input array.
        :param axis: Axis to reduce over. Returns global min if ``None``.

        :returns: Scalar or ndarray of minima.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([3, 1, 4, 1, 5])
            >>> print(np.min(a))  # 1.0
        ```
        """
        ...

    def roll(self, a: _ArrayLike, shift: int, axis: Optional[int] = None) -> ndarray:
        """
        Roll array elements along the given axis.

        Elements that roll off one end re-enter at the other. If ``axis`` is
        ``None``, the array is flattened first.

        :param a: Input array.
        :param shift: Number of positions to shift. Positive shifts right
            (or down); negative shifts left (or up).
        :param axis: Axis to roll along.

        :returns: ndarray with elements shifted.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3, 4, 5])
            >>> print(np.roll(a, 2))   # array([4, 5, 1, 2, 3])
            >>> print(np.roll(a, -1))  # array([2, 3, 4, 5, 1])
        ```
        """
        ...

    def size(self, a: _ArrayLike, axis: Optional[int] = None) -> int:
        """
        Return the total number of elements, or the size along one axis.

        :param a: Input array.
        :param axis: Axis index. Returns total element count if ``None``.

        :returns: Integer element count.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([[1, 2, 3], [4, 5, 6]])
            >>> print(np.size(a))     # 6
            >>> print(np.size(a, 0))  # 2
        ```
        """
        ...

    def sort(self, a: _ArrayLike, axis: int = -1) -> ndarray:
        """
        Return a sorted copy of the array (module-level function).

        Unlike ``ndarray.sort()``, this does not modify the input.

        :param a: Input array.
        :param axis: Axis to sort along. Default ``-1`` (last axis).

        :returns: Sorted copy of the array.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([3, 1, 2])
            >>> print(np.sort(a))  # array([1, 2, 3])
        ```
        """
        ...

    def std(self, array: _ArrayLike, *, axis: Optional[int] = None, ddof: int = 0, keepdims: bool = False) -> Any:
        """
        Compute the standard deviation.

        :param array: Input array.
        :param axis: Axis to reduce over. Global std if ``None``.
        :param ddof: Delta degrees of freedom. Use ``1`` for sample std.
        :param keepdims: Preserve reduced axes as length-1 dimensions.

        :returns: Scalar or ndarray of standard deviations.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
            >>> print(np.std(a))  # 2.0
        ```
        """
        ...

    def sum(self, array: _ArrayLike, *, axis: Optional[int] = None, keepdims: bool = False) -> Any:
        """
        Sum the array elements.

        :param array: Input array.
        :param axis: Axis to sum along. Returns the total sum if ``None``.
        :param keepdims: Preserve reduced axes as length-1 dimensions.

        :returns: Scalar or ndarray of sums.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1, 2, 3, 4])
            >>> print(np.sum(a))  # 10.0
        ```
        """
        ...

    def polyfit(self, x: _ArrayLike, y: _ArrayLike, deg: int) -> ndarray:
        """
        Least-squares polynomial fit to data (``x``, ``y``).

        Coefficients are ordered from highest degree to lowest,
        matching NumPy convention.

        :param x: x-axis sample positions.
        :param y: Observed y-axis values.
        :param deg: Degree of the fitting polynomial.

        :returns: 1-D ndarray of coefficients, length ``deg + 1``.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> x = np.array([0.0, 1.0, 2.0, 3.0])
            >>> y = np.array([0.0, 1.0, 4.0, 9.0])
            >>> coeffs = np.polyfit(x, y, deg=2)
            >>> print(coeffs)  # approx [1.0, 0.0, 0.0]
        ```
        """
        ...

    def polyval(self, p: _ArrayLike, x: _ArrayLike) -> ndarray:
        """
        Evaluate a polynomial at the given points.

        :param p: 1-D array of polynomial coefficients, highest degree first.
        :param x: Points at which to evaluate.

        :returns: ndarray of polynomial values at ``x``.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> p = np.array([1.0, 0.0, -1.0])  # x^2 - 1
            >>> x = np.array([0.0, 1.0, 2.0])
            >>> print(np.polyval(p, x))  # array([-1.0, 0.0, 3.0])
        ```
        """
        ...

    def interp(self, x: _ArrayLike, xp: _ArrayLike, fp: _ArrayLike) -> ndarray:
        """
        Perform one-dimensional piecewise-linear interpolation.

        :param x: Points at which to interpolate.
        :param xp: 1-D array of reference x-positions (must be strictly
            increasing).
        :param fp: 1-D array of reference y-values at ``xp``.

        :returns: Interpolated ndarray of the same length as ``x``.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> xp = np.array([0.0, 1.0, 2.0])
            >>> fp = np.array([0.0, 10.0, 20.0])
            >>> xi = np.array([0.5, 1.5])
            >>> print(np.interp(xi, xp, fp))  # array([5.0, 15.0])
        ```
        """
        ...

    def trapz(self, y: _ArrayLike, x: Optional[_ArrayLike] = None, dx: float = 1.0, axis: int = -1) -> Any:
        """
        Integrate using the composite trapezoidal rule.

        :param y: 1-D array of y-values to integrate.
        :param x: Sample positions. If ``None``, uniform spacing of ``dx``
            is assumed.
        :param dx: Spacing between samples when ``x`` is not provided.
        :param axis: Axis to integrate along.

        :returns: Scalar or ndarray of integral approximations.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> y = np.array([0.0, 1.0, 4.0, 9.0])
            >>> x = np.array([0.0, 1.0, 2.0, 3.0])
            >>> print(np.trapz(y, x))  # approx 9.0
        ```
        """
        ...

    def acos(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise arc cosine (in radians).

        :param x: Input array with values in [-1, 1].
        :param out: Optional pre-allocated output array.

        :returns: ndarray of arc cosine values in [0, π].

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 0.0, -1.0])
            >>> print(np.acos(a))  # array([0.0, 1.5708, 3.1416])
        ```
        """
        ...

    def acosh(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise inverse hyperbolic cosine.

        :param x: Input array with values >= 1.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of inverse hyperbolic cosine values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 2.0, 10.0])
            >>> print(np.acosh(a))
        ```
        """
        ...

    def arctan2(self, x1: _ArrayLike, x2: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise arc tangent of ``x1/x2``, using the signs to
        determine the correct quadrant.

        :param x1: y-coordinates.
        :param x2: x-coordinates.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of angles in radians in [-π, π].

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> y = np.array([ 1.0, -1.0])
            >>> x = np.array([ 1.0,  1.0])
            >>> print(np.arctan2(y, x))  # array([0.7854, -0.7854])
        ```
        """
        ...

    def around(self, x: _ArrayLike, decimals: int = 0, out: Optional[ndarray] = None) -> ndarray:
        """
        Round array elements to the given number of decimal places.

        :param x: Input array.
        :param decimals: Number of decimal places. Default ``0`` (nearest int).
        :param out: Optional pre-allocated output array.

        :returns: Rounded ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.235, 2.456])
            >>> print(np.around(a, decimals=1))  # array([1.2, 2.5])
        ```
        """
        ...

    def asin(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise arc sine (in radians).

        :param x: Input array with values in [-1, 1].
        :param out: Optional pre-allocated output array.

        :returns: ndarray of arc sine values in [-π/2, π/2].

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, 0.5, 1.0])
            >>> print(np.asin(a))
        ```
        """
        ...

    def asinh(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise inverse hyperbolic sine.

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of inverse hyperbolic sine values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, 1.0, 2.0])
            >>> print(np.asinh(a))
        ```
        """
        ...

    def atan(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise arc tangent (in radians).

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of arc tangent values in [-π/2, π/2].

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, 1.0, -1.0])
            >>> print(np.atan(a))
        ```
        """
        ...

    def atanh(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise inverse hyperbolic tangent.

        :param x: Input array with values in the open interval (-1, 1).
        :param out: Optional pre-allocated output array.

        :returns: ndarray of inverse hyperbolic tangent values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, 0.5, -0.5])
            >>> print(np.atanh(a))
        ```
        """
        ...

    def ceil(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Round each element up to the nearest integer.

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of ceiling values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.2, 2.7, -0.3])
            >>> print(np.ceil(a))  # array([2.0, 3.0, 0.0])
        ```
        """
        ...

    def cos(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise cosine. Input in radians.

        :param x: Input array of angles in radians.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of cosine values in [-1, 1].

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> x = np.linspace(0, np.pi, num=5)
            >>> print(np.cos(x))
        ```
        """
        ...

    def cosh(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise hyperbolic cosine.

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of hyperbolic cosine values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, 1.0, 2.0])
            >>> print(np.cosh(a))
        ```
        """
        ...

    def degrees(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Convert angles from radians to degrees.

        :param x: Input array of angles in radians.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of angles in degrees.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, np.pi / 2, np.pi])
            >>> print(np.degrees(a))  # array([0.0, 90.0, 180.0])
        ```
        """
        ...

    def exp(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise natural exponential e^x.

        :param x: Input array (exponents).
        :param out: Optional pre-allocated output array.

        :returns: ndarray of e^x values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, 1.0, 2.0])
            >>> print(np.exp(a))  # array([1.0, 2.7183, 7.3891])
        ```
        """
        ...

    def expm1(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise exp(x) - 1, accurate near zero.

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of exp(x) - 1 values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, 0.001, 1.0])
            >>> print(np.expm1(a))
        ```
        """
        ...

    def floor(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Round each element down to the nearest integer.

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of floor values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.7, 2.1, -0.3])
            >>> print(np.floor(a))  # array([1.0, 2.0, -1.0])
        ```
        """
        ...

    def log(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise natural logarithm (base e).

        :param x: Input array (values must be positive).
        :param out: Optional pre-allocated output array.

        :returns: ndarray of natural log values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, np.e, np.e ** 2])
            >>> print(np.log(a))  # array([0.0, 1.0, 2.0])
        ```
        """
        ...

    def log10(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise base-10 logarithm.

        :param x: Input array (values must be positive).
        :param out: Optional pre-allocated output array.

        :returns: ndarray of log₁₀ values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 10.0, 100.0])
            >>> print(np.log10(a))  # array([0.0, 1.0, 2.0])
        ```
        """
        ...

    def log2(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise base-2 logarithm.

        :param x: Input array (values must be positive).
        :param out: Optional pre-allocated output array.

        :returns: ndarray of log₂ values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 2.0, 8.0])
            >>> print(np.log2(a))  # array([0.0, 1.0, 3.0])
        ```
        """
        ...

    def radians(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Convert angles from degrees to radians.

        :param x: Input array of angles in degrees.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of angles in radians.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, 90.0, 180.0])
            >>> print(np.radians(a))  # array([0.0, 1.5708, 3.1416])
        ```
        """
        ...

    def sin(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise sine. Input in radians.

        :param x: Input array of angles in radians.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of sine values in [-1, 1].

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> x = np.linspace(0, 2 * np.pi, num=4)
            >>> print(np.sin(x))
        ```
        """
        ...

    def sinc(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise normalized sinc: sin(πx) / (πx).

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of sinc values (1.0 at x=0).

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([-1.0, 0.0, 1.0])
            >>> print(np.sinc(a))  # array([0.0, 1.0, 0.0])
        ```
        """
        ...

    def sinh(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise hyperbolic sine.

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of hyperbolic sine values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, 1.0, 2.0])
            >>> print(np.sinh(a))
        ```
        """
        ...

    def sqrt(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise square root.

        :param x: Input array (non-negative for real results).
        :param out: Optional pre-allocated output array.

        :returns: ndarray of square root values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([1.0, 4.0, 9.0, 16.0])
            >>> print(np.sqrt(a))  # array([1.0, 2.0, 3.0, 4.0])
        ```
        """
        ...

    def tan(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise tangent. Input in radians.

        :param x: Input array of angles in radians.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of tangent values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([0.0, np.pi / 4])
            >>> print(np.tan(a))  # array([0.0, 1.0])
        ```
        """
        ...

    def tanh(self, x: _ArrayLike, out: Optional[ndarray] = None) -> ndarray:
        """
        Compute element-wise hyperbolic tangent.

        :param x: Input array.
        :param out: Optional pre-allocated output array.

        :returns: ndarray of hyperbolic tangent values in (-1, 1).

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> a = np.array([-2.0, 0.0, 2.0])
            >>> print(np.tanh(a))
        ```
        """
        ...

    def vectorize(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """
        Return a vectorized version of a Python scalar function.

        The returned callable accepts ndarray inputs and applies ``func``
        element-wise, returning an ndarray of results.

        :param func: Callable that accepts a single scalar and returns a scalar.

        :returns: Vectorized function accepting ndarray arguments.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> def clip01(v):
            ...     return max(0.0, min(1.0, v))
            >>> vclip = np.vectorize(clip01)
            >>> a = np.array([-0.5, 0.3, 1.2])
            >>> print(vclip(a))  # array([0.0, 0.3, 1.0])
        ```
        """
        ...

    def real(self, x: _ArrayLike) -> ndarray:
        """
        Return the real part of a complex array.

        :param x: Input complex ndarray.

        :returns: ndarray of real parts.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> fr, fi = np.fft.fft(np.array([1.0, 2.0, 3.0, 4.0]))
            >>> print(np.real(fr))
        ```
        """
        ...

    def imag(self, x: _ArrayLike) -> ndarray:
        """
        Return the imaginary part of a complex array.

        For real-valued inputs the result is an array of zeros.

        :param x: Input complex ndarray.

        :returns: ndarray of imaginary parts.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> fr, fi = np.fft.fft(np.array([1.0, 2.0, 3.0, 4.0]))
            >>> print(np.imag(fi))
        ```
        """
        ...

    def conjugate(self, x: _ArrayLike) -> ndarray:
        """
        Return the complex conjugate of each element.

        For real-valued arrays the result is identical to the input.

        :param x: Input array.

        :returns: ndarray of complex conjugates.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> x = np.array([1.0, 2.0])
            >>> print(np.conjugate(x))
        ```
        """
        ...

    def sort_complex(self, x: _ArrayLike) -> ndarray:
        """
        Sort a complex array, first by real part then by imaginary part.

        :param x: Input complex ndarray.

        :returns: Sorted ndarray.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>>
            >>> fr, _ = np.fft.fft(np.array([3.0, 1.0, 2.0, 4.0]))
            >>> print(np.sort_complex(fr))
        ```
        """
        ...


class ScipyIntegrateModule(Protocol):
    """ulab.scipy.integrate — numerical integration routines."""

    def tanhsinh(self, f: Callable[[float], float], a: float, b: float, *, eps: float = 1e-8, levels: int = 10) -> Any:
        """
        Numerically integrate ``f`` on [a, b] using tanh-sinh (double-exponential)
        quadrature.

        Handles endpoint singularities well and converges quickly for smooth
        integrands.

        :param f: Scalar function to integrate.
        :param a: Lower limit.
        :param b: Upper limit.
        :param eps: Target absolute error tolerance.
        :param levels: Maximum number of refinement levels.

        :returns: Approximated integral value.

        Example
        -------
        ```python
            >>> from ulab import scipy as spy
            >>>
            >>> result = spy.integrate.tanhsinh(lambda x: x ** 2, 0, 1)
            >>> print(result)  # approx 0.3333
        ```
        """
        ...

    def romberg(self, f: Callable[[float], float], a: float, b: float, *, eps: float = 1e-8, steps: int = 8) -> Any:
        """
        Numerically integrate ``f`` on [a, b] using Romberg's method.

        :param f: Scalar function to integrate.
        :param a: Lower limit.
        :param b: Upper limit.
        :param eps: Target absolute error tolerance.
        :param steps: Number of Richardson extrapolation steps.

        :returns: Approximated integral value.

        Example
        -------
        ```python
            >>> from ulab import scipy as spy
            >>>
            >>> result = spy.integrate.romberg(lambda x: x ** 2, 0, 1)
            >>> print(result)  # approx 0.3333
        ```
        """
        ...

    def simpson(self, y: _ArrayLike, x: Optional[_ArrayLike] = None, dx: float = 1.0, axis: int = -1) -> Any:
        """
        Integrate array ``y`` using composite Simpson's rule.

        :param y: 1-D array of function values.
        :param x: Optional sample positions. Uniform spacing of ``dx``
            is assumed when omitted.
        :param dx: Sample spacing when ``x`` is omitted.
        :param axis: Axis to integrate along.

        :returns: Approximated integral value.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import scipy as spy
            >>>
            >>> x = np.linspace(0, 1, num=5)
            >>> y = x ** 2
            >>> print(spy.integrate.simpson(y, x))  # approx 0.3333
        ```
        """
        ...

    def quad(self, f: Callable[[float], float], a: float, b: float, *, order: int = 3, eps: float = 1e-8) -> Any:
        """
        Compute a definite integral using Gaussian quadrature.

        :param f: Scalar function to integrate.
        :param a: Lower limit.
        :param b: Upper limit.
        :param order: Order of the Gaussian quadrature rule.
        :param eps: Absolute error tolerance.

        :returns: Approximated integral value.

        Example
        -------
        ```python
            >>> from ulab import scipy as spy
            >>>
            >>> result = spy.integrate.quad(lambda x: x ** 2, 0, 1)
            >>> print(result)  # approx 0.3333
        ```
        """
        ...


class ScipyLinalgModule(Protocol):
    """ulab.scipy.linalg — advanced linear algebra routines."""

    def solve_triangular(self, a: _ArrayLike, b: _ArrayLike, lower: bool = False) -> ndarray:
        """
        Solve ``a @ x = b`` for ``x``, assuming ``a`` is triangular.

        :param a: Upper or lower triangular 2-D square matrix.
        :param b: Right-hand side vector or matrix.
        :param lower: Treat ``a`` as lower triangular if ``True``.
            Defaults to ``False`` (upper triangular).

        :returns: Solution ndarray ``x`` such that ``a @ x == b``.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import scipy as spy
            >>>
            >>> a = np.array([[1.0, 2.0], [0.0, 3.0]])  # upper triangular
            >>> b = np.array([5.0, 6.0])
            >>> x = spy.linalg.solve_triangular(a, b)
            >>> print(x)
        ```
        """
        ...

    def cho_solve(self, c_and_lower: Any, b: _ArrayLike) -> ndarray:
        """
        Solve a linear system using a pre-computed Cholesky factorization.

        :param c_and_lower: Tuple ``(c, lower)`` — Cholesky factor array and
            a bool indicating whether it is the lower triangle.
        :param b: Right-hand side vector.

        :returns: Solution ndarray ``x`` such that ``A @ x == b``.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import scipy as spy
            >>>
            >>> a = np.array([[4.0, 2.0], [2.0, 3.0]])
            >>> L = np.linalg.cholesky(a)
            >>> b = np.array([1.0, 2.0])
            >>> x = spy.linalg.cho_solve((L, True), b)
            >>> print(x)
        ```
        """
        ...


class ScipyOptimizeModule(Protocol):
    """ulab.scipy.optimize — scalar function optimization and root finding."""

    def bisect(self, f: Callable[[float], float], a: float, b: float, *, xtol: float = 1e-12, maxiter: int = 100) -> float:
        """
        Find a root of ``f`` in [a, b] using the bisection method.

        ``f(a)`` and ``f(b)`` must have opposite signs.

        :param f: Scalar function for which a root is sought.
        :param a: Left endpoint of the bracket.
        :param b: Right endpoint of the bracket.
        :param xtol: Absolute tolerance on the root position.
        :param maxiter: Maximum number of bisection iterations.

        :returns: Approximate root as a float.

        Example
        -------
        ```python
            >>> from ulab import scipy as spy
            >>>
            >>> root = spy.optimize.bisect(lambda x: x ** 2 - 2, 1.0, 2.0)
            >>> print(root)  # approx 1.4142
        ```
        """
        ...

    def fmin(self, f: Callable[[Any], float], x0: _ArrayLike, *, xatol: float = 1e-4, fatol: float = 1e-4, maxiter: int = 200) -> Any:
        """
        Minimize a scalar function using the Nelder-Mead simplex algorithm.

        :param f: Objective function returning a scalar.
        :param x0: Initial guess (scalar or 1-D ndarray).
        :param xatol: Absolute tolerance on the solution position.
        :param fatol: Absolute tolerance on the function value.
        :param maxiter: Maximum number of function evaluations.

        :returns: Approximate minimizer as a scalar or ndarray.

        Example
        -------
        ```python
            >>> from ulab import scipy as spy
            >>>
            >>> def cost(x): return (x - 3.0) ** 2
            >>> result = spy.optimize.fmin(cost, 0.0)
            >>> print(result)  # approx 3.0
        ```
        """
        ...

    def newton(self, f: Callable[[float], float], x0: float, *, tol: float = 1e-8, rtol: float = 0.0, maxiter: int = 50) -> float:
        """
        Find a root of ``f`` near ``x0`` using the Newton-Raphson / secant method.

        :param f: Scalar function for which a root is sought.
        :param x0: Initial guess.
        :param tol: Absolute convergence tolerance.
        :param rtol: Relative convergence tolerance.
        :param maxiter: Maximum number of iterations.

        :returns: Approximate root as a float.

        :raises RuntimeError: If convergence is not achieved within ``maxiter``.

        Example
        -------
        ```python
            >>> from ulab import scipy as spy
            >>>
            >>> root = spy.optimize.newton(lambda x: x ** 2 - 2, 1.5)
            >>> print(root)  # approx 1.4142
        ```
        """
        ...

    def curve_fit(self, f: Callable[..., Any], x: _ArrayLike, y: _ArrayLike, p0: Optional[_ArrayLike] = None) -> Any:
        """
        Fit a user-defined model function to data using non-linear least squares.

        :param f: Model function ``f(x, *params)`` returning fitted y values.
        :param x: 1-D array of independent variable samples.
        :param y: 1-D array of observed values.
        :param p0: Initial parameter guess. All parameters start at 1 if
            ``None``.

        :returns: Tuple ``(popt, pcov)`` — optimal parameters and covariance
            matrix estimate.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import scipy as spy
            >>>
            >>> def model(x, a, b):
            ...     return a * np.exp(-b * x)
            >>> x = np.linspace(0, 2, num=10)
            >>> y = model(x, 2.0, 1.5)
            >>> popt, _ = spy.optimize.curve_fit(model, x, y)
            >>> print(popt)
        ```
        """
        ...


class ScipySignalModule(Protocol):
    """ulab.scipy.signal — digital signal processing filters."""

    def sosfilt(self, sos: _ArrayLike, x: _ArrayLike, zi: Optional[_ArrayLike] = None) -> Any:
        """
        Filter data using cascaded second-order sections (SOS).

        SOS form is the numerically stable IIR filter representation. Each
        row of ``sos`` is ``[b0, b1, b2, a0, a1, a2]`` for one biquad section.

        :param sos: 2-D array of SOS coefficients, shape ``(n_sections, 6)``.
        :param x: 1-D input signal array.
        :param zi: Optional initial delay state, shape ``(n_sections, 2)``.

        :returns: Tuple ``(y, zf)`` — filtered signal and final delay state,
            or just ``y`` when ``zi`` is omitted.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import scipy as spy
            >>>
            >>> sos = np.array([[0.1, 0.2, 0.1, 1.0, -0.5, 0.1]])
            >>> x = np.ones(16)
            >>> y, zf = spy.signal.sosfilt(sos, x)
            >>> print(y)
        ```
        """
        ...


class ScipySpecialModule(Protocol):
    """ulab.scipy.special — special mathematical functions."""

    def erf(self, x: _ArrayLike) -> Any:
        """
        Compute the error function element-wise.

        erf(x) = (2/√π) ∫₀ˣ e^(−t²) dt. Used in statistics to express
        cumulative normal probabilities.

        :param x: Input array.

        :returns: ndarray of erf values in (-1, 1).

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import scipy as spy
            >>>
            >>> a = np.array([0.0, 0.5, 1.0, 2.0])
            >>> print(spy.special.erf(a))
        ```
        """
        ...

    def erfc(self, x: _ArrayLike) -> Any:
        """
        Compute the complementary error function erfc(x) = 1 - erf(x).

        Avoids catastrophic cancellation for large ``x`` where 1 - erf(x) is
        very small.

        :param x: Input array.

        :returns: ndarray of erfc values in (0, 2).

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import scipy as spy
            >>>
            >>> a = np.array([0.0, 1.0, 2.0])
            >>> print(spy.special.erfc(a))
        ```
        """
        ...

    def gamma(self, x: _ArrayLike) -> Any:
        """
        Compute the Gamma function Γ(x) element-wise.

        For positive integers ``n``, Γ(n) = (n-1)!.

        :param x: Input array (real values; undefined for non-positive integers).

        :returns: ndarray of Gamma function values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import scipy as spy
            >>>
            >>> a = np.array([1.0, 2.0, 3.0, 4.0])
            >>> print(spy.special.gamma(a))  # array([1.0, 1.0, 2.0, 6.0])
        ```
        """
        ...

    def gammaln(self, x: _ArrayLike) -> Any:
        """
        Compute ln|Γ(x)| element-wise.

        Avoids overflow for large ``x`` where ``gamma(x)`` exceeds the
        floating-point range.

        :param x: Input array (real values, must not be zero or negative
            integers).

        :returns: ndarray of ln|Γ(x)| values.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import scipy as spy
            >>>
            >>> a = np.array([1.0, 5.0, 10.0])
            >>> print(spy.special.gammaln(a))
        ```
        """
        ...


class ScipyModule(Protocol):
    """ulab.scipy — SciPy-compatible scientific computing for MicroPython."""

    integrate: ScipyIntegrateModule
    linalg: ScipyLinalgModule
    optimize: ScipyOptimizeModule
    signal: ScipySignalModule
    special: ScipySpecialModule


class UtilsModule(Protocol):
    """ulab.utils — buffer conversion and DSP utility functions."""

    def from_int16_buffer(
        self,
        buffer: Any,
        *,
        count: int = -1,
        offset: int = 0,
        out: Optional[ndarray] = None,
        byteswap: bool = False,
    ) -> ndarray:
        """
        Create a float ndarray from a buffer of signed 16-bit integers.

        Converts each int16 sample in ``buffer`` to a float. Commonly used
        to convert raw ADC or I²S audio samples.

        :param buffer: Source buffer (bytes, bytearray, memoryview).
        :param count: Number of int16 samples to convert. ``-1`` uses all.
        :param offset: Byte offset into the buffer before reading.
        :param out: Optional pre-allocated float ndarray for the output.
        :param byteswap: Swap the byte order of each int16 before converting.

        :returns: 1-D float ndarray of converted values.

        Example
        -------
        ```python
            >>> from ulab import utils, numpy as np
            >>>
            >>> raw = bytearray([0x00, 0x01, 0xFF, 0x7F])
            >>> a = utils.from_int16_buffer(raw)
            >>> print(a)
        ```
        """
        ...

    def from_uint16_buffer(
        self,
        buffer: Any,
        *,
        count: int = -1,
        offset: int = 0,
        out: Optional[ndarray] = None,
        byteswap: bool = False,
    ) -> ndarray:
        """
        Create a float ndarray from a buffer of unsigned 16-bit integers.

        :param buffer: Source buffer (bytes, bytearray, memoryview).
        :param count: Number of uint16 samples to convert. ``-1`` uses all.
        :param offset: Byte offset into the buffer.
        :param out: Optional pre-allocated output array.
        :param byteswap: Swap the byte order of each uint16 before converting.

        :returns: 1-D float ndarray of converted values.

        Example
        -------
        ```python
            >>> from ulab import utils, numpy as np
            >>>
            >>> raw = bytearray([0x00, 0x10, 0x00, 0x20])
            >>> a = utils.from_uint16_buffer(raw)
            >>> print(a)
        ```
        """
        ...

    def from_int32_buffer(
        self,
        buffer: Any,
        *,
        count: int = -1,
        offset: int = 0,
        out: Optional[ndarray] = None,
        byteswap: bool = False,
    ) -> ndarray:
        """
        Create a float ndarray from a buffer of signed 32-bit integers.

        :param buffer: Source buffer (bytes, bytearray, memoryview).
        :param count: Number of int32 samples to convert. ``-1`` uses all.
        :param offset: Byte offset into the buffer.
        :param out: Optional pre-allocated output array.
        :param byteswap: Swap the byte order of each int32 before converting.

        :returns: 1-D float ndarray of converted values.

        Example
        -------
        ```python
            >>> from ulab import utils, numpy as np
            >>>
            >>> raw = bytearray(8)  # two zero int32 values
            >>> a = utils.from_int32_buffer(raw)
            >>> print(a)
        ```
        """
        ...

    def from_uint32_buffer(
        self,
        buffer: Any,
        *,
        count: int = -1,
        offset: int = 0,
        out: Optional[ndarray] = None,
        byteswap: bool = False,
    ) -> ndarray:
        """
        Create a float ndarray from a buffer of unsigned 32-bit integers.

        :param buffer: Source buffer (bytes, bytearray, memoryview).
        :param count: Number of uint32 samples to convert. ``-1`` uses all.
        :param offset: Byte offset into the buffer.
        :param out: Optional pre-allocated output array.
        :param byteswap: Swap the byte order of each uint32 before converting.

        :returns: 1-D float ndarray of converted values.

        Example
        -------
        ```python
            >>> from ulab import utils, numpy as np
            >>>
            >>> raw = bytearray(8)
            >>> a = utils.from_uint32_buffer(raw)
            >>> print(a)
        ```
        """
        ...

    def spectrogram(self, r: ndarray, *args: Any, scratchpad: Optional[ndarray] = None, out: Optional[ndarray] = None, log: bool = False) -> ndarray:
        """
        Compute the power spectrum of a 1-D signal.

        Performs an in-place FFT and returns the magnitude (or log-magnitude)
        squared for each frequency bin. The signal length must be a power of 2.

        :param r: Real input signal array (length must be a power of 2).
        :param args: Optional imaginary part array.
        :param scratchpad: Optional working buffer of the same length as ``r``.
        :param out: Optional pre-allocated output array.
        :param log: Return the log (dB-scale) power spectrum when ``True``.

        :returns: 1-D float ndarray of power values,
            length ``len(r) // 2 + 1``.

        Example
        -------
        ```python
            >>> from ulab import numpy as np
            >>> from ulab import utils
            >>>
            >>> signal = np.array([float(i % 8) for i in range(64)])
            >>> spectrum = utils.spectrogram(signal)
            >>> print(spectrum.shape)
        ```
        """
        ...


class UserModule(Protocol):
    """
    ulab.user — firmware-customizable extension namespace.

    Any user-registered C function may appear as an attribute. Dynamic
    attribute access is allowed by design.
    """

    def __getattr__(self, name: str) -> Any:
        """
        Return a user-registered function or value by name.

        :param name: Name of the function registered in the firmware's
            ulab user module.

        :returns: Callable or value registered under ``name``.

        :raises AttributeError: If no entry with that name has been registered.

        Example
        -------
        ```python
            >>> from ulab import user
            >>>
            >>> # Assumes 'my_func' was registered in custom firmware
            >>> result = user.my_func(1.0, 2.0)
        ```
        """
        ...


__name__: str
__version__: str
__sha__: str

numpy: NumpyModule
scipy: ScipyModule
utils: UtilsModule
user: UserModule
