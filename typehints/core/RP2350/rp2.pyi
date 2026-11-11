"""
RP2040/RP2350 specific functions.

PIO, DMA, and other RP2-specific features.

Example
-------
```python
    >>> import rp2
    >>> from machine import Pin
    >>> 
    >>> # PIO program for blinking LED
    >>> @rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
    >>> def blink():
    ...     wrap_target()
    ...     set(pins, 1)   [31]
    ...     nop()          [31]
    ...     set(pins, 0)   [31]
    ...     nop()          [31]
    ...     wrap()
    >>> 
    >>> sm = rp2.StateMachine(0, blink, freq=2000, set_base=Pin(25))
    >>> sm.active(1)
```
"""

from typing import Any, Callable, Dict, Optional, Union
from machine import Pin


class PIOASMError(Exception):
    """
    Exception raised from asm_pio() or asm_pio_encode() 
    if there is an error assembling a PIO program.
    """
    ...


def asm_pio(
    *,
    out_init: int = None,
    set_init: int = None,
    sideset_init: int = None,
    side_pindir: bool = False,
    in_shiftdir: int = 0,
    out_shiftdir: int = 0,
    push_thresh: int = 32,
    pull_thresh: int = 32,
    autopush: bool = False,
    autopull: bool = False,
    fifo_join: int = 0
) -> Callable:
    """
    Decorator for PIO assembly programs.

    Assembles a PIO program defined using Python syntax and returns a decorator
    that attaches the assembled program to the function.

    The pin init parameters (``out_init``, ``set_init``, ``sideset_init``) accept
    either a single ``PIO.IN_*``/``PIO.OUT_*`` value or a tuple of such values when
    more than one pin is used.

    Some parameters (e.g. shift directions, thresholds, autopush/pull, fifo_join)
    act as defaults and can be overridden in ``StateMachine.init()``.

    :param out_init: Initial OUT pin state
    :param set_init: Initial SET pin state (max 5 pins)
    :param sideset_init: Initial sideset pin state (max 5 pins)
    :param side_pindir: If True, .side() controls pin direction
    :param in_shiftdir: Input shift direction (``PIO.SHIFT_LEFT`` or ``PIO.SHIFT_RIGHT``)
    :param out_shiftdir: Output shift direction (``PIO.SHIFT_LEFT`` or ``PIO.SHIFT_RIGHT``)
    :param push_thresh: Bits before auto-push
    :param pull_thresh: Bits before auto-pull
    :param autopush: Enable auto-push
    :param autopull: Enable auto-pull
    :param fifo_join: FIFO join mode (JOIN_NONE, JOIN_TX, JOIN_RX)

    :returns: Decorated program

    Example
    -------
    ```python
        >>> import rp2
        >>> 
        >>> @rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
        >>> def blink():
        ...     wrap_target()
        ...     set(pins, 1)
        ...     set(pins, 0)
        ...     wrap()
    ```
    """
    ...


def asm_pio_encode(instr: str, sideset_count: int, sideset_opt: bool = False) -> int:
    """
    Assemble a single PIO instruction.

    Usually you want to use asm_pio() instead.

    :param instr: PIO instruction string
    :param sideset_count: Number of sideset pins
    :param sideset_opt: Whether sideset is optional

    :returns: 16-bit encoded instruction word

    :raises PIOASMError: If there is an error assembling

    Example
    -------
    ```python
        >>> import rp2
        >>> 
        >>> rp2.asm_pio_encode("set(0, 1)", 0)
        57345
    ```
    """
    ...


