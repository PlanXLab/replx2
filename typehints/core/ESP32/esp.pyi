"""
ESP8266 and ESP32 common functions.

Low-level flash access, deep sleep, and debug functions
available on both ESP8266 and ESP32.

.. note::
    Some functions are only available on one of these ports. Where possible,
    prefer higher-level, portable APIs such as ``machine.deepsleep()``.

Example
-------
```python
    >>> import esp
    >>> 
    >>> # Check flash size
    >>> print(f"Flash: {esp.flash_size()} bytes")
    >>> 
    >>> # Enter deep sleep for 10 seconds
    >>> esp.deepsleep(10_000_000)
```
"""

from typing import Optional, Union, overload


def flash_size() -> int:
    """
    Get flash chip size.

    :returns: Flash size in bytes

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> size = esp.flash_size()
        >>> print(f"Flash: {size // (1024*1024)} MB")
    ```
    """
    ...


def flash_user_start() -> int:
    """
    Get start address of user flash area.

    :returns: Start address

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> start = esp.flash_user_start()
        >>> print(f"User flash starts at: 0x{start:X}")
    ```
    """
    ...


@overload
def flash_read(byte_offset: int, length_or_buffer: int) -> bytes:
    ...


@overload
def flash_read(byte_offset: int, length_or_buffer: bytearray) -> None:
    ...


def flash_read(byte_offset: int, length_or_buffer: Union[int, bytearray]) -> Union[bytes, None]:
    """
    Read from flash memory.

    This function supports two forms:
    - ``flash_read(byte_offset, length) -> bytes``
    - ``flash_read(byte_offset, buffer) -> None``

    :param byte_offset: Byte offset in flash
    :param length_or_buffer: Length in bytes, or a buffer to read into

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> buf = bytearray(256)
        >>> esp.flash_read(0x100000, buf)
    ```
    """
    ...


def flash_write(offset: int, buf: bytes) -> None:
    """
    Write to flash memory.

    Flash must be erased before writing.

    :param offset: Byte offset in flash (must be 4-byte aligned)
    :param buf: Data to write (length must be multiple of 4)

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> data = bytes([0x12, 0x34, 0x56, 0x78])
        >>> esp.flash_erase(0x100000)  # Erase sector first
        >>> esp.flash_write(0x100000, data)
    ```
    """
    ...


def flash_erase(sector: int) -> None:
    """
    Erase flash sector.

    Sector size is typically 4096 bytes.

    :param sector: Sector number to erase

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> # Erase sector at offset 0x100000
        >>> sector = 0x100000 // 4096
        >>> esp.flash_erase(sector)
    ```
    """
    ...


def deepsleep(time_us: int = 0) -> None:
    """
    Enter deep sleep mode.

    Note: ESP8266 only. On ESP32, use ``machine.deepsleep()``.

    The whole module powers down except for the RTC clock circuit.
    The RTC can restart the module after the specified time if GPIO16 is
    connected to the reset pin.

    :param time_us: Sleep time in microseconds (0 = indefinite)

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> # Sleep for 10 seconds
        >>> esp.deepsleep(10_000_000)
        >>> 
        >>> # Sleep indefinitely (wake on external trigger)
        >>> esp.deepsleep(0)
    ```
    """
    ...


def sleep_type(sleep_type: int = None) -> Optional[int]:
    """
    Get or set sleep type (ESP8266 only).

    :param sleep_type: Sleep type (None to query)

    :returns: Current sleep type if querying

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> current = esp.sleep_type()
        >>> esp.sleep_type(esp.SLEEP_MODEM)
    ```
    """
    ...


# Sleep type constants (ESP8266)
SLEEP_NONE: int
"""No sleep."""

SLEEP_MODEM: int
"""Modem sleep (WiFi off during idle)."""

SLEEP_LIGHT: int
"""Light sleep (CPU paused)."""


def osdebug(level: int, log_dest: int = None) -> None:
    """
        Configure OS serial debug log messages.

        This function has different forms depending on port:

        ESP8266:
        - ``osdebug(uart_no)`` where ``uart_no`` is the UART number to receive OS output,
            or ``None`` to disable OS debug output.

        ESP32:
        - ``osdebug(None)`` restores the default OS log level (``LOG_ERROR``)
        - ``osdebug(0)`` enables all available OS debug log messages (typically up to
            ``LOG_INFO`` in the default build)
        - ``osdebug(0, level)`` sets the OS log level to one of the ``LOG_*`` constants

        .. note::
                ``LOG_DEBUG`` and ``LOG_VERBOSE`` are not compiled into the default
                MicroPython binary (custom build required).

        .. note::
                On ESP32, OS log output is automatically suspended in Raw REPL mode.

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> # ESP8266: disable OS debug output
        >>> esp.osdebug(None)
        >>> 
        >>> # ESP32: set log level
        >>> esp.osdebug(0, esp.LOG_WARN)
    ```
    """
    ...


