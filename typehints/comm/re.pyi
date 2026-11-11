"""
Regular expression operations.

Basic regex matching and searching.

Example
-------
```python
    >>> import re
    >>> 
    >>> # Search pattern
    >>> m = re.search(r'\\d+', 'Value: 42')
    >>> if m:
    ...     print(m.group())  # '42'
    >>> 
    >>> # Compile for reuse
    >>> pat = re.compile(r'[a-z]+')
```
"""

from typing import Iterator, Optional, Union


def compile(pattern: str, flags: int = 0) -> 'regex':
    """
    Compile regex pattern.

    :param pattern: Regex pattern string
    :param flags: Flags (not used in MicroPython)

    :returns: Compiled regex object

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> pat = re.compile(r'\\d+')
        >>> m = pat.match('123abc')
        >>> m.group()  # '123'
    ```
    """
    ...


def match(pattern: str, string: str) -> Optional['match']:
    """
    Match pattern at start of string.

    :param pattern: Regex pattern
    :param string: String to match

    :returns: Match object or None

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> m = re.match(r'\\d+', '123abc')
        >>> if m:
        ...     print(m.group())  # '123'
        >>> 
        >>> # No match (not at start)
        >>> re.match(r'\\d+', 'abc123')  # None
    ```
    """
    ...


def search(pattern: str, string: str) -> Optional['match']:
    """
    Search for pattern anywhere in string.

    :param pattern: Regex pattern
    :param string: String to search

    :returns: Match object or None

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> m = re.search(r'\\d+', 'Value: 42 units')
        >>> if m:
        ...     print(m.group())  # '42'
    ```
    """
    ...


def sub(pattern: str, repl: Union[str, callable], string: str, count: int = 0) -> str:
    """
    Replace pattern occurrences.

    :param pattern: Regex pattern
    :param repl: Replacement string or function
    :param string: Input string
    :param count: Max replacements (0 = all)

    :returns: String with replacements

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> re.sub(r'\\s+', ' ', 'a   b  c')  # 'a b c'
        >>> 
        >>> # Replacement function
        >>> def upper(m):
        ...     return m.group().upper()
        >>> re.sub(r'[a-z]+', upper, 'hello world')
        ... # 'HELLO WORLD'
    ```
    """
    ...


def split(pattern: str, string: str, maxsplit: int = 0) -> list[str]:
    """
    Split string by pattern.

    :param pattern: Regex pattern
    :param string: String to split
    :param maxsplit: Max splits (0 = all)

    :returns: List of parts

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> re.split(r'\\s+', 'a b  c   d')
        ... # ['a', 'b', 'c', 'd']
        >>> 
        >>> re.split(r'[,;]', 'a,b;c,d')
        ... # ['a', 'b', 'c', 'd']
    ```
    """
    ...


def fullmatch(pattern: str, string: str) -> Optional['match']:
    """
    Match pattern against entire string.

    Returns a match object only if the whole string matches the pattern;
    returns ``None`` otherwise.

    :param pattern: Regex pattern string.
    :param string: String to match against.
    :returns: Match object or ``None``.

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> re.fullmatch(r'\\d+', '123')   # match: entire string is digits
        >>> re.fullmatch(r'\\d+', '12x')   # None: 'x' is not a digit
    ```
    """
    ...


def findall(pattern: str, string: str) -> list:
    """
    Return all non-overlapping matches as a list.

    If the pattern has no groups, returns a list of strings.
    If the pattern has one group, returns a list of group strings.
    If the pattern has multiple groups, returns a list of tuples.

    :param pattern: Regex pattern string.
    :param string: String to search.
    :returns: List of matches.

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> re.findall(r'\\d+', 'a1 b22 c333')
        ['1', '22', '333']
    ```
    """
    ...


def finditer(pattern: str, string: str) -> Iterator['match']:
    """
    Return an iterator over all non-overlapping match objects.

    :param pattern: Regex pattern string.
    :param string: String to search.
    :returns: Iterator of match objects.

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> for m in re.finditer(r'\\d+', 'a1 b22 c333'):
        ...     print(m.group(), m.start())
    ```
    """
    ...


