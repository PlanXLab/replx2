"""
ESP32 specific functions.

ESP32-specific features including ULP, RMT, partitions, and deep sleep.

Example
-------
```python
    >>> import esp32
    >>> from machine import Pin
    >>> 
    >>> # Wake up from deep sleep on GPIO touch
    >>> esp32.wake_on_touch(True)
    >>> 
    >>> # Check reset reason
    >>> print(esp32.wake_reason())
```
"""

from typing import Any, Callable, Optional, Union, Tuple


# Wake reasons
WAKEUP_ALL_LOW: int
"""Wake when all pins are low."""

WAKEUP_ANY_HIGH: int
"""Wake when any pin is high."""


def wake_on_touch(wake: bool) -> None:
    """
    Configure wake from deep sleep on touch pad.

    :param wake: True to enable touch wake

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> esp32.wake_on_touch(True)
        >>> machine.deepsleep()
    ```
    """
    ...


def wake_on_ext0(pin: Any, level: int) -> None:
    """
    Configure wake from deep sleep on a single RTC pin (EXT0).

    :param pin: Pin to wake on, or ``None`` to disable EXT0 wake.
    :param level: Wake level: ``0`` to wake on low, ``1`` to wake on high.

    .. note::
        EXT0 wake is only available on boards/chips with EXT0 support.

    Example
    -------
    ```python
        >>> import esp32
        >>> from machine import Pin
        >>> 
        >>> wake_pin = Pin(4, Pin.IN)
        >>> esp32.wake_on_ext0(wake_pin, 1)
    ```
    """
    ...


def wake_on_ext1(pins: Any, level: int) -> None:
    """
    Configure wake from deep sleep on multiple RTC pins (EXT1).

    :param pins: Tuple/list of Pin objects, or ``None`` to disable EXT1 wake.
    :param level: One of ``WAKEUP_ALL_LOW`` or ``WAKEUP_ANY_HIGH``.

    .. note::
        EXT1 wake is only available on boards/chips with EXT1 support.

    Example
    -------
    ```python
        >>> import esp32
        >>> from machine import Pin
        >>> 
        >>> pins = (Pin(4), Pin(5), Pin(6))
        >>> esp32.wake_on_ext1(pins, esp32.WAKEUP_ALL_LOW)
    ```
    """
    ...


def wake_on_ulp(wake: bool) -> None:
    """
    Configure wake from deep sleep on ULP coprocessor.

    :param wake: True to enable ULP wake

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> esp32.wake_on_ulp(True)
    ```
    """
    ...


def wake_on_gpio(pins: Any, level: int) -> None:
    """
    Configure wake from deep sleep on GPIO pins.

    :param pins: Tuple/list of Pin objects, or None to disable
    :param level: WAKEUP_ALL_LOW or WAKEUP_ANY_HIGH

    .. note::
        Some boards don't support waking on GPIO from deep sleep.
        On those boards, pins set here can only wake from light sleep.

    Example
    -------
    ```python
        >>> import esp32
        >>> from machine import Pin
        >>> 
        >>> pins = (Pin(4), Pin(5))
        >>> esp32.wake_on_gpio(pins, esp32.WAKEUP_ANY_HIGH)
    ```
    """
    ...


def wake_reason() -> int:
    """
    Get the wake reason from deep sleep.

    :returns: Wake reason code

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> reason = esp32.wake_reason()
        >>> if reason == 2:
        ...     print("Woke from EXT0")
    ```
    """
    ...


def gpio_deep_sleep_hold(enable: bool) -> None:
    """
    Enable or disable GPIO hold during deep sleep.

    :param enable: True to hold GPIO states

    Example
    -------
    ```python
        >>> import esp32
        >>> from machine import Pin
        >>> 
        >>> led = Pin(2, Pin.OUT, value=1)
        >>> esp32.gpio_deep_sleep_hold(True)
        >>> machine.deepsleep(10000)
    ```
    """
    ...


def raw_temperature() -> int:
    """
    Read raw internal temperature sensor value.

    :returns: Raw ADC value (use for relative comparison)

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> temp_raw = esp32.raw_temperature()
        >>> # Convert to Fahrenheit (approximate)
        >>> temp_f = (temp_raw - 32) / 1.8
    ```
    """
    ...


