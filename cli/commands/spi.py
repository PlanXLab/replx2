from typing import Optional
import typer
from ..helpers import OutputHelper
from ..connection import _ensure_connected, _create_agent_client, _get_device_port
from ..app import app
from ._common import (
    exec_code as _exec,
    get_core as _get_core,
    get_device as _get_device,
    parse_json_strict as _parse_json_strict,
    render_hex_dump as _render_hex_dump,
    parse_gp_pin as _parse_gp_pin,
    parse_text_bytes as _parse_text_data,
)
from ...utils import device_name_to_path
from ._common import require_standard_hardware


_RP_SPI_SCK_CH: dict[int, int] = {
    2: 0, 6: 0, 18: 0, 22: 0,
    10: 1, 14: 1, 26: 1,
}


def _resolve_spi_ch(core: str, sck_no: int) -> int:
    c = (core or '').upper()
    if 'RP2350' in c or 'RP2040' in c:
        if sck_no not in _RP_SPI_SCK_CH:
            valid = ', '.join(f"GP{p}" for p in sorted(_RP_SPI_SCK_CH))
            raise ValueError(
                f"GP{sck_no} is not a valid SPI SCK pin on {core}.\n"
                f"Valid SCK pins: {valid}"
            )
        return _RP_SPI_SCK_CH[sck_no]
    return 1


def _make_spi_init(cfg: dict) -> str:
    ch = cfg['ch']
    sck = cfg['sck']
    mosi = cfg['mosi']
    miso = cfg.get('miso')
    baud = cfg['baud']
    mode = cfg.get('mode', 0)
    bits = cfg.get('bits', 8)
    polarity = int(mode) >> 1
    phase = int(mode) & 1
    lsb = cfg.get('lsb', False)
    firstbit = "SPI.LSB" if lsb else "SPI.MSB"
    if miso is not None:
        return (
            f"from machine import SPI,Pin\n"
            f"s=SPI({ch},baudrate={baud},sck=Pin({sck}),mosi=Pin({mosi}),miso=Pin({miso}),"
            f"polarity={polarity},phase={phase},bits={bits},firstbit={firstbit})"
        )
    return (
        f"from machine import SPI,Pin\n"
        f"s=SPI({ch},baudrate={baud},sck=Pin({sck}),mosi=Pin({mosi}),"
        f"polarity={polarity},phase={phase},bits={bits},firstbit={firstbit})"
    )


def _cs_context(cs_pin: Optional[int]) -> tuple[str, str]:
    if cs_pin is None:
        return '', ''
    setup = f"from machine import Pin as _P\n_cs=_P({cs_pin},_P.OUT,value=1)\n"
    assert_ = "_cs.value(0)\n"
    deassert = "_cs.value(1)\n"
    return setup + assert_, deassert


def _make_open_code(cfg: dict) -> str:
    init = _make_spi_init(cfg)
    return (
        f"import json\n{init}\n"
        f"s.deinit()\n"
        f"print(json.dumps({{'ok':True,'ch':{cfg['ch']},"
        f"'sck':{cfg['sck']},'mosi':{cfg['mosi']},'miso':{cfg.get('miso')!r},"
        f"'baud':{cfg['baud']},'mode':{cfg.get('mode', 0)},'bits':{cfg.get('bits', 8)}}}))"
    )


def _make_write_code(cfg: dict, data: list[int], cs_no: Optional[int]) -> str:
    init = _make_spi_init(cfg)
    data_str = "bytes([" + ",".join(hex(b) for b in data) + "])"
    cs_pre, cs_post = _cs_context(cs_no)
    return (
        f"import json\n{init}\n"
        f"{cs_pre}"
        f"try:\n"
        f" s.write({data_str})\n"
        f"finally:\n"
        f" {cs_post}"
        f" s.deinit()\n"
        f"print(json.dumps({{'written':{len(data)}}}))"
    )


