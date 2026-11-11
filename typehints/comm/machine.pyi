"""
Hardware control module for MicroPython.

Provides access to hardware-specific functions for GPIO, PWM, I2C, SPI,
UART, ADC, Timer, RTC, and other peripheral interfaces.

Example
-------
```python
    >>> from machine import Pin, PWM, I2C
    >>> 
    >>> # GPIO control
    >>> led = Pin(25, Pin.OUT)
    >>> led.toggle()
    >>> 
    >>> # PWM output
    >>> pwm = PWM(Pin(15))
    >>> pwm.freq(1000)
    >>> pwm.duty_u16(32768)
    >>> 
    >>> # I2C communication
    >>> i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
    >>> devices = i2c.scan()
```
"""

from typing import Callable, Optional, Union, Any

# Type aliases
_IRQHandler = Callable[["Pin"], None]


def freq(hz: Optional[int] = None) -> int:
    """
    Get or set the CPU frequency.

    This controls the CPU (and sometimes system) clock rate. Changing the CPU
    frequency can trade performance vs power consumption and may affect timing-
    sensitive code.

    Support and valid frequency values are port/board specific. On ports that
    support changing frequency, passing a value attempts to reconfigure the CPU
    clock. On ports that don't support changing frequency, providing ``hz`` may
    raise an exception.

    :param hz: New frequency in Hz (if setting). Use ``None`` to query only.

    :returns: Current CPU frequency in Hz.

    :raises ValueError: If the requested frequency is invalid (port-specific).
    :raises OSError: If the frequency cannot be set on this port/board.

    Example
    -------
    ```python
        >>> from machine import freq
        >>> 
        >>> print(freq())        # Get current frequency
        >>> freq(250_000_000)    # Set to 250MHz
        >>> 
        >>> # Restore previous frequency
        >>> old = freq()
        >>> try:
        ...     freq(old)
        ... except Exception:
        ...     # Some ports may not allow changing it
        ...     pass
    ```
    """
    ...


def unique_id() -> bytes:
    """
    Get the unique identifier of the board.

    The returned value is a board- or MCU-specific identifier. It is commonly
    used to derive a per-device name, a network identifier, or to seed a PRNG.
    The exact length and stability guarantees are port dependent.

    :returns: Unique ID as bytes (often 6 or 8 bytes, but port-specific).

    Example
    -------
    ```python
        >>> from machine import unique_id
        >>> 
        >>> uid = unique_id()
        >>> print(uid.hex())
    ```
    """
    ...


def reset() -> None:
    """
    Reset the device.

    This performs a full system reset (similar to pressing the reset button).
    After calling this function the board restarts and the current program
    does not continue.

    Example
    -------
    ```python
        >>> from machine import reset
        >>> 
        >>> reset()  # Device will restart
    ```
    """
    ...


def soft_reset() -> None:
    """
    Perform a soft reset of the interpreter.

    A soft reset restarts the MicroPython runtime (VM) without necessarily
    performing the same kind of full hardware reset as ``reset()``. The exact
    effect on peripherals and hardware state is port/board specific.

    Example
    -------
    ```python
        >>> from machine import soft_reset
        >>> 
        >>> soft_reset()
    ```
    """
    ...


def reset_cause() -> int:
    """
    Get the reset cause.

    The returned value can be compared to reset-cause constants such as
    ``PWRON_RESET`` or ``WDT_RESET``. Availability and meaning of constants
    is port dependent.

    :returns: Reset cause constant

    Example
    -------
    ```python
        >>> from machine import reset_cause, PWRON_RESET, WDT_RESET
        >>> 
        >>> cause = reset_cause()
        >>> if cause == PWRON_RESET:
        ...     print("Power-on reset")
    ```
    """
    ...


def bootloader(size: int = 0) -> None:
    """
    Enter the bootloader (UF2 mode on RP2).

    This is typically used to put the board into a firmware update mode.
    Behavior varies by port/board. On some ports the optional ``size``
    argument is used to control the USB MSC/UF2 presentation.

    :param size: Optional size parameter

    Example
    -------
    ```python
        >>> from machine import bootloader
        >>> 
        >>> bootloader()  # Enter UF2 mode
    ```
    """
    ...


def idle() -> None:
    """
    Wait for an interrupt, reducing power consumption.

    This function hints to the CPU that it can sleep until the next interrupt.
    It is commonly used in polling loops to reduce power consumption.

    Example
    -------
    ```python
        >>> from machine import idle
        >>> 
        >>> while True:
        ...     idle()  # Low-power wait
    ```
    """
    ...


def lightsleep(time_ms: Optional[int] = None) -> None:
    """
    Enter light sleep mode.

    Light sleep is a low-power state where the CPU stops or slows down, but the
    system can usually resume without a full reset. Wake sources and what state
    is retained are port/board specific.

    :param time_ms: Sleep duration in milliseconds (None = indefinite)

    Example
    -------
    ```python
        >>> from machine import lightsleep
        >>> 
        >>> lightsleep(5000)  # Sleep for 5 seconds
    ```
    """
    ...


def deepsleep(time_ms: Optional[int] = None) -> None:
    """
    Enter deep sleep mode.

    Deep sleep is a lower-power state than ``lightsleep()``. On many ports the
    device will reset on wake-up (i.e. the program restarts from boot). What
    memory/state is retained depends on the port and hardware.

    :param time_ms: Sleep duration in milliseconds (None = indefinite)

    Example
    -------
    ```python
        >>> from machine import deepsleep
        >>> 
        >>> deepsleep(10000)  # Deep sleep for 10 seconds
    ```
    """
    ...


def disable_irq() -> int:
    """
    Disable interrupt requests.

    Returns a value representing the previous IRQ state. Pass this value back
    to ``enable_irq()`` to restore the prior state.

    This is useful for short critical sections. Keep the protected code small:
    disabling interrupts for too long can break time-sensitive peripherals.

    :returns: Previous IRQ state (pass to enable_irq)

    Example
    -------
    ```python
        >>> from machine import disable_irq, enable_irq
        >>> 
        >>> state = disable_irq()
        >>> try:
        ...     # Critical section
        ...     pass
        ... finally:
        ...     enable_irq(state)
    ```
    """
    ...


def enable_irq(state: int = 1) -> None:
    """
    Re-enable interrupt requests.

    The recommended pattern is to call ``enable_irq()`` with the state returned
    by ``disable_irq()``. Passing ``1`` will enable IRQs unconditionally.

    :param state: IRQ state from disable_irq()

    Example
    -------
    ```python
        >>> from machine import disable_irq, enable_irq
        >>> 
        >>> state = disable_irq()
        >>> # Critical section
        >>> enable_irq(state)
    ```
    """
    ...


def mem8() -> Any:
    """Memory access at byte level.

    This provides a memory-mapped view for direct register/RAM access:
    ``mem8[addr]`` reads a byte and ``mem8[addr] = value`` writes a byte.

    Misaligned or invalid addresses can raise an exception or cause a crash,
    depending on the MCU and port.
    """
    ...


def mem16() -> Any:
    """Memory access at 16-bit level.

    Provides 16-bit (halfword) memory-mapped access via indexing.
    Addresses are typically expected to be 2-byte aligned.
    """
    ...


def mem32() -> Any:
    """Memory access at 32-bit level.

    Provides 32-bit (word) memory-mapped access via indexing.
    Addresses are typically expected to be 4-byte aligned.
    """
    ...


def wake_reason() -> int:
    """
    Get the wake reason after light or deep sleep.

    The returned value can be compared to the wake-reason constants
    ``PIN_WAKE``, ``RTC_WAKE``, or ``WLAN_WAKE``.

    :returns: Wake reason constant

    :raises NotImplementedError: On ports that do not support wake-reason query.

    Example
    -------
    ```python
        >>> from machine import wake_reason, PIN_WAKE, RTC_WAKE
        >>> 
        >>> reason = wake_reason()
        >>> if reason == PIN_WAKE:
        ...     print("Woke from GPIO pin")
        >>> elif reason == RTC_WAKE:
        ...     print("Woke from RTC alarm")
    ```
    """
    ...


def time_pulse_us(pin: "Pin", pulse_level: int,
                  timeout_us: int = 1_000_000) -> int:
    """
    Time a pulse on the given pin.

    If the current value of the pin differs from ``pulse_level``, the function
    first waits until the pin equals ``pulse_level``, then times how long the
    pin stays at ``pulse_level``.

    Returns the pulse duration in microseconds. Returns ``-2`` if there was a
    timeout waiting for the initial edge, or ``-1`` if the pulse timed out
    while being measured.

    :param pin: Pin object to read
    :param pulse_level: Pulse level to time (0 or 1)
    :param timeout_us: Timeout in microseconds (default 1 second)

    :returns: Pulse duration in microseconds (negative on timeout)

    Example
    -------
    ```python
        >>> from machine import Pin, time_pulse_us
        >>> 
        >>> trig = Pin(5, Pin.OUT)
        >>> echo = Pin(6, Pin.IN)
        >>> 
        >>> # HC-SR04 ultrasonic sensor
        >>> trig.value(0)
        >>> trig.value(1)
        >>> trig.value(0)
        >>> duration = time_pulse_us(echo, 1, 30000)
        >>> distance_cm = duration / 58.0
        >>> print(f"Distance: {distance_cm:.1f} cm")
    ```
    """
    ...


