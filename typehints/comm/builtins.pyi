"""MicroPython built-in functions and types.

This file provides type hints for built-in functions and classes available in
the global namespace.

Notes
-----
- MicroPython is not CPython: some built-ins may be missing, simplified, or
    behave slightly differently depending on the port and build configuration.
- Memory and performance constraints are a major design driver; prefer streaming
    APIs and avoid large temporary allocations where possible.
"""

from typing import Any, Callable, Generator, Iterable, Iterator, Optional, Sequence, Type, Union, overload


# ============================================================================
# Viper Types
# ============================================================================

class uint:
    """
    Viper type: unsigned integer.
    
    Use inside @micropython.viper decorated functions for native unsigned int operations.
    Cast Python integers to native machine word for faster arithmetic.
    
    Example
    -------
    ```python
        >>> @micropython.viper
        >>> def fast_count() -> uint:
        ...     count: uint = uint(0)
        ...     for i in range(1000):
        ...         count = uint(count) + uint(1)
        ...     return count
    ```
    """
    def __init__(self, value: int) -> None: ...


class ptr:
    """
    Viper type: generic pointer (machine word size).
    
    Use inside @micropython.viper decorated functions for raw memory access.
    Points to machine-word sized values.
    
    Example
    -------
    ```python
        >>> @micropython.viper
        >>> def get_address(buf) -> ptr:
        ...     p = ptr(buf)
        ...     return p
    ```
    """
    def __init__(self, buf: Any) -> None: ...
    def __getitem__(self, index: int) -> int: ...
    def __setitem__(self, index: int, value: int) -> None: ...


class ptr8:
    """
    Viper type: pointer to 8-bit (byte) values.
    
    Use inside @micropython.viper decorated functions for fast byte access.
    
    Example
    -------
    ```python
        >>> @micropython.viper
        >>> def fill_buffer(buf):
        ...     p = ptr8(buf)
        ...     for i in range(len(buf)):
        ...         p[i] = 0xFF
    ```
    """
    def __init__(self, buf: Any) -> None: ...
    def __getitem__(self, index: int) -> int: ...
    def __setitem__(self, index: int, value: int) -> None: ...


class ptr16:
    """
    Viper type: pointer to 16-bit (half-word) values.
    
    Use inside @micropython.viper decorated functions for fast 16-bit access.
    
    Example
    -------
    ```python
        >>> @micropython.viper
        >>> def fill_shorts(buf):
        ...     p = ptr16(buf)
        ...     for i in range(len(buf) // 2):
        ...         p[i] = 0xFFFF
    ```
    """
    def __init__(self, buf: Any) -> None: ...
    def __getitem__(self, index: int) -> int: ...
    def __setitem__(self, index: int, value: int) -> None: ...


class ptr32:
    """
    Viper type: pointer to 32-bit (word) values.
    
    Use inside @micropython.viper decorated functions for fast 32-bit access.
    
    Example
    -------
    ```python
        >>> @micropython.viper
        >>> def fill_words(buf):
        ...     p = ptr32(buf)
        ...     for i in range(len(buf) // 4):
        ...         p[i] = 0xFFFFFFFF
    ```
    """
    def __init__(self, buf: Any) -> None: ...
    def __getitem__(self, index: int) -> int: ...
    def __setitem__(self, index: int, value: int) -> None: ...


# ============================================================================
# Built-in Types
# ============================================================================

class object:
    """Base class for all objects."""
    def __init__(self) -> None: ...
    def __repr__(self) -> str: ...
    def __str__(self) -> str: ...


class int:
    """
    Integer type.

    Example
    -------
    ```python
        >>> x = int(42)
        >>> y = int("ff", 16)  # 255
        >>> z = int(3.14)       # 3
    ```
    """
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, x: Union[str, bytes, int, float]) -> None: ...
    @overload
    def __init__(self, x: str, base: int) -> None: ...

    def to_bytes(self, length: int, byteorder: str) -> bytes:
        """
        Return bytes representation.

        :param length: Number of bytes
        :param byteorder: 'big' or 'little'

        :returns: Bytes representation

        Example
        -------
        ```python
            >>> n = 256
            >>> n.to_bytes(2, 'big')    # b'\\x01\\x00'
            >>> n.to_bytes(2, 'little') # b'\\x00\\x01'
        ```
        """
        ...

    @classmethod
    def from_bytes(cls, bytes: bytes, byteorder: str) -> int:
        """
        Create int from bytes.

        :param bytes: Source bytes
        :param byteorder: 'big' or 'little'

        :returns: Integer value

        Example
        -------
        ```python
            >>> int.from_bytes(b'\\x01\\x00', 'big')  # 256
        ```
        """
        ...


