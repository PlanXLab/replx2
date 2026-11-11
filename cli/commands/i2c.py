import json
import shutil
import signal
import sys
import time
from typing import Optional

import typer

from ..helpers import OutputHelper
from ..connection import _ensure_connected, _create_agent_client, _get_device_port
from ..app import app
from replx.utils.constants import CTRL_C
from ._common import exec_code as _exec, get_core as _get_core, parse_json_strict as _parse_json_strict
from ._common import PinId, parse_hardware_pin
from replx.utils.device_info import normalize_core
from ...terminal import enable_vt_mode, restore_vt_mode

_ADDR_COLORS = [
    'bright_yellow', 'bright_cyan', 'bright_green',
    'bright_magenta', 'bright_red', 'bright_blue',
]

_TEENSY_PIN_TABLE = {
    (18, 19): 0,
    (17, 16): 1,
    (25, 24): 2,
    (38, 37): 3,
}


def _parse_hex(s: str) -> int:
    s = s.strip()
    if s.lower().startswith('0x'):
        return int(s, 16)
    try:
        return int(s, 16)
    except ValueError:
        raise ValueError(f"Invalid hex value: {s!r}")


def _parse_data(tokens: list) -> list:
    data = [_parse_hex(t) for t in tokens]
    if any(value < 0 or value > 255 for value in data):
        raise ValueError("I2C data bytes must be in range 00..FF")
    return data


def _resolve_ch(core: str, sda: PinId, scl: PinId) -> int:
    c = core.upper() if core else ''
    if normalize_core(c) == 'EFR32MG':
        if (sda, scl) != ('P1', 'D1'):
            raise ValueError("XBee3 I2C requires SDA=P1 (DIO11), SCL=D1 (DIO1), bus 1")
        return 1
    if not isinstance(sda, int) or not isinstance(scl, int):
        raise ValueError("This board requires numeric GPIO pins, not Digi pin names")
    if 'RP2350' in c or 'RP2040' in c:
        if sda % 4 == 0:
            ch = 0
        elif sda % 4 == 2:
            ch = 1
        else:
            raise ValueError(
                f"GP{sda} is not a valid I2C SDA pin on {core}.\n"
                f"Valid SDA pins: GP0,GP2,GP4,GP6,GP8,GP10,GP12,GP14,GP16,GP18,GP20,GP22,GP24,GP26,GP28"
            )
        if scl != sda + 1:
            raise ValueError(
                f"SCL must be SDA+1 on {core}. For SDA=GP{sda}, SCL must be GP{sda + 1}."
            )
        return ch
    if 'MIMXRT1062' in c:
        key = (sda, scl)
        if key not in _TEENSY_PIN_TABLE:
            valid = ', '.join(f"SDA=GP{k[0]}/SCL=GP{k[1]}" for k in _TEENSY_PIN_TABLE)
            raise ValueError(
                f"SDA=GP{sda}/SCL=GP{scl} is not a valid I2C pin pair on Teensy 4.1.\n"
                f"Valid pairs: {valid}"
            )
        return _TEENSY_PIN_TABLE[key]
    return 0


def _make_init(ch: int, sda: PinId, scl: PinId, freq: int) -> str:
    if (sda, scl) == ('P1', 'D1'):
        return f"from machine import I2C\ni2c=I2C(1,freq={freq})"
    return (
        f"from machine import I2C,Pin\n"
        f"i2c=I2C({ch},sda=Pin({sda}),scl=Pin({scl}),freq={freq})"
    )


def _make_target_open_code(ch: int, sda: int, scl: int, addr: int, mem_size: int) -> str:
    return (
        "from machine import I2CTarget, Pin\n"
        "import json\n"
        f"_i2c_target_mem = bytearray({mem_size})\n"
        f"_i2c_target = I2CTarget({ch}, addr={addr}, "
        f"sda=Pin({sda}), scl=Pin({scl}), mem=_i2c_target_mem)\n"
        f"print(json.dumps({{'open': True, 'addr': {addr}, 'mem_size': {mem_size}}}))"
    )


def _make_target_mem_read_code(offset: int, nbytes: int) -> str:
    end = offset + nbytes
    return (
        "import json, binascii\n"
        f"_d = bytes(_i2c_target_mem[{offset}:{end}])\n"
        f"print(json.dumps({{'hex': binascii.hexlify(_d).decode(), "
        f"'offset': {offset}, 'len': len(_d)}}))"
    )


def _make_target_mem_write_code(offset: int, data: list) -> str:
    end = offset + len(data)
    return (
        "import json\n"
        f"_i2c_target_mem[{offset}:{end}] = bytes({data!r})\n"
        f"print(json.dumps({{'ok': True, 'offset': {offset}, 'len': {len(data)}}}))"
    )


def _make_target_close_code() -> str:
    return (
        "import json\n"
        "_i2c_target.deinit()\n"
        "del _i2c_target, _i2c_target_mem\n"
        "print(json.dumps({'closed': True}))"
    )


def _calc_timeout(repeat: int, interval_ms: int, op_ms: int = 300) -> float:
    total = 2.0 + repeat * (interval_ms / 1000.0 + op_ms / 1000.0)
    return max(3.0, total)


def _bus_config_line(bus: dict) -> str:
    ch = bus.get('ch', 0)
    sda = bus.get('sda', '?')
    scl = bus.get('scl', '?')
    freq = bus.get('freq', 400000)
    return f"SDA={sda}  SCL={scl}  CH={ch}  {freq // 1000}kHz"


def _format_hex_bytes(data: list) -> str:
    return ' '.join(f"{b:02X}" for b in data)


def _format_int16_be(data: list) -> str:
    pairs = len(data) // 2
    vals = []
    for i in range(pairs):
        hi = data[i * 2]
        lo = data[i * 2 + 1]
        v = (hi << 8) | lo
        if v >= 0x8000:
            v -= 0x10000
        vals.append(str(v))
    return '  '.join(vals) + '  (BE)'


def _render_read_block(data: list, label: str = '') -> list:
    lines = []
    prefix = f"  {label}  " if label else "  "
    lines.append(f"{prefix}[cyan]HEX[/cyan]   {_format_hex_bytes(data)}")
    if len(data) >= 2 and len(data) % 2 == 0:
        lines.append(f"{prefix}[dim]INT16[/dim] {_format_int16_be(data)}")
    return lines