def hall_sensor() -> int:
    """
    Read internal Hall effect sensor.

    :returns: Hall sensor value

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> hall = esp32.hall_sensor()
        >>> print(f"Hall sensor: {hall}")
    ```
    """
    ...


def idf_heap_info(caps: int) -> list:
    """
    Get IDF heap information.

    :param caps: Capability flags (HEAP_DATA or HEAP_EXEC)

    :returns: List of 4-tuples (total_bytes, free_bytes, largest_free, min_free)

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> info = esp32.idf_heap_info(esp32.HEAP_DATA)
        >>> for heap in info:
        ...     print(heap)
    ```
    """
    ...


def idf_task_info() -> Tuple[int, list]:
    """
    Get information about running ESP-IDF/FreeRTOS tasks.

    This includes MicroPython threads. Useful for debugging
    task scheduling and stack usage.

    .. note::
        Requires CONFIG_FREERTOS_USE_TRACE_FACILITY=y in board config.
        CONFIG_FREERTOS_GENERATE_RUN_TIME_STATS=y and
        CONFIG_FREERTOS_VTASKLIST_INCLUDE_COREID=y are recommended.

    :returns: 2-tuple of (total_runtime, task_list) where task_list
              contains 7-tuples: (task_id, name, state, priority,
              runtime, stack_high_water, core_id)

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> total, tasks = esp32.idf_task_info()
        >>> for task in tasks:
        ...     print(f"{task[1]}: state={task[2]}, priority={task[3]}")
    ```
    """
    ...


# Heap capability flags
HEAP_DATA: int
"""Data memory heap."""

HEAP_EXEC: int
"""Executable memory heap."""


class NVS:
    """
    Non-Volatile Storage namespace.

    Persistent key-value storage that survives reboots.

    The underlying ESP-IDF NVS is partitioned into namespaces, each containing
    typed key-value pairs.

    .. warning::
        Changes made via ``set_*`` methods must be persisted by calling
        :meth:`commit`. Otherwise the changes may be lost on the next reset.

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> nvs = esp32.NVS("my_app")
        >>> nvs.set_i32("counter", 42)
        >>> nvs.commit()
        >>> 
        >>> value = nvs.get_i32("counter")
    ```
    """

    def __init__(self, namespace: str) -> None:
        """
        Open NVS namespace.

        :param namespace: Namespace name (max 15 chars)

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> nvs = esp32.NVS("settings")
        ```
        """
        ...

    def set_i32(self, key: str, value: int) -> None:
        """
        Set 32-bit signed integer.

        :param key: Key name (max 15 chars)
        :param value: Integer value

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> nvs.set_i32("brightness", 100)
            >>> nvs.commit()
        ```
        """
        ...

    def get_i32(self, key: str) -> int:
        """
        Get 32-bit signed integer.

        :param key: Key name

        :returns: Stored value

        :raises OSError: If key not found

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> try:
            ...     val = nvs.get_i32("brightness")
            ... except OSError:
            ...     val = 50  # default
        ```
        """
        ...

    def set_blob(self, key: str, value: bytes) -> None:
        """
        Set binary blob.

        :param key: Key name
        :param value: Binary data (any buffer-protocol object is accepted at runtime)

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> nvs.set_blob("calibration", bytes([1, 2, 3, 4]))
            >>> nvs.commit()
        ```
        """
        ...

    def get_blob(self, key: str, buffer: bytearray) -> int:
        """
        Get binary blob.

        :param key: Key name
        :param buffer: Buffer to read into

        :returns: Number of bytes read

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> buf = bytearray(100)
            >>> length = nvs.get_blob("calibration", buf)
            >>> data = buf[:length]
        ```
        """
        ...

    def erase_key(self, key: str) -> None:
        """
        Erase a key.

        :param key: Key name

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> nvs.erase_key("old_setting")
            >>> nvs.commit()
        ```
        """
        ...

    def commit(self) -> None:
        """
        Commit changes to flash.

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> nvs.set_i32("count", 123)
            >>> nvs.commit()  # Persist to flash
        ```
        """
        ...