class PIO:
    """
    Programmable I/O block.

    Each RP2 has 2 PIO blocks with 4 state machines each.

    Example
    -------
    ```python
        >>> import rp2
        >>> 
        >>> pio0 = rp2.PIO(0)
        >>> pio0.irq(lambda pio: print("IRQ"))
    ```
    """

    # Pin direction constants
    IN_LOW: int
    """Input, pull low."""
    
    IN_HIGH: int
    """Input, pull high."""
    
    OUT_LOW: int
    """Output, initially low."""
    
    OUT_HIGH: int
    """Output, initially high."""

    # Shift direction
    SHIFT_LEFT: int
    """Shift left."""
    
    SHIFT_RIGHT: int
    """Shift right."""

    # FIFO join modes
    JOIN_NONE: int
    """No FIFO join."""
    
    JOIN_TX: int
    """Join both FIFOs for TX."""
    
    JOIN_RX: int
    """Join both FIFOs for RX."""

    # IRQ flags
    IRQ_SM0: int
    """State machine 0 IRQ."""
    
    IRQ_SM1: int
    """State machine 1 IRQ."""
    
    IRQ_SM2: int
    """State machine 2 IRQ."""
    
    IRQ_SM3: int
    """State machine 3 IRQ."""

    def __init__(self, id: int) -> None:
        """
        Create PIO instance.

        :param id: PIO block (0 or 1)

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> pio0 = rp2.PIO(0)
            >>> pio1 = rp2.PIO(1)
        ```
        """
        ...

    def add_program(self, program: Any) -> int:
        """
        Add program to PIO instruction memory.

        :param program: PIO program

        :returns: Program offset

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> offset = pio0.add_program(my_program)
        ```
        """
        ...

    def remove_program(self, program: Any = None) -> None:
        """
        Remove program from instruction memory.

        :param program: Program to remove (None = all)

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> pio0.remove_program(my_program)
        ```
        """
        ...

    def state_machine(self, id: int, *args, **kwargs) -> 'StateMachine':
        """
        Get state machine.

        :param id: State machine ID (0-3)

        :returns: StateMachine instance

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> sm = pio0.state_machine(0)
        ```
        """
        ...

    def irq(self, handler: Callable[['PIO'], None], trigger: int = ..., hard: bool = False) -> None:
        """
        Set PIO IRQ handler.

        :param handler: Callback function
        :param trigger: IRQ trigger mask
        :param hard: Hard IRQ (fast but restricted)

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> def pio_handler(pio):
            ...     print("PIO IRQ")
            >>> 
            >>> pio0.irq(pio_handler, trigger=rp2.PIO.IRQ_SM0)
        ```
        """
        ...


class StateMachine:
    """
    PIO State Machine.

    Example
    -------
    ```python
        >>> import rp2
        >>> from machine import Pin
        >>> 
        >>> sm = rp2.StateMachine(0, my_program, freq=125_000_000, 
        ...                       set_base=Pin(25))
        >>> sm.active(1)
        >>> sm.put(0xFFFF)
    ```
    """

    def __init__(
        self,
        id: int,
        program: Any = None,
        freq: int = -1,
        *,
        in_base: Pin = None,
        out_base: Pin = None,
        set_base: Pin = None,
        jmp_pin: Pin = None,
        sideset_base: Pin = None,
        in_shiftdir: int = None,
        out_shiftdir: int = None,
        push_thresh: int = None,
        pull_thresh: int = None
    ) -> None:
        """
        Create/configure state machine.

        :param id: State machine ID (0-7)
        :param program: PIO program
        :param freq: Clock frequency
        :param in_base: First IN pin
        :param out_base: First OUT pin
        :param set_base: First SET pin
        :param jmp_pin: JMP pin
        :param sideset_base: First sideset pin
        :param in_shiftdir: Input shift direction
        :param out_shiftdir: Output shift direction
        :param push_thresh: Auto-push threshold
        :param pull_thresh: Auto-pull threshold

        Example
        -------
        ```python
            >>> import rp2
            >>> from machine import Pin
            >>> 
            >>> sm = rp2.StateMachine(0, ws2812, freq=8_000_000,
            ...                       sideset_base=Pin(16))
        ```
        """
        ...

    def init(
        self,
        program: Any = None,
        freq: int = -1,
        *,
        in_base: Pin = None,
        out_base: Pin = None,
        set_base: Pin = None,
        jmp_pin: Pin = None,
        sideset_base: Pin = None
    ) -> None:
        """
        Reinitialize state machine.

        Same parameters as __init__.

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> sm.init(new_program, freq=1_000_000)
        ```
        """
        ...

    def active(self, value: int = None) -> Optional[int]:
        """
        Get or set active state.

        :param value: 1=start, 0=stop

        :returns: Current state if querying

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> sm.active(1)  # Start
            >>> sm.active(0)  # Stop
            >>> print(sm.active())  # Query
        ```
        """
        ...

    def restart(self) -> None:
        """
        Restart state machine from beginning.

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> sm.restart()
        ```
        """
        ...

    def exec(self, instr: int) -> None:
        """
        Execute single instruction.

        :param instr: Encoded instruction

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> sm.exec(rp2.asm_pio_encode("set(pins, 1)", 0))
        ```
        """
        ...

    def get(self, buf: bytearray = None, shift: int = 0) -> int:
        """
        Read from RX FIFO.

        Blocks if empty.

        :param buf: Optional buffer for DMA
        :param shift: Right shift amount

        :returns: Value read

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> value = sm.get()
        ```
        """
        ...

    def put(self, value: int, shift: int = 0) -> None:
        """
        Write to TX FIFO.

        Blocks if full.

        :param value: Value to write
        :param shift: Left shift amount

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> sm.put(0xFFFF)
            >>> sm.put(0x12345678, shift=8)
        ```
        """
        ...

    def rx_fifo(self) -> int:
        """
        Get RX FIFO level.

        :returns: Number of words in RX FIFO

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> if sm.rx_fifo() > 0:
            ...     data = sm.get()
        ```
        """
        ...

    def tx_fifo(self) -> int:
        """
        Get TX FIFO level.

        :returns: Number of words in TX FIFO

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> if sm.tx_fifo() < 4:
            ...     sm.put(data)
        ```
        """
        ...

    def irq(self, handler: Callable[['StateMachine'], None] = None, trigger: int = 0, hard: bool = False) -> None:
        """
        Set state machine IRQ handler.

        :param handler: Callback function
        :param trigger: IRQ trigger value
        :param hard: Hard IRQ

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> def sm_handler(sm):
            ...     data = sm.get()
            >>> 
            >>> sm.irq(sm_handler)
        ```
        """
        ...