def _make_read_code(cfg: dict, nbytes: int, fill_byte: int, cs_no: Optional[int]) -> str:
    init = _make_spi_init(cfg)
    cs_pre, cs_post = _cs_context(cs_no)
    return (
        f"import json,binascii\n{init}\n"
        f"{cs_pre}"
        f"try:\n"
        f" data=s.read({nbytes},{fill_byte})\n"
        f"finally:\n"
        f" {cs_post}"
        f" s.deinit()\n"
        r"print(json.dumps({'hex':binascii.hexlify(data).decode(),'len':len(data)}))"
    )


def _make_xfer_code(cfg: dict, tx_data: list[int], cs_no: Optional[int]) -> str:
    init = _make_spi_init(cfg)
    data_str = "bytearray([" + ",".join(hex(b) for b in tx_data) + "])"
    cs_pre, cs_post = _cs_context(cs_no)
    return (
        f"import json,binascii\n{init}\n"
        f"tx={data_str}\n"
        f"rx=bytearray(len(tx))\n"
        f"{cs_pre}"
        f"try:\n"
        f" s.write_readinto(tx,rx)\n"
        f"finally:\n"
        f" {cs_post}"
        f" s.deinit()\n"
        r"print(json.dumps({'hex':binascii.hexlify(rx).decode(),'len':len(rx)}))"
    )


def _make_slave_open_code(cfg: dict, device: str) -> str:
    sck      = cfg['sck']
    mosi     = cfg['mosi']
    cs       = cfg['cs']
    miso     = cfg.get('miso')
    buf_size = cfg.get('buf_size', 8192)
    miso_arg = f", miso={miso}" if miso is not None else ""
    mod = device_name_to_path(device) + '.spi' if device else 'spi'
    return (
        f"import json\n"
        f"from {mod} import SpiSlave\n"
        f"_spi_slave = SpiSlave(sck={sck}, mosi={mosi}, cs={cs}{miso_arg}, buf_size={buf_size})\n"
        f"print(json.dumps({{'ok':True,'sck':{sck},'mosi':{mosi},'cs':{cs},"
        f"'miso':{miso!r},'buf_size':{buf_size}}}))"
    )


def _make_slave_read_code(timeout_ms: int) -> str:
    return (
        f"import json,binascii\n"
        f"_d=_spi_slave.read(timeout={timeout_ms})\n"
        f"if _d:\n"
        f"    print(json.dumps({{'hex':binascii.hexlify(_d).decode(),'len':len(_d)}}))\n"
        f"else:\n"
        f"    print(json.dumps({{'hex':'','len':0}}))"
    )


def _make_slave_write_code(data: list[int]) -> str:
    data_str = "bytes([" + ",".join(hex(b) for b in data) + "])"
    return (
        f"import json\n"
        f"_spi_slave.write({data_str})\n"
        f"print(json.dumps({{'written':{len(data)}}}))"
    )


def _make_slave_writeinto_code(data: list[int], timeout_ms: int) -> str:
    data_str = "bytes([" + ",".join(hex(b) for b in data) + "])"
    return (
        f"import json,binascii\n"
        f"_tx={data_str}\n"
        f"_rx=bytearray(len(_tx))\n"
        f"_n=_spi_slave.writeinto(_tx,_rx,timeout={timeout_ms})\n"
        r"print(json.dumps({'hex':binascii.hexlify(_rx[:_n]).decode(),'len':_n}))"
    )


def _make_slave_close_code() -> str:
    return (
        "import json\n"
        "_spi_slave.deinit()\n"
        "del _spi_slave\n"
        "print(json.dumps({'closed':True}))"
    )