def bitstream(pin: "Pin", encoding: int, timing: tuple, data: bytes) -> None:
    """
    Transmit data on ``pin`` using the given ``encoding``.

    Provides bit-banged signal generation with precise timing, primarily used
    for driving WS2812 / NeoPixel RGB LED strips.

    The supported encodings are:

    * ``0`` — "high low" pulse duration modulation. The ``timing`` must be a
      4-tuple of nanoseconds ``(high_time_0, low_time_0, high_time_1, low_time_1)``.
      For example, ``(400, 850, 800, 450)`` is the timing for WS2812 at 800kHz.

    :param pin: Output pin to transmit on (must be configured as output)
    :param encoding: Signal encoding type (0 = WS2812 pulse-width modulation)
    :param timing: 4-tuple of timing values in nanoseconds
    :param data: Bytes to transmit

    Example
    -------
    ```python
        >>> from machine import Pin, bitstream
        >>> 
        >>> pin = Pin(5, Pin.OUT)
        >>> # WS2812 (NeoPixel) timing at 800kHz
        >>> timing = (400, 850, 800, 450)
        >>> # RGB pixels: Red, Green, Blue
        >>> pixels = bytearray([255, 0, 0,   # Red
        ...                     0, 255, 0,   # Green
        ...                     0, 0, 255])  # Blue
        >>> bitstream(pin, 0, timing, pixels)
    ```
    """
    ...


# Reset cause constants
PWRON_RESET: int
"""Power-on reset.

Indicates the last reset was caused by power-on, or a reset source treated as
equivalent to a power-on reset on this port.
"""

WDT_RESET: int
"""Watchdog timer reset.

Indicates the last reset was caused by the watchdog timer.
"""

HARD_RESET: int
"""Hard reset cause.

Indicates the last reset was a hardware reset (e.g. RESET pin pulled low,
or power button). Port specific.
"""

SOFT_RESET: int
"""Soft reset cause.

Indicates the last reset was a software reset triggered by the MicroPython
runtime (e.g. ``machine.soft_reset()``).
"""

DEEPSLEEP_RESET: int
"""Deep sleep wake-up reset cause.

Indicates the device woke from deep sleep mode. The reset cause is set to
this value on wake from deep sleep on ports that perform a full reset on
wake (i.e. the program restarts from boot).
"""

# IRQ wake-up mode constants (for lightsleep/deepsleep)
IDLE: int
"""IRQ wake mode: CPU idle.

The CPU can be woken by any interrupt. Lowest-power active state.
"""

SLEEP: int
"""IRQ wake mode: light sleep.

Similar to IDLE; used on some ports to indicate a light-sleep state where
the CPU clock is gated.
"""

DEEPSLEEP: int
"""IRQ wake mode: deep sleep.

Full deep sleep mode. On most ports, a wake-up causes a full system reset
and the program restarts from boot.
"""

# Wake reason constants (returned by wake_reason())
PIN_WAKE: int
"""Wake reason: GPIO pin trigger.

Indicates the device woke up from light or deep sleep due to a GPIO pin
level or edge event. Availability is port specific.
"""

RTC_WAKE: int
"""Wake reason: RTC alarm.

Indicates the device woke up from light or deep sleep due to an RTC timer
alarm. Availability is port specific.
"""

WLAN_WAKE: int
"""Wake reason: WLAN (network) activity.

Indicates the device woke up due to WLAN/network activity.
Availability: ESP32.
"""


class Pin:
    """
    GPIO pin control for digital I/O operations.

    Supports input/output modes, optional pull resistors, and (on many ports)
    edge-triggered interrupts.

    Pin numbering and which pins are valid is board specific. Some ports accept
    additional identifiers (e.g. strings like ``"LED"``), but this stub types
    the id as an integer.
    """

    # Mode constants
    IN: int
    """Input mode."""

    OUT: int
    """Output mode."""

    OPEN_DRAIN: int
    """Open-drain output mode."""

    ALT: int
    """Alternate function mode."""

    # Pull constants
    PULL_UP: int
    """Enable internal pull-up resistor."""

    PULL_DOWN: int
    """Enable internal pull-down resistor."""

    # IRQ trigger constants
    IRQ_RISING: int
    """Trigger on rising edge."""

    IRQ_FALLING: int
    """Trigger on falling edge."""

    def __init__(self, id: int, mode: int = -1, pull: int = -1,
                 *, value: int = None, alt: int = -1) -> None:
        """
        Create a new Pin object.

        The special value ``-1`` for ``mode``/``pull``/``alt`` typically means
        "leave unchanged" or "use a default" (port specific).

        :param id: GPIO pin number
        :param mode: Pin.IN, Pin.OUT, Pin.OPEN_DRAIN, or Pin.ALT
        :param pull: Pin.PULL_UP, Pin.PULL_DOWN, or None
        :param value: Initial output value (0 or 1)
        :param alt: Alternate function number

        Example
        -------
        ```python
            >>> from machine import Pin
            >>> 
            >>> # Output pin
            >>> led = Pin(25, Pin.OUT)
            >>> 
            >>> # Input with pull-up
            >>> btn = Pin(14, Pin.IN, Pin.PULL_UP)
            >>> 
            >>> # Output with initial value
            >>> relay = Pin(16, Pin.OUT, value=0)
        ```
        """
        ...

    def init(self, mode: int = -1, pull: int = -1,
             *, value: int = None, alt: int = -1) -> None:
        """
        Reinitialize the pin with new parameters.

        This is equivalent to re-creating the pin object, but can be more
        convenient when reusing the same ``Pin`` instance.

        :param mode: Pin.IN, Pin.OUT, Pin.OPEN_DRAIN, or Pin.ALT
        :param pull: Pin.PULL_UP, Pin.PULL_DOWN, or None
        :param value: Initial output value
        :param alt: Alternate function number

        Example
        -------
        ```python
            >>> pin = Pin(25)
            >>> pin.init(Pin.OUT)
            >>> pin.init(Pin.IN, Pin.PULL_UP)
        ```
        """
        ...

    def value(self, x: Optional[int] = None) -> Optional[int]:
        """
        Get or set the pin value.

        Reading returns ``0`` or ``1``. When setting, values are treated as
        boolean (typically ``0`` for low, non-zero for high).

        :param x: If provided, set pin to this value (0 or 1)

        :returns: Current pin value if no argument, None if setting

        Example
        -------
        ```python
            >>> pin = Pin(25, Pin.OUT)
            >>> pin.value(1)      # Set high
            >>> pin.value(0)      # Set low
            >>> v = pin.value()   # Read current value
        ```
        """
        ...

    def __call__(self, x: Optional[int] = None) -> Optional[int]:
        """
        Shorthand for value().

        :param x: If provided, set pin to this value

        :returns: Current pin value if no argument

        Example
        -------
        ```python
            >>> pin = Pin(25, Pin.OUT)
            >>> pin(1)    # Same as pin.value(1)
            >>> pin()     # Same as pin.value()
        ```
        """
        ...

    def on(self) -> None:
        """
        Set the pin to high (1).

        The pin must be configured for output for this to have an effect.

        Example
        -------
        ```python
            >>> led = Pin(25, Pin.OUT)
            >>> led.on()
        ```
        """
        ...

    def off(self) -> None:
        """
        Set the pin to low (0).

        The pin must be configured for output for this to have an effect.

        Example
        -------
        ```python
            >>> led = Pin(25, Pin.OUT)
            >>> led.off()
        ```
        """
        ...

    def toggle(self) -> None:
        """
        Toggle the pin value.

        Example
        -------
        ```python
            >>> led = Pin(25, Pin.OUT)
            >>> led.toggle()  # If off, turn on; if on, turn off
        ```
        """
        ...

    def high(self) -> None:
        """
        Set the pin to high (1). Alias for on().

        Example
        -------
        ```python
            >>> led = Pin(25, Pin.OUT)
            >>> led.high()
        ```
        """
        ...

    def low(self) -> None:
        """
        Set the pin to low (0). Alias for off().

        Example
        -------
        ```python
            >>> led = Pin(25, Pin.OUT)
            >>> led.low()
        ```
        """
        ...

    def irq(self, handler: Optional[_IRQHandler] = None,
            trigger: int = 0,
            *, wake: int = None, hard: bool = False) -> Optional[_IRQHandler]:
        """
        Configure an interrupt handler for the pin.

        Calling ``irq()`` registers (or updates) an IRQ handler that will be
        invoked when the configured edge(s) occur.

        If ``hard`` is True, the handler may run in a hard-interrupt context.
        In that case, avoid allocating memory and avoid operations that may
        allocate (e.g. building strings, printing, appending to lists). Use
        ``micropython.schedule()`` if you need to defer work to the VM.

        :param handler: Function called on interrupt, receives Pin as argument
        :param trigger: Pin.IRQ_RISING, Pin.IRQ_FALLING, or both (OR'd)
        :param wake: Power mode to wake from (board specific)
        :param hard: If True, use hard interrupt (no memory allocation)

        :returns: Previous handler if getting, None if setting

        Example
        -------
        ```python
            >>> def on_press(pin):
            ...     print(f"Pin {pin} triggered!")
            >>> 
            >>> btn = Pin(14, Pin.IN, Pin.PULL_UP)
            >>> btn.irq(trigger=Pin.IRQ_FALLING, handler=on_press)
            >>> 
            >>> # Disable interrupt
            >>> btn.irq(handler=None)
        ```
        """
        ...