def _display_scan(found: list, sda: int, scl: int, ch: int, freq: int):
    COLS = 16
    ROWS = 8

    addr_color = {}
    for i, a in enumerate(found):
        addr_color[a] = _ADDR_COLORS[i % len(_ADDR_COLORS)]

    lines = []
    lines.append(f"[dim]SDA={sda}  SCL={scl}  CH={ch}  {freq // 1000}kHz[/dim]")
    lines.append("")

    hdr = "       "
    for c in range(COLS):
        hdr += f"{c:02X} "
    lines.append("[dim]" + hdr + "[/dim]")
    lines.append("[dim]  " + "\u2500" * 53 + "[/dim]")

    for r in range(ROWS):
        row_str = f"[dim]  {r * COLS:02X}:[/dim]  "
        for c in range(COLS):
            addr = r * COLS + c
            if addr in addr_color:
                col = addr_color[addr]
                row_str += f"[{col}]{addr:02X}[/{col}] "
            else:
                row_str += "[dim]\u00b7[/dim]  "
        lines.append(row_str)

    lines.append("")

    if found:
        parts = []
        for a in found:
            col = addr_color[a]
            parts.append(f"[{col}]0x{a:02X}[/{col}]")
        lines.append("  Discovery " + str(len(found)) + ": " + "  ".join(parts))
    else:
        lines.append("  [dim yellow]No devices found[/dim yellow]")

    OutputHelper.print_panel(
        "\n".join(lines),
        title="I2C Target Scan",
        border_style="data",
    )


def _display_bus(bus: dict):
    if not bus:
        OutputHelper.print_panel(
            "[dim]No bus config saved.\n"
            "Run: replx PORT i2c scan --sda SDA --scl SCL[/dim]",
            title="I2C Bus",
            border_style="data",
        )
        return
    if bus.get('target'):
        addr = bus.get('addr', 0)
        mem_size = bus.get('mem_size', 128)
        OutputHelper.print_panel(
            f"[bold yellow]Mode: TARGET[/bold yellow]  "
            f"I2C Addr: [bright_yellow]0x{addr:02X}[/bright_yellow]\n"
            f"{_bus_config_line(bus)}\n"
            f"Mem: [bright_cyan]{mem_size}[/bright_cyan] bytes",
            title="I2C Bus (Target)",
            border_style="data",
        )
    else:
        OutputHelper.print_panel(
            _bus_config_line(bus),
            title="I2C Bus",
            border_style="data",
        )


def _display_read(raw_output: str, addr: int, nbytes: int, reg: Optional[int],
                  repeat: int, bus: dict):
    title = f"I2C Read  0x{addr:02X}"
    if repeat > 1:
        title += f"  \u00d7{repeat}"

    reg_str = f"reg 0x{reg:02X}  " if reg is not None else ""
    sub = f"  {reg_str}{nbytes} bytes  [dim]{_bus_config_line(bus)}[/dim]"

    lines_raw = [ln for ln in raw_output.split('\n') if ln.strip()]
    content = [sub, ""]

    for i, line in enumerate(lines_raw):
        try:
            parsed = json.loads(line.strip())
        except Exception:
            content.append(f"  [red]Parse error: {line.strip()}[/red]")
            continue
        if isinstance(parsed, dict) and 'error' in parsed:
            label = f"[{i + 1}/{repeat}]" if repeat > 1 else ""
            content.append(f"  [red]{label} Error: {parsed['error']}[/red]")
        else:
            label = f"[{i + 1}/{repeat}]" if repeat > 1 else ""
            content.extend(_render_read_block(parsed, label))
        if repeat > 1 and i < len(lines_raw) - 1:
            content.append("")

    OutputHelper.print_panel("\n".join(content), title=title, border_style="data")


_I2C_D = '\033[38;2;150;150;150m'
_I2C_C = '\033[38;2;80;200;255m'
_I2C_R = '\033[38;2;255;100;100m'
_I2C_RST = '\033[0m'
_I2C_SEP_W = 72


def _setup_i2c_scroll_screen(header: str) -> None:
    enable_vt_mode()
    _, rows = shutil.get_terminal_size(fallback=(80, 24))
    w = sys.stdout.buffer.write
    w(b'\033[?1049h')
    w(b'\033[2J\033[H\033[?25l')
    w((header + '\n').encode())
    w(('  ' + '\u2500' * _I2C_SEP_W + '\n').encode())
    w(f'\033[3;{rows}r\033[3;1H'.encode())
    sys.stdout.buffer.flush()


def _teardown_i2c_scroll_screen() -> None:
    try:
        w = sys.stdout.buffer.write
        w(b'\033[r\033[?25h')
        w(b'\033[?1049l')
        sys.stdout.buffer.flush()
    finally:
        restore_vt_mode()


def _run_i2c_stream(client, code: str, on_line) -> None:
    stop_requested = False
    pending_input: list = []
    line_buf = bytearray()
    original_sigint = signal.getsignal(signal.SIGINT)

    def sigint_handler(signum, frame):
        nonlocal stop_requested
        stop_requested = True
        pending_input.append(CTRL_C)

    def output_callback(data: bytes, stream_type: str = 'stdout'):
        nonlocal line_buf
        if stream_type == 'stderr':
            return
        line_buf += data
        while b'\n' in line_buf:
            line, _, line_buf = line_buf.partition(b'\n')
            text = line.decode('utf-8', errors='replace').strip()
            if text:
                on_line(text)

    def input_provider() -> bytes:
        if pending_input:
            return pending_input.pop(0)
        return b''

    def stop_check() -> bool:
        return stop_requested

    try:
        signal.signal(signal.SIGINT, sigint_handler)
        client.run_interactive(
            script_content=code,
            echo=False,
            output_callback=output_callback,
            input_provider=input_provider,
            stop_check=stop_check,
            ctrl_c_grace_s=1.5,
        )
    finally:
        signal.signal(signal.SIGINT, original_sigint)