class float:
    """
    Floating point type.

    Example
    -------
    ```python
        >>> x = float(42)
        >>> y = float("3.14")
    ```
    """
    def __init__(self, x: Union[str, int, float] = ...) -> None: ...


class bool:
    """
    Boolean type.

    Example
    -------
    ```python
        >>> x = bool(1)    # True
        >>> y = bool([])   # False
        >>> z = bool("hi") # True
    ```
    """
    def __init__(self, x: Any = ...) -> None: ...


class str:
    """
    String type.

    Example
    -------
    ```python
        >>> s = str(42)
        >>> s = "hello"
        >>> s.upper()  # "HELLO"
    ```
    """
    def __init__(self, object: Any = ..., encoding: str = ..., errors: str = ...) -> None: ...

    def encode(self, encoding: str = "utf-8") -> bytes:
        """Encode string to bytes."""
        ...

    def format(self, *args, **kwargs) -> str:
        """Format string."""
        ...

    def split(self, sep: str = None, maxsplit: int = -1) -> list:
        """Split string."""
        ...

    def join(self, iterable: Iterable[str]) -> str:
        """Join strings."""
        ...

    def strip(self, chars: str = None) -> str:
        """Strip characters."""
        ...

    def lstrip(self, chars: str = None) -> str:
        """Strip left characters."""
        ...

    def rstrip(self, chars: str = None) -> str:
        """Strip right characters."""
        ...

    def find(self, sub: str, start: int = 0, end: int = None) -> int:
        """Find substring."""
        ...

    def rfind(self, sub: str, start: int = 0, end: int = None) -> int:
        """Find substring from right."""
        ...

    def replace(self, old: str, new: str, count: int = -1) -> str:
        """Replace substring."""
        ...

    def startswith(self, prefix: str) -> bool:
        """Check prefix."""
        ...

    def endswith(self, suffix: str) -> bool:
        """Check suffix."""
        ...

    def upper(self) -> str:
        """Convert to uppercase."""
        ...

    def lower(self) -> str:
        """Convert to lowercase."""
        ...

    def isdigit(self) -> bool:
        """Check if all digits."""
        ...

    def isalpha(self) -> bool:
        """Check if all alphabetic."""
        ...

    def isspace(self) -> bool:
        """Check if all whitespace."""
        ...

    def count(self, sub: str) -> int:
        """Count occurrences."""
        ...

    def center(self, width: int, fillchar: str = " ") -> str:
        """Center string."""
        ...

    def partition(self, sep: str) -> tuple:
        """Partition string."""
        ...

    def rpartition(self, sep: str) -> tuple:
        """Partition from right."""
        ...


class bytes:
    """
    Bytes type (immutable).

    Example
    -------
    ```python
        >>> b = bytes([0x01, 0x02, 0x03])
        >>> b = b'hello'
        >>> b.decode()  # 'hello'
    ```
    """
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, length: int) -> None: ...
    @overload
    def __init__(self, source: Iterable[int]) -> None: ...
    @overload
    def __init__(self, source: str, encoding: str = ...) -> None: ...

    def decode(self, encoding: str = "utf-8") -> str:
        """Decode to string."""
        ...

    def find(self, sub: bytes, start: int = 0, end: int = None) -> int:
        """Find subsequence."""
        ...

    def count(self, sub: bytes) -> int:
        """Count occurrences."""
        ...

    def startswith(self, prefix: bytes) -> bool:
        """Check prefix."""
        ...

    def endswith(self, suffix: bytes) -> bool:
        """Check suffix."""
        ...


class bytearray:
    """
    Mutable bytes type.

    Example
    -------
    ```python
        >>> ba = bytearray(10)
        >>> ba[0] = 0xFF
        >>> ba.extend(b'more')
    ```
    """
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(self, length: int) -> None: ...
    @overload
    def __init__(self, source: Iterable[int]) -> None: ...

    def append(self, item: int) -> None:
        """Append byte."""
        ...

    def extend(self, iterable: Iterable[int]) -> None:
        """Extend with bytes."""
        ...

    def decode(self, encoding: str = "utf-8") -> str:
        """Decode to string."""
        ...


class list:
    """
    List type.

    Example
    -------
    ```python
        >>> l = [1, 2, 3]
        >>> l.append(4)
        >>> l.sort()
    ```
    """
    def __init__(self, iterable: Iterable = ...) -> None: ...

    def append(self, item: Any) -> None:
        """Append item."""
        ...

    def extend(self, iterable: Iterable) -> None:
        """Extend list."""
        ...

    def insert(self, index: int, item: Any) -> None:
        """Insert item at index."""
        ...

    def remove(self, item: Any) -> None:
        """Remove first occurrence."""
        ...

    def pop(self, index: int = -1) -> Any:
        """Remove and return item."""
        ...

    def clear(self) -> None:
        """Remove all items."""
        ...

    def index(self, item: Any, start: int = 0, end: int = None) -> int:
        """Find item index."""
        ...

    def count(self, item: Any) -> int:
        """Count occurrences."""
        ...

    def sort(self, key: Callable = None, reverse: bool = False) -> None:
        """Sort in place."""
        ...

    def reverse(self) -> None:
        """Reverse in place."""
        ...

    def copy(self) -> list:
        """Shallow copy."""
        ...