class PWM:
    """
    Pulse Width Modulation control.

    Used for LED dimming, motor control, servo control, and tone generation.

    The exact resolution and supported frequencies depend on the port and the
    underlying hardware PWM implementation.
    """

    def __init__(self, pin: Pin, *, freq: int = 0, duty_u16: int = 0,
                 duty_ns: int = 0, invert: bool = False) -> None:
        """
        Create a PWM object on a pin.

        :param pin: Pin object to use for PWM
        :param freq: PWM frequency in Hz
        :param duty_u16: Duty cycle as 16-bit value (0-65535)
        :param duty_ns: Duty cycle in nanoseconds
        :param invert: Invert the PWM output

        Example
        -------
        ```python
            >>> from machine import Pin, PWM
            >>> 
            >>> pwm = PWM(Pin(15))
            >>> pwm.freq(1000)
            >>> pwm.duty_u16(32768)  # 50% duty
            >>> 
            >>> # Or initialize with parameters
            >>> pwm = PWM(Pin(15), freq=1000, duty_u16=32768)
        ```
        """
        ...

    def freq(self, value: Optional[int] = None) -> Optional[int]:
        """
        Get or set the PWM frequency.

        Note that changing the frequency may affect duty-cycle resolution on
        some ports.

        :param value: New frequency in Hz (if setting)

        :returns: Current frequency if no argument

        Example
        -------
        ```python
            >>> pwm.freq(1000)      # Set to 1kHz
            >>> print(pwm.freq())   # Get current frequency
        ```
        """
        ...

    def duty_u16(self, value: Optional[int] = None) -> Optional[int]:
        """
        Get or set duty cycle as 16-bit value.

        ``0`` means always off and ``65535`` means always on. Intermediate
        values approximate the requested duty cycle.

        :param value: Duty cycle 0-65535 (0=0%, 65535=100%)

        :returns: Current duty cycle if no argument

        Example
        -------
        ```python
            >>> pwm.duty_u16(0)       # 0% duty (off)
            >>> pwm.duty_u16(32768)   # 50% duty
            >>> pwm.duty_u16(65535)   # 100% duty (full on)
        ```
        """
        ...

    def duty_ns(self, value: Optional[int] = None) -> Optional[int]:
        """
        Get or set duty cycle in nanoseconds.

        Not all ports support ``duty_ns()``. Where supported, it can be useful
        for applications where absolute pulse width matters.

        :param value: Duty cycle in nanoseconds

        :returns: Current duty cycle in ns if no argument

        Example
        -------
        ```python
            >>> pwm.freq(1000)         # 1kHz = 1ms period
            >>> pwm.duty_ns(500000)    # 500us = 50% duty
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Disable the PWM output.

        Example
        -------
        ```python
            >>> pwm.deinit()
        ```
        """
        ...


class ADC:
    """
    Analog to Digital Converter.

    Read analog voltage levels from GPIO pins.

    Supported pins, reference voltage, and calibration are port specific.
    """

    CORE_TEMP: int
    """Internal temperature sensor channel."""

    def __init__(self, pin: Union[Pin, int]) -> None:
        """
        Create an ADC object.

        :param pin: Pin object or GPIO number (26-29 on RP2)

        Example
        -------
        ```python
            >>> from machine import ADC, Pin
            >>> 
            >>> adc = ADC(Pin(26))
            >>> # Or using pin number
            >>> adc = ADC(26)
            >>> 
            >>> # Read internal temperature
            >>> temp_adc = ADC(ADC.CORE_TEMP)
        ```
        """
        ...

    def read_u16(self) -> int:
        """
        Read analog value as 16-bit unsigned integer.

        The returned value is scaled to the full 16-bit range (0..65535), even
        if the underlying ADC has fewer bits of resolution.

        :returns: ADC value 0-65535

        Example
        -------
        ```python
            >>> adc = ADC(26)
            >>> value = adc.read_u16()
            >>> voltage = value * 3.3 / 65535
            >>> print(f"Voltage: {voltage:.2f}V")
        ```
        """
        ...

    def read_uv(self) -> int:
        """
        Read analog value in microvolts.

        Availability and accuracy of microvolt readings are port specific.

        :returns: Voltage in microvolts

        Example
        -------
        ```python
            >>> adc = ADC(26)
            >>> uv = adc.read_uv()
            >>> voltage = uv / 1_000_000
            >>> print(f"Voltage: {voltage:.3f}V")
        ```
        """
        ...


class I2C:
    """
    I2C bus protocol for communicating with sensors and devices.

    Hardware I2C implementation using dedicated I2C peripherals.

    Addresses are typically 7-bit device addresses. Most methods raise
    ``OSError`` on bus errors or if a device does not respond.
    """

    def __init__(self, id: int, *, scl: Pin = None, sda: Pin = None,
                 freq: int = 400000) -> None:
        """
        Create an I2C object.

        :param id: I2C peripheral ID (0 or 1 on RP2)
        :param scl: Pin object for SCL (clock)
        :param sda: Pin object for SDA (data)
        :param freq: Clock frequency in Hz (default 400kHz)

        Example
        -------
        ```python
            >>> from machine import I2C, Pin
            >>> 
            >>> i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=400000)
            >>> 
            >>> # Scan for devices
            >>> devices = i2c.scan()
            >>> print([hex(d) for d in devices])
        ```
        """
        ...

    def scan(self) -> list[int]:
        """
        Scan for I2C devices on the bus.

        Returns a list of responding 7-bit addresses.

        :returns: List of addresses that responded

        Example
        -------
        ```python
            >>> devices = i2c.scan()
            >>> print(f"Found {len(devices)} devices")
            >>> for addr in devices:
            ...     print(f"  0x{addr:02x}")
        ```
        """
        ...

    def readfrom(self, addr: int, nbytes: int, stop: bool = True) -> bytes:
        """
        Read bytes from a device.

        If ``stop`` is False, the bus is left active (no STOP condition). This
        is useful for combined transactions on some devices.

        :param addr: I2C device address
        :param nbytes: Number of bytes to read
        :param stop: Generate STOP condition

        :returns: Bytes read from device

        Example
        -------
        ```python
            >>> data = i2c.readfrom(0x68, 7)
        ```
        """
        ...

    def readfrom_into(self, addr: int, buf: bytearray, stop: bool = True) -> None:
        """
        Read bytes from a device into a buffer.

        :param addr: I2C device address
        :param buf: Buffer to read into
        :param stop: Generate STOP condition

        Example
        -------
        ```python
            >>> buf = bytearray(7)
            >>> i2c.readfrom_into(0x68, buf)
        ```
        """
        ...

    def writeto(self, addr: int, buf: bytes, stop: bool = True) -> int:
        """
        Write bytes to a device.

        Returns the number of bytes written if successful.

        :param addr: I2C device address
        :param buf: Bytes to write
        :param stop: Generate STOP condition

        :returns: Number of bytes written

        Example
        -------
        ```python
            >>> i2c.writeto(0x68, b'\\x00')
        ```
        """
        ...

    def readfrom_mem(self, addr: int, memaddr: int, nbytes: int,
                     *, addrsize: int = 8) -> bytes:
        """
        Read from a device's memory/register.

        This performs a write of ``memaddr`` followed by a read of ``nbytes``.
        Many sensors expose registers this way.

        :param addr: I2C device address
        :param memaddr: Memory/register address
        :param nbytes: Number of bytes to read
        :param addrsize: Memory address size in bits (8 or 16)

        :returns: Bytes read from device

        Example
        -------
        ```python
            >>> # Read 6 bytes from register 0x3B
            >>> data = i2c.readfrom_mem(0x68, 0x3B, 6)
        ```
        """
        ...

    def readfrom_mem_into(self, addr: int, memaddr: int, buf: bytearray,
                          *, addrsize: int = 8) -> None:
        """
        Read from device memory into buffer.

        :param addr: I2C device address
        :param memaddr: Memory/register address
        :param buf: Buffer to read into
        :param addrsize: Memory address size in bits

        Example
        -------
        ```python
            >>> buf = bytearray(6)
            >>> i2c.readfrom_mem_into(0x68, 0x3B, buf)
        ```
        """
        ...

    def writeto_mem(self, addr: int, memaddr: int, buf: bytes,
                    *, addrsize: int = 8) -> None:
        """
        Write to a device's memory/register.

        :param addr: I2C device address
        :param memaddr: Memory/register address
        :param buf: Bytes to write
        :param addrsize: Memory address size in bits

        Example
        -------
        ```python
            >>> # Write 0x00 to register 0x6B
            >>> i2c.writeto_mem(0x68, 0x6B, b'\\x00')
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Disable the I2C bus.

        Example
        -------
        ```python
            >>> i2c.deinit()
        ```
        """
        ...


