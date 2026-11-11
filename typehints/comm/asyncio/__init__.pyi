"""asyncio - cooperative multitasking (MicroPython).

This is MicroPython's `asyncio` implementation (often closely related to
`uasyncio`). It enables cooperative multitasking using `async`/`await`.

Notes
-----
- API coverage differs from CPython `asyncio`.
- Tasks run cooperatively: blocking I/O or long CPU loops will block the loop.
- Cancellation is commonly implemented via raising `CancelledError` into the
    coroutine; ensure your coroutines are cancellation-safe.

Example
-------
```python
    >>> import asyncio
    >>> 
    >>> async def blink():
    ...     while True:
    ...         led.toggle()
    ...         await asyncio.sleep(0.5)
    >>> 
    >>> async def main():
    ...     task = asyncio.create_task(blink())
    ...     await asyncio.sleep(10)
    ...     task.cancel()
    >>> 
    >>> asyncio.run(main())
```
"""

from typing import Any, Awaitable, Callable, Coroutine, Optional, TypeVar, Union

T = TypeVar('T')


class Task:
    """
    Wrapper for running coroutine.

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> async def my_coro():
        ...     await asyncio.sleep(1)
        ...     return 42
        >>> 
        >>> task = asyncio.create_task(my_coro())
        >>> result = await task
    ```
    """

    def cancel(self) -> bool:
        """
        Cancel the task.

        :returns: True if cancel request was made

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> task.cancel()
        ```
        """
        ...

    def done(self) -> bool:
        """
        Check if task completed.

        :returns: True if finished

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> if task.done():
            ...     print("Task completed")
        ```
        """
        ...

    def __await__(self) -> Any:
        """Allow awaiting task."""
        ...


class Event:
    """
    Synchronization primitive for signaling.

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> event = asyncio.Event()
        >>> 
        >>> async def waiter():
        ...     print("Waiting...")
        ...     await event.wait()
        ...     print("Got signal!")
        >>> 
        >>> async def setter():
        ...     await asyncio.sleep(1)
        ...     event.set()
    ```
    """

    def __init__(self) -> None:
        """Create new event."""
        ...

    def set(self) -> None:
        """
        Set event flag.

        Wakes all waiting coroutines.

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> event.set()
        ```
        """
        ...

    def clear(self) -> None:
        """
        Clear event flag.

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> event.clear()
        ```
        """
        ...

    def is_set(self) -> bool:
        """
        Check if event is set.

        :returns: True if set

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> if event.is_set():
            ...     print("Event is set")
        ```
        """
        ...

    async def wait(self) -> bool:
        """
        Wait for event to be set.

        :returns: True when set

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> await event.wait()
        ```
        """
        ...


class Lock:
    """
    Mutual exclusion lock.

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> lock = asyncio.Lock()
        >>> 
        >>> async def critical_section():
        ...     async with lock:
        ...         # Only one task at a time
        ...         await do_work()
    ```
    """

    def __init__(self) -> None:
        """Create new lock."""
        ...

    def locked(self) -> bool:
        """
        Check if lock is held.

        :returns: True if locked

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> if lock.locked():
            ...     print("Resource is busy")
        ```
        """
        ...

    async def acquire(self) -> bool:
        """
        Acquire the lock.

        Blocks until available.

        :returns: True when acquired

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> await lock.acquire()
            >>> try:
            ...     # critical section
            ...     pass
            >>> finally:
            ...     lock.release()
        ```
        """
        ...

    def release(self) -> None:
        """
        Release the lock.

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> lock.release()
        ```
        """
        ...

    async def __aenter__(self) -> None:
        """Async context entry."""
        ...

    async def __aexit__(self, *args) -> None:
        """Async context exit."""
        ...