class Partition:
    """
    Flash partition access.

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> # Get running partition
        >>> part = esp32.Partition(esp32.Partition.RUNNING)
        >>> print(part.info())
    ```
    """

    # Partition type constants
    BOOT: int
    """Boot partition."""

    RUNNING: int
    """Currently running partition."""

    TYPE_APP: int
    """Application partition type."""

    TYPE_DATA: int
    """Data partition type."""

    def __init__(self, id: Union[str, int], block_size: int = 4096) -> None:
        """
        Get partition by name or type.

        :param id: Partition name or BOOT/RUNNING constant
        :param block_size: Block size for the block device interface (default 4096)

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> app = esp32.Partition(esp32.Partition.RUNNING)
            >>> data = esp32.Partition("nvs")
        ```
        """
        ...

    def info(self) -> Tuple[int, int, int, int, str, bool]:
        """
        Get partition information.

        :returns: (type, subtype, addr, size, label, encrypted)

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> part = esp32.Partition(esp32.Partition.RUNNING)
            >>> ptype, subtype, addr, size, label, enc = part.info()
            >>> print(f"Partition: {label}, size: {size}")
        ```
        """
        ...

    def readblocks(self, block_num: int, buf: bytearray, offset: int = None) -> None:
        """
        Read blocks from partition.

        :param block_num: Starting block number
        :param buf: Buffer to read into
        :param offset: Optional byte offset within the block (extended block protocol)

        Implements the simple and extended block protocol defined by
        ``vfs.AbstractBlockDev``.

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> buf = bytearray(4096)
            >>> part.readblocks(0, buf)
        ```
        """
        ...

    def writeblocks(self, block_num: int, buf: bytes, offset: int = None) -> None:
        """
        Write blocks to partition.

        :param block_num: Starting block number
        :param buf: Data to write
        :param offset: Optional byte offset within the block (extended block protocol)

        Implements the simple and extended block protocol defined by
        ``vfs.AbstractBlockDev``.

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> data = bytes([0xFF] * 4096)
            >>> part.writeblocks(0, data)
        ```
        """
        ...

    def ioctl(self, op: int, arg: int = 0) -> Optional[int]:
        """
        Perform I/O control operation.

        :param op: Operation code (see ``vfs`` block device protocol)
        :param arg: Operation argument

        :returns: Result

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> # Get block count
            >>> blocks = part.ioctl(4, 0)
        ```
        """
        ...

    def set_boot(self) -> None:
        """
        Set this partition as boot partition.

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> ota_part = esp32.Partition("ota_0")
            >>> ota_part.set_boot()
            >>> machine.reset()
        ```
        """
        ...

    def get_next_update(self) -> 'Partition':
        """
        Get next OTA update partition.

        :returns: Next OTA partition

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> current = esp32.Partition(esp32.Partition.RUNNING)
            >>> next_part = current.get_next_update()
        ```
        """
        ...

    @staticmethod
    def mark_app_valid_cancel_rollback() -> None:
        """
        Mark app as valid, cancel rollback.

        Call after successful OTA update boot.

        .. note::
            This uses the ESP-IDF “app rollback” feature. An ``OSError(-261)`` is
            raised if the firmware wasn’t built with rollback enabled.
            It is OK to call this on every boot.

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> esp32.Partition.mark_app_valid_cancel_rollback()
        ```
        """
        ...

    @staticmethod
    def find(type: int = TYPE_APP, subtype: int = 0xff, label: str = None) -> list:
        """
        Find partitions by type/subtype/label.

        :param type: Partition type
        :param subtype: Partition subtype (0xff = any)
        :param label: Partition label

        :returns: List of matching partitions

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> apps = esp32.Partition.find(esp32.Partition.TYPE_APP)
            >>> for p in apps:
            ...     print(p.info())
        ```
        """
        ...