class SoftI2C(I2C):
    """
    Software I2C implementation using bit-banging.

    Can use any GPIO pins but slower than hardware I2C.

    Because it is implemented in software, timing is more sensitive to system
    load and interrupt latency.
    """

    def __init__(self, scl: Pin, sda: Pin, *, freq: int = 400000,
                 timeout: int = 50000) -> None:
        """
        Create a software I2C object.

        :param scl: Pin object for SCL
        :param sda: Pin object for SDA
        :param freq: Clock frequency in Hz
        :param timeout: Timeout in microseconds

        Example
        -------
        ```python
            >>> from machine import SoftI2C, Pin
            >>> 
            >>> i2c = SoftI2C(scl=Pin(5), sda=Pin(4), freq=100000)
        ```
        """
        ...


class SPI:
    """
    SPI bus protocol for high-speed communication.

    Hardware SPI implementation using dedicated SPI peripherals.

    SPI mode is configured using ``polarity`` (CPOL) and ``phase`` (CPHA).
    """

    MSB: int
    """Most significant bit first."""

    LSB: int
    """Least significant bit first."""

    def __init__(self, id: int, baudrate: int = 1000000, *, polarity: int = 0,
                 phase: int = 0, bits: int = 8, firstbit: int = MSB,
                 sck: Pin = None, mosi: Pin = None, miso: Pin = None) -> None:
        """
        Create an SPI object.

        :param id: SPI peripheral ID (0 or 1 on RP2)
        :param baudrate: Clock speed in Hz
        :param polarity: Clock polarity (0 or 1)
        :param phase: Clock phase (0 or 1)
        :param bits: Bits per transfer (usually 8)
        :param firstbit: SPI.MSB or SPI.LSB
        :param sck: Pin for clock
        :param mosi: Pin for MOSI (Master Out Slave In)
        :param miso: Pin for MISO (Master In Slave Out)

        Example
        -------
        ```python
            >>> from machine import SPI, Pin
            >>> 
            >>> spi = SPI(0, baudrate=1000000, polarity=0, phase=0,
            ...           sck=Pin(2), mosi=Pin(3), miso=Pin(4))
        ```
        """
        ...

    def init(self, baudrate: int = 1000000, *, polarity: int = 0,
             phase: int = 0, bits: int = 8, firstbit: int = 0) -> None:
        """
        Reinitialize SPI with new parameters.

        :param baudrate: Clock speed in Hz
        :param polarity: Clock polarity
        :param phase: Clock phase
        :param bits: Bits per transfer
        :param firstbit: Bit order

        Example
        -------
        ```python
            >>> spi.init(baudrate=2000000, polarity=1, phase=1)
        ```
        """
        ...

    def read(self, nbytes: int, write: int = 0x00) -> bytes:
        """
        Read bytes while writing a constant value.

        SPI is full-duplex: while reading, the controller must transmit
        something. The ``write`` value specifies the byte sent for each byte
        received.

        :param nbytes: Number of bytes to read
        :param write: Byte value to write during read

        :returns: Bytes read

        Example
        -------
        ```python
            >>> data = spi.read(10)
            >>> data = spi.read(10, write=0xFF)
        ```
        """
        ...

    def readinto(self, buf: bytearray, write: int = 0x00) -> None:
        """
        Read bytes into a buffer.

        :param buf: Buffer to read into
        :param write: Byte value to write during read

        Example
        -------
        ```python
            >>> buf = bytearray(10)
            >>> spi.readinto(buf)
        ```
        """
        ...

    def write(self, buf: bytes) -> None:
        """
        Write bytes.

        :param buf: Bytes to write

        Example
        -------
        ```python
            >>> spi.write(b'\\x01\\x02\\x03')
        ```
        """
        ...

    def write_readinto(self, write_buf: bytes, read_buf: bytearray) -> None:
        """
        Write and read simultaneously.

        :param write_buf: Bytes to write
        :param read_buf: Buffer for read data

        Example
        -------
        ```python
            >>> write_buf = b'\\x00\\x00\\x00'
            >>> read_buf = bytearray(3)
            >>> spi.write_readinto(write_buf, read_buf)
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Disable the SPI bus.

        Example
        -------
        ```python
            >>> spi.deinit()
        ```
        """
        ...


class SoftSPI(SPI):
    """
    Software SPI implementation using bit-banging.

    Can use any GPIO pins but slower than hardware SPI.

    Suitable for low-speed peripherals or when hardware SPI pins are not
    available.
    """

    def __init__(self, baudrate: int = 500000, *, polarity: int = 0,
                 phase: int = 0, bits: int = 8, firstbit: int = SPI.MSB,
                 sck: Pin = None, mosi: Pin = None, miso: Pin = None) -> None:
        """
        Create a software SPI object.

        :param baudrate: Clock speed in Hz
        :param polarity: Clock polarity
        :param phase: Clock phase
        :param bits: Bits per transfer
        :param firstbit: Bit order
        :param sck: Pin for clock
        :param mosi: Pin for MOSI
        :param miso: Pin for MISO

        Example
        -------
        ```python
            >>> from machine import SoftSPI, Pin
            >>> 
            >>> spi = SoftSPI(baudrate=100000, sck=Pin(10), 
            ...               mosi=Pin(11), miso=Pin(12))
        ```
        """
        ...


class UART:
    """
    UART/Serial communication interface.

    Provides asynchronous serial communication.

    Read methods may return ``None`` on timeout. Many ports raise ``OSError``
    for invalid configuration or I/O errors.
    """

    def __init__(self, id: int, baudrate: int = 9600, bits: int = 8,
                 parity: int = None, stop: int = 1, *,
                 tx: Pin = None, rx: Pin = None,
                 txbuf: int = 256, rxbuf: int = 256,
                 timeout: int = 0, timeout_char: int = 2,
                 flow: int = 0) -> None:
        """
        Create a UART object.

        :param id: UART peripheral ID (0 or 1 on RP2)
        :param baudrate: Baud rate
        :param bits: Data bits (5-8)
        :param parity: Parity (None, 0=even, 1=odd)
        :param stop: Stop bits (1 or 2)
        :param tx: Pin for TX
        :param rx: Pin for RX
        :param txbuf: TX buffer size
        :param rxbuf: RX buffer size
        :param timeout: Read timeout in ms
        :param timeout_char: Inter-character timeout in ms
        :param flow: Flow control (0=none)

        Example
        -------
        ```python
            >>> from machine import UART, Pin
            >>> 
            >>> uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
        ```
        """
        ...

    def init(self, baudrate: int = 9600, bits: int = 8, parity: int = None,
             stop: int = 1, **kwargs) -> None:
        """
        Reinitialize UART with new parameters.

        :param baudrate: Baud rate
        :param bits: Data bits
        :param parity: Parity
        :param stop: Stop bits

        Example
        -------
        ```python
            >>> uart.init(baudrate=9600)
        ```
        """
        ...

    def any(self) -> int:
        """
        Check if data is available to read.

        This returns the number of bytes currently available in the receive
        buffer.

        :returns: Number of bytes available

        Example
        -------
        ```python
            >>> if uart.any():
            ...     data = uart.read()
        ```
        """
        ...

    def read(self, nbytes: int = -1) -> Optional[bytes]:
        """
        Read bytes from UART.

        If ``nbytes`` is ``-1``, reads as many bytes as are available (subject
        to buffering and timeout behavior of the port).

        :param nbytes: Max bytes to read (-1 for all available)

        :returns: Bytes read or None if timeout

        Example
        -------
        ```python
            >>> data = uart.read(10)
            >>> data = uart.read()  # Read all available
        ```
        """
        ...

    def readline(self) -> Optional[bytes]:
        """
        Read a line ending with newline.

        :returns: Line including newline, or None if timeout

        Example
        -------
        ```python
            >>> line = uart.readline()
            >>> if line:
            ...     print(line.decode())
        ```
        """
        ...

    def readinto(self, buf: bytearray) -> Optional[int]:
        """
        Read bytes into a buffer.

        :param buf: Buffer to read into

        :returns: Number of bytes read or None if timeout

        Example
        -------
        ```python
            >>> buf = bytearray(10)
            >>> n = uart.readinto(buf)
        ```
        """
        ...

    def write(self, buf: bytes) -> Optional[int]:
        """
        Write bytes to UART.

        Returns the number of bytes accepted for transmission, or ``None`` on
        timeout (port dependent).

        :param buf: Bytes to write

        :returns: Number of bytes written or None if timeout

        Example
        -------
        ```python
            >>> uart.write(b'Hello\\n')
            >>> uart.write('Hello\\n'.encode())
        ```
        """
        ...

    def sendbreak(self) -> None:
        """
        Send a break condition.

        Example
        -------
        ```python
            >>> uart.sendbreak()
        ```
        """
        ...

    def flush(self) -> None:
        """
        Wait until all data is sent.

        Example
        -------
        ```python
            >>> uart.write(b'data')
            >>> uart.flush()  # Wait for transmission
        ```
        """
        ...

    def txdone(self) -> bool:
        """
        Check if transmission is complete.

        :returns: True if all data sent

        Example
        -------
        ```python
            >>> while not uart.txdone():
            ...     pass
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Disable the UART.

        Example
        -------
        ```python
            >>> uart.deinit()
        ```
        """
        ...


