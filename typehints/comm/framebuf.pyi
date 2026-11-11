"""framebuf - framebuffer drawing primitives.

Provides an in-memory framebuffer and drawing operations (lines, rectangles,
text, blitting) suitable for driving displays.

Notes
-----
- The `buffer` memory layout depends on the `format` constant and sometimes
    on the display driver you use.
- `stride` defaults to `width` for many formats, but some drivers require a
    custom stride or alignment.
- Color interpretation depends on format: monochrome formats typically use 0/1,
    while RGB565 uses 16-bit packed values (see `rgb565`).

Example
-------
```python
    >>> import framebuf
    >>> 
    >>> # Create 128x64 monochrome buffer
    >>> buf = bytearray(128 * 64 // 8)
    >>> fb = framebuf.FrameBuffer(buf, 128, 64, framebuf.MONO_HLSB)
    >>> 
    >>> fb.fill(0)
    >>> fb.text('Hello', 0, 0, 1)
```
"""

from typing import Optional, Union


# Format constants
MONO_VLSB: int
"""Monochrome, vertical LSB (1 bit per pixel, columns)."""

MONO_HLSB: int
"""Monochrome, horizontal LSB (1 bit per pixel, rows)."""

MONO_HMSB: int
"""Monochrome, horizontal MSB (1 bit per pixel, rows)."""

RGB565: int
"""RGB 5-6-5 format (16 bits per pixel)."""

GS2_HMSB: int
"""2-bit grayscale (4 levels)."""

GS4_HMSB: int
"""4-bit grayscale (16 levels)."""

GS8: int
"""8-bit grayscale (256 levels)."""