def _display_bus(bus: dict) -> None:
    if bus.get('slave'):
        miso_str = f"GP{bus['miso']}" if bus.get('miso') is not None else "[dim]none[/dim]"
        OutputHelper.print_panel(
            f"Mode: [bright_yellow]SLAVE[/bright_yellow]\n"
            f"SCK: [bright_green]GP{bus['sck']}[/bright_green]  "
            f"MOSI: [bright_green]GP{bus['mosi']}[/bright_green]  "
            f"CS: [bright_green]GP{bus['cs']}[/bright_green]  "
            f"MISO: [bright_green]{miso_str}[/bright_green]\n"
            f"Buffer: [bright_cyan]{bus.get('buf_size', 8192)}[/bright_cyan] bytes",
            title="SPI Bus",
            border_style="data",
        )
        return
    miso_str = f"GP{bus['miso']}" if bus.get('miso') is not None else "[dim]none[/dim]"
    lsb = "[dim]yes[/dim]" if bus.get('lsb') else "[dim]no[/dim]"
    OutputHelper.print_panel(
        f"CH: [bright_cyan]{bus['ch']}[/bright_cyan]\n"
        f"SCK: [bright_green]GP{bus['sck']}[/bright_green]  "
        f"MOSI: [bright_green]GP{bus['mosi']}[/bright_green]  "
        f"MISO: [bright_green]{miso_str}[/bright_green]\n"
        f"Baud: [bright_cyan]{bus['baud']}[/bright_cyan]  "
        f"Mode: [bright_cyan]{bus.get('mode', 0)}[/bright_cyan]  "
        f"Bits: [bright_cyan]{bus.get('bits', 8)}[/bright_cyan]  "
        f"LSB-first: {lsb}",
        title="SPI Bus",
        border_style="data",
    )


def _get_bus(client) -> dict:
    bus = client.send_command('spi_bus_get')
    if not bus:
        OutputHelper.print_panel(
            "No SPI bus config. Open first:\n\n"
            "  replx PORT spi open --sck [yellow]GP<num>[/yellow] --mosi [yellow]GP<num>[/yellow]",
            title="SPI Error",
            border_style="error",
        )
        raise typer.Exit(1)
    return bus


def _require_miso(bus: dict, subcmd: str) -> None:
    if bus.get('miso') is None:
        OutputHelper.print_panel(
            f"spi {subcmd} requires a MISO pin.\n"
            "Re-open with --miso GP<num>:\n\n"
            "  replx PORT spi open --sck GP<num> --mosi GP<num> --miso [yellow]GP<num>[/yellow]",
            title="SPI Error",
            border_style="error",
        )
        raise typer.Exit(1)


def _parse_cs(cs_str: Optional[str]) -> Optional[int]:
    if cs_str is None:
        return None
    return _parse_gp_pin(cs_str, 'CS')


def _parse_hex_bytes(tokens: list[str]) -> list[int]:
    result: list[int] = []
    for token in tokens:
        parts = token.split()
        for part in parts:
            t = part.strip()
            if t.lower().startswith('0x'):
                t = t[2:]
            if not t:
                continue
            if len(t) % 2 != 0:
                raise ValueError(
                    f"Odd-length hex token: {part!r}. "
                    "Each token must have an even number of hex digits."
                )
            for i in range(0, len(t), 2):
                pair = t[i:i + 2]
                try:
                    result.append(int(pair, 16))
                except ValueError:
                    raise ValueError(f"Invalid hex byte {pair!r} in token {part!r}")
    return result