class Timer:
    """
    Hardware timer for periodic callbacks.

    Provides precise timing and periodic function execution.

    Timer callbacks are often executed in interrupt context. Keep callbacks
    short and avoid memory allocation where required by the port.
    """

    ONE_SHOT: int
    """Timer fires once."""

    PERIODIC: int
    """Timer fires repeatedly."""

    def __init__(self, id: int = -1, *, mode: int = PERIODIC,
                 period: int = -1, freq: float = -1,
                 callback: Callable[["Timer"], None] = None) -> None:
        """
        Create a Timer object.

        :param id: Timer ID (-1 for virtual timer)
        :param mode: Timer.ONE_SHOT or Timer.PERIODIC
        :param period: Period in milliseconds
        :param freq: Frequency in Hz (alternative to period)
        :param callback: Function called on timer event

        Example
        -------
        ```python
            >>> from machine import Timer
            >>> 
            >>> def tick(t):
            ...     print("Timer fired!")
            >>> 
            >>> timer = Timer(period=1000, callback=tick)
            >>> 
            >>> # Using frequency
            >>> timer = Timer(freq=10, callback=tick)  # 10 Hz
        ```
        """
        ...

    def init(self, *, mode: int = PERIODIC, period: int = -1,
             freq: float = -1,
             callback: Callable[["Timer"], None] = None) -> None:
        """
        Reinitialize the timer.

        :param mode: Timer.ONE_SHOT or Timer.PERIODIC
        :param period: Period in milliseconds
        :param freq: Frequency in Hz
        :param callback: Function called on timer event

        Example
        -------
        ```python
            >>> timer.init(period=500, callback=my_callback)
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Disable the timer.

        Example
        -------
        ```python
            >>> timer.deinit()
        ```
        """
        ...


class RTC:
    """
    Real-Time Clock for date and time keeping.

    Maintains current date and time, optionally with battery backup.

    Support for battery-backed timekeeping and the resolution/meaning of the
    ``subseconds`` field is port dependent.
    """

    def __init__(self) -> None:
        """
        Create an RTC object.

        Example
        -------
        ```python
            >>> from machine import RTC
            >>> 
            >>> rtc = RTC()
            >>> rtc.datetime((2026, 1, 7, 1, 12, 0, 0, 0))
        ```
        """
        ...

    def datetime(self, dt: tuple = None) -> tuple:
        """
        Get or set the date and time.

        The datetime tuple is ``(year, month, day, weekday, hours, minutes,
        seconds, subseconds)``. The meaning/range of ``weekday`` and
        ``subseconds`` can vary by port.

        :param dt: Tuple (year, month, day, weekday, hours, minutes, seconds, subseconds)

        :returns: Current datetime tuple if no argument

        Example
        -------
        ```python
            >>> rtc = RTC()
            >>> 
            >>> # Set datetime
            >>> rtc.datetime((2026, 1, 7, 1, 12, 0, 0, 0))
            >>> 
            >>> # Get datetime
            >>> dt = rtc.datetime()
            >>> year, month, day, wd, h, m, s, ss = dt
        ```
        """
        ...


class WDT:
    """
    Watchdog Timer for system recovery.

    Resets the system if not fed within timeout period.

    On many ports the watchdog cannot be disabled once started.
    """

    def __init__(self, timeout: int = 5000) -> None:
        """
        Create and start a watchdog timer.

        :param timeout: Timeout in milliseconds before reset

        Example
        -------
        ```python
            >>> from machine import WDT
            >>> 
            >>> wdt = WDT(timeout=5000)  # 5 second timeout
            >>> 
            >>> while True:
            ...     # Do work
            ...     wdt.feed()  # Reset watchdog
        ```
        """
        ...

    def feed(self) -> None:
        """
        Feed the watchdog to prevent reset.

        Example
        -------
        ```python
            >>> wdt.feed()
        ```
        """
        ...


class Signal:
    """
    Signal abstraction over Pin with inversion support.

    Provides a consistent interface regardless of active-high/low logic.

    This is handy for working with active-low LEDs, chip-select lines, and
    similar signals while keeping application logic consistent.
    """

    def __init__(self, pin: Pin, *, invert: bool = False) -> None:
        """
        Create a Signal object.

        :param pin: Underlying Pin object
        :param invert: If True, logic is inverted

        Example
        -------
        ```python
            >>> from machine import Pin, Signal
            >>> 
            >>> # Active-low LED (common on many boards)
            >>> led = Signal(Pin(25, Pin.OUT), invert=True)
            >>> led.on()   # Actually sets pin LOW
        ```
        """
        ...

    def value(self, x: Optional[int] = None) -> Optional[int]:
        """
        Get or set the signal value (with inversion applied).

        :param x: If provided, set signal to this value (0 or 1)

        :returns: Current signal value if no argument

        Example
        -------
        ```python
            >>> led.value(1)  # Turn on (respects inversion)
        ```
        """
        ...

    def on(self) -> None:
        """
        Set the signal active.

        Example
        -------
        ```python
            >>> led.on()
        ```
        """
        ...

    def off(self) -> None:
        """
        Set the signal inactive.

        Example
        -------
        ```python
            >>> led.off()
        ```
        """
        ...


class I2S:
    """
    Inter-IC Sound (I2S) digital audio bus controller.

    Supports both transmit (TX) and receive (RX) modes, with blocking,
    non-blocking (IRQ callback), and asyncio-based operation.

    Availability: ESP32, STM32/PyBoard, RP2.

    Example
    -------
    ```python
        >>> from machine import I2S, Pin
        >>> 
        >>> # Audio output (ESP32)
        >>> audio_out = I2S(0,
        ...                 sck=Pin(14), ws=Pin(13), sd=Pin(12),
        ...                 mode=I2S.TX, bits=16, format=I2S.STEREO,
        ...                 rate=44100, ibuf=20000)
        >>> 
        >>> # Write audio samples
        >>> samples = bytearray(1024)
        >>> num_written = audio_out.write(samples)
        >>> audio_out.deinit()
    ```
    """

    RX: int
    """Receive mode constant. Use for ``mode`` parameter."""

    TX: int
    """Transmit mode constant. Use for ``mode`` parameter."""

    MONO: int
    """Mono channel format constant. Use for ``format`` parameter."""

    STEREO: int
    """Stereo channel format constant. Use for ``format`` parameter."""

    def __init__(self, id: int, *, sck: "Pin", ws: "Pin", sd: "Pin",
                 mck: Optional["Pin"] = None,
                 mode: int, bits: int, format: int,
                 rate: int, ibuf: int) -> None:
        """
        Construct and initialise an I2S object.

        :param id: I2S peripheral ID (0 or 1; depends on port)
        :param sck: Serial clock pin
        :param ws: Word select (LRCLK) pin
        :param sd: Serial data pin
        :param mck: Optional master clock pin
        :param mode: I2S.TX or I2S.RX
        :param bits: Sample bit depth (16 or 32)
        :param format: I2S.MONO or I2S.STEREO
        :param rate: Audio sample rate in Hz (e.g. 44100)
        :param ibuf: Internal DMA buffer size in bytes

        Example
        -------
        ```python
            >>> from machine import I2S, Pin
            >>> 
            >>> audio_out = I2S(0,
            ...                 sck=Pin(14), ws=Pin(13), sd=Pin(12),
            ...                 mode=I2S.TX, bits=16, format=I2S.STEREO,
            ...                 rate=44100, ibuf=20000)
        ```
        """
        ...

    def init(self, *, sck: "Pin", ws: "Pin", sd: "Pin",
             mck: Optional["Pin"] = None,
             mode: int, bits: int, format: int,
             rate: int, ibuf: int) -> None:
        """
        Re-initialise the I2S bus with new parameters.

        :param sck: Serial clock pin
        :param ws: Word select pin
        :param sd: Serial data pin
        :param mck: Optional master clock pin
        :param mode: I2S.TX or I2S.RX
        :param bits: Sample bit depth
        :param format: Channel format
        :param rate: Sample rate in Hz
        :param ibuf: DMA buffer size in bytes

        Example
        -------
        ```python
            >>> audio_out.init(sck=Pin(14), ws=Pin(13), sd=Pin(12),
            ...                mode=I2S.TX, bits=16, format=I2S.MONO,
            ...                rate=22050, ibuf=10000)
        ```
        """
        ...

    def write(self, buf: bytes) -> int:
        """
        Write audio samples from ``buf`` to the I2S bus.

        Buffer byte ordering is little-endian. For stereo, left channel precedes
        right channel. For mono, sample data is written to both channels.

        :param buf: Bytes-like object containing audio samples

        :returns: Number of bytes written

        Example
        -------
        ```python
            >>> samples = bytearray(1024)  # fill with audio data
            >>> num_written = audio_out.write(samples)
        ```
        """
        ...

    def readinto(self, buf: bytearray) -> int:
        """
        Read audio samples from I2S bus into ``buf``.

        Buffer byte ordering is little-endian. For stereo, left channel
        precedes right channel. For mono, left channel data is used.

        :param buf: Writable buffer to read into

        :returns: Number of bytes read

        Example
        -------
        ```python
            >>> buf = bytearray(1024)
            >>> num_read = audio_in.readinto(buf)
        ```
        """
        ...

    def irq(self, handler: Callable) -> None:
        """
        Set a non-blocking callback for I2S transfers.

        The ``handler`` is called when ``buf`` is emptied (for TX) or filled
        (for RX), switching ``write`` and ``readinto`` to non-blocking mode.

        :param handler: Callable invoked in the MicroPython scheduler context

        Example
        -------
        ```python
            >>> def callback(i2s):
            ...     # refill/drain buffer
            ...     pass
            >>> 
            >>> audio_out.irq(callback)
            >>> audio_out.write(samples)  # returns immediately
        ```
        """
        ...

    @staticmethod
    def shift(*, buf: bytearray, bits: int, shift: int) -> None:
        """
        Bitwise shift all audio samples in ``buf``.

        Used for volume control. Each bit shift changes volume by ~6 dB.
        Positive ``shift`` increases volume (left shift); negative decreases it.

        :param buf: Buffer containing audio samples (modified in place)
        :param bits: Sample size in bits (e.g. 16 or 32)
        :param shift: Number of bits to shift (positive=louder, negative=quieter)

        Example
        -------
        ```python
            >>> from machine import I2S
            >>> 
            >>> samples = bytearray(1024)
            >>> # Halve volume (shift right by 1 = -6dB)
            >>> I2S.shift(buf=samples, bits=16, shift=-1)
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Deinitialise the I2S bus.

        Example
        -------
        ```python
            >>> audio_out.deinit()
        ```
        """
        ...