def osdebug(uart_no: Optional[int], level: int = None) -> None:
    """Alias for the documented ``osdebug(uart_no[, level])`` signature."""
    ...


# Log levels (ESP32)
LOG_NONE: int
"""No logging."""

LOG_ERROR: int
"""Error messages only."""

LOG_WARN: int
"""Warnings and errors."""

LOG_INFO: int
"""Info, warnings, and errors."""

LOG_DEBUG: int
"""Debug and above."""

LOG_VERBOSE: int
"""All messages."""


def set_native_code_location(start: Optional[int], length: Optional[int]) -> None:
    """
    Set location for native code in iRAM.

    Note: ESP8266 only.

    Native code is emitted when using ``@micropython.native``, ``@micropython.viper``
    or ``@micropython.asm_xtensa``.

    If ``start`` and ``length`` are both ``None``, native code is placed in the unused
    portion of iRAM1 (typically small, but does not wear out).

    If neither is ``None``, ``start`` is the byte offset from the beginning of flash
    and ``length`` is the number of bytes reserved. Both must be multiples of 4096.
    The flash region is erased automatically before use; repeated use may wear flash.

    When using flash, ``start + length`` must be <= 1MB.

    :param start: Flash byte offset, or ``None`` to use iRAM1
    :param length: Length in bytes, or ``None`` to use iRAM1

    :raises MemoryError: If the configured region is exhausted when compiling native code.

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> # Allocate 4KB for native code
        >>> esp.set_native_code_location(0x40100000, 4096)
    ```
    """
    ...


def dht_readinto(pin: int, buf: bytearray) -> None:
    """
    Read DHT sensor (low-level).

    Prefer using the `dht` module instead.

    :param pin: GPIO pin number
    :param buf: 5-byte buffer for result

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> buf = bytearray(5)
        >>> esp.dht_readinto(4, buf)
        >>> humidity = buf[0]
        >>> temperature = buf[2]
    ```
    """
    ...


def flash_id() -> int:
    """
    Read the device ID of the flash memory.

    Note: ESP8266 only.

    :returns: Flash device ID
    """
    ...


def check_fw() -> bool:
    """
    Check firmware integrity (ESP8266 only).

    :returns: True if firmware is valid

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> if esp.check_fw():
        ...     print("Firmware OK")
    ```
    """
    ...


def free(size: int = None) -> Optional[int]:
    """
    Get free memory or free specific memory (ESP8266 only).

    :param size: Size to free (None to query)

    :returns: Free bytes if querying

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> print(f"Free: {esp.free()} bytes")
    ```
    """
    ...


def malloc(size: int) -> int:
    """
    Allocate memory from heap (low-level).

    :param size: Number of bytes to allocate

    :returns: Memory address

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> addr = esp.malloc(256)
    ```
    """
    ...


def memfree() -> int:
    """
    Get free heap memory (ESP8266 only).

    :returns: Free bytes

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> print(f"Heap free: {esp.memfree()} bytes")
    ```
    """
    ...


def esf_free_bufs() -> int:
    """
    Get number of free ESP-NOW buffers (ESP8266 only).

    :returns: Number of free buffers

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> bufs = esp.esf_free_bufs()
    ```
    """
    ...


def apa102_write(clock_pin: int, data_pin: int, buf: bytes) -> None:
    """
    Write to APA102/DotStar LED strip.

    Low-level bit-banged APA102 driver.

    :param clock_pin: Clock GPIO pin
    :param data_pin: Data GPIO pin
    :param buf: LED data (4 bytes per LED: brightness, blue, green, red)

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> # 3 LEDs, all red at half brightness
        >>> data = bytearray([
        ...     0xEF, 0x00, 0x00, 0xFF,  # LED 0: brightness=15, R=255
        ...     0xEF, 0x00, 0x00, 0xFF,  # LED 1
        ...     0xEF, 0x00, 0x00, 0xFF,  # LED 2
        ... ])
        >>> esp.apa102_write(14, 13, data)
    ```
    """
    ...


def gpio_matrix_in(gpio: int, signal: int, invert: bool = False) -> None:
    """
    Route GPIO to peripheral input (ESP32 only).

    :param gpio: GPIO number
    :param signal: Peripheral signal number
    :param invert: Invert signal

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> esp.gpio_matrix_in(4, 14, False)  # Route GPIO4 to signal 14
    ```
    """
    ...


def gpio_matrix_out(gpio: int, signal: int, out_inv: bool = False, oen_inv: bool = False) -> None:
    """
    Route peripheral output to GPIO (ESP32 only).

    :param gpio: GPIO number
    :param signal: Peripheral signal number
    :param out_inv: Invert output
    :param oen_inv: Invert output enable

    Example
    -------
    ```python
        >>> import esp
        >>> 
        >>> esp.gpio_matrix_out(4, 14, False, False)
    ```
    """
    ...