def subn(pattern: str, repl: Union[str, callable], string: str, count: int = 0) -> tuple:
    """
    Like ``sub()``, but return a 2-tuple ``(new_string, number_of_subs_made)``.

    :param pattern: Regex pattern string.
    :param repl: Replacement string or callable.
    :param string: Input string.
    :param count: Maximum number of substitutions (0 = all).
    :returns: Tuple ``(result_string, count)`` where *count* is the number of replacements made.

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> re.subn(r'\\s+', ' ', 'a   b  c')
        ('a b c', 2)
    ```
    """
    ...


def escape(pattern: str) -> str:
    """
    Escape special regex characters in *pattern*.

    Returns a string with all non-alphanumeric characters backslash-escaped,
    so it can be used as a literal string in a regex.

    :param pattern: String to escape.
    :returns: Escaped string.

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> re.escape('1+1=2')
        '1\\\\+1\\\\=2'
        >>> re.search(re.escape('file.txt'), 'dir/file.txt')
    ```
    """
    ...


def purge() -> None:
    """
    Clear the regular expression cache.

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> re.purge()
    ```
    """
    ...


class regex:
    """
    Compiled regular expression.

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> pat = re.compile(r'\\w+')
        >>> m = pat.match('hello')
        >>> m.group()  # 'hello'
    ```
    """

    def match(self, string: str) -> Optional['match']:
        """
        Match at start of string.

        :param string: String to match

        :returns: Match object or None
        """
        ...

    def search(self, string: str) -> Optional['match']:
        """
        Search for match anywhere.

        :param string: String to search

        :returns: Match object or None
        """
        ...

    def sub(self, repl: Union[str, callable], string: str, count: int = 0) -> str:
        """
        Replace matches.

        :param repl: Replacement
        :param string: Input string
        :param count: Max replacements

        :returns: String with replacements
        """
        ...

    def split(self, string: str, maxsplit: int = 0) -> list[str]:
        """
        Split by pattern.

        :param string: String to split
        :param maxsplit: Max splits

        :returns: List of parts
        """
        ...


class match:
    """
    Match object from regex operation.

    Example
    -------
    ```python
        >>> import re
        >>> 
        >>> m = re.search(r'(\\w+)@(\\w+)', 'email: user@host')
        >>> m.group()   # 'user@host'
        >>> m.group(1)  # 'user'
        >>> m.group(2)  # 'host'
    ```
    """

    def group(self, index: int = 0) -> str:
        """
        Get matched group.

        :param index: Group number (0 = entire match)

        :returns: Matched string

        Example
        -------
        ```python
            >>> import re
            >>> 
            >>> m = re.match(r'(\\d+)-(\\d+)', '123-456')
            >>> m.group(0)  # '123-456'
            >>> m.group(1)  # '123'
            >>> m.group(2)  # '456'
        ```
        """
        ...

    def groups(self) -> tuple:
        """
        Get all captured groups.

        :returns: Tuple of group strings

        Example
        -------
        ```python
            >>> import re
            >>> 
            >>> m = re.match(r'(\\d+)-(\\d+)', '123-456')
            >>> m.groups()  # ('123', '456')
        ```
        """
        ...

    def start(self, index: int = 0) -> int:
        """
        Get start index of match.

        :param index: Group number

        :returns: Start index

        Example
        -------
        ```python
            >>> import re
            >>> 
            >>> m = re.search(r'\\d+', 'abc123def')
            >>> m.start()  # 3
        ```
        """
        ...

    def end(self, index: int = 0) -> int:
        """
        Get end index of match.

        :param index: Group number

        :returns: End index

        Example
        -------
        ```python
            >>> import re
            >>> 
            >>> m = re.search(r'\\d+', 'abc123def')
            >>> m.end()  # 6
        ```
        """
        ...

    def span(self, index: int = 0) -> tuple[int, int]:
        """
        Get (start, end) indices of match.

        :param index: Group number

        :returns: (start, end) tuple

        Example
        -------
        ```python
            >>> import re
            >>> 
            >>> m = re.search(r'\\d+', 'abc123def')
            >>> m.span()  # (3, 6)
        ```
        """
        ...