class dict:
    """
    Dictionary type.

    Example
    -------
    ```python
        >>> d = {'a': 1, 'b': 2}
        >>> d['c'] = 3
        >>> for k, v in d.items():
        ...     print(k, v)
    ```
    """
    def __init__(self, *args, **kwargs) -> None: ...

    def keys(self) -> Iterable:
        """Return keys."""
        ...

    def values(self) -> Iterable:
        """Return values."""
        ...

    def items(self) -> Iterable:
        """Return key-value pairs."""
        ...

    def get(self, key: Any, default: Any = None) -> Any:
        """Get with default."""
        ...

    def pop(self, key: Any, default: Any = ...) -> Any:
        """Remove and return."""
        ...

    def setdefault(self, key: Any, default: Any = None) -> Any:
        """Set default value."""
        ...

    def update(self, other: dict = None, **kwargs) -> None:
        """Update dictionary."""
        ...

    def clear(self) -> None:
        """Remove all items."""
        ...

    def copy(self) -> dict:
        """Shallow copy."""
        ...


class tuple:
    """
    Tuple type (immutable).

    Example
    -------
    ```python
        >>> t = (1, 2, 3)
        >>> x, y, z = t
        >>> print(t[0])
    ```
    """
    def __init__(self, iterable: Iterable = ...) -> None: ...

    def count(self, item: Any) -> int:
        """Count occurrences."""
        ...

    def index(self, item: Any) -> int:
        """Find item index."""
        ...


class set:
    """
    Set type.

    Example
    -------
    ```python
        >>> s = {1, 2, 3}
        >>> s.add(4)
        >>> s.remove(1)
    ```
    """
    def __init__(self, iterable: Iterable = ...) -> None: ...

    def add(self, item: Any) -> None:
        """Add item."""
        ...

    def remove(self, item: Any) -> None:
        """Remove item (raises if not found)."""
        ...

    def discard(self, item: Any) -> None:
        """Remove item (no error if not found)."""
        ...

    def pop(self) -> Any:
        """Remove and return arbitrary item."""
        ...

    def clear(self) -> None:
        """Remove all items."""
        ...

    def update(self, *others: Iterable) -> None:
        """Update with union."""
        ...

    def intersection_update(self, *others: Iterable) -> None:
        """Update with intersection."""
        ...

    def difference_update(self, *others: Iterable) -> None:
        """Update with difference."""
        ...

    def union(self, *others: Iterable) -> set:
        """Return union."""
        ...

    def intersection(self, *others: Iterable) -> set:
        """Return intersection."""
        ...

    def difference(self, *others: Iterable) -> set:
        """Return difference."""


# PIO Assembly overload for set() - takes precedence in @asm_pio context
@overload
def set(destination: Union[_PIOSpecial, str], value: int) -> None:
    """
    PIO: Set destination to immediate value.
    
    Only valid inside @rp2.asm_pio decorated function.
    
    :param destination: Destination (pins, x, y, pindirs)
    :param value: Immediate value (0-31)
    
    Example
    -------
    ```python
        @rp2.asm_pio()
        def my_program():
            set(pins, 1)      # Set pins high
            set(x, 31)        # Set X to 31
            set(pindirs, 0)   # Set pins as inputs
    ```
    """
    ...

    def issubset(self, other: Iterable) -> bool:
        """Check if subset."""
        ...

    def issuperset(self, other: Iterable) -> bool:
        """Check if superset."""
        ...


class frozenset:
    """
    Immutable set type.

    Example
    -------
    ```python
        >>> fs = frozenset([1, 2, 3])
        >>> 2 in fs  # True
    ```
    """
    def __init__(self, iterable: Iterable = ...) -> None: ...

    def union(self, *others: Iterable) -> frozenset:
        """Return union."""
        ...

    def intersection(self, *others: Iterable) -> frozenset:
        """Return intersection."""
        ...

    def difference(self, *others: Iterable) -> frozenset:
        """Return difference."""
        ...


class memoryview:
    """
    Memory view type.

    Example
    -------
    ```python
        >>> ba = bytearray(10)
        >>> mv = memoryview(ba)
        >>> mv[0] = 0xFF
    ```
    """
    def __init__(self, obj: Union[bytes, bytearray]) -> None: ...