def _subcmd_open(client, port: str, core: str,
                 sck: Optional[str], mosi: Optional[str], miso: Optional[str],
                 baud: int, mode: int, bits: int, lsb: bool,
                 slave: bool, slave_buf: int, cs_pin: Optional[str]) -> None:
    if slave:
        if 'RP2350' not in core:
            OutputHelper.print_panel(
                f"[red]SPI slave mode requires RP2350.[/red]\n"
                f"Detected core: [yellow]{core}[/yellow]\n\n"
                "Slave mode uses PIO + DMA which is only supported on RP2350.",
                title="SPI Error", border_style="error",
            )
            raise typer.Exit(1)
        if sck is None:
            raise ValueError("--sck is required. e.g. --sck GP2")
        if mosi is None:
            raise ValueError("--mosi is required. e.g. --mosi GP3")
        if cs_pin is None:
            raise ValueError("--cs is required for slave mode. e.g. --cs GP5")
        try:
            sck_no  = _parse_gp_pin(sck,  'SCK')
            mosi_no = _parse_gp_pin(mosi, 'MOSI')
            cs_no   = _parse_gp_pin(cs_pin, 'CS')
            miso_no = _parse_gp_pin(miso, 'MISO') if miso else None
            if slave_buf < 1:
                raise ValueError("--slave-buf must be >= 1")
            if mosi_no != sck_no + 1:
                raise ValueError(
                    f"MOSI (GP{mosi_no}) must equal SCK+1 (GP{sck_no + 1}) for slave mode."
                )
        except ValueError as e:
            OutputHelper.print_panel(str(e), title="SPI Error", border_style="error")
            raise typer.Exit(1)
        cfg = dict(sck=sck_no, mosi=mosi_no, cs=cs_no, miso=miso_no,
                   buf_size=slave_buf, slave=True)
        device = _get_device(client, port)
        code = _make_slave_open_code(cfg, device)
        raw = _exec(client, code, timeout=5.0)
        try:
            _parse_json_strict(raw)
        except RuntimeError as e:
            OutputHelper.print_panel(str(e), title="SPI Error", border_style="error")
            raise typer.Exit(1)
        client.send_command('spi_bus_set', **cfg)
        _display_bus(cfg)
        return

    if sck is None:
        raise ValueError("--sck is required. e.g. --sck GP2")
    if mosi is None:
        raise ValueError("--mosi is required. e.g. --mosi GP3")

    try:
        sck_no = _parse_gp_pin(sck, 'SCK')
        mosi_no = _parse_gp_pin(mosi, 'MOSI')
        miso_no = _parse_gp_pin(miso, 'MISO') if miso else None
        if baud <= 0:
            raise ValueError("--baud must be > 0")
        selected_pins = [pin for pin in (sck_no, mosi_no, miso_no) if pin is not None]
        if len(selected_pins) != len(set(selected_pins)):
            raise ValueError("SCK, MOSI, and MISO must use distinct pins")
        if mode not in (0, 1, 2, 3):
            raise ValueError("--mode must be 0, 1, 2, or 3")
        if bits not in (8, 16):
            raise ValueError("--bits must be 8 or 16")
        ch = _resolve_spi_ch(core, sck_no)
    except ValueError as e:
        OutputHelper.print_panel(str(e), title="SPI Error", border_style="error")
        raise typer.Exit(1)

    cfg = dict(
        sck=sck_no, mosi=mosi_no, miso=miso_no, ch=ch,
        baud=baud, mode=mode, bits=bits, lsb=lsb,
    )
    code = _make_open_code(cfg)
    raw = _exec(client, code, timeout=5.0)
    try:
        _parse_json_strict(raw)
    except RuntimeError as e:
        OutputHelper.print_panel(str(e), title="SPI Error", border_style="error")
        raise typer.Exit(1)

    client.send_command('spi_bus_set',
                        sck=sck_no, mosi=mosi_no, miso=miso_no, ch=ch,
                        baud=baud, mode=mode, bits=bits, lsb=lsb)
    _display_bus(cfg)


def _subcmd_bus(client) -> None:
    bus = client.send_command('spi_bus_get')
    if not bus:
        OutputHelper.print_panel(
            "[dim]No SPI bus config saved.[/dim]\n"
            "Run: replx PORT spi open --sck [yellow]GP<num>[/yellow] --mosi [yellow]GP<num>[/yellow]",
            title="SPI Bus",
            border_style="data",
        )
        return
    _display_bus(bus)