class DMA:
    """
    DMA channel controller.

    The RP2040 has 12 independent DMA channels.

    Example
    -------
    ```python
        >>> import rp2
        >>> 
        >>> a = bytearray(32*1024)
        >>> b = bytearray(32*1024)
        >>> d = rp2.DMA()
        >>> c = d.pack_ctrl()
        >>> d.config(read=a, write=b, count=len(a)//4, ctrl=c, trigger=True)
        >>> while d.active():
        ...     pass
    ```
    """

    # Attributes
    read: int
    """Address from which next transfer will read. Can be int or buffer object."""
    
    write: int
    """Address to which next transfer will write. Can be int or buffer object."""
    
    count: int
    """Number of remaining bus transfers."""
    
    ctrl: int
    """DMA channel control register value."""
    
    channel: int
    """The channel number of this DMA channel."""
    
    registers: Any
    """Array-like access to DMA channel registers by word index."""

    def __init__(self) -> None:
        """
        Claim one of the DMA controller channels for exclusive use.

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> dma = rp2.DMA()
        ```
        """
        ...

    def config(
        self,
        read: Any = None,
        write: Any = None,
        count: int = None,
        ctrl: int = None,
        trigger: bool = False
    ) -> None:
        """
        Configure DMA transfer.

        :param read: Source address (int or buffer object)
        :param write: Destination address (int or buffer object)
        :param count: Number of transfers (not bytes)
        :param ctrl: Control register value from pack_ctrl()
        :param trigger: Start transfer immediately

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> src = bytearray(1024)
            >>> dst = bytearray(1024)
            >>> ctrl = dma.pack_ctrl()
            >>> dma.config(read=src, write=dst, count=len(src)//4, 
            ...            ctrl=ctrl, trigger=True)
        ```
        """
        ...

    def active(self, value: int = None) -> Optional[int]:
        """
        Get or set active state.

        :param value: 1=start, 0=stop

        :returns: Current state if querying

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> dma.active(1)
            >>> while dma.active():
            ...     pass
        ```
        """
        ...

    def irq(self, handler: Callable[['DMA'], None] = None, hard: bool = False) -> Any:
        """
        Configure and return the IRQ object for this DMA channel.

        :param handler: Callback function
        :param hard: Hard IRQ

        :returns: IRQ object

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> def done(dma):
            ...     print("Transfer complete")
            >>> 
            >>> dma.irq(done)
        ```
        """
        ...

    def close(self) -> None:
        """
        Release the claim on the DMA channel and free interrupt handler.

        The DMA object cannot be used after this.

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> dma.close()
        ```
        """
        ...

    def pack_ctrl(
        self,
        default: int = None,
        *,
        enable: bool = True,
        high_pri: bool = False,
        size: int = 2,
        inc_read: bool = True,
        inc_write: bool = True,
        ring_size: int = 0,
        ring_sel: bool = False,
        chain_to: int = None,
        treq_sel: int = None,
        irq_quiet: bool = True,
        bswap: bool = False,
        sniff_en: bool = False,
        write_err: bool = False,
        read_err: bool = False
    ) -> int:
        """
        Pack values into a DMA control register value.

        The returned integer can be passed to :meth:`config` as the ``ctrl``
        argument. Field meanings correspond to the RP2040/RP2350 DMA controller.

        :param default: Base value (None=default for channel)
        :param enable: Enable the channel (default True)
        :param high_pri: High priority bus traffic (default False)
        :param size: Transfer size: 0=byte, 1=half word, 2=word (default 2)
        :param inc_read: Increment read address (default True)
        :param inc_write: Increment write address (default True)
        :param ring_size: Address wrap bits (0=disabled)
        :param ring_sel: Apply ring to write (True) or read (False)
        :param chain_to: Channel to trigger on completion
        :param treq_sel: Transfer request signal index
        :param irq_quiet: No IRQ on each transfer (default True)
        :param bswap: Byte swap before writing (default False)
        :param sniff_en: Allow sniff hardware access (default False)
        :param write_err: Clear write error flag
        :param read_err: Clear read error flag

        :returns: Packed control register value

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> # Transfer bytes, don't increment write
            >>> ctrl = dma.pack_ctrl(size=0, inc_write=False)
        ```
        """
        ...

    @staticmethod
    def unpack_ctrl(value: int) -> Dict[str, Any]:
        """
        Unpack a control register value into a dictionary.

        :param value: Control register value to unpack

        :returns: Dictionary with all control register fields

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> fields = rp2.DMA.unpack_ctrl(dma.ctrl)
            >>> print(fields['size'], fields['busy'])
        ```
        """
        ...