class range:
    """
    Range type.

    Example
    -------
    ```python
        >>> for i in range(10):
        ...     print(i)
        >>> 
        >>> list(range(0, 10, 2))  # [0, 2, 4, 6, 8]
    ```
    """
    @overload
    def __init__(self, stop: int) -> None: ...
    @overload
    def __init__(self, start: int, stop: int, step: int = 1) -> None: ...


class slice:
    """Slice type."""
    start: Optional[int]
    stop: Optional[int]
    step: Optional[int]

    def __init__(self, start: int = None, stop: int = None, step: int = None) -> None: ...


class type:
    """Type metaclass."""
    def __init__(self, object_or_name, bases=..., dict=...) -> None: ...


class Exception(BaseException):
    """Base exception class."""
    def __init__(self, *args) -> None: ...


class BaseException:
    """Base class for all exceptions."""
    args: tuple

    def __init__(self, *args) -> None: ...


class StopIteration(Exception):
    """Signal end of iteration."""
    value: Any


class GeneratorExit(BaseException):
    """Generator exit."""
    ...


class ArithmeticError(Exception):
    """Arithmetic error."""
    ...


class ZeroDivisionError(ArithmeticError):
    """Division by zero."""
    ...


class OverflowError(ArithmeticError):
    """Overflow error."""
    ...


class AssertionError(Exception):
    """Assertion failed."""
    ...


class AttributeError(Exception):
    """Attribute not found."""
    ...


class EOFError(Exception):
    """End of file."""
    ...


class ImportError(Exception):
    """Import error."""
    ...


class IndexError(Exception):
    """Index out of range."""
    ...


class KeyError(Exception):
    """Key not found."""
    ...


class KeyboardInterrupt(BaseException):
    """Keyboard interrupt."""
    ...


class MemoryError(Exception):
    """Memory error."""
    ...


class NameError(Exception):
    """Name not found."""
    ...


class NotImplementedError(Exception):
    """Not implemented."""
    ...


class OSError(Exception):
    """OS error."""
    ...


class RuntimeError(Exception):
    """Runtime error."""
    ...


class SyntaxError(Exception):
    """Syntax error."""
    ...


class SystemExit(BaseException):
    """System exit."""
    ...


class TypeError(Exception):
    """Type error."""
    ...


class ValueError(Exception):
    """Value error."""
    ...


class UnicodeError(ValueError):
    """Unicode error."""
    ...


# Python 3 compatibility exceptions (aliases or additional)
class IOError(OSError):
    """I/O error (alias for OSError in Python 3)."""
    ...


class TimeoutError(OSError):
    """Timeout error."""
    ...


class ConnectionError(OSError):
    """Connection error."""
    ...


class BrokenPipeError(ConnectionError):
    """Broken pipe error."""
    ...


class ConnectionResetError(ConnectionError):
    """Connection reset error."""
    ...


class ConnectionRefusedError(ConnectionError):
    """Connection refused error."""
    ...


# ============================================================================
# Built-in Decorators and Descriptors
# ============================================================================

class staticmethod:
    """Transform a method into a static method."""
    def __init__(self, f: Callable[..., Any]) -> None: ...
    def __get__(self, obj: Any, type: Any = None) -> Callable[..., Any]: ...


class classmethod:
    """Transform a method into a class method."""
    def __init__(self, f: Callable[..., Any]) -> None: ...
    def __get__(self, obj: Any, type: Any = None) -> Callable[..., Any]: ...


class property:
    """Property attribute."""
    fget: Optional[Callable[[Any], Any]]
    fset: Optional[Callable[[Any, Any], None]]
    fdel: Optional[Callable[[Any], None]]
    
    @overload
    def __init__(self) -> None: ...
    @overload
    def __init__(
        self,
        fget: Optional[Callable[[Any], Any]] = None,
        fset: Optional[Callable[[Any, Any], None]] = None,
        fdel: Optional[Callable[[Any], None]] = None,
        doc: Optional[str] = None
    ) -> None: ...
    
    def getter(self, fget: Callable[[Any], Any]) -> "property": ...
    def setter(self, fset: Callable[[Any, Any], None]) -> "property": ...
    def deleter(self, fdel: Callable[[Any], None]) -> "property": ...
    def __get__(self, obj: Any, type: Any = None) -> Any: ...
    def __set__(self, obj: Any, value: Any) -> None: ...
    def __delete__(self, obj: Any) -> None: ...


# ============================================================================
# Built-in Functions
# ============================================================================