def _subcmd_write(client, pos_args: list[str], cs_str: Optional[str], text_mode: bool) -> None:
    if not pos_args:
        if text_mode:
            raise ValueError("Specify text to write. e.g. spi write --text Hello")
        raise ValueError("Specify hex bytes to write. e.g. spi write 01 02 03")
    if text_mode:
        data = _parse_text_data(pos_args)
        display = repr(bytes(data).decode('utf-8', errors='replace'))
        mode_label = 'TEXT'
    else:
        data = _parse_hex_bytes(pos_args)
        display = ' '.join(f'{b:02X}' for b in data)
        mode_label = 'HEX'
    bus = _get_bus(client)
    if bus.get('slave'):
        raw = _exec(client, _make_slave_write_code(data), timeout=5.0)
        _parse_json_strict(raw)
        OutputHelper.print_panel(
            f"MISO pre-loaded: [bright_cyan]{len(data)}[/bright_cyan] bytes  [dim]({mode_label})[/dim]\n"
            f"Data: [dim]{display}[/dim]",
            title="SPI Slave Write",
            border_style="data",
        )
        return
    cs_no = _parse_cs(cs_str)
    raw = _exec(client, _make_write_code(bus, data, cs_no), timeout=5.0)
    _parse_json_strict(raw)
    cs_label = f"  CS: GP{cs_no}" if cs_no is not None else ""
    OutputHelper.print_panel(
        f"Written: [bright_cyan]{len(data)}[/bright_cyan] bytes  [dim]({mode_label})[/dim]{cs_label}\n"
        f"Data: [dim]{display}[/dim]",
        title="SPI Write",
        border_style="success",
    )


def _subcmd_read(client, pos_args: list[str], fill: str,
                cs_str: Optional[str], timeout_ms: int) -> None:
    bus = _get_bus(client)
    if bus.get('slave'):
        exec_timeout = timeout_ms / 1000 + 3.0
        raw = _exec(client, _make_slave_read_code(timeout_ms), timeout=exec_timeout)
        result = _parse_json_strict(raw)
        hex_str = result.get('hex', '')
        length  = result.get('len', 0)
        if not hex_str or length == 0:
            OutputHelper.print_panel(
                f"[dim]No data received (timeout {timeout_ms}ms)[/dim]",
                title="SPI Slave Read",
                border_style="neutral",
            )
            return
        data = bytes.fromhex(hex_str)
        OutputHelper.print_panel(
            f"Received: [bright_cyan]{length}[/bright_cyan] bytes\n"
            + _render_hex_dump(data),
            title="SPI Slave Read",
            border_style="data",
        )
        return
    if not pos_args:
        raise ValueError("Specify NBYTES. e.g. spi read 4")
    try:
        nbytes = int(pos_args[0])
        if nbytes < 1:
            raise ValueError("NBYTES must be >= 1")
    except ValueError as e:
        raise ValueError(str(e))
    try:
        fill_byte = int(fill, 16) if not fill.startswith('0x') else int(fill, 16)
        if not (0 <= fill_byte <= 255):
            raise ValueError(f"--fill must be 00-FF, got {fill!r}")
    except ValueError:
        raise ValueError(f"Invalid --fill value: {fill!r}. Use hex byte e.g. 00 or FF")
    cs_no = _parse_cs(cs_str)
    _require_miso(bus, 'read')
    raw = _exec(client, _make_read_code(bus, nbytes, fill_byte, cs_no), timeout=5.0)
    result = _parse_json_strict(raw)
    hex_str = result.get('hex', '')
    length = result.get('len', 0)
    cs_label = f"  CS: GP{cs_no}" if cs_no is not None else ""
    if not hex_str or length == 0:
        OutputHelper.print_panel(
            f"[dim]No data received[/dim]{cs_label}",
            title="SPI Read",
            border_style="neutral",
        )
        return
    data = bytes.fromhex(hex_str)
    OutputHelper.print_panel(
        f"Received: [bright_cyan]{length}[/bright_cyan] bytes{cs_label}\n"
        + _render_hex_dump(data),
        title="SPI Read",
        border_style="data",
    )