class Flash:
    """
    Access to built-in SPI flash storage.

    For most cases, use the filesystem via Python's standard file API.
    This is useful for custom filesystem configuration.

    Example
    -------
    ```python
        >>> import rp2
        >>> 
        >>> flash = rp2.Flash()
        >>> buf = bytearray(4096)
        >>> flash.readblocks(0, buf)
    ```
    """

    def __init__(self) -> None:
        """
        Get the singleton object for accessing SPI flash memory.

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> flash = rp2.Flash()
        ```
        """
        ...

    def readblocks(self, block_num: int, buf: bytearray, offset: int = None) -> None:
        """
        Read blocks from flash.

        :param block_num: Starting block number
        :param buf: Buffer to read into
        :param offset: Byte offset within block (extended protocol)

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> buf = bytearray(4096)
            >>> flash.readblocks(0, buf)
        ```
        """
        ...

    def writeblocks(self, block_num: int, buf: bytes, offset: int = None) -> None:
        """
        Write blocks to flash.

        :param block_num: Starting block number
        :param buf: Data to write
        :param offset: Byte offset within block (extended protocol)

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> data = b'\\x00' * 4096
            >>> flash.writeblocks(0, data)
        ```
        """
        ...

    def ioctl(self, cmd: int, arg: int) -> Optional[int]:
        """
        Control flash device.

        Implements the block device protocol defined by ``vfs.AbstractBlockDev``.

        :param cmd: Control command
        :param arg: Command argument

        :returns: Command result

        Example
        -------
        ```python
            >>> import rp2
            >>> 
            >>> # Get block count
            >>> blocks = flash.ioctl(4, 0)
        ```
        """
        ...


def bootsel_button() -> int:
    """
    Read BOOTSEL button state.

    :returns: 1 if pressed, 0 otherwise

    Example
    -------
    ```python
        >>> import rp2
        >>> 
        >>> if rp2.bootsel_button():
        ...     print("BOOTSEL pressed!")
    ```
    """
    ...


def country(code: str = None) -> Optional[str]:
    """
    Get or set WiFi country code (Pico W).

    :param code: 2-letter country code

    :returns: Current code if querying

    Example
    -------
    ```python
        >>> import rp2
        >>> 
        >>> rp2.country('US')
        >>> print(rp2.country())
    ```
    """
    ...