class I2CTarget:
    """
    I2C target (peripheral/slave) controller.

    Implements the I2C target (formerly "slave") role, allowing a MicroPython
    board to respond to requests from an I2C controller.

    New in MicroPython v1.28.0. Availability is port specific.

    Example
    -------
    ```python
        >>> from machine import I2CTarget, Pin
        >>> 
        >>> # Respond at address 0x42 with a 256-byte memory buffer
        >>> mem = bytearray(256)
        >>> target = I2CTarget(0, addr=0x42, mem=mem,
        ...                    scl=Pin(1), sda=Pin(0))
        >>> # The controller can now read/write mem[] via I2C
    ```
    """

    IRQ_ADDR_MATCH_READ: int
    """IRQ trigger: controller addressed this target for a read transaction."""

    IRQ_ADDR_MATCH_WRITE: int
    """IRQ trigger: controller addressed this target for a write transaction."""

    IRQ_READ_REQ: int
    """IRQ trigger: controller is requesting data (call write() to respond)."""

    IRQ_WRITE_REQ: int
    """IRQ trigger: controller has written data (call readinto() to read it)."""

    IRQ_END_READ: int
    """IRQ trigger: controller finished a read transaction."""

    IRQ_END_WRITE: int
    """IRQ trigger: controller finished a write transaction."""

    def __init__(self, id: int, addr: int, *, addrsize: int = 7,
                 mem: Optional[bytearray] = None, mem_addrsize: int = 8,
                 scl: Optional["Pin"] = None,
                 sda: Optional["Pin"] = None) -> None:
        """
        Create an I2C target object.

        :param id: I2C peripheral ID
        :param addr: This device's I2C address (7-bit or 10-bit)
        :param addrsize: Address size in bits (7 or 10)
        :param mem: Optional backing memory buffer (bytearray). If provided,
                    the controller can read/write it directly.
        :param mem_addrsize: Memory address size in bits (0, 8, 16, 24, or 32)
        :param scl: SCL pin
        :param sda: SDA pin

        Example
        -------
        ```python
            >>> from machine import I2CTarget, Pin
            >>> 
            >>> mem = bytearray(64)
            >>> target = I2CTarget(0, addr=0x50, mem=mem,
            ...                    scl=Pin(1), sda=Pin(0))
        ```
        """
        ...

    def write(self, buf: bytes) -> int:
        """
        Write bytes to be sent to the I2C controller.

        Called in response to an ``IRQ_READ_REQ`` event to provide data
        requested by the controller.

        :param buf: Data to send to the controller

        :returns: Number of bytes written

        Example
        -------
        ```python
            >>> def on_irq(target):
            ...     if irq_flags & I2CTarget.IRQ_READ_REQ:
            ...         target.write(b"hello")
        ```
        """
        ...

    def readinto(self, buf: bytearray) -> int:
        """
        Read bytes written by the I2C controller into ``buf``.

        Called in response to an ``IRQ_WRITE_REQ`` event to consume data
        sent by the controller.

        :param buf: Buffer to read controller's data into

        :returns: Number of bytes read

        Example
        -------
        ```python
            >>> def on_irq(target):
            ...     if irq_flags & I2CTarget.IRQ_WRITE_REQ:
            ...         buf = bytearray(8)
            ...         target.readinto(buf)
        ```
        """
        ...

    def irq(self, handler: Optional[Callable] = None,
            trigger: int = 0, hard: bool = False) -> Any:
        """
        Configure an interrupt handler for I2C target events.

        ``IRQ_ADDR_MATCH_READ``, ``IRQ_ADDR_MATCH_WRITE``, ``IRQ_READ_REQ``,
        and ``IRQ_WRITE_REQ`` must be handled as hard IRQs (``hard=True``)
        because they have strict timing requirements.

        :param handler: Callable invoked on IRQ events
        :param trigger: OR of IRQ constants to enable
        :param hard: If True, use hard interrupt

        Example
        -------
        ```python
            >>> def irq_handler(target):
            ...     pass
            >>> 
            >>> target.irq(handler=irq_handler,
            ...             trigger=I2CTarget.IRQ_READ_REQ | I2CTarget.IRQ_WRITE_REQ,
            ...             hard=True)
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Deinitialise the I2C target.

        After this call, the hardware will no longer respond to I2C requests.

        Example
        -------
        ```python
            >>> target.deinit()
        ```
        """
        ...


class ADCBlock:
    """
    ADC block providing access to multiple ADC channels.

    Represents a hardware ADC converter block that may contain multiple
    input channels. Use ``connect()`` to get an ``ADC`` object for a
    specific channel or pin.

    Availability: RP2 and some other ports.

    Example
    -------
    ```python
        >>> from machine import ADCBlock, Pin
        >>> 
        >>> # Connect ADC block 0, channel 0 to GPIO26
        >>> block = ADCBlock(0)
        >>> adc = block.connect(0, Pin(26))
        >>> value = adc.read_u16()
        >>> print(f"ADC: {value}")
    ```
    """

    def __init__(self, id: int, *, bits: int = 12) -> None:
        """
        Create an ADCBlock object.

        :param id: ADC block ID (hardware-specific)
        :param bits: Resolution in bits (hardware-specific; RP2 supports 12)

        Example
        -------
        ```python
            >>> from machine import ADCBlock
            >>> 
            >>> block = ADCBlock(0, bits=12)
        ```
        """
        ...

    def connect(self, channel: int, source: Optional["Pin"] = None,
                **kwargs: Any) -> "ADC":
        """
        Connect a channel or pin to this ADC block and return an ADC object.

        Can be called as:
        - ``connect(channel)`` — connect by channel number
        - ``connect(source)`` — connect by pin
        - ``connect(channel, source)`` — connect channel to specific pin

        :param channel: ADC channel number
        :param source: Pin object to connect to this channel

        :returns: ADC object configured for this channel/pin

        Example
        -------
        ```python
            >>> from machine import ADCBlock, Pin
            >>> 
            >>> block = ADCBlock(0)
            >>> # Connect channel 0 to GPIO26
            >>> adc = block.connect(0, Pin(26))
            >>> print(adc.read_u16())
        ```
        """
        ...


class USBDevice:
    """
    Low-level USB device controller for custom USB device descriptors.

    This is a singleton: calling the constructor multiple times returns the
    same object. Allows implementing custom USB device classes at a low level.

    New in MicroPython v1.28.0. Availability: RP2350 and other ports with
    TinyUSB support.

    Example
    -------
    ```python
        >>> from machine import USBDevice
        >>> 
        >>> usb = USBDevice()
        >>> # Configure with custom descriptors
        >>> usb.config(desc_dev=my_dev_descriptor,
        ...            desc_cfg=my_cfg_descriptor,
        ...            xfer_cb=my_xfer_callback)
        >>> usb.active(1)
    ```
    """

    BUILTIN_NONE: Any
    """No built-in USB class (disable built-in USB)."""

    BUILTIN_DEFAULT: Any
    """Use the default built-in USB class (CDC + MSC)."""

    BUILTIN_CDC: Any
    """Built-in CDC (USB serial) class only."""

    BUILTIN_MSC: Any
    """Built-in MSC (USB mass storage) class only."""

    BUILTIN_CDC_MSC: int
    """Built-in CDC + MSC combined."""

    def __init__(self) -> None:
        """
        Return the USBDevice singleton.

        Example
        -------
        ```python
            >>> from machine import USBDevice
            >>> 
            >>> usb = USBDevice()
        ```
        """
        ...

    def config(self, desc_dev: bytes, desc_cfg: bytes,
               desc_strs: Any = None,
               open_itf_cb: Optional[Callable] = None,
               reset_cb: Optional[Callable] = None,
               control_xfer_cb: Optional[Callable] = None,
               xfer_cb: Optional[Callable] = None) -> None:
        """
        Configure the USB device with descriptors and callbacks.

        :param desc_dev: USB device descriptor (bytes)
        :param desc_cfg: USB configuration descriptor (bytes)
        :param desc_strs: Optional string descriptors (list, dict, or subscriptable)
        :param open_itf_cb: Called when an interface is accepted by host
        :param reset_cb: Called on USB bus reset
        :param control_xfer_cb: Called for control endpoint transfers
        :param xfer_cb: Called when a transfer on a non-control endpoint completes

        Example
        -------
        ```python
            >>> usb = USBDevice()
            >>> usb.config(desc_dev=dev_desc,
            ...            desc_cfg=cfg_desc,
            ...            xfer_cb=lambda ep, result, xferred: None)
        ```
        """
        ...

    def active(self, state: Optional[bool] = None) -> bool:
        """
        Get or set the USB device active state.

        :param state: If provided, activate (True) or deactivate (False)

        :returns: Current active state

        Example
        -------
        ```python
            >>> usb = USBDevice()
            >>> usb.active(True)   # enable USB
            >>> print(usb.active())
        ```
        """
        ...

    def submit_xfer(self, ep: int, buffer: Any) -> bool:
        """
        Submit a USB transfer on endpoint ``ep``.

        :param ep: Endpoint number (not 0; use control_xfer_cb for EP0)
        :param buffer: Buffer with read access for IN endpoints,
                       write access for OUT endpoints

        :returns: True if queued successfully, False if the transfer could
                  not be queued

        :raises OSError: If the USB device is not active

        Example
        -------
        ```python
            >>> buf = bytearray(64)
            >>> if usb.submit_xfer(0x81, buf):
            ...     print("Transfer queued")
        ```
        """
        ...