def __import__(
    name: str,
    globals: dict = None,
    locals: dict = None,
    fromlist: tuple = (),
    level: int = 0
) -> Any:
    """
    Import a module dynamically.

    This function is invoked by the import statement.

    :param name: Module name
    :param globals: Global namespace (optional)
    :param locals: Local namespace (optional)
    :param fromlist: Names to import from module
    :param level: Relative import level (0 = absolute)

    :returns: Imported module object

    Example
    -------
    ```python
        >>> mod = __import__('json')
        >>> data = mod.loads('{"x": 1}')
        >>> 
        >>> # Dynamic import
        >>> module_name = 'time'
        >>> mod = __import__(module_name)
        >>> mod.sleep(1)
    ```
    """
    ...


def abs(x: Union[int, float]) -> Union[int, float]:
    """
    Return absolute value.

    :param x: Number

    :returns: Absolute value

    Example
    -------
    ```python
        >>> abs(-5)
        5
        >>> abs(-3.14)
        3.14
    ```
    """
    ...


def all(iterable: Iterable) -> bool:
    """
    Return True if all elements are truthy.

    :param iterable: Input iterable

    :returns: Boolean result

    Example
    -------
    ```python
        >>> all([True, True, True])
        True
        >>> all([True, False, True])
        False
    ```
    """
    ...


def any(iterable: Iterable) -> bool:
    """
    Return True if any element is truthy.

    :param iterable: Input iterable

    :returns: Boolean result

    Example
    -------
    ```python
        >>> any([False, True, False])
        True
        >>> any([False, False])
        False
    ```
    """
    ...


def bin(x: int) -> str:
    """
    Return binary string.

    :param x: Integer

    :returns: Binary string

    Example
    -------
    ```python
        >>> bin(42)
        '0b101010'
    ```
    """
    ...


def callable(obj: Any) -> bool:
    """
    Return True if object is callable.

    :param obj: Object to check

    :returns: Boolean result

    Example
    -------
    ```python
        >>> callable(print)
        True
        >>> callable(42)
        False
    ```
    """
    ...


def chr(i: int) -> str:
    """
    Return character for Unicode code point.

    :param i: Code point

    :returns: Character string

    Example
    -------
    ```python
        >>> chr(65)
        'A'
        >>> chr(0x1F600)
        '😀'
    ```
    """
    ...


def dir(obj: Any = ...) -> list:
    """
    Return list of names in scope or object.

    :param obj: Object to inspect

    :returns: List of names

    Example
    -------
    ```python
        >>> dir()
        ['__name__', ...]
        >>> dir([])
        ['append', 'clear', ...]
    ```
    """
    ...


def divmod(a: Union[int, float], b: Union[int, float]) -> tuple:
    """
    Return (quotient, remainder).

    :param a: Dividend
    :param b: Divisor

    :returns: Tuple (quotient, remainder)

    Example
    -------
    ```python
        >>> divmod(17, 5)
        (3, 2)
    ```
    """
    ...


def enumerate(iterable: Iterable, start: int = 0) -> Iterator:
    """
    Return enumerate object.

    :param iterable: Input iterable
    :param start: Starting index

    :returns: Iterator of (index, value) tuples

    Example
    -------
    ```python
        >>> list(enumerate(['a', 'b', 'c']))
        [(0, 'a'), (1, 'b'), (2, 'c')]
    ```
    """
    ...


def eval(expression: str, globals: dict = None, locals: dict = None) -> Any:
    """
    Evaluate expression.

    :param expression: Python expression string
    :param globals: Global namespace
    :param locals: Local namespace

    :returns: Expression result

    Example
    -------
    ```python
        >>> eval('2 + 2')
        4
        >>> eval('x + y', {'x': 1, 'y': 2})
        3
    ```
    """
    ...


def exec(code: str, globals: dict = None, locals: dict = None) -> None:
    """
    Execute code.

    :param code: Python code string
    :param globals: Global namespace
    :param locals: Local namespace

    Example
    -------
    ```python
        >>> exec('print("hello")')
        hello
    ```
    """
    ...


def filter(function: Callable, iterable: Iterable) -> Iterator:
    """
    Filter elements by function.

    :param function: Filter function
    :param iterable: Input iterable

    :returns: Filtered iterator

    Example
    -------
    ```python
        >>> list(filter(lambda x: x > 0, [-1, 0, 1, 2]))
        [1, 2]
    ```
    """
    ...


def getattr(obj: Any, name: str, default: Any = ...) -> Any:
    """
    Get attribute value.

    :param obj: Object
    :param name: Attribute name
    :param default: Default if not found

    :returns: Attribute value

    Example
    -------
    ```python
        >>> getattr([], 'append')
        <built-in method append ...>
    ```
    """
    ...


def globals() -> dict:
    """
    Return global namespace.

    :returns: Global namespace dict

    Example
    -------
    ```python
        >>> g = globals()
        >>> g['x'] = 42
    ```
    """
    ...


