import re
from typing import Optional

import typer

from ..app import app
from ..connection import _create_agent_client, _ensure_connected
from ..helpers import OutputHelper
from ._common import exec_code as _exec, parse_gp_pin, parse_json_strict
from ._common import require_standard_hardware

_POSITION_RE = re.compile(r'^\[([^,]+),([^,]+)\]$')


def _parse_axis(token: str, limit: int, name: str) -> list[int]:
    token = token.strip()
    if ':' not in token:
        if not token.isdigit():
            raise ValueError(f"Invalid {name} coordinate: {token!r}")
        value = int(token)
        if not 0 <= value < limit:
            raise ValueError(f"{name} coordinate {value} is outside 0..{limit - 1}")
        return [value]
    parts = token.split(':')
    if len(parts) not in (2, 3) or any(part and not part.isdigit() for part in parts):
        raise ValueError(f"Invalid {name} slice: {token!r}")
    start = int(parts[0]) if parts[0] else 0
    stop = int(parts[1]) if parts[1] else limit
    step = int(parts[2]) if len(parts) == 3 and parts[2] else 1
    if step <= 0:
        raise ValueError(f"{name} slice step must be > 0")
    if not 0 <= start <= limit or not 0 <= stop <= limit:
        raise ValueError(f"{name} slice bounds must be within 0..{limit}")
    values = list(range(start, stop, step))
    if not values:
        raise ValueError(f"{name} slice selects no pixels")
    return values


def _parse_position(token: str, width: int, height: int) -> list[tuple[int, int]]:
    match = _POSITION_RE.fullmatch((token or '').replace(' ', ''))
    if not match:
        raise ValueError("Position must be [x,y], e.g. [0,0] or [1:7,3:10]")
    xs = _parse_axis(match.group(1), width, 'x')
    ys = _parse_axis(match.group(2), height, 'y')
    return [(x, y) for y in ys for x in xs]


def _parse_color(tokens: list[str]) -> tuple[int, int, int]:
    if len(tokens) == 1:
        token = tokens[0].lower()
        if not re.fullmatch(r'0x[0-9a-f]{6}', token):
            raise ValueError("Color must be decimal R G B or 0xRRGGBB")
        return tuple(int(token[index:index + 2], 16) for index in (2, 4, 6))
    if len(tokens) == 3:
        try:
            color = tuple(int(token, 10) for token in tokens)
        except ValueError:
            raise ValueError("Decimal RGB channels must be integers")
        if any(channel < 0 or channel > 255 for channel in color):
            raise ValueError("RGB channels must be in range 0..255")
        return color
    raise ValueError("Color must be decimal R G B or 0xRRGGBB")


def _physical_indices(points: list[tuple[int, int]], width: int, layout: str) -> list[int]:
    if layout not in ('row-major', 'serpentine'):
        raise ValueError("--layout must be row-major or serpentine")
    result = []
    for x, y in points:
        physical_x = width - 1 - x if layout == 'serpentine' and y % 2 else x
        result.append(y * width + physical_x)
    return result


def _make_write_code(pin: int, width: int, height: int, indices: list[int],
                     color: tuple[int, int, int], state_machine: int) -> str:
    count = width * height
    pio_write = (
        "    try:\n"
        f"     sm=rp2.StateMachine({state_machine},_ws2812,freq=8000000,sideset_base=Pin(pin_no))\n"
        "     sm.active(1)\n"
        "     for offset in range(0,len(frame),3): sm.put((frame[offset]<<16)|(frame[offset+1]<<8)|frame[offset+2],8)\n"
        "     time.sleep_ms(max(1,count//30+1))\n"
        "     return 'rp2-pio'\n"
        "    finally:\n"
        "     if sm is not None: sm.active(0)\n"
        "     try: pio.remove_program(_ws2812)\n"
        "     except Exception: pass"
    )
    return f'''import gc,json,sys,time
from machine import Pin
pin_no={pin}
count={count}
indices={indices!r}
color={color!r}

def _cleanup_legacy_rp2():
 state=globals().get('__replx_ws2812_state__')
 if state is not None:
    state.clear()
    del globals()['__replx_ws2812_state__']
 if sys.platform!='rp2': return
 try:
    import rp2
    old_program=globals().get('_ws2812')
    if old_program is None: return
    old_sm=globals().get('sm')
    if old_sm is not None: old_sm.active(0)
    rp2.PIO({state_machine}//4).remove_program(old_program)
 except Exception:
    pass
 for name in ('sm','_ws2812','frame','strip','data'):
    if name in globals(): del globals()[name]

def _make_frame():
 frame=bytearray(count*3)
 r,g,b=color
 for index in indices:
    offset=index*3
    frame[offset]=g
    frame[offset+1]=r
    frame[offset+2]=b
 return frame

def _write_once():
 try:
    import neopixel
    strip=neopixel.NeoPixel(Pin(pin_no),count)
    for index in indices: strip[index]=color
    strip.write()
    return 'neopixel'
 except ImportError:
    pass
 frame=_make_frame()
 if sys.platform=='rp2':
    import rp2
    @rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW,out_shiftdir=rp2.PIO.SHIFT_LEFT,autopull=True,pull_thresh=24)
    def _ws2812():
     T1=2
     T2=5
     T3=3
     label('bitloop')
     out(x,1).side(0)[T3-1]
     jmp(not_x,'do_zero').side(1)[T1-1]
     jmp('bitloop').side(1)[T2-1]
     label('do_zero')
     nop().side(0)[T2-1]
    sm=None
    pio=rp2.PIO({state_machine}//4)
{pio_write}
 try:
    from machine import bitstream
 except ImportError:
    bitstream=None
 if bitstream is None: raise RuntimeError('No neopixel, RP2 PIO, or machine.bitstream backend')
 bitstream(Pin(pin_no,Pin.OUT),0,(400,850,800,450),frame)
 return 'bitstream'

_cleanup_legacy_rp2()
gc.collect()
try:
 backend=_write_once()
 print(json.dumps({{'backend':backend,'pixels':{len(indices)},'count':count}}))
finally:
 for name in ('pin_no','count','indices','color','backend','_cleanup_legacy_rp2','_make_frame','_write_once'):
    if name in globals(): del globals()[name]
 gc.collect()
'''


