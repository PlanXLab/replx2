"""
uasyncio compatibility module.

This module provides backward compatibility with older uasyncio code.
Use 'import asyncio' for new code.

In many MicroPython builds, ``uasyncio`` historically provided the asyncio
event loop implementation. Modern ports typically expose the API as
``asyncio``, with ``uasyncio`` acting as a compatibility alias.

Example
-------
```python
    >>> import uasyncio as asyncio
    >>> 
    >>> async def main():
    ...     await asyncio.sleep(1)
    >>> 
    >>> asyncio.run(main())
```
"""

from asyncio import *