class CAN:
    """
    Controller Area Network (CAN) bus interface.

    Supports CAN 2.0 (classic CAN). Some ports may also support CAN FD.
    New in MicroPython v1.28.0.

    Example
    -------
    ```python
        >>> from machine import CAN
        >>> 
        >>> can = CAN(1, 500_000)         # CAN bus 1, 500 kbps
        >>> can.set_filters(None)         # receive all messages
        >>> 
        >>> # Send a message
        >>> can.send(0x123, b'\\x01\\x02\\x03')
        >>> 
        >>> # Receive a message
        >>> msg = can.recv()
        >>> if msg:
        ...     can_id, data, flags, errs = msg
        ...     print(hex(can_id), bytes(data).hex())
        >>> 
        >>> can.deinit()
    ```
    """

    # Mode constants
    MODE_NORMAL: int
    """Normal operating mode: sends/receives on the CAN bus."""

    MODE_SLEEP: int
    """Low-power sleep mode."""

    MODE_LOOPBACK: int
    """Test mode: receives own transmitted messages; ignores ACK errors."""

    MODE_SILENT: int
    """Listen-only mode: receives messages without transmitting (no ACK)."""

    MODE_SILENT_LOOPBACK: int
    """Test mode without a transceiver: receives own TX messages internally."""

    # State constants
    STATE_STOPPED: int
    """Controller has not been initialised."""

    STATE_ACTIVE: int
    """Controller is active; TEC and REC error counters below 96."""

    STATE_WARNING: int
    """One or both error counters are between 96 and 127."""

    STATE_PASSIVE: int
    """Error Passive state; at least one counter >= 128 but TEC < 255."""

    STATE_BUS_OFF: int
    """Bus-Off state; TEC > 255. Call restart() to recover."""

    # Message flag constants
    FLAG_RTR: int
    """Indicates a Remote Transmission Request message."""

    FLAG_EXT_ID: int
    """Indicates an Extended (29-bit) CAN identifier."""

    FLAG_UNORDERED: int
    """Allow multiple messages with the same ID to be queued in any order."""

    # Receive error flags
    RECV_ERR_FULL: int
    """Hardware FIFO is full; messages may be lost."""

    RECV_ERR_OVERRUN: int
    """Hardware FIFO overrun; one or more messages have been lost."""

    # IRQ constants
    IRQ_RX: int
    """IRQ trigger: at least one message received."""

    IRQ_TX: int
    """IRQ trigger: message successfully transmitted or transmission failed."""

    IRQ_STATE: int
    """IRQ trigger: controller entered a more severe error state."""

    IRQ_TX_FAILED: int
    """Additional IRQ flag for IRQ_TX: transmission failed."""

    FILTERS_MAX: int
    """Maximum number of receive filters supported by this controller."""

    TX_QUEUE_LEN: int
    """Maximum number of messages that can be queued for transmission."""

    def __init__(self, id: int, *args: int, **kwargs: Any) -> None:
        """
        Construct and initialise a CAN controller.

        :param id: CAN peripheral ID (board-specific)
        :param args: Additional positional arguments (e.g. bitrate) passed
                     to ``init()``

        Example
        -------
        ```python
            >>> from machine import CAN
            >>> 
            >>> can = CAN(1, 500_000)  # bus 1 at 500 kbps
        ```
        """
        ...

    def init(self, bitrate: int, mode: int = 0,
             sample_point: int = 75, sjw: int = 1,
             tseg1: Optional[int] = None,
             tseg2: Optional[int] = None,
             **kwargs: Any) -> None:
        """
        Initialise the CAN bus.

        :param bitrate: Bus bit rate in bits per second
        :param mode: Operating mode constant (default MODE_NORMAL)
        :param sample_point: Sample point as integer percentage (default 75%)
        :param sjw: Resynchronisation jump width in time quanta (1-4)
        :param tseg1: Propagation + phase segment 1 (time quanta)
        :param tseg2: Phase segment 2 (time quanta)

        Example
        -------
        ```python
            >>> can.init(500_000, mode=CAN.MODE_NORMAL, sample_point=75)
            >>> 
            >>> # Or with explicit timing segments
            >>> can.init(500_000, tseg1=13, tseg2=2, sjw=1)
        ```
        """
        ...

    def deinit(self) -> None:
        """
        De-initialise the CAN controller.

        Pending messages are dropped and the controller stops interacting
        with the bus.

        Example
        -------
        ```python
            >>> can.deinit()
        ```
        """
        ...

    def restart(self) -> None:
        """
        Exit the Bus-Off error state.

        Cancels pending messages and attempts to recover the controller to
        an active state.

        Example
        -------
        ```python
            >>> if can.state() == CAN.STATE_BUS_OFF:
            ...     can.restart()
        ```
        """
        ...

    def state(self) -> int:
        """
        Return the current controller state.

        :returns: One of STATE_STOPPED, STATE_ACTIVE, STATE_WARNING,
                  STATE_PASSIVE, or STATE_BUS_OFF

        Example
        -------
        ```python
            >>> if can.state() == CAN.STATE_ACTIVE:
            ...     print("CAN bus OK")
        ```
        """
        ...

    def set_filters(self, filters: Any) -> None:
        """
        Set receive filters.

        :param filters: ``None`` to accept all; empty list to reject all;
                        or an iterable of ``(identifier, bit_mask, flags)``
                        tuples.

        Example
        -------
        ```python
            >>> can.set_filters(None)    # receive all
            >>> 
            >>> # Only receive standard IDs 0x301 and 0x700
            >>> can.set_filters(((0x301, 0x7FF, 0),
            ...                   (0x700, 0x7FF, 0)))
        ```
        """
        ...

    def send(self, id: int, data: bytes, flags: int = 0) -> Optional[int]:
        """
        Queue a CAN message for transmission.

        :param id: CAN identifier (integer)
        :param data: Message data bytes (up to 8 bytes for classic CAN)
        :param flags: OR of FLAG_* constants

        :returns: Transmit buffer index if queued, or None if queue is full

        Example
        -------
        ```python
            >>> idx = can.send(0x123, b'\\x01\\x02\\x03')
            >>> if idx is None:
            ...     print("TX queue full")
        ```
        """
        ...

    def recv(self, arg: Optional[list] = None) -> Optional[list]:
        """
        Return a received CAN message, or None if none available.

        Returns a list of ``[id, data_memoryview, flags, errors]``.
        If ``arg`` is provided, it must be a list of at least 4 elements
        (with a memoryview at index 1) to avoid allocation.

        Note: ``set_filters()`` must be called before receiving.

        :param arg: Optional pre-allocated result list

        :returns: ``[id, data, flags, errors]`` or None

        Example
        -------
        ```python
            >>> can.set_filters(None)
            >>> msg = can.recv()
            >>> if msg:
            ...     can_id, data, flags, errs = msg
            ...     print(hex(can_id), bytes(data).hex())
        ```
        """
        ...

    def cancel_send(self, index: int) -> bool:
        """
        Cancel a pending transmit at the given buffer index.

        :param index: Transmit buffer index from send()

        :returns: True if a pending message was cancelled; False otherwise

        Example
        -------
        ```python
            >>> idx = can.send(0x100, b'\\x00')
            >>> if idx is not None:
            ...     can.cancel_send(idx)
        ```
        """
        ...

    def irq(self, handler: Optional[Callable] = None,
            trigger: int = 0, hard: bool = False) -> Any:
        """
        Configure a CAN interrupt handler.

        :param handler: Callable receiving the CAN instance as argument
        :param trigger: OR of IRQ_RX, IRQ_TX, IRQ_STATE
        :param hard: If True, use hard interrupt

        :returns: IRQ object

        Example
        -------
        ```python
            >>> def can_callback(can):
            ...     msg = can.recv()
            ...     if msg:
            ...         print("Received:", hex(msg[0]))
            >>> 
            >>> can.irq(handler=can_callback, trigger=CAN.IRQ_RX)
        ```
        """
        ...

    def get_counters(self, list: Optional[list] = None) -> list:
        """
        Return error and statistics counters.

        Returns a list of 8 values: TEC, REC, warning-entries,
        passive-entries, bus-off-entries, pending TX, pending RX, RX overruns.
        Pass an existing list to avoid allocation.

        :param list: Optional pre-allocated result list

        :returns: List of 8 counter values (None for unsupported counters)

        Example
        -------
        ```python
            >>> counters = can.get_counters()
            >>> tec, rec = counters[0], counters[1]
            >>> print(f"TEC={tec} REC={rec}")
        ```
        """
        ...

    def get_timings(self, list: Optional[list] = None) -> list:
        """
        Return the current CAN bus timing configuration.

        Returns a list of 6 values: exact bitrate, SJW, tseg1, tseg2,
        FD timings (or None), and controller-specific timings (or None).

        :param list: Optional pre-allocated result list

        :returns: List of timing values

        Example
        -------
        ```python
            >>> timings = can.get_timings()
            >>> print(f"Bitrate: {timings[0]}, tseg1: {timings[2]}, tseg2: {timings[3]}")
        ```
        """
        ...


