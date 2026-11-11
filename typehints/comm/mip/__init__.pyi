"""mip - MicroPython package installer.

`mip` is a lightweight installer used on-device to fetch and install modules.
It commonly supports installing from the MicroPython package index and from
GitHub URLs.

Notes
-----
- Network access is required. Errors are typically reported as `OSError`.
- The exact index format and supported URL schemes can vary by MicroPython
    version/port.
- Installing to flash writes to the filesystem; ensure you have space.

Example
-------
```python
    >>> import mip
    >>> 
    >>> # Install package
    >>> mip.install('aiohttp')
    >>> 
    >>> # Install from GitHub
    >>> mip.install('github:user/repo/package.py')
```
"""

from typing import Optional


def install(
    package: str,
    index: str = None,
    target: str = None,
    version: str = None,
    mpy: bool = True
) -> None:
    """
    Install a package.

    :param package: Package name or URL
    :param index: Package index URL
    :param target: Install directory
    :param version: Specific version
    :param mpy: Install compiled .mpy files

    Example
    -------
    ```python
        >>> import mip
        >>> 
        >>> # Install from micropython-lib
        >>> mip.install('aiohttp')
        >>> 
        >>> # Install specific version
        >>> mip.install('requests', version='0.9.1')
        >>> 
        >>> # Install from GitHub
        >>> mip.install('github:micropython/micropython-lib/python-stdlib/functools/functools.py')
        >>> 
        >>> # Install to specific directory
        >>> mip.install('mypackage', target='/lib')
    ```
    """
    ...


def update() -> None:
    """Update installed packages.

    Update behaviour is port/version dependent. Some builds may re-fetch packages
    based on recorded metadata or reinstall from the configured index.

    Example
    -------
    ```python
        >>> import mip
        >>> 
        >>> mip.update()
    ```
    """
    ...