def _display_read_scroll(client, code: str, addr: int, nbytes: int,
                         reg: Optional[int], repeat: int, bus: dict) -> None:
    reg_str = f"reg 0x{reg:02X}  " if reg is not None else ""
    repeat_str = '\u221e' if repeat == 0 else f'\u00d7{repeat}'
    hint = 'Ctrl+C exit' if repeat == 0 else 'Ctrl+C cancel'
    hdr = (
        f'  {_I2C_D}I2C Read{_I2C_RST}  '
        f'{_I2C_C}0x{addr:02X}{_I2C_RST}  '
        f'{reg_str}{nbytes} bytes  '
        f'{repeat_str}  '
        f'{_I2C_D}{_bus_config_line(bus)}  [{hint}]{_I2C_RST}'
    )
    _setup_i2c_scroll_screen(hdr)

    start_t = time.monotonic()
    counter = [0]

    def on_line(json_str: str) -> None:
        try:
            parsed = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return
        counter[0] += 1
        s = int(time.monotonic() - start_t)
        ts = f'{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}'
        n = counter[0]
        if isinstance(parsed, dict) and 'error' in parsed:
            line = (
                f'  {_I2C_D}{ts}{_I2C_RST}  '
                f'{_I2C_D}#{n}{_I2C_RST}  '
                f'{_I2C_R}Error: {parsed["error"]}{_I2C_RST}'
            )
        else:
            hex_str = ' '.join(f'{b:02X}' for b in parsed)
            line = (
                f'  {_I2C_D}{ts}{_I2C_RST}  '
                f'{_I2C_D}#{n}{_I2C_RST}  '
                f'{_I2C_C}[{hex_str}]{_I2C_RST}'
            )
        sys.stdout.write(line + '\n')
        sys.stdout.flush()

    try:
        _run_i2c_stream(client, code, on_line)
    except KeyboardInterrupt:
        pass
    finally:
        _teardown_i2c_scroll_screen()

    total = counter[0]
    done_msg = f'Stopped: {total} reads' if repeat == 0 else f'Done: {total}/{repeat} reads'
    sys.stdout.write(f'  {_I2C_D}{done_msg}{_I2C_RST}\n')
    sys.stdout.flush()


def _display_write(raw_output: str, addr: int, data: list, repeat: int, bus: dict):
    title = f"I2C Write  0x{addr:02X}"
    if repeat > 1:
        title += f"  \u00d7{repeat}"

    data_str = _format_hex_bytes(data)
    sub = f"  [{data_str}]  {len(data)} bytes  [dim]{_bus_config_line(bus)}[/dim]"

    lines_raw = [ln for ln in raw_output.split('\n') if ln.strip()]
    content = [sub, ""]

    for i, line in enumerate(lines_raw):
        try:
            parsed = json.loads(line.strip())
        except Exception:
            content.append(f"  [red]Parse error: {line.strip()}[/red]")
            continue
        label = f"[{i + 1}/{repeat}]  " if repeat > 1 else ""
        if isinstance(parsed, dict) and parsed.get('ok'):
            content.append(f"  {label}[green]\u2192 ACK {parsed['ack']} byte(s)[/green]")
        else:
            err = parsed.get('error', 'NACK') if isinstance(parsed, dict) else 'NACK'
            content.append(f"  {label}[red]\u2192 {err}[/red]")

    OutputHelper.print_panel("\n".join(content), title=title, border_style="success")