def _subcmd_xfer(client, pos_args: list[str], cs_str: Optional[str],
                 text_mode: bool, timeout_ms: int) -> None:
    if not pos_args:
        if text_mode:
            raise ValueError("Specify text to xfer. e.g. spi xfer --text Hello")
        raise ValueError("Specify hex bytes to xfer. e.g. spi xfer 01 02 03")
    if text_mode:
        tx_data = _parse_text_data(pos_args)
        display = repr(bytes(tx_data).decode('utf-8', errors='replace'))
        mode_label = 'TEXT'
    else:
        tx_data = _parse_hex_bytes(pos_args)
        display = ' '.join(f'{b:02X}' for b in tx_data)
        mode_label = 'HEX'
    bus = _get_bus(client)
    if bus.get('slave'):
        exec_timeout = timeout_ms / 1000 + 3.0
        raw = _exec(client, _make_slave_writeinto_code(tx_data, timeout_ms), timeout=exec_timeout)
        result = _parse_json_strict(raw)
        hex_str = result.get('hex', '')
        length  = result.get('len', 0)
        rx_section = (
            "\n" + _render_hex_dump(bytes.fromhex(hex_str))
            if hex_str and length > 0
            else "\n[dim]No RX data[/dim]"
        )
        OutputHelper.print_panel(
            f"TX (MISO): [bright_cyan]{len(tx_data)}[/bright_cyan] bytes  [dim]({mode_label})[/dim]  "
            f"[dim]→ {display}[/dim]\n"
            f"RX (MOSI): [bright_cyan]{length}[/bright_cyan] bytes"
            + rx_section,
            title="SPI Slave Xfer",
            border_style="data",
        )
        return
    cs_no = _parse_cs(cs_str)
    _require_miso(bus, 'xfer')
    raw = _exec(client, _make_xfer_code(bus, tx_data, cs_no), timeout=5.0)
    result = _parse_json_strict(raw)
    hex_str = result.get('hex', '')
    length = result.get('len', 0)
    rx_section = (
        "\n" + _render_hex_dump(bytes.fromhex(hex_str))
        if hex_str and length > 0
        else "\n[dim]No RX data[/dim]"
    )
    cs_label = f"  CS: GP{cs_no}" if cs_no is not None else ""
    OutputHelper.print_panel(
        f"TX: [bright_cyan]{len(tx_data)}[/bright_cyan] bytes  [dim]({mode_label})[/dim]  "
        f"[dim]→ {display}[/dim]\n"
        f"RX: [bright_cyan]{length}[/bright_cyan] bytes{cs_label}"
        + rx_section,
        title="SPI Xfer",
        border_style="data",
    )


def _subcmd_close(client) -> None:
    bus = client.send_command('spi_bus_get')
    if not bus:
        OutputHelper.print_panel(
            "[dim]No SPI bus config to close.[/dim]",
            title="SPI Close",
            border_style="neutral",
        )
        return
    if bus.get('slave'):
        try:
            _exec(client, _make_slave_close_code(), timeout=3.0)
        except Exception:
            pass
        client.send_command('spi_bus_clear')
        OutputHelper.print_panel(
            "SPI Slave stopped.",
            title="SPI Close",
            border_style="success",
        )
        return
    init = _make_spi_init(bus)
    code = f"import json\n{init}\ns.deinit()\nprint(json.dumps({{'closed':True}}))"
    try:
        _exec(client, code, timeout=3.0)
    except Exception:
        pass
    client.send_command('spi_bus_clear')
    OutputHelper.print_panel(
        f"SPI CH{bus['ch']} closed.",
        title="SPI Close",
        border_style="success",
    )