class StreamReader:
    """
    Async stream reader.

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> reader, writer = await asyncio.open_connection('host', 80)
        >>> data = await reader.read(1024)
    ```
    """

    async def read(self, n: int = -1) -> bytes:
        """
        Read up to n bytes.

        :param n: Max bytes (-1 for all available)

        :returns: Read data

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> data = await reader.read(100)
        ```
        """
        ...

    async def readline(self) -> bytes:
        """
        Read one line.

        :returns: Line with newline

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> line = await reader.readline()
        ```
        """
        ...

    async def readexactly(self, n: int) -> bytes:
        """
        Read exactly n bytes.

        :param n: Exact byte count

        :returns: Read data

        :raises: EOFError if not enough data

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> header = await reader.readexactly(10)
        ```
        """
        ...

    async def readinto(self, buf: bytearray) -> int:
        """
        Read into buffer.

        :param buf: Target buffer

        :returns: Bytes read

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> buf = bytearray(100)
            >>> n = await reader.readinto(buf)
        ```
        """
        ...


class StreamWriter:
    """
    Async stream writer.

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> reader, writer = await asyncio.open_connection('host', 80)
        >>> writer.write(b'GET / HTTP/1.1\\r\\n\\r\\n')
        >>> await writer.drain()
    ```
    """

    def write(self, data: bytes) -> None:
        """
        Write data to stream.

        :param data: Data to write

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> writer.write(b'Hello')
        ```
        """
        ...

    async def drain(self) -> None:
        """
        Wait for write buffer to flush.

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> writer.write(b'Data')
            >>> await writer.drain()
        ```
        """
        ...

    def close(self) -> None:
        """
        Close the stream.

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> writer.close()
            >>> await writer.wait_closed()
        ```
        """
        ...

    async def wait_closed(self) -> None:
        """
        Wait for close to complete.

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> writer.close()
            >>> await writer.wait_closed()
        ```
        """
        ...

    def get_extra_info(self, name: str) -> Any:
        """
        Get stream info.

        :param name: Info key ('peername', 'sockname', etc.)

        :returns: Info value

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> addr = writer.get_extra_info('peername')
        ```
        """
        ...


class ThreadSafeFlag:
    """
    Thread-safe flag for signaling from IRQ.

    Example
    -------
    ```python
        >>> import asyncio
        >>> from machine import Pin
        >>> 
        >>> flag = asyncio.ThreadSafeFlag()
        >>> 
        >>> def button_isr(pin):
        ...     flag.set()
        >>> 
        >>> button = Pin(15, Pin.IN, Pin.PULL_UP)
        >>> button.irq(button_isr, Pin.IRQ_FALLING)
        >>> 
        >>> async def wait_button():
        ...     await flag.wait()
        ...     print("Button pressed!")
    ```
    """

    def __init__(self) -> None:
        """Create thread-safe flag."""
        ...

    def set(self) -> None:
        """
        Set flag (safe from IRQ).

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> flag.set()  # Can call from IRQ handler
        ```
        """
        ...

    def clear(self) -> None:
        """
        Clear flag.

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> flag.clear()
        ```
        """
        ...

    async def wait(self) -> None:
        """
        Wait for flag to be set.

        Example
        -------
        ```python
            >>> import asyncio
            >>> 
            >>> await flag.wait()
        ```
        """
        ...


def run(coro: Coroutine) -> Any:
    """
    Run coroutine until complete.

    Main entry point for async programs.

    :param coro: Coroutine to run

    :returns: Coroutine result

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> async def main():
        ...     print("Hello")
        ...     await asyncio.sleep(1)
        ...     print("World")
        >>> 
        >>> asyncio.run(main())
    ```
    """
    ...


def create_task(coro: Coroutine) -> Task:
    """
    Schedule coroutine as task.

    :param coro: Coroutine to schedule

    :returns: Task object

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> async def background():
        ...     while True:
        ...         await asyncio.sleep(1)
        ...         print("tick")
        >>> 
        >>> task = asyncio.create_task(background())
    ```
    """
    ...


def current_task() -> Optional[Task]:
    """
    Get currently running task.

    :returns: Current task or None

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> async def show_task():
        ...     t = asyncio.current_task()
        ...     print(t)
    ```
    """
    ...