def _display_dump(raw_output: str, addr: int, from_r: int, to_r: int,
                  repeat: int, bus: dict):
    title = f"I2C Dump  0x{addr:02X}"
    if repeat > 1:
        title += f"  \u00d7{repeat}"

    sub = f"  reg 0x{from_r:02X}\u20130x{to_r:02X}  [dim]{_bus_config_line(bus)}[/dim]"

    lines_raw = [ln for ln in raw_output.split('\n') if ln.strip()]
    content = [sub]

    COLS = 16
    row_start = (from_r // COLS) * COLS
    row_end_base = (to_r // COLS) * COLS

    def render_reg_grid(reg_data: dict, label: str = '') -> list:
        out = []
        if label:
            out.append(f"\n  [dim]{label}[/dim]")
        out.append("")
        hdr = "  [dim]REG  " + " ".join(f"{c:02X}" for c in range(COLS)) + "[/dim]"
        out.append(hdr)
        out.append("  [dim]" + "\u2500" * (5 + COLS * 3) + "[/dim]")
        for row_base in range(row_start, row_end_base + COLS, COLS):
            row_str = f"  [dim]{row_base:02X}:[/dim]  "
            for c in range(COLS):
                reg = row_base + c
                if reg < from_r or reg > to_r:
                    row_str += "   "
                elif reg not in reg_data:
                    row_str += "   "
                elif reg_data[reg] is None:
                    row_str += "[dim]--[/dim] "
                else:
                    row_str += f"{reg_data[reg]:02X} "
            out.append(row_str)
        return out

    for i, line in enumerate(lines_raw):
        try:
            parsed = json.loads(line.strip())
        except Exception:
            content.append(f"\n  [red]Parse error: {line.strip()}[/red]")
            continue
        if isinstance(parsed, dict) and 'error' in parsed and len(parsed) == 1:
            content.append(f"\n  [red]Error: {parsed['error']}[/red]")
            continue
        reg_data = {int(k): v for k, v in parsed.items()}
        label = f"[{i + 1}/{repeat}]" if repeat > 1 else ""
        content.extend(render_reg_grid(reg_data, label))

    OutputHelper.print_panel("\n".join(content), title=title, border_style="data")


def _get_bus(client) -> dict:
    bus = client.send_command('i2c_bus_get')
    if not bus:
        OutputHelper.print_panel(
            "No bus config found. Scan first:\n\n"
            "  replx PORT i2c scan --sda [yellow]GP<num>[/yellow] --scl [yellow]GP<num>[/yellow]",
            title="I2C Error",
            border_style="error",
        )
        raise typer.Exit(1)
    return bus


def _subcmd_scan(client, core: str, sda: Optional[str], scl: Optional[str], freq: int):
    if normalize_core(core) == 'EFR32MG':
        sda, scl = sda or 'P1', scl or 'D1'
    explicit_pins = sda is not None and scl is not None

    if not explicit_pins:
        bus = client.send_command('i2c_bus_get')
        if not bus:
            OutputHelper.print_panel(
                "No bus config saved. Specify pins for the first scan:\n\n"
                "[bold cyan]Usage:[/bold cyan]\n"
                "  replx PORT i2c scan --sda [yellow]GP<num>[/yellow] --scl [yellow]GP<num>[/yellow]"
                " [--freq HZ]",
                title="I2C Error",
                border_style="error",
            )
            raise typer.Exit(1)
        sda_no, scl_no, ch, freq = bus['sda'], bus['scl'], bus['ch'], bus['freq']
    else:
        try:
            sda_no = parse_hardware_pin(sda, 'SDA')
            scl_no = parse_hardware_pin(scl, 'SCL')
            ch = _resolve_ch(core, sda_no, scl_no)
        except ValueError as e:
            OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
            raise typer.Exit(1)

    init = _make_init(ch, sda_no, scl_no, freq)
    code = (
        f"import json\n{init}\n"
        f"r=[a for a in i2c.scan() if 8<=a<120]\n"
        f"print(json.dumps(r))"
    )

    raw = _exec(client, code, timeout=15.0)

    try:
        found = _parse_json_strict(raw)
        if not isinstance(found, list):
            raise ValueError("Unexpected result type")
    except Exception as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)

    _display_scan(found, sda_no, scl_no, ch, freq)

    if explicit_pins:
        client.send_command('i2c_bus_set', sda=sda_no, scl=scl_no, ch=ch, freq=freq)


def _subcmd_bus(client):
    bus = client.send_command('i2c_bus_get')
    _display_bus(bus)


def _parse_seq_tokens(pos_args: list) -> tuple:
    if not pos_args:
        raise ValueError("Missing ADDR")
    addr = _parse_hex(pos_args[0])
    if not 0 <= addr <= 0x7F:
        raise ValueError("I2C address must be in range 0x00..0x7F")
    ops = []
    for tok in pos_args[1:]:
        t = tok.lower()
        if t.startswith('u'):
            if not t[1:].isdigit():
                raise ValueError(f"Invalid delay token: {tok!r}")
            ops.append(('us', int(t[1:])))
        elif t.startswith('m'):
            if not t[1:].isdigit():
                raise ValueError(f"Invalid delay token: {tok!r}")
            ops.append(('ms', int(t[1:])))
        else:
            value = _parse_hex(tok)
            if not 0 <= value <= 0xFF:
                raise ValueError("I2C sequence bytes must be in range 00..FF")
            ops.append(('w', value))
    return addr, ops


def _subcmd_seq(client, pos_args: list):
    try:
        addr, ops = _parse_seq_tokens(pos_args)
    except ValueError as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)

    if not ops:
        OutputHelper.print_panel(
            "No operations specified.",
            title="I2C Error", border_style="error",
        )
        raise typer.Exit(1)

    bus = _get_bus(client)
    ch, sda, scl, freq = bus['ch'], bus['sda'], bus['scl'], bus['freq']
    init = _make_init(ch, sda, scl, freq)

    lines = [f"import time\n{init}"]
    writes = 0
    for kind, val in ops:
        if kind == 'w':
            lines.append(f"i2c.writeto({hex(addr)},bytes([{hex(val)}]))")
            writes += 1
        elif kind == 'us':
            lines.append(f"time.sleep_us({val})")
        elif kind == 'ms':
            lines.append(f"time.sleep_ms({val})")
    lines.append("print('ok')")

    code = '\n'.join(lines)
    op_ms = writes * 5 + sum(value for kind, value in ops if kind == 'ms')
    op_ms += sum(value for kind, value in ops if kind == 'us') / 1000
    raw = _exec(client, code, timeout=max(5.0, op_ms / 1000.0 + 2.0))

    op_log = []
    for kind, val in ops:
        if kind == 'w':
            op_log.append(f"[cyan]{val:02X}[/cyan]")
        elif kind == 'us':
            op_log.append(f"[dim]u{val}[/dim]")
        elif kind == 'ms':
            op_log.append(f"[dim]m{val}[/dim]")

    ok = raw.strip() == 'ok'
    status = "[green]\u2192 ok[/green]" if ok else f"[red]\u2192 {raw.strip()}[/red]"
    content = (
        f"  {writes} write(s)  [dim]{_bus_config_line(bus)}[/dim]\n\n"
        f"  {' '.join(op_log)}\n\n"
        f"  {status}"
    )
    OutputHelper.print_panel(content, title=f"I2C Seq  0x{addr:02X}", border_style="success")


def _render_mem_table(data: bytes, offset: int, bus: dict) -> list:
    COLS = 16
    addr = bus.get('addr', 0)
    lines = [
        f"  Addr: [bright_yellow]0x{addr:02X}[/bright_yellow]  "
        f"offset 0x{offset:02X}  {len(data)} bytes  "
        f"[dim]{_bus_config_line(bus)}[/dim]",
        "",
        "  [dim]     " + " ".join(f"{c:02X}" for c in range(COLS)) + "[/dim]",
        "  [dim]" + "─" * (5 + COLS * 3) + "[/dim]",
    ]
    for i in range(0, len(data), COLS):
        row = data[i:i + COLS]
        base = offset + i
        row_str = f"  [dim]{base:02X}:[/dim]  " + " ".join(f"{b:02X}" for b in row)
        ascii_str = "  " + "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in row)
        lines.append(row_str + ascii_str)
    return lines


def _target_mem_read(client, pos_args: list, bus: dict) -> None:
    mem_size = int(bus.get('mem_size', 128))
    try:
        offset = _parse_hex(pos_args[0]) if pos_args else 0
        nbytes = int(pos_args[1]) if len(pos_args) >= 2 else mem_size - offset
    except (ValueError, IndexError) as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)
    raw = _exec(client, _make_target_mem_read_code(offset, nbytes), timeout=3.0)
    try:
        d = _parse_json_strict(raw)
    except RuntimeError as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)
    data = bytes.fromhex(d.get('hex', ''))
    lines = _render_mem_table(data, offset, bus)
    OutputHelper.print_panel("\n".join(lines), title="I2C Target Mem Read", border_style="data")