def _print_spi_help() -> None:
    help_text = """\
SPI open/write/read/xfer/close command.

[bold cyan]Usage (Master):[/bold cyan]
  replx PORT spi open    --sck [yellow]GP<num>[/yellow] --mosi [yellow]GP<num>[/yellow] [[green]--miso GP<num>[/green]] [[green]--baud N[/green]]
                         [[green]--mode 0-3[/green]] [[green]--bits 8|16[/green]] [[green]--lsb[/green]]
  replx PORT spi write   [yellow]HEX...[/yellow] [[green]--cs GP<num>[/green]]
  replx PORT spi read    [yellow]NBYTES[/yellow] [[green]--fill HH[/green]] [[green]--cs GP<num>[/green]]
  replx PORT spi xfer    [yellow]HEX...[/yellow] [[green]--cs GP<num>[/green]]
  replx PORT spi close

[bold yellow]Usage (Slave):[/bold yellow]
  replx PORT spi open    --slave --sck [yellow]GP<num>[/yellow] --mosi [yellow]GP<num>[/yellow] --cs [yellow]GP<num>[/yellow] [[green]--miso GP<num>[/green]]
                         [[green]--slave-buf N[/green]]
  replx PORT spi write   [yellow]HEX...[/yellow]                 [dim](pre-load MISO)[/dim]
  replx PORT spi read    [[green]--timeout MS[/green]]         [dim](block until master sends)[/dim]
  replx PORT spi xfer    [yellow]HEX...[/yellow] [[green]--timeout MS[/green]]  [dim](MISO=TX, MOSI=RX)[/dim]
  replx PORT spi close

[bold cyan]Subcommands:[/bold cyan]
  [green]open[/green]     Configure SPI and save to agent. Validates on board.
           [dim]--slave: PIO+DMA slave mode (requires SpiSlave on device).[/dim]
           [dim]--miso is optional; master read/xfer require it.[/dim]
  [green]bus[/green]      Show saved SPI config.
  [green]write[/green]    Master: send hex to MOSI.  Slave: pre-load MISO buffer.
  [green]read[/green]     Master: receive NBYTES.    Slave: wait for master frame.
  [green]xfer[/green]     Master: write+receive.     Slave: load MISO, wait for RX frame.
  [green]close[/green]    Deinit SPI/Slave and clear bus config.

[bold cyan]Pin format:[/bold cyan]  [yellow]GP<num>[/yellow]  e.g. [cyan]GP2[/cyan], [cyan]GP10[/cyan]

[bold cyan]Channel resolution (master):[/bold cyan]
  RP2350    SPI0: GP2,GP6,GP18,GP22  SPI1: GP10,GP14,GP26
  ESP32     CH=1 for all pins

[bold cyan]Slave pin constraint:[/bold cyan]  MOSI = SCK + 1  [dim](e.g. SCK=GP2 → MOSI=GP3)[/dim]

[bold cyan]Options:[/bold cyan]
  [yellow]--sck GP<num>[/yellow]       SCK pin [red](required)[/red]
  [yellow]--mosi GP<num>[/yellow]      MOSI pin [red](required)[/red]
  [yellow]--miso GP<num>[/yellow]      MISO pin [dim](optional)[/dim]
  [yellow]--cs GP<num>[/yellow]        CS pin (open: slave only; write/read/xfer: master only)
  [yellow]--slave[/yellow]             Slave mode (open only)
  [yellow]--slave-buf N[/yellow]       Slave RX buffer bytes [dim](default: 8192)[/dim]
  [yellow]--baud N[/yellow]            Baud rate [dim](master, default: 1000000 = 1 MHz)[/dim]
  [yellow]--mode 0-3[/yellow]          SPI mode [dim](master only, default: 0)[/dim]
  [yellow]--bits 8|16[/yellow]         Word bits [dim](master only, default: 8)[/dim]
  [yellow]--lsb[/yellow]               LSB-first [dim](master only)[/dim]
  [yellow]--fill HH[/yellow]           Fill byte for master read [dim](default: 00)[/dim]
  [yellow]--text[/yellow]              Text mode for write/xfer [dim](supports \\n, \\r, \\t, \\\\, \\xHH)[/dim]
  [yellow]--timeout MS[/yellow]        Timeout ms for slave read/xfer [dim](default: 10000)[/dim]

[bold cyan]Examples:[/bold cyan]
  replx COM1 spi open --sck GP2 --mosi GP3 --miso GP4 --baud 50000000
  replx COM1 spi write 01 02 03 --cs GP5
  replx COM1 spi xfer 01 02 03 --cs GP5
  replx COM1 spi write --text "Hello\\n" --cs GP5
  replx COM1 spi xfer --text "Ping\\r\\n" --cs GP5
  replx COM1 spi close

  replx COM2 spi open --slave --sck GP2 --mosi GP3 --cs GP5
  replx COM2 spi read --timeout 10000
  replx COM2 spi open --slave --sck GP2 --mosi GP3 --cs GP5 --miso GP4
  replx COM2 spi write AA BB CC
  replx COM2 spi xfer AA BB CC --timeout 10000"""
    OutputHelper.print_panel(help_text, title="spi", border_style="help")