async def sleep(t: float) -> None:
    """
    Async sleep for t seconds.

    :param t: Sleep duration in seconds

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> async def delayed():
        ...     await asyncio.sleep(2.5)
        ...     print("Done!")
    ```
    """
    ...


async def sleep_ms(t: int) -> None:
    """
    Async sleep for t milliseconds.

    :param t: Sleep duration in milliseconds

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> async def blink():
        ...     while True:
        ...         led.toggle()
        ...         await asyncio.sleep_ms(500)
    ```
    """
    ...


async def gather(*coros: Coroutine, return_exceptions: bool = False) -> list:
    """
    Run coroutines concurrently.

    :param coros: Coroutines to run
    :param return_exceptions: Return exceptions instead of raising

    :returns: List of results

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> async def task1():
        ...     await asyncio.sleep(1)
        ...     return 1
        >>> 
        >>> async def task2():
        ...     await asyncio.sleep(2)
        ...     return 2
        >>> 
        >>> results = await asyncio.gather(task1(), task2())
        >>> print(results)  # [1, 2]
    ```
    """
    ...


async def wait_for(coro: Coroutine, timeout: float) -> Any:
    """
    Wait for coroutine with timeout.

    :param coro: Coroutine to wait for
    :param timeout: Timeout in seconds

    :returns: Coroutine result

    :raises: asyncio.TimeoutError on timeout

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> try:
        ...     result = await asyncio.wait_for(slow_op(), 5.0)
        >>> except asyncio.TimeoutError:
        ...     print("Timed out!")
    ```
    """
    ...


async def wait_for_ms(coro: Coroutine, timeout: int) -> Any:
    """
    Wait for coroutine with timeout in ms.

    :param coro: Coroutine to wait for
    :param timeout: Timeout in milliseconds

    :returns: Coroutine result

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> result = await asyncio.wait_for_ms(operation(), 5000)
    ```
    """
    ...


async def open_connection(host: str, port: int) -> tuple[StreamReader, StreamWriter]:
    """
    Open TCP connection.

    :param host: Host name or IP
    :param port: Port number

    :returns: (reader, writer) tuple

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> async def http_get():
        ...     reader, writer = await asyncio.open_connection('example.com', 80)
        ...     writer.write(b'GET / HTTP/1.1\\r\\nHost: example.com\\r\\n\\r\\n')
        ...     await writer.drain()
        ...     response = await reader.read(4096)
        ...     writer.close()
        ...     await writer.wait_closed()
        ...     return response
    ```
    """
    ...


async def start_server(
    callback: Callable[[StreamReader, StreamWriter], Coroutine],
    host: str,
    port: int,
    backlog: int = 5
) -> 'Server':
    """
    Start TCP server.

    :param callback: Handler for connections
    :param host: Bind host
    :param port: Bind port
    :param backlog: Connection queue size

    :returns: Server object

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> async def handle_client(reader, writer):
        ...     data = await reader.read(1024)
        ...     writer.write(b'Echo: ' + data)
        ...     await writer.drain()
        ...     writer.close()
        ...     await writer.wait_closed()
        >>> 
        >>> async def main():
        ...     server = await asyncio.start_server(
        ...         handle_client, '0.0.0.0', 8080
        ...     )
        ...     await server.wait_closed()
    ```
    """
    ...


class Server:
    """
    Async TCP server.

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> server = await asyncio.start_server(handler, '0.0.0.0', 80)
        >>> await server.wait_closed()
    ```
    """

    def close(self) -> None:
        """Close server."""
        ...

    async def wait_closed(self) -> None:
        """Wait for server to close."""
        ...


class CancelledError(BaseException):
    """Task was cancelled."""
    ...


class TimeoutError(Exception):
    """Operation timed out."""
    ...


def get_event_loop() -> object:
    """
    Get event loop.

    :returns: Event loop object

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> loop = asyncio.get_event_loop()
    ```
    """
    ...


def new_event_loop() -> object:
    """
    Create new event loop.

    :returns: New event loop

    Example
    -------
    ```python
        >>> import asyncio
        >>> 
        >>> loop = asyncio.new_event_loop()
    ```
    """
    ...