class RMT:
    """
    Remote Control Transceiver.

    Hardware for generating precise timing signals.

    Commonly used for WS2812 LEDs, IR remotes, and other digital protocols that
    require accurate pulse timing.

    .. warning::
        MicroPython’s RMT support is considered beta and the interface may change.

    Example
    -------
    ```python
        >>> import esp32
        >>> from machine import Pin
        >>> 
        >>> r = esp32.RMT(pin=Pin(18), resolution_hz=10000000)
        >>> r.write_pulses((1, 20, 2, 40), 0)
    ```
    """

    # Constants
    PULSE_MAX: int
    """Maximum integer that can be set for a pulse duration."""

    def __init__(
        self,
        channel: int = None,
        *,
        pin: Any = None,
        resolution_hz: int = 10000000,
        clock_div: int = None,
        idle_level: bool = False,
        num_symbols: int = None,
        tx_carrier: Tuple[int, int, bool] = None
    ) -> None:
        """
        Create RMT channel.

        :param channel: Channel number (optional, for backward compatibility)
        :param pin: GPIO pin (required)
        :param resolution_hz: Channel resolution in Hz (default 10MHz = 100ns units)
        :param clock_div: Clock divider (deprecated, use resolution_hz)
        :param idle_level: Idle output level (False=low, True=high)
        :param num_symbols: Buffer size (min 48 or 64 depending on chip)
        :param tx_carrier: Carrier tuple (freq_hz, duty_percent, output_level)

        Example
        -------
        ```python
            >>> import esp32
            >>> from machine import Pin
            >>> 
            >>> r = esp32.RMT(pin=Pin(18), resolution_hz=10000000)
            >>> 
            >>> # With carrier for IR
            >>> r = esp32.RMT(pin=Pin(19), resolution_hz=10000000,
            ...               tx_carrier=(38000, 50, True))
        ```
        """
        ...

    def source_freq(self) -> int:
        """
        Get source clock frequency.

        :returns: Frequency in Hz

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> freq = rmt.source_freq()
            >>> print(f"Source: {freq} Hz")
        ```
        """
        ...

    def clock_div(self) -> int:
        """
        Get clock divider.

        .. note::
            Deprecated. May not be accurate if resolution_hz was used.

        :returns: Clock divider value

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> div = rmt.clock_div()
            >>> resolution = rmt.source_freq() / div
        ```
        """
        ...

    def wait_done(self, *, timeout: int = 0) -> bool:
        """
        Wait for transmission to complete.

        :param timeout: Timeout in ms (0=no wait, -1=wait forever; blocks forever if looping)

        :returns: True if idle, False if still transmitting

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> rmt.write_pulses(data, True)
            >>> if not rmt.wait_done(timeout=1000):
            ...     print("Timeout!")
        ```
        """
        ...

    def loop(self, enable: bool) -> None:
        """
        Enable/disable continuous loop mode.

        .. note::
            Deprecated. Use loop_count() instead.

        :param enable: True for continuous output

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> rmt.loop(True)
            >>> rmt.write_pulses([100, 100], True)
            >>> # Outputs continuously until loop(False)
        ```
        """
        ...

    def loop_count(self, n: int) -> None:
        """
        Configure looping on the channel.

        :param n: 0=disable, -1=infinite, positive=loop n times

        .. note::
            Looping for a finite number of times is not supported
            by all flavors of ESP32.

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> rmt.loop_count(-1)  # Infinite loop
            >>> rmt.write_pulses([100, 100], True)
            >>> # ...
            >>> rmt.loop_count(0)  # Stop looping
        ```
        """
        ...

    def active(self, value: bool = None) -> Optional[bool]:
        """
        Get or set whether there is an ongoing transmission.

        :param value: False to stop transmission (True does nothing)

        :returns: True if transmitting, False if idle

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> if rmt.active():
            ...     print("Still transmitting")
            >>> rmt.active(False)  # Stop infinite loop
        ```
        """
        ...

    def write_pulses(
        self,
        duration: Union[list, tuple, int],
        data: Union[bool, list, tuple] = True
    ) -> None:
        """
        Begin transmitting a sequence of pulses.

        Three modes are supported:
        - Mode 1: duration is list/tuple of durations, data is initial level
        - Mode 2: duration is fixed duration, data is list/tuple of levels  
        - Mode 3: both duration and data are lists/tuples of equal length

        :param duration: Pulse durations (1 to PULSE_MAX) or single duration
        :param data: Initial level (bool) or list of levels

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> # Mode 1: Toggle level after each duration
            >>> rmt.write_pulses((1, 20, 2, 40), False)
            >>> 
            >>> # Mode 2: Fixed duration, varying levels
            >>> rmt.write_pulses(100, [True, False, True, False])
            >>> 
            >>> # Mode 3: Individual duration for each level
            >>> rmt.write_pulses([100, 200], [True, False])
        ```
        """
        ...

    @staticmethod
    def bitstream_rmt(value: bool = None) -> Optional[bool]:
        """
        Configure RMT usage in machine.bitstream implementation.

        :param value: True to use RMT, False for bit-banging

        :returns: Current state if no argument given

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> esp32.RMT.bitstream_rmt(True)  # Use RMT
            >>> print(esp32.RMT.bitstream_rmt())  # Query state
        ```
        """
        ...

    @staticmethod
    def bitstream_channel(channel: int = None) -> Optional[int]:
        """
        Get or set RMT channel for bitstream.

        .. note::
            Deprecated. Use bitstream_rmt() instead.

        :param channel: Channel to use (None to query)

        :returns: 1 if RMT enabled, None otherwise

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> esp32.RMT.bitstream_channel(0)
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Deinitialize RMT channel.

        Release all RMT resources and invalidate the object.

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> rmt.deinit()
        ```
        """
        ...