def hasattr(obj: Any, name: str) -> bool:
    """
    Check if attribute exists.

    :param obj: Object
    :param name: Attribute name

    :returns: Boolean result

    Example
    -------
    ```python
        >>> hasattr([], 'append')
        True
    ```
    """
    ...


def hash(obj: Any) -> int:
    """
    Return hash value.

    :param obj: Hashable object

    :returns: Hash value

    Example
    -------
    ```python
        >>> hash('hello')
        -1267296259
    ```
    """
    ...


def hex(x: int) -> str:
    """
    Return hex string.

    :param x: Integer

    :returns: Hex string

    Example
    -------
    ```python
        >>> hex(255)
        '0xff'
    ```
    """
    ...


def id(obj: Any) -> int:
    """
    Return object identity.

    :param obj: Object

    :returns: Identity integer

    Example
    -------
    ```python
        >>> x = []
        >>> id(x)
        123456789
    ```
    """
    ...


def input(prompt: str = "") -> str:
    """
    Read line from stdin.

    :param prompt: Input prompt

    :returns: Input string

    Example
    -------
    ```python
        >>> name = input("Name: ")
        Name: Bob
    ```
    """
    ...


def isinstance(obj: Any, classinfo: Union[type, tuple]) -> bool:
    """
    Check instance type.

    :param obj: Object
    :param classinfo: Type or tuple of types

    :returns: Boolean result

    Example
    -------
    ```python
        >>> isinstance(42, int)
        True
        >>> isinstance(42, (int, str))
        True
    ```
    """
    ...


def issubclass(cls: type, classinfo: Union[type, tuple]) -> bool:
    """
    Check class inheritance.

    :param cls: Class
    :param classinfo: Type or tuple of types

    :returns: Boolean result

    Example
    -------
    ```python
        >>> issubclass(bool, int)
        True
    ```
    """
    ...


def iter(obj: Any, sentinel: Any = ...) -> Iterator:
    """
    Return iterator.

    :param obj: Iterable object
    :param sentinel: Stop value

    :returns: Iterator

    Example
    -------
    ```python
        >>> it = iter([1, 2, 3])
        >>> next(it)
        1
    ```
    """
    ...


def len(obj: Sequence) -> int:
    """
    Return length.

    :param obj: Sequence

    :returns: Length

    Example
    -------
    ```python
        >>> len([1, 2, 3])
        3
        >>> len('hello')
        5
    ```
    """
    ...


def locals() -> dict:
    """
    Return local namespace.

    :returns: Local namespace dict

    Example
    -------
    ```python
        >>> def f():
        ...     x = 1
        ...     return locals()
        >>> f()
        {'x': 1}
    ```
    """
    ...


def map(function: Callable, *iterables: Iterable) -> Iterator:
    """
    Apply function to iterables.

    :param function: Mapping function
    :param iterables: Input iterables

    :returns: Mapped iterator

    Example
    -------
    ```python
        >>> list(map(lambda x: x * 2, [1, 2, 3]))
        [2, 4, 6]
    ```
    """
    ...


def max(*args, key: Callable = None, default: Any = ...) -> Any:
    """
    Return maximum value.

    :param args: Values or iterable
    :param key: Key function
    :param default: Default if empty

    :returns: Maximum value

    Example
    -------
    ```python
        >>> max(1, 2, 3)
        3
        >>> max([1, 2, 3])
        3
    ```
    """
    ...


def min(*args, key: Callable = None, default: Any = ...) -> Any:
    """
    Return minimum value.

    :param args: Values or iterable
    :param key: Key function
    :param default: Default if empty

    :returns: Minimum value

    Example
    -------
    ```python
        >>> min(1, 2, 3)
        1
        >>> min([1, 2, 3])
        1
    ```
    """
    ...


def next(iterator: Iterator, default: Any = ...) -> Any:
    """
    Return next item from iterator.

    :param iterator: Iterator
    :param default: Default if exhausted

    :returns: Next item

    Example
    -------
    ```python
        >>> it = iter([1, 2])
        >>> next(it)
        1
        >>> next(it)
        2
    ```
    """
    ...


def oct(x: int) -> str:
    """
    Return octal string.

    :param x: Integer

    :returns: Octal string

    Example
    -------
    ```python
        >>> oct(8)
        '0o10'
    ```
    """
    ...


def open(
    file: str,
    mode: str = "r",
    buffering: int = -1,
    encoding: str = None,
    errors: str = None
) -> Any:
    """
    Open file.

    :param file: File path
    :param mode: Open mode
    :param buffering: Buffer size
    :param encoding: Text encoding
    :param errors: Error handling

    :returns: File object

    Example
    -------
    ```python
        >>> f = open('data.txt', 'r')
        >>> content = f.read()
        >>> f.close()
    ```
    """
    ...