@app.command(name="spi", rich_help_panel="Hardware")
def spi_cmd(
    args: Optional[list[str]] = typer.Argument(None, help="Subcommand: open bus write read xfer close"),
    sck: Optional[str] = typer.Option(None, "--sck", metavar="GP<num>", help="SCK pin (open only)"),
    mosi: Optional[str] = typer.Option(None, "--mosi", metavar="GP<num>", help="MOSI pin (open only)"),
    miso: Optional[str] = typer.Option(None, "--miso", metavar="GP<num>", help="MISO pin (open only)"),
    baud: int = typer.Option(1_000_000, "--baud", metavar="N", help="Baud rate (default 1MHz)"),
    mode: int = typer.Option(0, "--mode", metavar="0-3", help="SPI mode"),
    bits: int = typer.Option(8, "--bits", metavar="8|16", help="Word bits"),
    lsb: bool = typer.Option(False, "--lsb", help="LSB-first bit order"),
    cs: Optional[str] = typer.Option(None, "--cs", metavar="GP<num>", help="CS pin"),
    fill: str = typer.Option("00", "--fill", metavar="HH", help="Fill byte for read"),
    text_mode: bool = typer.Option(False, "--text", help="Text mode for write/xfer"),
    slave: bool = typer.Option(False, "--slave", help="Slave mode (open only)"),
    slave_buf: int = typer.Option(8192, "--slave-buf", metavar="N", help="Slave RX buffer size"),
    timeout_ms: int = typer.Option(10_000, "--timeout", metavar="MS", help="Timeout ms for slave read/xfer"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True),
):
    if show_help:
        _print_spi_help()
        raise typer.Exit()
    if not args:
        OutputHelper.print_panel(
            "Subcommands: [bright_blue]open  bus  write  read  xfer  close[/bright_blue]\n\n"
            "  [bright_green]replx PORT spi open --sck GP2 --mosi GP3[/bright_green]\n"
            "  [bright_green]replx PORT spi write 01 02 03[/bright_green]\n"
            "  [bright_green]replx PORT spi read 4[/bright_green]\n\n"
            "Use [bright_blue]replx spi --help[/bright_blue] for details.",
            title="SPI",
            border_style="help",
        )
        raise typer.Exit(1)

    subcmd = args[0].lower()
    pos_args = args[1:]

    valid_subcmds = ('open', 'bus', 'write', 'read', 'xfer', 'close')
    if subcmd not in valid_subcmds:
        OutputHelper.print_panel(
            f"Unknown subcommand: {subcmd!r}\n\n"
            "Valid subcommands: " + "  ".join(valid_subcmds),
            title="SPI Error",
            border_style="error",
        )
        raise typer.Exit(1)

    _ensure_connected()

    if timeout_ms < 0:
        OutputHelper.print_panel("--timeout must be >= 0", title="SPI Error", border_style="error")
        raise typer.Exit(1)

    try:
        with _create_agent_client() as client:
            require_standard_hardware(client, 'spi')
            port = _get_device_port()

            if subcmd == 'bus':
                _subcmd_bus(client)
                return

            if subcmd == 'close':
                _subcmd_close(client)
                return

            if subcmd == 'open':
                core = _get_core(client, port)
                _subcmd_open(client, port, core, sck, mosi, miso,
                             baud, mode, bits, lsb, slave, slave_buf, cs)
                return

            if subcmd == 'write':
                _subcmd_write(client, pos_args, cs, text_mode)
            elif subcmd == 'read':
                _subcmd_read(client, pos_args, fill, cs, timeout_ms)
            elif subcmd == 'xfer':
                _subcmd_xfer(client, pos_args, cs, text_mode, timeout_ms)

    except typer.Exit:
        raise
    except ValueError as e:
        OutputHelper.print_panel(str(e), title="SPI Error", border_style="error")
        raise typer.Exit(1)
    except RuntimeError as e:
        OutputHelper.print_panel(str(e), title="SPI Error", border_style="error")
        raise typer.Exit(1)