class PCNT:
    """
    Pulse Counter hardware.

    There are 8 pulse counter units (id 0..7).

    See machine.Counter and machine.Encoder for simpler abstractions.

    Example
    -------
    ```python
        >>> import esp32
        >>> from machine import Pin
        >>> 
        >>> pin_a = Pin(2, Pin.INPUT, pull=Pin.PULL_UP)
        >>> pcnt = esp32.PCNT(0, pin=pin_a, rising=esp32.PCNT.INCREMENT)
        >>> pcnt.start()
        >>> print(pcnt.value())
    ```
    """

    # Action constants
    INCREMENT: int
    """Increment counter on edge."""
    
    DECREMENT: int
    """Decrement counter on edge."""
    
    IGNORE: int
    """Ignore edge (default)."""

    # Mode constants
    HOLD: int
    """Hold/suspend counting when mode_pin matches."""
    
    REVERSE: int
    """Reverse count direction when mode_pin matches."""
    
    NORMAL: int
    """Normal counting (default for mode_low/mode_high)."""

    # IRQ trigger constants
    IRQ_ZERO: int
    """IRQ when counter resets to zero."""
    
    IRQ_MIN: int
    """IRQ when counter hits min value."""
    
    IRQ_MAX: int
    """IRQ when counter hits max value."""
    
    IRQ_THRESHOLD0: int
    """IRQ when counter hits threshold0 value."""
    
    IRQ_THRESHOLD1: int
    """IRQ when counter hits threshold1 value."""

    def __init__(self, id: int, **kwargs) -> None:
        """
        Get the singleton PCNT instance for the given unit id.

        :param id: Unit ID (0-7)
        :param kwargs: Passed to init() method

        Example
        -------
        ```python
            >>> import esp32
            >>> from machine import Pin
            >>> 
            >>> pcnt = esp32.PCNT(0, pin=Pin(2), rising=esp32.PCNT.INCREMENT)
        ```
        """
        ...

    def init(
        self,
        *,
        channel: int = 0,
        pin: Any = None,
        rising: int = None,
        falling: int = None,
        mode_pin: Any = None,
        mode_low: int = None,
        mode_high: int = None,
        filter: int = None,
        min: int = None,
        max: int = None,
        threshold0: int = None,
        threshold1: int = None,
        value: int = None
    ) -> None:
        """
        (Re-)initialize a pulse counter unit.

        Keyword arguments may be provided in groups to partially reconfigure a unit
        (e.g. rebinding pins, updating counting actions, updating filter/limits).
        Each unit supports two channels (0 and 1) which update the same counter value.

        :param channel: Channel (0 or 1) for dual-channel config
        :param pin: Input Pin to monitor for pulses
        :param rising: Action on rising edge (INCREMENT, DECREMENT, IGNORE)
        :param falling: Action on falling edge
        :param mode_pin: Second Pin for mode control
        :param mode_low: Behavior when mode_pin is low (HOLD, REVERSE, NORMAL)
        :param mode_high: Behavior when mode_pin is high
        :param filter: Pulse width filter (1-1023 in 80MHz ticks)
        :param min: Minimum counter value (-32768..-1, 0 to disable)
        :param max: Maximum counter value (1..32767, 0 to disable)
        :param threshold0: Counter value for IRQ_THRESHOLD0 event
        :param threshold1: Counter value for IRQ_THRESHOLD1 event
        :param value: Set to 0 to reset counter

        Example
        -------
        ```python
            >>> import esp32
            >>> from machine import Pin
            >>> 
            >>> # 4X quadrature decoding
            >>> pin_a = Pin(2, Pin.INPUT, pull=Pin.PULL_UP)
            >>> pin_b = Pin(3, Pin.INPUT, pull=Pin.PULL_UP)
            >>> rotary = esp32.PCNT(0, min=-32000, max=32000)
            >>> rotary.init(channel=0, pin=pin_a, 
            ...             falling=esp32.PCNT.INCREMENT,
            ...             rising=esp32.PCNT.DECREMENT,
            ...             mode_pin=pin_b, mode_low=esp32.PCNT.REVERSE)
            >>> rotary.init(channel=1, pin=pin_b,
            ...             falling=esp32.PCNT.DECREMENT,
            ...             rising=esp32.PCNT.INCREMENT,
            ...             mode_pin=pin_a, mode_low=esp32.PCNT.REVERSE)
        ```
        """
        ...

    def start(self) -> None:
        """
        Start counting.

        Example
        -------
        ```python
            >>> pcnt.start()
        ```
        """
        ...

    def value(self, value: int = None) -> int:
        """
        Get or reset counter value.

        :param value: Set to 0 to reset (other values raise an error)

        .. note::
            Read-and-reset is not atomic, so pulses may be missed. Also, ``value()``
            may force execution of pending IRQ events before returning.

        :returns: Current counter value (before reset if resetting)

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> count = pcnt.value()
            >>> pcnt.value(0)  # Reset
        ```
        """
        ...

    def irq(
        self,
        handler: Callable[['PCNT'], None] = None,
        trigger: int = None
    ) -> Any:
        """
        Configure interrupt handler.

        :param handler: Callback function (receives PCNT instance)
        :param trigger: Bitmask of IRQ_* events (OR'd together)

        :returns: Callback object with flags() method

        .. note::
            Calling ``irq().flags()`` clears the flags, so call it once per handler.
            ``IRQ_ZERO`` also triggers when hitting min/max, because the hardware
            resets to zero at those limits.

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> def pcnt_irq(pcnt):
            ...     flags = pcnt.irq().flags()
            ...     if flags & esp32.PCNT.IRQ_ZERO:
            ...         print("Reset to zero")
            >>> 
            >>> pcnt.irq(handler=pcnt_irq, 
            ...          trigger=esp32.PCNT.IRQ_ZERO | esp32.PCNT.IRQ_MAX)
        ```
        """
        ...