def ord(c: str) -> int:
    """
    Return Unicode code point.

    :param c: Character

    :returns: Code point

    Example
    -------
    ```python
        >>> ord('A')
        65
    ```
    """
    ...


def pow(base: Union[int, float], exp: Union[int, float], mod: int = None) -> Union[int, float]:
    """
    Return power.

    :param base: Base
    :param exp: Exponent
    :param mod: Modulus (optional)

    :returns: Power result

    Example
    -------
    ```python
        >>> pow(2, 10)
        1024
        >>> pow(2, 10, 100)
        24
    ```
    """
    ...


def print(*args, sep: str = " ", end: str = "\n", file: Any = None) -> None:
    """
    Print to output.

    :param args: Values to print
    :param sep: Separator
    :param end: End string
    :param file: Output file

    Example
    -------
    ```python
        >>> print("Hello", "World")
        Hello World
        >>> print(1, 2, 3, sep=', ')
        1, 2, 3
    ```
    """
    ...


def repr(obj: Any) -> str:
    """
    Return string representation.

    :param obj: Object

    :returns: String representation

    Example
    -------
    ```python
        >>> repr('hello')
        "'hello'"
        >>> repr([1, 2, 3])
        '[1, 2, 3]'
    ```
    """
    ...


def reversed(seq: Sequence) -> Iterator:
    """
    Return reversed iterator.

    :param seq: Sequence

    :returns: Reversed iterator

    Example
    -------
    ```python
        >>> list(reversed([1, 2, 3]))
        [3, 2, 1]
    ```
    """
    ...


def round(number: float, ndigits: int = None) -> Union[int, float]:
    """
    Round number.

    :param number: Number to round
    :param ndigits: Decimal digits

    :returns: Rounded number

    Example
    -------
    ```python
        >>> round(3.14159, 2)
        3.14
        >>> round(3.5)
        4
    ```
    """
    ...


def setattr(obj: Any, name: str, value: Any) -> None:
    """
    Set attribute value.

    :param obj: Object
    :param name: Attribute name
    :param value: Attribute value

    Example
    -------
    ```python
        >>> class C: pass
        >>> c = C()
        >>> setattr(c, 'x', 42)
    ```
    """
    ...


def sorted(iterable: Iterable, key: Callable = None, reverse: bool = False) -> list:
    """
    Return sorted list.

    :param iterable: Input iterable
    :param key: Key function
    :param reverse: Reverse order

    :returns: Sorted list

    Example
    -------
    ```python
        >>> sorted([3, 1, 2])
        [1, 2, 3]
        >>> sorted([3, 1, 2], reverse=True)
        [3, 2, 1]
    ```
    """
    ...


def sum(iterable: Iterable, start: Union[int, float] = 0) -> Union[int, float]:
    """
    Return sum of iterable.

    :param iterable: Input iterable
    :param start: Starting value

    :returns: Sum

    Example
    -------
    ```python
        >>> sum([1, 2, 3])
        6
        >>> sum([1, 2, 3], 10)
        16
    ```
    """
    ...


def super(type: type = None, object_or_type: Any = None) -> Any:
    """
    Return super object.

    :param type: Class
    :param object_or_type: Instance or class

    :returns: Super object

    Example
    -------
    ```python
        >>> class B(A):
        ...     def __init__(self):
        ...         super().__init__()
    ```
    """
    ...


def zip(*iterables: Iterable) -> Iterator:
    """
    Zip iterables together.

    :param iterables: Input iterables

    :returns: Iterator of tuples

    Example
    -------
    ```python
        >>> list(zip([1, 2], ['a', 'b']))
        [(1, 'a'), (2, 'b')]
    ```
    """
    ...


# Special constants
Ellipsis: type
"""The ellipsis literal (...)."""

NotImplemented: type
"""Returned by binary special methods to indicate operation not implemented."""


# ============================================================================
# PIO Assembly DSL (RP2040/RP2350)
# ============================================================================
# These names are automatically available inside @rp2.asm_pio decorated functions.
# They represent PIO assembly instructions and special registers.

class _PIORegister:
    """PIO scratch register - only valid in @rp2.asm_pio context."""
    ...

class _PIOSpecial:
    """PIO special name - only valid in @rp2.asm_pio context."""
    ...

class _PIOCondition:
    """PIO jump condition - only valid in @rp2.asm_pio context."""
    ...


# PIO Registers
x: _PIORegister
"""PIO scratch register X."""

y: _PIORegister
"""PIO scratch register Y."""

# PIO Special names
pins: _PIOSpecial
"""PIO pins destination/source."""

pindirs: _PIOSpecial
"""PIO pin directions."""

null: _PIOSpecial
"""Discard written data or provide 0 when read."""