class FrameBuffer:
    """
    In-memory frame buffer for display operations.

    Example
    -------
    ```python
        >>> import framebuf
        >>> 
        >>> # 128x64 OLED buffer
        >>> buf = bytearray(128 * 64 // 8)
        >>> fb = framebuf.FrameBuffer(buf, 128, 64, framebuf.MONO_VLSB)
        >>> 
        >>> # Draw
        >>> fb.fill(0)
        >>> fb.rect(10, 10, 50, 30, 1)
        >>> fb.text('Hi', 20, 20, 1)
    ```
    """

    def __init__(
        self,
        buffer: Union[bytearray, memoryview],
        width: int,
        height: int,
        format: int,
        stride: int = ...
    ) -> None:
        """Create a framebuffer view over an existing buffer.

        The buffer must be large enough for the requested width/height/format.
        If `buffer` is a `memoryview`, changes affect the underlying object.

        :param buffer: Underlying buffer
        :param width: Width in pixels
        :param height: Height in pixels
        :param format: Pixel format (MONO_VLSB, RGB565, etc.)
        :param stride: Line stride (default: width)

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> # Monochrome 128x64
            >>> buf = bytearray(128 * 64 // 8)
            >>> fb = framebuf.FrameBuffer(buf, 128, 64, framebuf.MONO_VLSB)
            >>> 
            >>> # RGB565 240x240
            >>> buf = bytearray(240 * 240 * 2)
            >>> fb = framebuf.FrameBuffer(buf, 240, 240, framebuf.RGB565)
        ```
        """
        ...

    def fill(self, c: int) -> None:
        """
        Fill entire buffer with color.

        :param c: Color value

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.fill(0)  # Clear to black
            >>> fb.fill(1)  # Fill white (mono)
            >>> fb.fill(0xFFFF)  # White (RGB565)
        ```
        """
        ...

    def pixel(self, x: int, y: int, c: int = None) -> Optional[int]:
        """
        Get or set pixel.

        :param x: X coordinate
        :param y: Y coordinate
        :param c: Color (None to read)

        :returns: Pixel color if reading

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.pixel(10, 20, 1)  # Set pixel
            >>> color = fb.pixel(10, 20)  # Read pixel
        ```
        """
        ...

    def hline(self, x: int, y: int, w: int, c: int) -> None:
        """
        Draw horizontal line.

        :param x: Start X
        :param y: Y coordinate
        :param w: Width
        :param c: Color

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.hline(0, 32, 128, 1)  # Full width line
        ```
        """
        ...

    def vline(self, x: int, y: int, h: int, c: int) -> None:
        """
        Draw vertical line.

        :param x: X coordinate
        :param y: Start Y
        :param h: Height
        :param c: Color

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.vline(64, 0, 64, 1)  # Full height line
        ```
        """
        ...

    def line(self, x1: int, y1: int, x2: int, y2: int, c: int) -> None:
        """
        Draw line between points.

        :param x1: Start X
        :param y1: Start Y
        :param x2: End X
        :param y2: End Y
        :param c: Color

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.line(0, 0, 127, 63, 1)  # Diagonal
        ```
        """
        ...

    def rect(self, x: int, y: int, w: int, h: int, c: int, f: bool = False) -> None:
        """
        Draw rectangle.

        :param x: Top-left X
        :param y: Top-left Y
        :param w: Width
        :param h: Height
        :param c: Color
        :param f: Fill rectangle

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.rect(10, 10, 50, 30, 1)       # Outline
            >>> fb.rect(10, 10, 50, 30, 1, True) # Filled
        ```
        """
        ...

    def fill_rect(self, x: int, y: int, w: int, h: int, c: int) -> None:
        """
        Draw filled rectangle.

        :param x: Top-left X
        :param y: Top-left Y
        :param w: Width
        :param h: Height
        :param c: Color

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.fill_rect(10, 10, 50, 30, 1)
        ```
        """
        ...

    def ellipse(self, x: int, y: int, xr: int, yr: int, c: int, f: bool = False, m: int = 0xf) -> None:
        """
        Draw ellipse.

        :param x: Center X
        :param y: Center Y
        :param xr: X radius
        :param yr: Y radius
        :param c: Color
        :param f: Fill ellipse
        :param m: Quadrant mask

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.ellipse(64, 32, 30, 20, 1)        # Outline
            >>> fb.ellipse(64, 32, 30, 20, 1, True)  # Filled
        ```
        """
        ...

    def poly(self, x: int, y: int, coords: list, c: int, f: bool = False) -> None:
        """
        Draw polygon.

        :param x: Origin X offset
        :param y: Origin Y offset
        :param coords: List/tuple of coordinate pairs
        :param c: Color
        :param f: Fill polygon

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> # Triangle
            >>> coords = [0, 0, 20, 0, 10, 20]
            >>> fb.poly(50, 20, coords, 1)
        ```
        """
        ...

    def text(self, s: str, x: int, y: int, c: int = 1) -> None:
        """
        Draw text string (8x8 font).

        :param s: Text string
        :param x: X position
        :param y: Y position
        :param c: Color

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.text('Hello', 0, 0, 1)
            >>> fb.text('World', 0, 10, 1)
        ```
        """
        ...

    def scroll(self, xstep: int, ystep: int) -> None:
        """
        Scroll buffer content.

        :param xstep: X scroll amount
        :param ystep: Y scroll amount

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> fb.scroll(0, -8)  # Scroll up 8 pixels
        ```
        """
        ...

    def blit(self, fbuf: 'FrameBuffer', x: int, y: int, key: int = -1, palette: 'FrameBuffer' = None) -> None:
        """
        Copy from another frame buffer.

        :param fbuf: Source frame buffer
        :param x: Destination X
        :param y: Destination Y
        :param key: Transparent color (-1 = none)
        :param palette: Color palette for format conversion

        Example
        -------
        ```python
            >>> import framebuf
            >>> 
            >>> # Copy sprite
            >>> fb.blit(sprite_fb, 50, 20)
            >>> 
            >>> # With transparency
            >>> fb.blit(sprite_fb, 50, 20, key=0)
        ```
        """
        ...


def rgb565(r: int, g: int, b: int) -> int:
    """
    Convert RGB to RGB565 format.

    :param r: Red (0-255)
    :param g: Green (0-255)
    :param b: Blue (0-255)

    :returns: RGB565 color value

    Example
    -------
    ```python
        >>> import framebuf
        >>> 
        >>> red = framebuf.rgb565(255, 0, 0)
        >>> green = framebuf.rgb565(0, 255, 0)
        >>> blue = framebuf.rgb565(0, 0, 255)
    ```
    """
    ...