class ULP:
    """
    Ultra Low Power coprocessor.

    Run code while main CPU is in deep sleep.

    Available on ESP32/ESP32-S2/ESP32-S3 chips with ULP support.

    .. warning::
        This does not provide access to the RISC-V ULP available on some chips.

    Example
    -------
    ```python
        >>> import esp32
        >>> 
        >>> ulp = esp32.ULP()
        >>> ulp.load_binary(0, ulp_code)
        >>> ulp.run(0)
    ```
    """

    # Memory constants
    RESERVE_MEM: int
    """Reserved memory size."""

    def __init__(self) -> None:
        """Create ULP instance."""
        ...

    def set_wakeup_period(self, period_index: int, period_us: int) -> None:
        """
        Set ULP wakeup period.

        :param period_index: Period index (0-4)
        :param period_us: Period in microseconds

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> ulp = esp32.ULP()
            >>> ulp.set_wakeup_period(0, 50000)  # 50ms
        ```
        """
        ...

    def load_binary(self, addr: int, binary: bytes) -> None:
        """
        Load ULP binary program.

        :param addr: Load address (word offset)
        :param binary: ULP binary code

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> with open('ulp_prog.bin', 'rb') as f:
            ...     code = f.read()
            >>> ulp.load_binary(0, code)
        ```
        """
        ...

    def run(self, entry: int) -> None:
        """
        Run ULP program.

        :param entry: Entry point (word offset)

        Example
        -------
        ```python
            >>> import esp32
            >>> 
            >>> ulp.load_binary(0, ulp_code)
            >>> ulp.run(0)
        ```
        """
        ...