class Counter:
    """
    Hardware pulse/event counter.

    Counts input pulses on a GPIO pin using dedicated hardware counter
    peripheral (e.g. PCNT on ESP32, QTIMER/XBAR on MIMXRT).

    New in MicroPython v1.28.0.

    Example
    -------
    ```python
        >>> from machine import Counter, Pin
        >>> 
        >>> cnt = Counter(0, src=Pin(5), edge=Counter.RISING)
        >>> 
        >>> # Count pulses for 1 second
        >>> import time
        >>> time.sleep(1)
        >>> print("Pulses:", cnt.value())
        >>> 
        >>> # Reset and count again
        >>> cnt.value(0)
        >>> cnt.deinit()
    ```
    """

    RISING: int
    """Count on rising edge."""

    FALLING: int
    """Count on falling edge."""

    UP: int
    """Count upward."""

    DOWN: int
    """Count downward."""

    IRQ_RESET: int
    """IRQ trigger: reset input transition. (MIMXRT)"""

    IRQ_INDEX: int
    """IRQ trigger: index input transition. (MIMXRT)"""

    IRQ_MATCH: int
    """IRQ trigger: counter value matches match value. (MIMXRT)"""

    IRQ_ROLL_OVER: int
    """IRQ trigger: counter rolled over from maximum to minimum. (MIMXRT)"""

    IRQ_ROLL_UNDER: int
    """IRQ trigger: counter rolled under from minimum to maximum. (MIMXRT)"""

    def __init__(self, id: int, *args: Any, **kwargs: Any) -> None:
        """
        Return the singleton Counter object for the given peripheral ID.

        Additional arguments are passed to ``init()``.

        :param id: Counter peripheral ID (hardware-specific)

        Example
        -------
        ```python
            >>> from machine import Counter, Pin
            >>> 
            >>> cnt = Counter(0, src=Pin(5), edge=Counter.RISING)
        ```
        """
        ...

    def init(self, src: "Pin", *args: Any, **kwargs: Any) -> None:
        """
        Initialise and reset the Counter.

        :param src: Input pin (Pin object)
        :param edge: Count edge: Counter.RISING (default) or Counter.FALLING
        :param direction: Count direction: Counter.UP (default) or Counter.DOWN
        :param filter_ns: Minimum stable signal duration in ns (default 0)
        :param max: Upper counting range (default is hardware maximum)
        :param min: Lower counting range (default 0)

        Example
        -------
        ```python
            >>> cnt.init(src=Pin(5), edge=Counter.RISING,
            ...          direction=Counter.UP)
        ```
        """
        ...

    def value(self, value: Optional[int] = None) -> int:
        """
        Get or set the counter value.

        :param value: If provided, reset counter to this value

        :returns: Current counter value as signed integer

        Example
        -------
        ```python
            >>> cnt.value(0)               # Reset
            >>> import time; time.sleep(1)
            >>> pulses = cnt.value()        # Read count
        ```
        """
        ...

    def cycles(self, value: Optional[int] = None) -> int:
        """
        Get or set the overflow/underflow cycle counter.

        :param value: If provided, set cycles counter to this value

        :returns: Previous cycles counter value

        Availability: MIMXRT only.

        Example
        -------
        ```python
            >>> cycles = cnt.cycles()
            >>> print("Overflow count:", cycles)
        ```
        """
        ...

    def irq(self, handler: Optional[Callable] = None,
            trigger: int = 0, hard: bool = False) -> Any:
        """
        Configure an interrupt handler for counter events.

        :param handler: Callable receiving Counter instance as argument
        :param trigger: OR of IRQ_RESET, IRQ_INDEX, IRQ_MATCH,
                        IRQ_ROLL_OVER, IRQ_ROLL_UNDER
        :param hard: If True, use hard interrupt

        Availability: MIMXRT only.

        Example
        -------
        ```python
            >>> def on_rollover(counter):
            ...     print("Counter rolled over!")
            >>> 
            >>> cnt.irq(handler=on_rollover,
            ...         trigger=Counter.IRQ_ROLL_OVER)
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Stop the counter and release hardware resources.

        Example
        -------
        ```python
            >>> cnt.deinit()
        ```
        """
        ...


class Encoder:
    """
    Quadrature encoder interface.

    Decodes two-phase quadrature signals (phase A and phase B) from rotary
    encoders or linear encoders using dedicated hardware peripherals.

    New in MicroPython v1.28.0.

    Example
    -------
    ```python
        >>> from machine import Encoder, Pin
        >>> 
        >>> enc = Encoder(0, phase_a=Pin(5), phase_b=Pin(6),
        ...               phases=4)  # 4x quadrature decoding
        >>> 
        >>> # Read position
        >>> print("Position:", enc.value())
        >>> enc.value(0)  # Reset to zero
        >>> enc.deinit()
    ```
    """

    IRQ_RESET: int
    """IRQ trigger: reset input transition. (MIMXRT)"""

    IRQ_INDEX: int
    """IRQ trigger: index input transition. (MIMXRT)"""

    IRQ_MATCH: int
    """IRQ trigger: position matches match value. (MIMXRT)"""

    IRQ_ROLL_OVER: int
    """IRQ trigger: position counter rolled over from maximum to minimum. (MIMXRT)"""

    IRQ_ROLL_UNDER: int
    """IRQ trigger: position counter rolled under from minimum to maximum. (MIMXRT)"""

    def __init__(self, id: int, *args: Any, **kwargs: Any) -> None:
        """
        Return the singleton Encoder object for the given peripheral ID.

        Additional arguments are passed to ``init()``.

        :param id: Encoder peripheral ID (hardware-specific)

        Example
        -------
        ```python
            >>> from machine import Encoder, Pin
            >>> 
            >>> enc = Encoder(0, phase_a=Pin(5), phase_b=Pin(6))
        ```
        """
        ...

    def init(self, phase_a: "Pin", phase_b: "Pin",
             *args: Any, **kwargs: Any) -> None:
        """
        Initialise and reset the Encoder.

        :param phase_a: Phase A input pin
        :param phase_b: Phase B input pin
        :param filter_ns: Minimum stable signal duration in ns (default 0)
        :param phases: Number of edges to count per pulse (1, 2, or 4; default 1)
        :param max: Upper position range
        :param min: Lower position range (default 0)
        :param index: Optional index pin (resets counter on rising edge)
        :param reset: Optional reset pin

        Example
        -------
        ```python
            >>> enc.init(phase_a=Pin(5), phase_b=Pin(6),
            ...          phases=4, min=-32768, max=32767)
        ```
        """
        ...

    def value(self, value: Optional[int] = None) -> int:
        """
        Get or set the encoder position value.

        :param value: If provided, set position to this value

        :returns: Current position as signed integer

        Example
        -------
        ```python
            >>> enc.value(0)        # Reset position
            >>> pos = enc.value()   # Read current position
        ```
        """
        ...

    def cycles(self, value: Optional[int] = None) -> int:
        """
        Get or set the overflow/underflow cycle counter.

        :param value: If provided, set cycles counter to this value

        :returns: Previous cycles counter value

        Availability: MIMXRT only.

        Example
        -------
        ```python
            >>> cycles = enc.cycles()
            >>> print("Full rotations:", cycles)
        ```
        """
        ...

    def irq(self, handler: Optional[Callable] = None,
            trigger: int = 0, hard: bool = False) -> Any:
        """
        Configure an interrupt handler for encoder events.

        :param handler: Callable receiving Encoder instance as argument
        :param trigger: OR of IRQ constants
        :param hard: If True, use hard interrupt

        Availability: MIMXRT only.

        Example
        -------
        ```python
            >>> def on_index(enc):
            ...     enc.value(0)  # Reset on index pulse
            >>> 
            >>> enc.irq(handler=on_index, trigger=Encoder.IRQ_INDEX)
        ```
        """
        ...

    def deinit(self) -> None:
        """
        Stop the encoder and release hardware resources.

        Example
        -------
        ```python
            >>> enc.deinit()
        ```
        """
        ...