def _target_mem_write(client, pos_args: list, bus: dict) -> None:
    if len(pos_args) < 2:
        OutputHelper.print_panel(
            "Usage: replx PORT i2c write [yellow]OFFSET HEX...[/yellow]\n"
            "[dim](target mode: OFFSET = register address in own mem)[/dim]",
            title="I2C Error", border_style="error",
        )
        raise typer.Exit(1)
    try:
        offset = _parse_hex(pos_args[0])
        data = _parse_data(pos_args[1:])
    except ValueError as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)
    raw = _exec(client, _make_target_mem_write_code(offset, data), timeout=3.0)
    try:
        _parse_json_strict(raw)
    except RuntimeError as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)
    addr = bus.get('addr', 0)
    OutputHelper.print_panel(
        f"  Addr: [bright_yellow]0x{addr:02X}[/bright_yellow]  "
        f"offset [bright_cyan]0x{offset:02X}[/bright_cyan]  "
        f"[bright_cyan]{len(data)}[/bright_cyan] bytes\n\n"
        f"  [{_format_hex_bytes(data)}]\n"
        f"  [green]\u2192 mem[0x{offset:02X}:0x{offset + len(data):02X}] written[/green]",
        title="I2C Target Mem Write", border_style="data",
    )


def _subcmd_read(client, pos_args: list, addr16: bool, repeat: int, interval: int):
    bus = _get_bus(client)
    if bus.get('target'):
        _target_mem_read(client, pos_args, bus)
        return

    if len(pos_args) < 2:
        OutputHelper.print_panel(
            "Missing ADDR NBYTES.\n\n"
            "[bold cyan]Usage:[/bold cyan]\n"
            "  replx PORT i2c read [yellow]ADDR NBYTES[/yellow] [[yellow]REG[/yellow]]",
            title="I2C Error",
            border_style="error",
        )
        raise typer.Exit(1)

    try:
        addr = _parse_hex(pos_args[0])
        nbytes = int(pos_args[1])
        reg = _parse_hex(pos_args[2]) if len(pos_args) >= 3 else None
    except ValueError as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)

    ch, sda, scl, freq = bus['ch'], bus['sda'], bus['scl'], bus['freq']
    init = _make_init(ch, sda, scl, freq)
    addrsize = 16 if addr16 else 8

    if reg is None:
        inner = (
            f"  print(json.dumps(list(i2c.readfrom({hex(addr)},{nbytes}))))"
        )
    else:
        inner = (
            f"  print(json.dumps(list("
            f"i2c.readfrom_mem({hex(addr)},{hex(reg)},{nbytes},addrsize={addrsize}))))"
        )

    if repeat == 1:
        code = (
            f"import json\n{init}\n"
            f"try:\n"
            f"{inner}\n"
            f"except OSError as e:\n"
            f" print(json.dumps({{'error':str(e)}}))"
        )
        timeout = _calc_timeout(1, 0, op_ms=200)
        raw = _exec(client, code, timeout=timeout)
        if not raw:
            OutputHelper.print_panel("No output from device", title="I2C Error", border_style="error")
            raise typer.Exit(1)
        _display_read(raw, addr, nbytes, reg, 1, bus)
    else:
        loop_line = "while True:\n" if repeat == 0 else f"for _ in range({repeat}):\n"
        code = (
            f"import json,time\n{init}\n"
            f"{loop_line}"
            f" try:\n"
            f" {inner}\n"
            f" except OSError as e:\n"
            f"  print(json.dumps({{'error':str(e)}}))\n"
            f" time.sleep_ms({interval})"
        )
        _display_read_scroll(client, code, addr, nbytes, reg, repeat, bus)


def _subcmd_write(client, pos_args: list, addr16: bool, repeat: int, interval: int):
    bus = _get_bus(client)
    if bus.get('target'):
        _target_mem_write(client, pos_args, bus)
        return

    if len(pos_args) < 2:
        OutputHelper.print_panel(
            "Missing ADDR DATA.\n\n"
            "[bold cyan]Usage:[/bold cyan]\n"
            "  replx PORT i2c write [yellow]ADDR DATA...[/yellow]",
            title="I2C Error",
            border_style="error",
        )
        raise typer.Exit(1)

    try:
        addr = _parse_hex(pos_args[0])
        data = _parse_data(pos_args[1:])
    except ValueError as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)

    ch, sda, scl, freq = bus['ch'], bus['sda'], bus['scl'], bus['freq']
    init = _make_init(ch, sda, scl, freq)
    data_bytes = "bytes([" + ",".join(hex(b) for b in data) + "])"

    if repeat == 1:
        code = (
            f"import json\n{init}\n"
            f"try:\n"
            f" n=i2c.writeto({hex(addr)},{data_bytes})\n"
            f" print(json.dumps({{'ack':n,'ok':True}}))\n"
            f"except OSError as e:\n"
            f" print(json.dumps({{'ok':False,'error':str(e)}}))"
        )
    else:
        code = (
            f"import json,time\n{init}\n"
            f"for _ in range({repeat}):\n"
            f" try:\n"
            f"  n=i2c.writeto({hex(addr)},{data_bytes})\n"
            f"  print(json.dumps({{'ack':n,'ok':True}}))\n"
            f" except OSError as e:\n"
            f"  print(json.dumps({{'ok':False,'error':str(e)}}))\n"
            f" time.sleep_ms({interval})"
        )

    timeout = _calc_timeout(repeat, interval, op_ms=200)
    raw = _exec(client, code, timeout=timeout)

    if not raw:
        OutputHelper.print_panel("No output from device", title="I2C Error", border_style="error")
        raise typer.Exit(1)

    _display_write(raw, addr, data, repeat, bus)