isr: _PIOSpecial
"""Input Shift Register."""

osr: _PIOSpecial
"""Output Shift Register."""

status: _PIOSpecial
"""Status value."""

pc: _PIOSpecial
"""Program Counter."""

exec: _PIOSpecial
"""Execute instruction."""

# PIO Conditions for jmp
not_x: _PIOCondition
"""Jump if X is non-zero."""

x_dec: _PIOCondition
"""Jump if X-- is non-zero."""

not_y: _PIOCondition
"""Jump if Y is non-zero."""

y_dec: _PIOCondition
"""Jump if Y-- is non-zero."""

x_not_y: _PIOCondition
"""Jump if X != Y."""

pin: _PIOCondition
"""Jump if pin is high."""

not_osre: _PIOCondition
"""Jump if OSR is not empty."""

# PIO Special values for instructions
clear: str
"""Clear IRQ flag (for irq instruction)."""

wait: str
"""Wait for IRQ clear (for irq instruction)."""

rel: str
"""Relative IRQ flag (for irq instruction)."""

block: str
"""Block on operation (for push/pull)."""

noblock: str
"""Don't block on operation (for push/pull)."""

iffull: str
"""Only if full (for push)."""

ifempty: str
"""Only if empty (for pull)."""

gpio: str
"""Wait on absolute GPIO (for wait instruction)."""

irq: str
"""Wait on IRQ (for wait instruction)."""


# PIO Assembly Instructions
def nop() -> None:
    """
    No operation (delay).
    
    Only valid inside @rp2.asm_pio decorated function.
    
    Example
    -------
    ```python
        @rp2.asm_pio()
        def my_program():
            nop()       # 1 cycle delay
            nop() [31]  # 32 cycle delay
    ```
    """
    ...


def jmp(condition: Union[_PIOCondition, str], label: str = None) -> None:
    """
    Jump instruction.
    
    Only valid inside @rp2.asm_pio decorated function.
    
    Example
    -------
    ```python
        @rp2.asm_pio()
        def my_program():
            jmp("start")         # Unconditional jump
            jmp(not_x, "loop")   # Jump if X != 0
            jmp(x_dec, "loop")   # Jump if --X != 0
    ```
    """
    ...


def in_(source: Union[_PIOSpecial, str], count: int) -> None:
    """
    Shift data from source into ISR.
    
    Only valid inside @rp2.asm_pio decorated function.
    
    Example
    -------
    ```python
        @rp2.asm_pio()
        def my_program():
            in_(pins, 8)  # Shift 8 bits from pins
            in_(x, 32)    # Shift X register
    ```
    """
    ...


def out(destination: Union[_PIOSpecial, str], count: int) -> None:
    """
    Shift data from OSR to destination.
    
    Only valid inside @rp2.asm_pio decorated function.
    
    Example
    -------
    ```python
        @rp2.asm_pio()
        def my_program():
            out(pins, 8)     # Output 8 bits to pins
            out(pindirs, 1)  # Set pin direction
    ```
    """
    ...


def push(block: bool = True, iffull: bool = False) -> None:
    """
    Push ISR to RX FIFO.
    
    Only valid inside @rp2.asm_pio decorated function.
    
    Example
    -------
    ```python
        @rp2.asm_pio()
        def my_program():
            push()              # Push and block
            push(block=False)   # Push without blocking
    ```
    """
    ...


def pull(block: bool = True, ifempty: bool = False) -> None:
    """
    Pull from TX FIFO to OSR.
    
    Only valid inside @rp2.asm_pio decorated function.
    
    Example
    -------
    ```python
        @rp2.asm_pio()
        def my_program():
            pull()              # Pull and block
            pull(block=False)   # Pull without blocking
    ```
    """
    ...


def mov(destination: Union[_PIOSpecial, str], source: Union[_PIOSpecial, str]) -> None:
    """
    Move data between registers.
    
    Only valid inside @rp2.asm_pio decorated function.
    
    Example
    -------
    ```python
        @rp2.asm_pio()
        def my_program():
            mov(x, y)       # Copy Y to X
            mov(isr, null)  # Clear ISR
    ```
    """
    ...


def label(name: str) -> None:
    """
    Define a label for jumps.
    
    Only valid inside @rp2.asm_pio decorated function.
    
    Example
    -------
    ```python
        @rp2.asm_pio()
        def my_program():
            label("loop")
            nop()
            jmp("loop")
    ```
    """
    ...


def wrap_target() -> None:
    """
    Mark wrap target (program loops back here).
    
    Only valid inside @rp2.asm_pio decorated function.
    """
    ...


def wrap() -> None:
    """
    Mark wrap point (jump back to wrap_target).
    
    Only valid inside @rp2.asm_pio decorated function.
    """
    ...