def _print_help() -> None:
    OutputHelper.print_panel("""Write one pixel or a region on a WS2812 (NeoPixel) LED matrix.

[bold cyan]Usage:[/bold cyan]
  replx PORT ws2812 write [yellow]GPn '[POSITION]' COLOR[/yellow] [--width 16] [--height 16]
                          [--layout row-major|serpentine] [--sm N]

POSITION is [x,y]; each axis is one coordinate or a Python-style exclusive slice:
  [0,0]  [1:7,3:10]  [:10:2,4::3]

COLOR is decimal R G B or hexadecimal 0xRRGGBB.

[bold cyan]Options:[/bold cyan]
  --width N            Matrix width in pixels (default: 16)
  --height N           Matrix height in pixels (default: 16, width*height <= 65535)
  --layout MODE        row-major (default) or serpentine (odd rows reversed)
  --sm N               RP2 PIO state machine 0..7 when neopixel is unavailable (default: 0)

[bold cyan]Examples:[/bold cyan]
  replx COM3 ws2812 write GP0 '[0,0]' 255 0 0
  replx COM3 ws2812 write GP0 '[1:7,3:10]' 0x00FF00
  replx COM3 ws2812 write GP0 '[:10:2,4::3]' 0x0000FF --layout serpentine
  replx COM3 ws2812 write GP0 '[0:8,0]' 0xFF8000 --width 8 --height 1

[dim]Each write sends a fresh frame; unselected pixels are off. Quote POSITION in PowerShell.
Backend order: neopixel module, RP2 PIO, machine.bitstream.
Do not power a large LED matrix from a GPIO pin.[/dim]""",
                             title='ws2812', border_style='help')


@app.command(name='ws2812', rich_help_panel='Hardware')
def ws2812_cmd(
    args: Optional[list[str]] = typer.Argument(None),
    width: int = typer.Option(16, '--width'),
    height: int = typer.Option(16, '--height'),
    layout: str = typer.Option('row-major', '--layout'),
    state_machine: int = typer.Option(0, '--sm'),
    show_help: bool = typer.Option(False, '--help', '-h', is_eager=True, hidden=True),
):
    if show_help:
        _print_help()
        raise typer.Exit()
    try:
        if not args or args[0].lower() != 'write' or len(args) < 4:
            raise ValueError("Usage: replx PORT ws2812 write GPn '[POSITION]' COLOR")
        if width < 1 or height < 1 or width * height > 65535:
            raise ValueError("--width and --height must be positive and contain at most 65535 pixels")
        if not 0 <= state_machine <= 7:
            raise ValueError("--sm must be in range 0..7")
        pin = parse_gp_pin(args[1], 'WS2812 data pin')
        points = _parse_position(args[2], width, height)
        color = _parse_color(args[3:])
        indices = _physical_indices(points, width, layout)
        _ensure_connected()
        with _create_agent_client() as client:
            require_standard_hardware(client, 'ws2812')
            result = parse_json_strict(_exec(client, _make_write_code(
                pin, width, height, indices, color, state_machine), timeout=15))
        OutputHelper.print_panel(
            f"GP{pin}  {width}x{height}  {layout}\nChanged: {result['pixels']}  Color: {color}\nBackend: {result['backend']}",
            title='WS2812 Write', border_style='success')
    except typer.Exit:
        raise
    except (ValueError, RuntimeError) as exc:
        OutputHelper.print_panel(str(exc), title='WS2812 Error', border_style='error')
        raise typer.Exit(1)