def _subcmd_dump(client, pos_args: list, addr16: bool, repeat: int, interval: int):
    if not pos_args:
        OutputHelper.print_panel(
            "Missing ADDR.\n\n"
            "[bold cyan]Usage:[/bold cyan]\n"
            "  replx PORT i2c dump [yellow]ADDR[/yellow] [[yellow]FROM[/yellow] [[yellow]TO[/yellow]]]",
            title="I2C Error",
            border_style="error",
        )
        raise typer.Exit(1)

    try:
        addr = _parse_hex(pos_args[0])
        from_r = _parse_hex(pos_args[1]) if len(pos_args) >= 2 else 0x00
        to_r = _parse_hex(pos_args[2]) if len(pos_args) >= 3 else 0x7F
    except ValueError as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)

    bus = _get_bus(client)
    ch, sda, scl, freq = bus['ch'], bus['sda'], bus['scl'], bus['freq']
    init = _make_init(ch, sda, scl, freq)
    addrsize = 16 if addr16 else 8

    single_dump = (
        "r={}\n"
        f"for a in range({from_r},{to_r + 1}):\n"
        f" try:r[a]=i2c.readfrom_mem({hex(addr)},a,1,addrsize={addrsize})[0]\n"
        " except OSError:r[a]=None\n"
        "print(json.dumps(r))"
    )

    if repeat == 1:
        code = f"import json\n{init}\n{single_dump}"
    else:
        indented = "\n".join(" " + ln for ln in single_dump.splitlines())
        code = (
            f"import json,time\n{init}\n"
            f"for _ in range({repeat}):\n"
            f"{indented}\n"
            f" time.sleep_ms({interval})"
        )

    op_ms = (to_r - from_r + 1) * 10
    timeout = _calc_timeout(repeat, interval, op_ms=op_ms)
    raw = _exec(client, code, timeout=timeout)

    if not raw:
        OutputHelper.print_panel("No output from device", title="I2C Error", border_style="error")
        raise typer.Exit(1)

    _display_dump(raw, addr, from_r, to_r, repeat, bus)


def _subcmd_open(
    client,
    core: str,
    sda: Optional[str],
    scl: Optional[str],
    freq: int,
    target: bool,
    addr_str: Optional[str],
    mem_size: int,
) -> None:
    if normalize_core(core) == 'EFR32MG':
        sda, scl = sda or 'P1', scl or 'D1'
    if sda is None or scl is None:
        OutputHelper.print_panel(
            "--sda and --scl are required for [green]open[/green].\n\n"
            "[bold cyan]Usage:[/bold cyan]\n"
            "  replx PORT i2c open --sda [yellow]GP<num>[/yellow] --scl [yellow]GP<num>[/yellow]"
            " [[yellow]--freq HZ[/yellow]]\n"
            "  replx PORT i2c open --sda [yellow]GP<num>[/yellow] --scl [yellow]GP<num>[/yellow]"
            " [yellow]--target --addr 0xNN[/yellow] [[yellow]--mem-size N[/yellow]]",
            title="I2C Error",
            border_style="error",
        )
        raise typer.Exit(1)

    try:
        sda_no = parse_hardware_pin(sda, 'SDA')
        scl_no = parse_hardware_pin(scl, 'SCL')
        ch = _resolve_ch(core, sda_no, scl_no)
    except ValueError as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)

    if target:
        available = _exec(
            client, "import machine;print(hasattr(machine,'I2CTarget'))", timeout=3.0
        )
        if available != 'True':
            OutputHelper.print_panel(
                f"I2C Target mode requires firmware with machine.I2CTarget. Detected core: [yellow]{core}[/yellow]",
                title="I2C Error",
                border_style="error",
            )
            raise typer.Exit(1)
        if addr_str is None:
            OutputHelper.print_panel(
                "--addr is required for target mode.",
                title="I2C Error",
                border_style="error",
            )
            raise typer.Exit(1)
        try:
            addr = int(addr_str, 16) if addr_str.startswith('0x') or addr_str.startswith('0X') \
                else int(addr_str, 16)
            if not 1 <= addr <= 127:
                raise ValueError(f"I2C address must be 1–127, got {addr}")
        except ValueError as e:
            OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
            raise typer.Exit(1)

        raw = _exec(client, _make_target_open_code(ch, sda_no, scl_no, addr, mem_size), timeout=5.0)
        try:
            _parse_json_strict(raw)
        except RuntimeError as e:
            OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
            raise typer.Exit(1)

        cfg = dict(sda=sda_no, scl=scl_no, ch=ch, freq=freq,
                   target=True, addr=addr, mem_size=mem_size)
        client.send_command('i2c_bus_set', **cfg)
        _display_bus(cfg)
    else:
        cfg = dict(sda=sda_no, scl=scl_no, ch=ch, freq=freq)
        client.send_command('i2c_bus_set', **cfg)
        _display_bus(cfg)


def _subcmd_mem(client, pos_args: list) -> None:
    bus = _get_bus(client)
    if not bus.get('target'):
        OutputHelper.print_panel(
            "[green]mem[/green] subcommand is only available in target mode.\n"
            "Open target first:  replx PORT i2c open ... [yellow]--target --addr 0xNN[/yellow]",
            title="I2C Error",
            border_style="error",
        )
        raise typer.Exit(1)

    mem_size = int(bus.get('mem_size', 128))
    try:
        offset = _parse_hex(pos_args[0]) if pos_args else 0
        nbytes = int(pos_args[1]) if len(pos_args) >= 2 else mem_size - offset
    except (ValueError, IndexError) as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)

    raw = _exec(client, _make_target_mem_read_code(offset, nbytes), timeout=3.0)
    try:
        d = _parse_json_strict(raw)
    except RuntimeError as e:
        OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
        raise typer.Exit(1)

    data = bytes.fromhex(d.get('hex', ''))
    lines = _render_mem_table(data, offset, bus)
    OutputHelper.print_panel(
        "\n".join(lines),
        title=f"I2C Target Mem Snapshot  ({mem_size} bytes total)",
        border_style="data",
    )


def _subcmd_close(client) -> None:
    bus = _get_bus(client)
    if bus.get('target'):
        raw = _exec(client, _make_target_close_code(), timeout=3.0)
        try:
            _parse_json_strict(raw)
        except RuntimeError as e:
            OutputHelper.print_panel(str(e), title="I2C Error", border_style="error")
            raise typer.Exit(1)
    client.send_command('i2c_bus_clear')
    OutputHelper.print_panel(
        "  I2C bus released. Run [green]scan[/green] or [green]open[/green] to reconfigure.",
        title="I2C Closed",
        border_style="data",
    )


def _print_i2c_help():
    help_text = """\
Interact with I2C devices connected to the board without writing a script.

[bold cyan]Platforms:[/bold cyan]
  Standard GPIO ids: GPn, GPIOn, or numeric n (not connector pin numbers).
  XBee3 Zigbee: controller bus 1, SDA=P1 and SCL=D1 (fixed/default pins).
  Use i2c scan or i2c open without pins on XBee3; no target mode or deinit.

[bold cyan]Usage (Controller mode):[/bold cyan]
  replx PORT i2c scan  --sda [yellow]GP<num>[/yellow] --scl [yellow]GP<num>[/yellow] [[yellow]--freq HZ[/yellow]]
  replx PORT i2c open  --sda [yellow]GP<num>[/yellow] --scl [yellow]GP<num>[/yellow] [[yellow]--freq HZ[/yellow]]
  replx PORT i2c bus
  replx PORT i2c read  [yellow]ADDR NBYTES[/yellow] [[yellow]REG[/yellow]] [[yellow]--addr16[/yellow]] [[yellow]-n N[/yellow] [yellow]--interval MS[/yellow]]
  replx PORT i2c write [yellow]ADDR DATA...[/yellow]      [[yellow]--addr16[/yellow]] [[yellow]-n N[/yellow] [yellow]--interval MS[/yellow]]
  replx PORT i2c dump  [yellow]ADDR[/yellow] [[yellow]FROM[/yellow] [[yellow]TO[/yellow]]]  [[yellow]--addr16[/yellow]] [[yellow]-n N[/yellow] [yellow]--interval MS[/yellow]]
  replx PORT i2c seq   [yellow]ADDR TOKEN...[/yellow]
  replx PORT i2c close

[bold yellow]Usage (Target mode — requires machine.I2CTarget):[/bold yellow]
  replx PORT i2c open --sda [yellow]GP<num>[/yellow] --scl [yellow]GP<num>[/yellow] [yellow]--target --addr 0xNN[/yellow] [[yellow]--mem-size N[/yellow]]
  replx PORT i2c bus
  replx PORT i2c read  [[yellow]OFFSET[/yellow] [[yellow]NBYTES[/yellow]]]      [dim](read bytes written by controller)[/dim]
  replx PORT i2c write [yellow]OFFSET HEX...[/yellow]           [dim](preload bytes for controller to read)[/dim]
  replx PORT i2c mem   [[yellow]OFFSET[/yellow] [[yellow]NBYTES[/yellow]]]      [dim](full mem snapshot)[/dim]
  replx PORT i2c close

[bold cyan]Subcommands:[/bold cyan]
  [green]scan[/green]   Scan I2C bus for responding devices (controller).
  [green]open[/green]   Configure I2C bus without scanning. --target activates I2CTarget.
  [green]bus[/green]    Show saved bus config [dim](in-memory, cleared on agent restart)[/dim].
  [green]read[/green]   Controller: read bytes from device. Target: read own mem region.
  [green]write[/green]  Controller: write bytes to device. Target: write own mem region.
  [green]dump[/green]   Dump device register range (controller only).
  [green]seq[/green]    Execute a write+delay sequence in a single board call (controller).
         TOKEN: hex byte [dim](e.g. 3C)[/dim]  u<N> [dim]= sleep_us[/dim]  m<N> [dim]= sleep_ms[/dim]
  [green]mem[/green]    Snapshot entire target mem buffer (target mode only).
  [green]close[/green]  Release I2C peripheral and clear bus config.

[bold cyan]Options:[/bold cyan]
  [yellow]--sda GP<num>[/yellow]     SDA GPIO pin [red](open/scan: required)[/red]  e.g. [cyan]GP12[/cyan]
  [yellow]--scl GP<num>[/yellow]     SCL GPIO pin [red](open/scan: required)[/red]  e.g. [cyan]GP13[/cyan]
  [yellow]--freq HZ[/yellow]         I2C clock frequency Hz [dim](default: 400000)[/dim]
  [yellow]--target[/yellow]          Activate I2CTarget (firmware API required)
  [yellow]--addr 0xNN[/yellow]       7-bit I2C address for target mode [dim](1-127)[/dim]
  [yellow]--mem-size N[/yellow]      Target mem buffer size bytes [dim](default: 256)[/dim]
  [yellow]--addr16[/yellow]          16-bit register addresses [dim](default: 8-bit)[/dim]
  [yellow]-n, --repeat N[/yellow]    Repeat N times, N≥1 [dim](default: 1)[/dim]
  [yellow]--interval MS[/yellow]     Delay between repeats ms [dim](default: 1000, requires -n≥2)[/dim]

[bold cyan]Arguments (controller mode):[/bold cyan]
  [yellow]ADDR[/yellow]      Device address  [dim]hex, 0x optional · e.g.[/dim] [cyan]68[/cyan] [cyan]0x68[/cyan]
  [yellow]NBYTES[/yellow]    Bytes to read   [dim]decimal           · e.g.[/dim] [cyan]6[/cyan]
  [yellow]REG[/yellow]       Register addr   [dim]hex, 0x optional · e.g.[/dim] [cyan]3B[/cyan] [cyan]0x3B[/cyan]
  [yellow]DATA[/yellow]      Bytes to write  [dim]hex space-sep     · e.g.[/dim] [cyan]6B 00[/cyan]
  [yellow]FROM TO[/yellow]   Dump range      [dim]hex, default[/dim] [cyan]00[/cyan][dim]–[/dim][cyan]7F[/cyan]

[bold cyan]Arguments (target mode):[/bold cyan]
  [yellow]OFFSET[/yellow]    Offset into target mem buffer  [dim]hex, 0x optional[/dim]
  [yellow]NBYTES[/yellow]    Bytes to read/write            [dim]decimal[/dim]
  [yellow]HEX...[/yellow]    Bytes to write to mem          [dim]hex space-sep  · e.g.[/dim] [cyan]DE AD BE EF[/cyan]

[bold cyan]Bus config:[/bold cyan]
  Saved in agent memory on successful scan/open. Read/write/dump rely on it.
  Cleared only when the agent restarts or [green]close[/green] is called.

[bold cyan]Board support:[/bold cyan]
  RP2350    GP%4==0→CH0, GP%4==2→CH1, SCL must equal SDA+1
  Teensy    Fixed Wire pairs: (GP18,GP19)→0  (GP17,GP16)→1  (GP25,GP24)→2  (GP38,GP37)→3
  ESP32     Any GPIO, CH=0 [dim](GPIO matrix)[/dim]
  EFR32MG   [red]Not supported[/red]

[bold cyan]Examples (controller):[/bold cyan]
  [dim]# Scan and save bus config[/dim]
  replx COM3 i2c scan --sda GP12 --scl GP13

  [dim]# Show saved bus config[/dim]
  replx COM3 i2c bus

  [dim]# WHO_AM_I (MPU-6050, reg 0x75, expect 0x68)[/dim]
  replx COM3 i2c read 0x68 1 75

  [dim]# Disable sleep (reg 0x6B = 0x00)[/dim]
  replx COM3 i2c write 0x68 6B 00

  [dim]# Read accelerometer XYZ 6 bytes from reg 0x3B[/dim]
  replx COM3 i2c read 0x68 6 3B

  [dim]# Repeat 5 times every 500ms[/dim]
  replx COM3 i2c read 0x68 6 3B -n 5 --interval 500

  [dim]# Dump all registers (0x00–0x7F)[/dim]
  replx COM3 i2c dump 0x68

  [dim]# PCF8574 LCD: pulse(0x30)×3 → 4-bit mode[/dim]
  replx COM3 i2c seq 27  3C u500 38 u100  m5  3C u500 38 u100  u200  3C u500 38 u100

[bold yellow]Examples (target):[/bold yellow]
  [dim]# Open as I2CTarget at address 0x42 with 256-byte mem[/dim]
  replx COM4 i2c open --sda GP12 --scl GP13 --target --addr 0x42 --mem-size 256

  [dim]# Preload bytes at offset 0x10 (controller will read these)[/dim]
  replx COM4 i2c write 0x10 DE AD BE EF

  [dim]# Inspect what the controller wrote at offset 0x00[/dim]
  replx COM4 i2c read 0x00 16

  [dim]# Full mem snapshot[/dim]
  replx COM4 i2c mem

  [dim]# Release target[/dim]
  replx COM4 i2c close"""
    OutputHelper.print_panel(help_text, title="i2c", border_style="help")




@app.command(name="i2c", rich_help_panel="Hardware")
def i2c_cmd(
    args: Optional[list[str]] = typer.Argument(
        None, help="Subcommand: scan  open  close  bus  read  write  dump  seq  mem"
    ),
    sda: Optional[str] = typer.Option(None, "--sda", metavar="GP<num>",
                                      help="SDA GPIO pin in GP<num> format (open/scan) e.g. GP20"),
    scl: Optional[str] = typer.Option(None, "--scl", metavar="GP<num>",
                                      help="SCL GPIO pin in GP<num> format (open/scan) e.g. GP21"),
    freq: int = typer.Option(400000, "--freq", metavar="HZ",
                             help="I2C clock frequency in Hz"),
    target: bool = typer.Option(False, "--target",
                                help="Activate I2CTarget mode (firmware API required, use with open)"),
    addr: Optional[str] = typer.Option(None, "--addr", metavar="0xNN",
                                       help="7-bit I2C address for target mode (1-127)"),
    mem_size: int = typer.Option(256, "--mem-size", metavar="N",
                                 help="Target mem buffer size in bytes (default: 256)"),
    addr16: bool = typer.Option(False, "--addr16",
                                help="Use 16-bit register addresses"),
    repeat: int = typer.Option(1, "--repeat", "-n", metavar="N",
                               help="Repeat N times (N>=1)"),
    interval: int = typer.Option(1000, "--interval-ms", "--interval", metavar="MS",
                                 help="Interval between repeats in ms"),
    show_help: bool = typer.Option(False, "--help", "-h",
                                   is_eager=True, hidden=True),
):
    if show_help:
        _print_i2c_help()
        raise typer.Exit()
    if not args:
        OutputHelper.print_panel(
            "Subcommands: [bright_blue]scan  open  close  bus  read  write  dump  seq  mem[/bright_blue]\n\n"
            "  [bright_green]replx PORT i2c scan --sda GP12 --scl GP13[/bright_green]\n"
            "  [bright_green]replx PORT i2c read 0x68 6 3B[/bright_green]\n"
            "  [bright_green]replx PORT i2c write 0x68 6B 00[/bright_green]\n\n"
            "Use [bright_blue]replx i2c --help[/bright_blue] for details.",
            title="I2C",
            border_style="help",
        )
        raise typer.Exit(1)

    subcmd = args[0].lower()
    pos_args = args[1:]

    _VALID = ('scan', 'open', 'close', 'bus', 'read', 'write', 'dump', 'seq', 'mem')
    if subcmd not in _VALID:
        OutputHelper.print_panel(
            f"Unknown subcommand: {subcmd!r}\n\n"
            "Valid subcommands: " + "  ".join(_VALID),
            title="I2C Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if subcmd not in ('scan', 'open', 'close', 'bus') and repeat < 1:
        OutputHelper.print_panel(
            "--repeat must be >= 1",
            title="I2C Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if freq <= 0 or interval < 0 or mem_size < 1:
        OutputHelper.print_panel(
            "--freq and --mem-size must be > 0; --interval-ms must be >= 0",
            title="I2C Error", border_style="error",
        )
        raise typer.Exit(1)

    _ensure_connected()

    with _create_agent_client() as client:
        port = _get_device_port()

        if subcmd == 'bus':
            _subcmd_bus(client)
            return

        if subcmd == 'close':
            _subcmd_close(client)
            return

        core = _get_core(client, port)

        if subcmd == 'scan':
            _subcmd_scan(client, core, sda, scl, freq)
        elif subcmd == 'open':
            _subcmd_open(client, core, sda, scl, freq, target, addr, mem_size)
        elif subcmd == 'read':
            _subcmd_read(client, pos_args, addr16, repeat, interval)
        elif subcmd == 'write':
            _subcmd_write(client, pos_args, addr16, repeat, interval)
        elif subcmd == 'dump':
            _subcmd_dump(client, pos_args, addr16, repeat, interval)
        elif subcmd == 'seq':
            _subcmd_seq(client, pos_args)
        elif subcmd == 'mem':
            _subcmd_mem(client, pos_args)
