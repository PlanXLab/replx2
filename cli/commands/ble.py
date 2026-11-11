import json
import os
import signal
import sys
import time

import typer
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from ..agent.client import AgentClient
from ..app import app
from ..connection import _create_agent_client, _ensure_connected
from ..helpers import CONSOLE_WIDTH, OutputHelper, get_panel_box
from replx.terminal import IS_WINDOWS
from replx.utils.constants import CTRL_C


@app.command(
    name="ble",
    rich_help_panel="Connectivity",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def ble(
    args: list[str] = typer.Argument(None, help="BLE arguments"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True),
):
    if show_help:
        help_text = """\
Manage BLE on the connected MicroPython device.

[bold cyan]Usage:[/bold cyan]
    replx ble                                        [dim]# BLE adapter info and radio state[/dim]
    replx ble on                                     [dim]# Enable BLE radio[/dim]
    replx ble off                                    [dim]# Disable BLE radio[/dim]
    replx ble scan [yellow][refresh_ms][/yellow]                                  [dim]# Advertisement scan (q/Ctrl+C to stop)[/dim]
    replx ble advertise [yellow]DEVICE_NAME[/yellow] [OPTIONS]        [dim]# Broadcast advertisement[/dim]
        [dim]--service-uuid UUID                          # Advertised service UUID[/dim]
        [dim]--service-data UUID:hex:DATA                 # Service Data bytes[/dim]
        [dim]--service-data UUID:text:TEXT                # Service Data UTF-8 text[/dim]
        [dim]--manufacturer-data COMPANY_ID:hex:DATA      # Manufacturer Data bytes[/dim]
        [dim]--manufacturer-data COMPANY_ID:text:TEXT     # Manufacturer Data UTF-8 text[/dim]
        [dim]--duration-ms MS                             # Advertising interval (default: 1000)[/dim]
        [dim]--no-connect                                 # Broadcaster mode (non-connectable)[/dim]
    replx ble server [cyan]--svc UUID --char UUID[/cyan] [OPTIONS]     [dim]# Run GATT server (Ctrl+C to stop)[/dim]
    replx ble client [yellow]ADDR[/yellow] [cyan]--svc UUID --char UUID[/cyan] [OPTIONS] [dim]# Run GATT client (q/Ctrl+C to stop)[/dim]
    replx ble ping [yellow]ADDR[/yellow][cyan]/TYPE[/cyan]                           [dim]# Test connection, then disconnect[/dim]
    replx ble read [yellow]ADDR SVC_UUID CHAR_UUID[/yellow]           [dim]# Read characteristic[/dim]
    replx ble write [yellow]ADDR SVC_UUID CHAR_UUID HEX[/yellow]      [dim]# Write characteristic[/dim]
    replx ble stream send [yellow]ADDR PSM HEX[/yellow]               [dim]# L2CAP send[/dim]
    replx ble stream recv [yellow]PSM[/yellow]                        [dim]# L2CAP receive (Ctrl+C to stop)[/dim]

[bold cyan]server Options:[/bold cyan]
    [cyan]--svc UUID[/cyan]           Service UUID (e.g. 0x1234 or full 128-bit)
    [cyan]--char UUID[/cyan]          Characteristic UUID
    [cyan]--value hex:HEX[/cyan]      Initial value bytes
    [cyan]--value text:TEXT[/cyan]    Initial value UTF-8 text
    [cyan]--read[/cyan]               Add READ property
    [cyan]--write[/cyan]              Add WRITE property
    [cyan]--notify[/cyan]             Add NOTIFY property
    [cyan]--indicate[/cyan]           Add INDICATE property
    [cyan]--notify-on-change[/cyan]   Notify/indicate immediately when value changes
    [cyan]--name NAME[/cyan]          GAP device name (default: replx-ble)
    [cyan]--interval MS[/cyan]        Auto-notify interval in ms (requires --notify)

[bold cyan]client Options:[/bold cyan]
    [cyan]--svc UUID[/cyan]           Service UUID (e.g. 0x1234 or full 128-bit)
    [cyan]--char UUID[/cyan]          Characteristic UUID
    [cyan]--value hex:HEX[/cyan]      Initial value to write after connecting
    [cyan]--value text:TEXT[/cyan]    Initial UTF-8 text to write after connecting
    [cyan]--notify[/cyan]             Subscribe to notifications after connecting

[bold cyan]Address Format:[/bold cyan]
    [yellow]ADDR/1[/yellow] random address, [yellow]ADDR/0[/yellow] public address
    Use the Type shown by [bright_blue]replx ble scan[/bright_blue].

[bold cyan]Examples:[/bold cyan]
    replx ble
    replx ble scan
    replx ble advertise ticle-lite --service-data 1010:text:hello ticle --no-connect
    replx ble ping 4D:0E:55:65:19:15/1
    replx ble server --svc 1010 --char 1011 --name ticle-lite --read --write --notify 
                    --value text:hello world --notify-on-change
    replx ble client AA:BB:CC:DD:EE:FF --svc 1010 --char 1011 --notify

[bold cyan]Note:[/bold cyan]
    • scan / advertise / server / stream recv run until stopped
    • scan panel: named devices are shown by default, press s to pause/resume and f to show named/all
    • server panel: press v to switch the value view, c to change the value
    • client panel: press r to read, w to write, n to toggle notify, v to switch the value view"""
        OutputHelper.print_panel(help_text, title="ble", border_style="help")
        raise typer.Exit()

    _ensure_connected()
    client = _create_agent_client()
    from ._common import require_standard_hardware
    try:
        require_standard_hardware(client, 'ble')
    except ValueError as exc:
        OutputHelper.print_panel(str(exc), title="BLE Error", border_style="error")
        raise typer.Exit(1)

    if not args:
        _ble_info(client)
        return

    cmd = args[0]

    if cmd == "on":
        _ble_on(client)

    elif cmd == "off":
        _ble_off(client)

    elif cmd == "scan":
        refresh_ms = int(args[1]) if len(args) >= 2 else 1000
        _ble_scan(client, refresh_ms)

    elif cmd == "advertise":
        _ble_advertise_from_args(client, args[1:])

    elif cmd == "server":
        _ble_serve_from_args(client, args[1:])

    elif cmd == "client":
        _ble_client_from_args(client, args[1:])

    elif cmd == "ping":
        if len(args) < 2:
            OutputHelper.print_panel(
                "Usage: [bright_blue]replx ble ping ADDR[/bright_blue][cyan]/TYPE[/cyan]\n\n"
                "TYPE: [yellow]1[/yellow]=random, [yellow]0[/yellow]=public. Use the Type shown by [bright_blue]replx ble scan[/bright_blue].",
                title="BLE Error", border_style="error",
            )
            raise typer.Exit(1)
        _ble_ping(client, args[1])

    elif cmd == "read":
        if len(args) < 4:
            OutputHelper.print_panel(
                "Usage: [bright_blue]replx ble read ADDR SVC_UUID CHAR_UUID[/bright_blue]",
                title="BLE Error", border_style="error",
            )
            raise typer.Exit(1)
        _ble_read(client, args[1], args[2], args[3])

    elif cmd == "write":
        if len(args) < 5:
            OutputHelper.print_panel(
                "Usage: [bright_blue]replx ble write ADDR SVC_UUID CHAR_UUID HEX[/bright_blue]",
                title="BLE Error", border_style="error",
            )
            raise typer.Exit(1)
        _ble_write(client, args[1], args[2], args[3], args[4])

    elif cmd == "stream":
        from ._common import exec_code
        available = exec_code(
            client, "import bluetooth;print(hasattr(bluetooth.BLE(),'l2cap_connect'))", timeout=3.0
        )
        if available != 'True':
            OutputHelper.print_panel(
                "BLE L2CAP channels are not enabled in this firmware. "
                "Use GATT client/server/read/write instead; this is a separate feature from BLE radio support.",
                title="BLE Error", border_style="error",
            )
            raise typer.Exit(1)
        if len(args) < 2:
            OutputHelper.print_panel(
                "Usage: [bright_blue]replx ble stream send ADDR PSM HEX[/bright_blue] "
                "or [bright_blue]replx ble stream recv PSM[/bright_blue]",
                title="BLE Error", border_style="error",
            )
            raise typer.Exit(1)
        sub = args[1]
        if sub == "send":
            if len(args) < 5:
                OutputHelper.print_panel(
                    "Usage: [bright_blue]replx ble stream send ADDR PSM HEX[/bright_blue]",
                    title="BLE Error", border_style="error",
                )
                raise typer.Exit(1)
            _ble_stream_send(client, args[2], args[3], args[4])
        elif sub == "recv":
            if len(args) < 3:
                OutputHelper.print_panel(
                    "Usage: [bright_blue]replx ble stream recv PSM[/bright_blue]",
                    title="BLE Error", border_style="error",
                )
                raise typer.Exit(1)
            _ble_stream_recv(client, args[2])
        else:
            OutputHelper.print_panel(
                f"Unknown stream subcommand: [yellow]{sub}[/yellow]\n\n"
                "Use [bright_blue]replx ble --help[/bright_blue] for usage.",
                title="BLE Error", border_style="error",
            )
            raise typer.Exit(1)

    else:
        OutputHelper.print_panel(
            f"Unknown subcommand: [yellow]{cmd}[/yellow]\n\n"
            "Use [bright_blue]replx ble --help[/bright_blue] for usage.",
            title="BLE Error", border_style="error",
        )
        raise typer.Exit(1)


_AIOBLE_CHECK = '''\
import io
if not hasattr(io, 'IOBase'):
    class _IOBase: pass
    io.IOBase = _IOBase
import asyncio
asyncio.IOBase = io.IOBase
try:
    import uasyncio
    uasyncio.IOBase = io.IOBase
except ImportError:
    pass
try:
    import aioble
except ImportError:
    import json
    print(json.dumps({"error": "aioble not found"}))
    raise SystemExit
'''

def _parse_uuid(uuid_str: str) -> str:
    s = uuid_str.strip()
    if s.lower().startswith("0x"):
        return s 
    try:
        int(s, 16)
        return f"0x{s}"
    except ValueError:
        pass
    return f'"{s}"'


def _hex_to_bytes_expr(hex_str: str) -> str:
    h = hex_str.strip().replace(" ", "").upper()
    return "bytes.fromhex('" + h + "')"


def _addr_to_parts(addr: str) -> tuple[str, str]:
    if "/" in addr:
        addr_str, addr_type_str = addr.rsplit("/", 1)
        addr_type = int(addr_type_str)
    else:
        addr_str = addr
        addr_type = 1  
    octets = addr_str.split(":")
    byte_vals = ", ".join(str(int(o, 16)) for o in octets)
    return f"bytes([{byte_vals}])", str(addr_type)


def _exec(client: AgentClient, code: str, timeout: float = 15.0) -> dict:
    result = client.send_command("exec", code=code, timeout=timeout, max_retries=1)
    output = result.get("output", "").strip()
    if not output:
        raise RuntimeError("No BLE response from device")
    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass
    raise RuntimeError(f"Invalid BLE response: {output}")


def _check_aioble(data: dict) -> bool:
    if data.get("error") == "aioble not found":
        OutputHelper.print_panel(
            "aioble is not installed on the device.\n\n"
            "Install it with: [bright_blue]replx mip install aioble[/bright_blue]",
            title="BLE Error", border_style="error",
        )
        return False
    return True


def _ble_info(client: AgentClient):
    code = '''
import bluetooth, json

def _cfg(ble, key):
    try:
        return ble.config(key)
    except (ValueError, OSError):
        return None

ble = bluetooth.BLE()
result = {"active": ble.active(), "info_available": False}

if result["active"]:
    mac_raw = ble.config("mac")
    addr_type = mac_raw[0]
    mac_bytes = mac_raw[1]
    result.update({
        "info_available": True,
        "mac": ":".join("%02X" % b for b in mac_bytes),
        "addr_type": addr_type,
        "addr_mode": _cfg(ble, "addr_mode"),
        "gap_name": _cfg(ble, "gap_name"),
        "mtu": _cfg(ble, "mtu"),
    })
print(json.dumps(result))
'''
    try:
        data = _exec(client, code)
        lines = []
        if data.get("active"):
            lines.append(f"  Radio:     [green]enabled[/green]")
        else:
            lines.append(f"  Radio:     [dim]disabled[/dim]")

        if data.get("info_available"):
            lines.append(f"  MAC:       [bright_cyan]{data.get('mac', '?')}[/bright_cyan]")
            lines.append(f"  Addr type: {data.get('addr_type', '?')} "
                         f"({'random' if data.get('addr_type') == 1 else 'public'})")
            if data.get("addr_mode") is not None:
                lines.append(f"  Addr mode: {data['addr_mode']}")
            if data.get("gap_name") is not None:
                lines.append(f"  GAP name:  {data['gap_name']}")
            if data.get("mtu") is not None:
                lines.append(f"  MTU:       {data['mtu']} bytes")
        else:
            lines.append("  Info:      enable the radio with ble on to query MAC/GAP/MTU")
        OutputHelper.print_panel("\n".join(lines), title="BLE Status", border_style="data")
    except typer.Exit:
        raise
    except Exception as e:
        OutputHelper.print_panel(f"Failed to get BLE status: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)


def _ble_on(client: AgentClient):
    code = '''
import bluetooth, json, sys, time

def _cfg(ble, key):
    try:
        return ble.config(key)
    except (ValueError, OSError):
        return None

ble = bluetooth.BLE()
ble.active(True)
time.sleep_ms(200)

mac_raw = ble.config("mac")
addr_type = mac_raw[0]
mac_bytes = mac_raw[1]
print(json.dumps({
    "ok": ble.active(),
    "mac": ":".join("%02X" % b for b in mac_bytes),
    "addr_type": addr_type,
    "gap_name": _cfg(ble, "gap_name"),
    "mtu": _cfg(ble, "mtu"),
}))
'''
    try:
        data = _exec(client, code)
        if data.get("ok"):
            lines = [
                "BLE radio enabled.",
                f"  MAC:       [bright_cyan]{data.get('mac', '?')}[/bright_cyan]",
                f"  Addr type: {data.get('addr_type', '?')} "
                f"({'random' if data.get('addr_type') == 1 else 'public'})",
                f"  GAP name:  {data.get('gap_name', '?')}",
                f"  MTU:       {data.get('mtu', '?')} bytes",
            ]
            OutputHelper.print_panel("\n".join(lines), title="BLE On", border_style="success")
        else:
            raise RuntimeError("BLE activation returned False")
    except Exception as e:
        OutputHelper.print_panel(f"Failed to enable BLE: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)


def _ble_off(client: AgentClient):
    code = '''
import bluetooth, json, time
ble = bluetooth.BLE()
try:
    ble.gap_scan(None)
except Exception:
    pass
try:
    ble.gap_advertise(None)
except Exception:
    pass
ble.active(False)
time.sleep_ms(100)
print(json.dumps({"ok": True, "active": ble.active()}))
'''
    try:
        data = _exec(client, code)
        if data.get("ok") and not data.get("active"):
            OutputHelper.print_panel("BLE interface disabled.", title="BLE Off", border_style="neutral")
        else:
            OutputHelper.print_panel("BLE deactivation returned unexpectedly.", title="BLE Off", border_style="warning")
    except Exception as e:
        OutputHelper.print_panel(f"Failed to disable BLE: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)


def _ble_scan(client: AgentClient, refresh_ms: int):
    try:
        refresh_ms = int(refresh_ms)
    except (TypeError, ValueError):
        refresh_ms = 1000
    refresh_ms = max(250, min(refresh_ms, 2000))

    code = f'''
import bluetooth, json, sys, time

_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6
_REFRESH_MS = {refresh_ms}
_MAX_DEVICES = 48
_RECENT_ADV_MS = 2500

def _uuid128(data):
    rev = bytearray(16)
    for i in range(16):
        rev[i] = data[15 - i]
    hx = "".join("%02x" % b for b in rev)
    return hx[0:8] + "-" + hx[8:12] + "-" + hx[12:16] + "-" + hx[16:20] + "-" + hx[20:32]

_AD_TYPES = {{
    0x01: "Flags",
    0x02: "Incomplete 16-bit UUIDs",
    0x03: "Complete 16-bit UUIDs",
    0x04: "Incomplete 32-bit UUIDs",
    0x05: "Complete 32-bit UUIDs",
    0x06: "Incomplete 128-bit UUIDs",
    0x07: "Complete 128-bit UUIDs",
    0x08: "Shortened Local Name",
    0x09: "Complete Local Name",
    0x0A: "TX Power",
    0x19: "Appearance",
    0x16: "Service Data 16-bit",
    0x20: "Service Data 32-bit",
    0x21: "Service Data 128-bit",
    0xFF: "Manufacturer Data",
}}

def _hex(data):
    return "".join("%02X" % b for b in bytes(data))

def _adv_type_name(value):
    names = {{
        0: "ADV_IND",
        1: "ADV_DIRECT_IND",
        2: "ADV_SCAN_IND",
        3: "ADV_NONCONN_IND",
        4: "SCAN_RSP",
    }}
    return names.get(value, str(value))

def _flags_text(data):
    if not data:
        return None
    value = data[0]
    names = []
    if value & 0x01:
        names.append("LE Limited Discoverable")
    if value & 0x02:
        names.append("LE General Discoverable")
    if value & 0x04:
        names.append("BR/EDR Not Supported")
    if value & 0x08:
        names.append("LE+BR/EDR Controller")
    if value & 0x10:
        names.append("LE+BR/EDR Host")
    return ", ".join(names) or "0x%02X" % value

def _decode_ad_fields(payload):
    fields = []
    services = []
    summary = []
    name = None
    i = 0
    n = len(payload)
    while i + 1 < n:
        size = payload[i]
        if size == 0:
            break
        typ = payload[i + 1]
        end = i + 1 + size
        data = payload[i + 2:end]
        label = _AD_TYPES.get(typ, "AD 0x%02X" % typ)
        value = None
        if typ == 0x01:
            value = _flags_text(data)
        elif typ in (0x08, 0x09):
            try:
                value = bytes(data).decode()
                name = value
            except Exception:
                value = _hex(data)
        elif typ in (0x02, 0x03):
            values = []
            for j in range(0, len(data) - 1, 2):
                values.append("0x%04X" % (data[j] | (data[j + 1] << 8)))
            services.extend(values)
            value = ", ".join(values)
        elif typ in (0x04, 0x05):
            values = []
            for j in range(0, len(data) - 3, 4):
                values.append("0x%08X" % (data[j] | (data[j + 1] << 8) | (data[j + 2] << 16) | (data[j + 3] << 24)))
            services.extend(values)
            value = ", ".join(values)
        elif typ in (0x06, 0x07):
            values = []
            for j in range(0, len(data) - 15, 16):
                values.append(_uuid128(data[j:j + 16]))
            services.extend(values)
            value = ", ".join(values)
        elif typ == 0x16 and len(data) >= 2:
            svc = "0x%04X" % (data[0] | (data[1] << 8))
            services.append(svc)
            value = svc + ":" + _hex(data[2:])
        elif typ == 0x20 and len(data) >= 4:
            svc = "0x%08X" % (data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24))
            services.append(svc)
            value = svc + ":" + _hex(data[4:])
        elif typ == 0x21 and len(data) >= 16:
            svc = _uuid128(data[0:16])
            services.append(svc)
            value = svc + ":" + _hex(data[16:])
        elif typ == 0x0A and data:
            tx = data[0]
            if tx > 127:
                tx -= 256
            value = "%ddBm" % tx
        elif typ == 0x19 and len(data) >= 2:
            value = "0x%04X" % (data[0] | (data[1] << 8))
        elif typ == 0xFF:
            value = _hex(data)
        else:
            value = _hex(data)

        field = {{
            "type": "0x%02X" % typ,
            "name": label,
            "len": len(data),
            "hex": _hex(data),
            "value": value,
        }}
        if len(fields) < 8:
            fields.append(field)
        if len(summary) < 4:
            if value:
                summary.append(label + "=" + value)
            else:
                summary.append(label)
        i = end
    return {{"fields": fields, "services": services, "summary": summary, "name": name}}

ble = bluetooth.BLE()
done = [False]
results = {{}}
attempts = []
total_reports = [0]
changed_keys = []
changed_seen = {{}}
was_active = False
started_at = time.ticks_ms()
scan_active = [False]
input_poll = [None]
input_buffer = []

try:
    was_active = ble.active()
except Exception:
    pass

def _mark_changed(key):
    if key in changed_seen:
        return
    changed_seen[key] = True
    changed_keys.append(key)

def _append_unique(target, value, limit):
    if value and value not in target and len(target) < limit:
        target.append(value)

def _refresh_recent(entry, now):
    recent = entry.get("recent") or []
    kept = []
    for item in recent:
        try:
            if time.ticks_diff(now, item.get("at", now)) <= _RECENT_ADV_MS:
                kept.append(item)
        except Exception:
            pass
    entry["recent"] = kept

    adv_types = []
    services = []
    payloads = []
    ad_summary = []
    fields = []
    field_seen = {{}}
    name = None

    for item in kept:
        _append_unique(adv_types, item.get("adv_type"), 6)
        _append_unique(payloads, item.get("raw"), 2)
        decoded = item.get("decoded") or {{}}
        if decoded.get("name"):
            name = decoded.get("name")
        for svc in decoded.get("services") or []:
            _append_unique(services, svc, 8)
        for summary in decoded.get("summary") or []:
            _append_unique(ad_summary, summary, 4)
        for field in decoded.get("fields") or []:
            field_key = str(field.get("type")) + ":" + str(field.get("hex"))
            if field_key not in field_seen and len(fields) < 16:
                field_seen[field_key] = True
                fields.append(field)

    entry["adv_types"] = adv_types
    entry["services"] = services
    entry["payloads"] = payloads
    entry["ad_summary"] = ad_summary
    entry["fields"] = fields
    entry["name"] = name

def _public_entry(entry):
    keys = (
        "key", "addr", "addr_type", "addr_type_label", "adv_type", "adv_types",
        "rssi", "last_rssi", "best_rssi", "name", "services", "payloads", "payload_len",
        "ad_summary", "fields", "reports",
    )
    output = {{}}
    for key in keys:
        output[key] = entry.get(key)
    return output

def _irq(event, data):
    if event == _IRQ_SCAN_RESULT:
        addr_type, addr, adv_type, rssi, adv_data = data
        total_reports[0] += 1
        addr_str = ":".join("%02X" % b for b in bytes(addr))
        payload = bytes(adv_data)
        try:
            decoded = _decode_ad_fields(payload)
        except MemoryError:
            gc.collect()
            decoded = {{"fields": [], "services": [], "summary": [], "name": None}}
        raw_hex = _hex(payload)
        key = str(addr_type) + "/" + addr_str
        entry = results.get(key)
        if entry is None:
            if len(results) >= _MAX_DEVICES:
                return
            entry = {{
                "key": key,
                "addr": addr_str,
                "addr_type": addr_type,
                "addr_type_label": "random" if addr_type else "public",
                "adv_type": adv_type,
                "adv_types": [],
                "rssi": rssi,
                "last_rssi": rssi,
                "best_rssi": rssi,
                "name": None,
                "services": [],
                "payloads": [],
                "payload_len": len(payload),
                "ad_summary": [],
                "fields": decoded.get("fields", []),
                "recent": [],
                "reports": 0,
            }}
            results[key] = entry

        entry["reports"] += 1
        entry["last_rssi"] = rssi
        entry["rssi"] = rssi
        entry["adv_type"] = adv_type
        entry["payload_len"] = len(payload)
        if rssi > entry.get("best_rssi", -999):
            entry["best_rssi"] = rssi
        now = time.ticks_ms()

        adv_name = _adv_type_name(adv_type)
        recent = entry.get("recent") or []
        found = False
        for item in recent:
            if item.get("raw") == raw_hex and item.get("adv_type") == adv_name:
                item["at"] = now
                item["rssi"] = rssi
                item["decoded"] = decoded
                found = True
                break
        if not found:
            recent.append({{"raw": raw_hex, "adv_type": adv_name, "at": now, "rssi": rssi, "decoded": decoded}})
            if len(recent) > 3:
                recent = recent[-3:]
        entry["recent"] = recent
        _refresh_recent(entry, now)
        _mark_changed(key)
    elif event == _IRQ_SCAN_DONE:
        scan_active[0] = False
        done[0] = True

def _setup_input():
    try:
        try:
            import select as _select
        except ImportError:
            import uselect as _select
        poll = _select.poll()
        poll.register(sys.stdin, _select.POLLIN)
        input_poll[0] = poll
    except Exception:
        input_poll[0] = None

def _handle_input_command(command):
    prefix = "@replx:scan:"
    if not command.startswith(prefix):
        return
    action = command[len(prefix):].strip()
    if action == "pause":
        try:
            ble.gap_scan(None)
        except Exception:
            pass
        scan_active[0] = False
        _snapshot("paused", devices=[])
    elif action == "resume":
        error = _start_scan(True)
        if error:
            _snapshot("error", error)
        else:
            _snapshot("resumed", devices=_pop_changed(4))

def _read_input_commands():
    poll = input_poll[0]
    if poll is None:
        return
    while True:
        try:
            events = poll.poll(0)
        except Exception:
            input_poll[0] = None
            return
        if not events:
            return
        try:
            chunk = sys.stdin.read(1)
        except Exception:
            input_poll[0] = None
            return
        if not chunk:
            return
        if isinstance(chunk, bytes):
            try:
                chunk = chunk.decode()
            except Exception:
                continue
        if chunk in ("\\r", "\\n"):
            command = "".join(input_buffer)
            del input_buffer[:]
            _handle_input_command(command.strip())
        else:
            input_buffer.append(chunk)
            if len(input_buffer) > 256:
                del input_buffer[:]

def _ensure_active():
    try:
        if ble.active():
            return
    except Exception:
        pass
    try:
        ble.active(False)
    except Exception:
        pass
    time.sleep_ms(200)
    ble.active(True)
    time.sleep_ms(500)

def _reset_ble():
    try:
        ble.gap_scan(None)
    except Exception:
        pass
    try:
        ble.active(False)
    except Exception:
        pass
    time.sleep_ms(300)
    ble.active(True)
    time.sleep_ms(1000)

def _start_scan(active):
    try:
        ble.gap_scan(None)
    except Exception:
        pass
    time.sleep_ms(100)
    try:
        ble.gap_scan(0, 30000, 30000, active)
        scan_active[0] = True
        return None
    except TypeError:
        try:
            ble.gap_scan(0, 30000, 30000)
            scan_active[0] = True
            return None
        except Exception as exc:
            scan_active[0] = False
            return exc
    except Exception as exc:
        scan_active[0] = False
        return exc

def _restore_if_needed():
    try:
        ble.gap_scan(None)
    except Exception:
        pass
    if not was_active:
        try:
            ble.active(False)
        except Exception:
            pass

def _pop_changed(limit):
    devices = []
    while changed_keys and len(devices) < limit:
        key = changed_keys.pop(0)
        try:
            del changed_seen[key]
        except Exception:
            pass
        entry = results.get(key)
        if entry:
            _refresh_recent(entry, time.ticks_ms())
            devices.append(_public_entry(entry))
    return devices

def _snapshot(event="scan", error=None, devices=None):
    output = {{
        "event": event,
        "attempts": attempts,
        "elapsed_ms": time.ticks_diff(time.ticks_ms(), started_at),
        "reports": total_reports[0],
        "scan_active": scan_active[0],
    }}
    if devices is not None:
        output["devices"] = devices
    if error:
        output["error"] = repr(error)
    try:
        print(json.dumps(output))
    except MemoryError:
        try:
            gc.collect()
            compact = {{
                "event": event,
                "elapsed_ms": time.ticks_diff(time.ticks_ms(), started_at),
                "reports": total_reports[0],
            }}
            print(json.dumps(compact))
        except Exception:
            pass
    try:
        gc.collect()
    except Exception:
        pass

def _emit_updates(event="scan"):
    _snapshot(event, devices=_pop_changed(1))

try:
    _ensure_active()
    ble.irq(_irq)
    _setup_input()
    before = len(results)
    error = _start_scan(True)
    attempts.append({{
        "label": "active",
        "active": True,
        "done": done[0],
        "elapsed_ms": time.ticks_diff(time.ticks_ms(), started_at),
        "count": len(results),
        "new": len(results) - before,
        "error": repr(error) if error else None,
    }})
    if error:
        _reset_ble()
        ble.irq(_irq)
        before = len(results)
        error = _start_scan(True)
        attempts.append({{
            "label": "active-after-error-reset",
            "active": True,
            "done": done[0],
            "elapsed_ms": time.ticks_diff(time.ticks_ms(), started_at),
            "count": len(results),
            "new": len(results) - before,
            "error": repr(error) if error else None,
        }})
    if error:
        _restore_if_needed()
        _snapshot("error", error)
    else:
        _emit_updates("scan")
        last_emit = time.ticks_ms()
        while True:
            _read_input_commands()
            now = time.ticks_ms()
            if changed_keys and time.ticks_diff(now, last_emit) >= 250:
                _emit_updates("scan")
                last_emit = now
            elif time.ticks_diff(now, last_emit) >= _REFRESH_MS:
                _emit_updates("scan")
                last_emit = now
            time.sleep_ms(50)
except KeyboardInterrupt:
    _restore_if_needed()
    _snapshot("stopped")
except Exception as exc:
    _restore_if_needed()
    _snapshot("error", exc)
'''

    console = OutputHelper.make_console(width=CONSOLE_WIDTH, emoji=False)
    device_map = {}
    source_identity_map = {}
    active_ttl_s = 12.0
    ui_state = {
        "devices": [],
        "attempts": [],
        "elapsed_ms": 0,
        "reports": 0,
        "page": 0,
        "selected_key": None,
        "number_buffer": "",
        "number_updated_at": 0.0,
        "status": "Starting BLE scan...",
        "error": None,
        "stopping": False,
        "scan_paused": False,
        "name_filter": "named",
    }
    pending_input: list[bytes] = []
    stdout_buffer = bytearray()
    stderr_buffer = bytearray()
    prune_state = {"last": 0.0, "count": 0}
    sort_state = {"keys": [], "last": 0.0, "interval": 2.0, "dirty": True}
    stop_requested = False
    live_ref: list[Live | None] = [None]

    old_settings = None
    fd = None
    if not IS_WINDOWS:
        import termios
        import tty
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except Exception:
            old_settings = None

    def _short(value, limit=32):
        text = str(value or "-")
        if len(text) <= limit:
            return text
        return text[:max(0, limit - 3)] + "..."

    def _device_has_name(device):
        return bool(str(device.get("name") or "").strip())

    def _passes_name_filter(device):
        return ui_state.get("name_filter") != "named" or _device_has_name(device)

    def _filter_label():
        return "named" if ui_state.get("name_filter") == "named" else "all"

    def _visible_devices():
        now = time.time()
        expired_keys = [] if ui_state.get("scan_paused") else [
            key for key, device in device_map.items()
            if now - device.get("last_seen_at", now) > active_ttl_s
        ]
        for key in expired_keys:
            device = device_map.pop(key, None)
            for source_key in (device or {}).get("source_keys", []):
                if source_identity_map.get(source_key) == key:
                    del source_identity_map[source_key]
        if expired_keys:
            sort_state["keys"] = [key for key in sort_state.get("keys", []) if key in device_map]
            sort_state["dirty"] = True

        current_keys = [key for key, device in device_map.items() if _passes_name_filter(device)]
        current_key_set = set(current_keys)
        known_keys = [key for key in sort_state.get("keys", []) if key in current_key_set]
        missing_keys = [key for key in current_keys if key not in known_keys]
        if missing_keys:
            known_keys.extend(sorted(
                missing_keys,
                key=lambda key: (_ble_rssi_value(device_map[key].get("rssi")) or -999, device_map[key].get("reports") or 0),
                reverse=True,
            ))
            sort_state["keys"] = known_keys
            sort_state["dirty"] = True

        sort_frozen = bool(ui_state.get("number_buffer") or ui_state.get("selected_key"))
        should_sort = not sort_frozen and (
            not sort_state.get("keys") or now - sort_state.get("last", 0.0) >= sort_state.get("interval", 2.0)
        )
        if should_sort:
            sort_state["keys"] = sorted(
                current_keys,
                key=lambda key: (_ble_rssi_value(device_map[key].get("rssi")) or -999, device_map[key].get("reports") or 0),
                reverse=True,
            )
            sort_state["last"] = now
            sort_state["dirty"] = False

        return [device_map[key] for key in sort_state.get("keys", []) if key in device_map]

    def _find_selected_device():
        selected_key = ui_state.get("selected_key")
        if not selected_key:
            return None, None
        for index, device in enumerate(_visible_devices(), start=1):
            if device.get("key") == selected_key:
                return index, device
        ui_state["selected_key"] = None
        return None, None

    def _signal_cell(device):
        signal = Text()
        signal.append_text(_ble_signal_icon(device.get("rssi")))
        signal.append(" ")
        signal.append_text(_ble_signal_text(device.get("rssi")))
        return signal

    def _device_source_key(device):
        return device.get("key") or f"{device.get('addr_type', '?')}/{device.get('addr', '?')}"

    def _stable_ad_parts(device, allow_uuid_lists=False):
        parts = []
        for field in device.get("fields") or []:
            field_type = field.get("type")
            if field_type in ("0x01", "0x08", "0x09", "0x0A"):
                continue
            if field_type in ("0x02", "0x03", "0x04", "0x05", "0x06", "0x07") and not allow_uuid_lists:
                continue
            value = field.get("value") or field.get("hex")
            if value:
                parts.append(f"{field_type}:{value}")
        return parts

    def _identity_key(device):
        source_key = _device_source_key(device)
        if device.get("addr_type_label") == "public" or str(device.get("addr_type", "")) == "0":
            return source_key

        name = str(device.get("name") or "").strip()
        services = sorted(str(item) for item in (device.get("services") or []) if item)
        if name and services:
            return "id/name-services/" + name + "/" + ",".join(services[:6])

        stable_parts = _stable_ad_parts(device, allow_uuid_lists=bool(name))
        if name and stable_parts:
            return "id/name-data/" + name + "/" + "|".join(stable_parts[:3])
        if name:
            return "id/name/" + name
        if stable_parts:
            return "id/data/" + "|".join(stable_parts[:3])
        return source_key

    def _append_unique(target, values, limit):
        for value in values or []:
            if value and value not in target and len(target) < limit:
                target.append(value)

    def _absorb_device(target, update):
        source_key = _device_source_key(update)
        if source_key not in target.get("source_keys", []):
            target.setdefault("source_keys", []).append(source_key)
        if update.get("addr") and update.get("addr") not in target.get("addresses", []):
            target.setdefault("addresses", []).append(update.get("addr"))
        target.setdefault("address_reports", {})[source_key] = update.get("reports", 0)
        target["reports"] = sum(target.get("address_reports", {}).values())
        target["last_rssi"] = update.get("last_rssi", target.get("last_rssi"))
        target["rssi"] = update.get("rssi", target.get("rssi"))
        target["adv_type"] = update.get("adv_type", target.get("adv_type"))
        target["payload_len"] = update.get("payload_len", target.get("payload_len"))
        target["last_seen_at"] = time.time()

        current_best_rssi = _ble_rssi_value(target.get("best_rssi"))
        update_rssi = _ble_rssi_value(update.get("rssi"))
        if current_best_rssi is None or (update_rssi is not None and update_rssi > current_best_rssi):
            target["best_rssi"] = update_rssi
            for key in ("addr", "addr_type", "addr_type_label", "fields"):
                target[key] = update.get(key, target.get(key))
        if update.get("name"):
            target["name"] = update.get("name")
        _append_unique(target.setdefault("adv_types", []), update.get("adv_types"), 8)
        _append_unique(target.setdefault("services", []), update.get("services"), 12)
        _append_unique(target.setdefault("payloads", []), update.get("payloads"), 6)
        _append_unique(target.setdefault("ad_summary", []), update.get("ad_summary"), 12)
        if update.get("fields") and not target.get("fields"):
            target["fields"] = update.get("fields")

    def _merge_device_update(device):
        source_key = _device_source_key(device)
        preferred_key = _identity_key(device)
        identity_key = source_identity_map.get(source_key)

        if identity_key and identity_key != preferred_key and identity_key == source_key and preferred_key != source_key:
            old_entry = device_map.pop(identity_key, None)
            identity_key = preferred_key
            if old_entry is not None:
                existing_preferred = device_map.get(identity_key)
                if existing_preferred is None:
                    old_entry["key"] = identity_key
                    old_entry["identity"] = "advertisement"
                    device_map[identity_key] = old_entry
                else:
                    _absorb_device(existing_preferred, old_entry)

        if identity_key is None:
            identity_key = preferred_key
        source_identity_map[source_key] = identity_key

        existing = device_map.get(identity_key)
        if existing is None:
            merged = dict(device)
            merged["key"] = identity_key
            merged["source_keys"] = [source_key]
            merged["addresses"] = [device.get("addr")] if device.get("addr") else []
            merged["address_reports"] = {source_key: device.get("reports", 0)}
            merged["identity"] = "address" if identity_key == source_key else "advertisement"
            if merged.get("best_rssi") is None:
                merged["best_rssi"] = merged.get("rssi")
            merged["last_seen_at"] = time.time()
            device_map[identity_key] = merged
            sort_state["dirty"] = True
            return

        _absorb_device(existing, device)
        sort_state["dirty"] = True

    def _page_size():
        try:
            terminal_height = console.size.height
        except Exception:
            terminal_height = 24
        return max(6, min(18, terminal_height - 8))

    def _render_list():
        devices = _visible_devices()
        page_size = _page_size()
        page_count = max(1, (len(devices) + page_size - 1) // page_size)
        if ui_state.get("page", 0) >= page_count:
            ui_state["page"] = page_count - 1
        if ui_state.get("page", 0) < 0:
            ui_state["page"] = 0
        page = ui_state.get("page", 0)
        page_start = page * page_size
        page_devices = devices[page_start:page_start + page_size]
        table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
        table.add_column("No", justify="right", width=3)
        table.add_column("Address", style="bright_cyan", no_wrap=True, width=17)
        table.add_column("Type", width=5)
        table.add_column("Signal", justify="right", width=11)
        table.add_column("Name", style="green", width=18)
        table.add_column("Services / PDU", width=20, no_wrap=True, overflow="crop")

        if page_devices:
            for index, device in enumerate(page_devices, start=page_start + 1):
                addr_type = device.get("addr_type_label") or str(device.get("addr_type", "?"))
                if addr_type == "public":
                    addr_type = "pub"
                elif addr_type == "random":
                    addr_type = "rand"
                services = device.get("services") or []
                adv_types = device.get("adv_types") or [str(device.get("adv_type", "?"))]
                summary_items = services if services else adv_types
                summary = ", ".join(summary_items[:2]) if summary_items else "-"
                if len(summary_items) > 2:
                    summary += ", ..."
                table.add_row(
                    str(index),
                    Text(device.get("addr", "?"), style="bright_cyan"),
                    addr_type,
                    _signal_cell(device),
                    Text(_short(device.get("name"), 18), style="green"),
                    _short(summary, 20),
                )
        else:
            table.add_row("-", "-", "-", Text("scanning", style="dim"), "-", "-")

        footer = Text("\n")
        if ui_state.get("number_buffer"):
            footer.append(f"Number: {ui_state['number_buffer']}  ", style="bright_yellow")
            footer.append("Order frozen. ", style="dim")
        footer.append("Press number for details. ", style="dim")
        if page_count > 1:
            footer.append(f"Page {page + 1}/{page_count}: n({chr(0x2192)})/p({chr(0x2190)}). ", style="dim")
        footer.append("s(pause/resume), f(named/all). ", style="dim")
        footer.append("q/Ctrl+C to stop.", style="dim")
        status = Text()
        if ui_state.get("stopping"):
            status.append("Stopping scan...", style="yellow")
        elif ui_state.get("scan_paused"):
            status.append(
                f"Paused, {len(devices)} shown ({_filter_label()}), {len(device_map)} tracked, "
                f"{ui_state.get('reports', 0)} report(s)",
                style="yellow",
            )
        elif ui_state.get("error"):
            status.append(f"Scan error: {ui_state['error']}", style="red")
        elif devices:
            shown_to = min(page_start + len(page_devices), len(devices))
            status.append(
                f"{len(devices)} shown ({_filter_label()}), showing {page_start + 1}-{shown_to}, "
                f"{len(device_map)} tracked, "
                f"{ui_state.get('reports', 0)} report(s), "
                f"{int((ui_state.get('elapsed_ms') or 0) / 1000)}s",
                style="dim",
            )
        else:
            status = Spinner("dots", text=Text(f" Scanning for {_filter_label()} advertisements...", style="bright_cyan"))
        return Group(status, table, footer)

    def _render_detail(device, number):
        info = Table(show_header=False, box=None, padding=(0, 1))
        info.add_column("Field", style="cyan", no_wrap=True, width=14)
        info.add_column("Value", overflow="fold")
        info.add_row("No", str(number or "?"))
        info.add_row("Address", device.get("addr", "?"))
        addresses = device.get("addresses") or []
        if len(addresses) > 1:
            info.add_row("Seen addrs", "\n".join(addresses[-8:]))
        info.add_row("Type", device.get("addr_type_label") or str(device.get("addr_type", "?")))
        if device.get("identity") == "advertisement":
            info.add_row("Identity", "advertisement fingerprint")
        info.add_row("Signal", f"{device.get('rssi', '?')} dBm current / {device.get('best_rssi', '?')} dBm best")
        info.add_row("Name", device.get("name") or "-")
        info.add_row("PDU", ", ".join(device.get("adv_types") or [str(device.get("adv_type", "?"))]))
        info.add_row("Reports", str(device.get("reports", 0)))
        info.add_row("Services", ", ".join(device.get("services") or []) or "-")
        info.add_row("Payloads", "\n".join(device.get("payloads") or []) or "-")
        summary = "; ".join(device.get("ad_summary") or [])
        info.add_row("Summary", summary or "-")

        fields = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 1))
        fields.add_column("Type", no_wrap=True, width=8)
        fields.add_column("Name", width=24)
        fields.add_column("Len", justify="right", width=5)
        fields.add_column("Value", overflow="fold")
        ad_fields = device.get("fields") or []
        if ad_fields:
            for field in ad_fields:
                value = field.get("value") or field.get("hex") or "-"
                fields.add_row(
                    field.get("type", "?"),
                    field.get("name", "?"),
                    str(field.get("len", "?")),
                    str(value),
                )
        else:
            fields.add_row("-", "No decoded AD fields", "-", "-")

        footer = Text("Press any key to return. Press q or Ctrl+C to stop.", style="dim")
        return Group(info, Text("Advertisement data", style="bold cyan"), fields, footer)

    def _render_panel():
        number, device = _find_selected_device()
        if device is not None:
            body = _render_detail(device, number)
            title = f"BLE Scan Detail #{number}"
        else:
            body = _render_list()
            paused = " paused" if ui_state.get("scan_paused") else ""
            title = f"BLE Advertisement Scan ({len(_visible_devices())}, {_filter_label()}){paused}"
        return Panel(
            body,
            title=title,
            title_align="left",
            border_style=OutputHelper._resolve_category_color("data"),
            box=get_panel_box(),
            width=CONSOLE_WIDTH,
        )

    def _update_live():
        live = live_ref[0]
        if live is not None:
            live.update(_render_panel())

    def _commit_number(force=False):
        digits = ui_state.get("number_buffer") or ""
        if not digits:
            return
        devices = _visible_devices()
        if not devices:
            ui_state["number_buffer"] = ""
            return
        try:
            value = int(digits)
        except ValueError:
            ui_state["number_buffer"] = ""
            return
        max_digits = len(str(len(devices)))
        if value <= 0:
            ui_state["number_buffer"] = ""
        elif value <= len(devices) and (force or len(digits) >= max_digits or value * 10 > len(devices)):
            ui_state["selected_key"] = devices[value - 1].get("key")
            ui_state["number_buffer"] = ""
        elif value > len(devices):
            ui_state["number_buffer"] = ""

    def _read_key():
        try:
            if IS_WINDOWS:
                import msvcrt
                if not msvcrt.kbhit():
                    return None
                key = msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    msvcrt.getwch()
                    return None
                return key

            import select
            if fd is None:
                return None
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if not ready:
                return None
            data = os.read(fd, 1)
            if data == CTRL_C:
                return "\x03"
            try:
                return data.decode("utf-8")
            except Exception:
                return None
        except Exception:
            return None

    def _handle_key(key):
        nonlocal stop_requested
        if key is None:
            return
        if key == "\x03":
            stop_requested = True
            ui_state["stopping"] = True
            pending_input.append(CTRL_C)
            _update_live()
            return

        if key.lower() == "q":
            stop_requested = True
            ui_state["stopping"] = True
            pending_input.append(CTRL_C)
            _update_live()
            return

        if key.lower() == "s":
            if ui_state.get("scan_paused"):
                ui_state["scan_paused"] = False
                ui_state["status"] = "Resuming BLE scan..."
                pending_input.append(b"@replx:scan:resume\n")
            else:
                ui_state["scan_paused"] = True
                ui_state["status"] = "BLE scan paused"
                pending_input.append(b"@replx:scan:pause\n")
            _update_live()
            return

        if key.lower() == "f":
            ui_state["name_filter"] = "all" if ui_state.get("name_filter") == "named" else "named"
            ui_state["page"] = 0
            ui_state["number_buffer"] = ""
            sort_state["dirty"] = True
            _update_live()
            return

        if ui_state.get("selected_key"):
            ui_state["selected_key"] = None
            ui_state["number_buffer"] = ""
            _update_live()
            return

        if key.lower() in ("n", "]", " "):
            devices = _visible_devices()
            page_count = max(1, (len(devices) + _page_size() - 1) // _page_size())
            ui_state["page"] = min(page_count - 1, ui_state.get("page", 0) + 1)
            _update_live()
            return

        if key.lower() in ("p", "["):
            ui_state["page"] = max(0, ui_state.get("page", 0) - 1)
            _update_live()
            return

        if key.isdigit():
            ui_state["number_buffer"] = (ui_state.get("number_buffer") or "") + key
            ui_state["number_updated_at"] = time.time()
            _commit_number(False)
            _update_live()
            return

    def _expire_number_buffer():
        if not ui_state.get("number_buffer"):
            return
        if time.time() - ui_state.get("number_updated_at", 0.0) >= 0.6:
            _commit_number(True)
            _update_live()

    def _refresh_expired_devices():
        now = time.time()
        if now - prune_state.get("last", 0.0) < 1.0:
            return
        prune_state["last"] = now
        before = len(device_map)
        _visible_devices()
        after = len(device_map)
        if after != before:
            ui_state["devices"] = list(device_map.values())
            _update_live()

    def output_callback(data: bytes, stream_type: str = "stdout") -> None:
        if stream_type == "stderr":
            stderr_buffer.extend(data)
            return
        stdout_buffer.extend(data.replace(b"\r", b"\n"))
        while b"\n" in stdout_buffer:
            line, _, rest = stdout_buffer.partition(b"\n")
            stdout_buffer[:] = rest
            text = line.decode("utf-8", "replace").strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                ui_state["status"] = text
                continue

            event = message.get("event")
            for device in message.get("devices") or []:
                _merge_device_update(device)
            ui_state["devices"] = list(device_map.values())
            ui_state["attempts"] = message.get("attempts") or ui_state.get("attempts") or []
            ui_state["elapsed_ms"] = message.get("elapsed_ms") or ui_state.get("elapsed_ms") or 0
            ui_state["reports"] = message.get("reports") or ui_state.get("reports") or 0
            if message.get("error"):
                ui_state["error"] = message.get("error")
            if "scan_active" in message and event not in ("stopped", "error"):
                ui_state["scan_paused"] = not bool(message.get("scan_active"))
            if event == "paused":
                ui_state["scan_paused"] = True
                ui_state["status"] = "Paused"
            elif event == "resumed":
                ui_state["scan_paused"] = False
                ui_state["status"] = "Scanning"
            if event == "stopped":
                ui_state["stopping"] = False
                ui_state["status"] = "Stopped"
            _update_live()

    def input_provider() -> bytes | None:
        if pending_input:
            return pending_input.pop(0)
        _expire_number_buffer()
        _refresh_expired_devices()
        _handle_key(_read_key())
        return None

    def stop_check() -> bool:
        return stop_requested

    original_sigint = signal.getsignal(signal.SIGINT)

    def sigint_handler(signum, frame):
        nonlocal stop_requested
        stop_requested = True
        ui_state["stopping"] = True
        pending_input.append(CTRL_C)
        _update_live()

    try:
        signal.signal(signal.SIGINT, sigint_handler)
        if not IS_WINDOWS and old_settings is not None and fd is not None:
            try:
                tty.setraw(fd)
            except Exception:
                pass

        with Live(_render_panel(), console=console, refresh_per_second=8, transient=False) as live:
            live_ref[0] = live
            client.run_interactive(
                script_content=code,
                echo=False,
                output_callback=output_callback,
                input_provider=input_provider,
                stop_check=stop_check,
                ctrl_c_grace_s=3,
            )
    except typer.Exit:
        raise
    except Exception as e:
        if stderr_buffer:
            message = stderr_buffer.decode("utf-8", "replace").strip()
            if message:
                OutputHelper.print_panel(message, title="BLE Scan Error", border_style="error")
                raise typer.Exit(1)
        OutputHelper.print_panel(f"Scan failed: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)
    finally:
        live_ref[0] = None
        signal.signal(signal.SIGINT, original_sigint)
        if not IS_WINDOWS and old_settings is not None and fd is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass


def _ble_rssi_value(rssi) -> int | None:
    try:
        return int(rssi)
    except (TypeError, ValueError):
        return None


def _ble_signal_style(rssi: int | None) -> str:
    if rssi is None:
        return "dim"
    if rssi >= -65:
        return "green"
    if rssi >= -85:
        return "yellow"
    return "red"


def _ble_signal_icon(rssi) -> Text:
    value = _ble_rssi_value(rssi)
    if value is None:
        return Text("-", style="dim")
    if value >= -50:
        icon = chr(0xF04A2)
    elif value >= -65:
        icon = chr(0xF08BE)
    elif value >= -75:
        icon = chr(0xF08BD)
    elif value >= -85:
        icon = chr(0xF08BC)
    else:
        icon = chr(0xF08BF)
    return Text(icon, style=_ble_signal_style(value))


def _ble_signal_text(rssi) -> Text:
    value = _ble_rssi_value(rssi)
    if value is None:
        return Text("?", style="dim")
    return Text(f"{value}dBm", style=_ble_signal_style(value))


def _ble_advertise_arg_error(message: str):
    OutputHelper.print_panel(message, title="BLE Error", border_style="error")
    raise typer.Exit(1)


def _ble_validate_uuid_text(uuid_text: str, option_name: str) -> str:
    text = uuid_text.strip()
    if not text:
        _ble_advertise_arg_error(f"[bright_blue]{option_name}[/bright_blue] UUID must not be empty.")

    lower = text.lower()
    if lower.startswith("0x"):
        try:
            value = int(lower, 16)
        except ValueError:
            _ble_advertise_arg_error(f"[bright_blue]{option_name}[/bright_blue] UUID is not valid hex.")
        if value <= 0xFFFFFFFF:
            return text
        _ble_advertise_arg_error(
            f"[bright_blue]{option_name}[/bright_blue] UUID must be 16-bit, 32-bit, or 128-bit."
        )

    compact = lower.replace("-", "").replace("{", "").replace("}", "")
    if len(compact) in (4, 8, 32):
        try:
            bytes.fromhex(compact)
            return text
        except ValueError:
            pass

    _ble_advertise_arg_error(
        f"[bright_blue]{option_name}[/bright_blue] UUID must be 16-bit, 32-bit, or 128-bit hex."
    )


def _ble_encode_ad_data(encoding: str, data_text: str, option_name: str) -> str:
    mode = encoding.strip().lower()
    if mode == "hex":
        compact = data_text.strip().replace(" ", "").replace(":", "").replace("-", "")
        if not compact:
            _ble_advertise_arg_error(f"[bright_blue]{option_name}[/bright_blue] hex data must not be empty.")
        if any(character not in "0123456789abcdefABCDEF" for character in compact):
            _ble_advertise_arg_error(
                f"[bright_blue]{option_name}[/bright_blue] hex data contains non-hex characters."
            )
        if len(compact) % 2:
            _ble_advertise_arg_error(
                f"[bright_blue]{option_name}[/bright_blue] hex data must contain an even number of digits."
            )
        bytes.fromhex(compact)
        return compact.upper()

    if mode == "text":
        data = data_text.encode("utf-8")
        if not data:
            _ble_advertise_arg_error(f"[bright_blue]{option_name}[/bright_blue] text data must not be empty.")
        return data.hex().upper()

    _ble_advertise_arg_error(
        f"[bright_blue]{option_name}[/bright_blue] encoding must be [yellow]hex[/yellow] or [yellow]text[/yellow]."
    )


def _ble_parse_encoded_data_arg(value: str, option_name: str, id_label: str) -> tuple[str, str, str]:
    parts = value.split(":", 2)
    if len(parts) != 3:
        _ble_advertise_arg_error(
            f"[bright_blue]{option_name}[/bright_blue] must use "
            f"[yellow]{id_label}:hex:DATA[/yellow] or [yellow]{id_label}:text:TEXT[/yellow]."
        )
    identity_text, encoding, data_text = parts
    if not identity_text.strip():
        _ble_advertise_arg_error(f"[bright_blue]{option_name}[/bright_blue] {id_label} must not be empty.")
    data_hex = _ble_encode_ad_data(encoding, data_text, option_name)
    return identity_text.strip(), encoding.strip().lower(), data_hex


def _ble_collect_ad_data_value(args: list[str], value_index: int) -> tuple[str, int]:
    value = args[value_index]
    parts = value.split(":", 2)
    if len(parts) < 2 or parts[1].strip().lower() != "text":
        return value, value_index + 1

    fragments = [value]
    index = value_index + 1
    while index < len(args) and not args[index].startswith("--"):
        fragments.append(args[index])
        index += 1
    if len(fragments) == 1:
        return value, index
    tail = " ".join(fragments[1:])
    if value.endswith(":"):
        return value + tail, index
    return value + " " + tail, index


def _ble_parse_service_data_arg(value: str) -> tuple[str, str]:
    uuid_text, _, service_data_hex = _ble_parse_encoded_data_arg(value, "--service-data", "UUID")
    service_data_uuid = _ble_validate_uuid_text(uuid_text, "--service-data")
    return service_data_uuid, service_data_hex


def _ble_normalize_company_id(company_id_text: str) -> tuple[str, str]:
    text = company_id_text.strip()
    if text.lower().startswith("0x"):
        text = text[2:]
    compact = text.replace(" ", "").replace(":", "").replace("-", "")
    if len(compact) != 4 or any(character not in "0123456789abcdefABCDEF" for character in compact):
        _ble_advertise_arg_error(
            "[bright_blue]--manufacturer-data[/bright_blue] company-id must be a 16-bit hex value, "
            "for example [yellow]FFFF[/yellow]."
        )
    value = int(compact, 16)
    return "%04X" % value, "%02X%02X" % (value & 0xFF, (value >> 8) & 0xFF)


def _ble_parse_manufacturer_data_arg(value: str) -> tuple[str, str]:
    company_id_text, _, data_hex = _ble_parse_encoded_data_arg(value, "--manufacturer-data", "COMPANY_ID")
    company_id, company_id_le_hex = _ble_normalize_company_id(company_id_text)
    return company_id, company_id_le_hex + data_hex


def _ble_advertise_from_args(client: AgentClient, args: list[str]):
    service_uuid = None
    service_data_uuid = None
    service_data_hex = None
    manufacturer_company_id = None
    manufacturer_data_hex = None
    duration_ms = 1000
    connectable = True
    positional = []

    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--service-uuid":
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                _ble_advertise_arg_error("Missing value for [bright_blue]--service-uuid[/bright_blue].")
            service_uuid = _ble_validate_uuid_text(args[index + 1], "--service-uuid")
            index += 2
        elif arg == "--service-data":
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                _ble_advertise_arg_error("Missing value for [bright_blue]--service-data[/bright_blue].")
            if service_data_hex is not None:
                _ble_advertise_arg_error("Use [bright_blue]--service-data[/bright_blue] only once.")
            service_data_value, index = _ble_collect_ad_data_value(args, index + 1)
            service_data_uuid, service_data_hex = _ble_parse_service_data_arg(service_data_value)
        elif arg == "--manufacturer-data":
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                _ble_advertise_arg_error("Missing value for [bright_blue]--manufacturer-data[/bright_blue].")
            if manufacturer_data_hex is not None:
                _ble_advertise_arg_error("Use only one manufacturer data option.")
            manufacturer_data_value, index = _ble_collect_ad_data_value(args, index + 1)
            manufacturer_company_id, manufacturer_data_hex = _ble_parse_manufacturer_data_arg(manufacturer_data_value)
        elif arg == "--duration-ms":
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                _ble_advertise_arg_error("Missing value for [bright_blue]--duration-ms[/bright_blue].")
            try:
                duration_ms = int(args[index + 1])
            except ValueError:
                _ble_advertise_arg_error(
                    "[bright_blue]--duration-ms[/bright_blue] must be an integer number of milliseconds."
                )
            index += 2
        elif arg == "--no-connect":
            connectable = False
            index += 1
        elif arg.startswith("-"):
            _ble_advertise_arg_error(
                f"Unknown advertise option: [yellow]{arg}[/yellow]\n\n"
                "Use [bright_blue]replx ble --help[/bright_blue] for usage."
            )
        else:
            positional.append(arg)
            index += 1

    if not positional:
        _ble_advertise_arg_error(
            "Required: [bright_blue]replx ble advertise DEVICE_NAME[/bright_blue]\n\n"
            "Use [bright_blue]replx ble --help[/bright_blue] for usage."
        )

    if len(positional) > 1:
        _ble_advertise_arg_error(
            f"Unexpected advertise argument: [yellow]{positional[1]}[/yellow]\n\n"
            "Use options such as [bright_blue]--service-data[/bright_blue] or "
            "[bright_blue]--manufacturer-data[/bright_blue] after DEVICE_NAME."
        )

    name = positional[0].strip()
    if not name:
        _ble_advertise_arg_error("DEVICE_NAME must not be empty.")

    if duration_ms <= 0:
        _ble_advertise_arg_error("[bright_blue]--duration-ms[/bright_blue] must be greater than 0.")

    _ble_advertise(
        client,
        name,
        duration_ms,
        connectable,
        service_uuid,
        service_data_uuid,
        service_data_hex,
        manufacturer_company_id,
        manufacturer_data_hex,
    )


def _ble_advertise(
    client: AgentClient,
    name: str,
    duration_ms: int,
    connectable: bool,
    service_uuid=None,
    service_data_uuid=None,
    service_data_hex=None,
    manufacturer_company_id=None,
    manufacturer_data_hex=None,
):
    name_expr = json.dumps(name)
    service_uuid_expr = "None" if service_uuid is None else json.dumps(service_uuid)
    service_data_uuid_expr = "None" if service_data_uuid is None else json.dumps(service_data_uuid)
    service_data_hex_expr = "None" if service_data_hex is None else json.dumps(service_data_hex)
    manufacturer_company_id_expr = "None" if manufacturer_company_id is None else json.dumps(manufacturer_company_id)
    manufacturer_data_hex_expr = "None" if manufacturer_data_hex is None else json.dumps(manufacturer_data_hex)
    mode = "connectable" if connectable else "broadcaster (non-connectable)"
    code = f'''
import bluetooth, json, sys, time

_IRQ_CENTRAL_CONNECT = 1
_IRQ_CENTRAL_DISCONNECT = 2

ble = bluetooth.BLE()
name = {name_expr}
service_uuid = {service_uuid_expr}
service_data_uuid = {service_data_uuid_expr}
service_data_hex = {service_data_hex_expr}
manufacturer_company_id = {manufacturer_company_id_expr}
manufacturer_data_hex = {manufacturer_data_hex_expr}
advertise_interval_us = {duration_ms} * 1000
was_active = False
conn_handle = [None]
peer = [None]
peer_info = [None]

def _append_adv(payload, adv_type, value):
    field = bytes((len(value) + 1, adv_type)) + value
    if len(payload) + len(field) > 31:
        raise ValueError("advertising payload exceeds 31 bytes")
    payload.extend(field)

def _le(value, size):
    out = bytearray(size)
    for i in range(size):
        out[i] = (value >> (8 * i)) & 0xFF
    return bytes(out)

def _uuid128_bytes(raw):
    out = bytearray(16)
    for i in range(16):
        out[i] = raw[15 - i]
    return bytes(out)

def _uuid_payload(uuid_text):
    if uuid_text is None:
        return None, None
    text = str(uuid_text).strip()
    if not text:
        return None, None
    lower = text.lower()
    if lower.startswith("0x"):
        value = int(lower, 16)
        if value <= 0xFFFF:
            return 16, _le(value, 2)
        if value <= 0xFFFFFFFF:
            return 32, _le(value, 4)
        raise ValueError("service-uuid integer is too large")

    compact = lower.replace("-", "").replace("{{", "").replace("}}", "")
    if len(compact) == 4:
        return 16, _le(int(compact, 16), 2)
    if len(compact) == 8:
        return 32, _le(int(compact, 16), 4)
    if len(compact) == 32:
        return 128, _uuid128_bytes(bytes.fromhex(compact))
    raise ValueError("service-uuid must be 16-bit, 32-bit, or 128-bit")

def _hex_bytes(value, label):
    if value is None:
        return None
    text = str(value).strip()
    if text.lower().startswith("hex:"):
        text = text[4:]
    compact = text.replace(" ", "").replace(":", "").replace("-", "")
    if not compact:
        raise ValueError(label + " data must not be empty")
    if len(compact) % 2:
        raise ValueError(label + " hex data must contain an even number of digits")
    return bytes.fromhex(compact)

def _append_uuid_list(payload, uuid_kind, uuid_bytes):
    if uuid_kind == 16:
        _append_adv(payload, 0x03, uuid_bytes)
    elif uuid_kind == 32:
        _append_adv(payload, 0x05, uuid_bytes)
    elif uuid_kind == 128:
        _append_adv(payload, 0x07, uuid_bytes)

def _append_service_data(payload, uuid_kind, uuid_bytes, data_bytes):
    if uuid_kind == 16:
        _append_adv(payload, 0x16, uuid_bytes + data_bytes)
    elif uuid_kind == 32:
        _append_adv(payload, 0x20, uuid_bytes + data_bytes)
    elif uuid_kind == 128:
        _append_adv(payload, 0x21, uuid_bytes + data_bytes)

def _adv_payload(name, service_uuid, service_data_uuid, service_data_hex, manufacturer_data_hex):
    payload = bytearray()
    _append_adv(payload, 0x01, bytes((0x06,)))

    uuid_kind, uuid_bytes = _uuid_payload(service_uuid)
    if uuid_bytes is not None:
        _append_uuid_list(payload, uuid_kind, uuid_bytes)

    data_uuid_kind, data_uuid_bytes = _uuid_payload(service_data_uuid)
    service_data_bytes = _hex_bytes(service_data_hex, "service-data")
    if service_data_bytes is not None:
        if data_uuid_bytes is None:
            raise ValueError("service-data requires a service UUID")
        _append_service_data(payload, data_uuid_kind, data_uuid_bytes, service_data_bytes)

    manufacturer_data_bytes = _hex_bytes(manufacturer_data_hex, "manufacturer-data")
    if manufacturer_data_bytes is not None:
        _append_adv(payload, 0xFF, manufacturer_data_bytes)

    encoded_name = name.encode()
    available = 31 - len(payload) - 2
    if available <= 0:
        raise ValueError("advertising payload has no room for device-name")
    if len(encoded_name) <= available:
        _append_adv(payload, 0x09, encoded_name)
    else:
        _append_adv(payload, 0x08, encoded_name[:available])
    return payload

def _ensure_active():
    try:
        if ble.active():
            return
    except Exception:
        pass
    try:
        ble.active(False)
    except Exception:
        pass
    time.sleep_ms(200)
    ble.active(True)
    time.sleep_ms(500)

def _restore_if_needed():
    try:
        ble.gap_advertise(None)
    except Exception:
        pass
    if conn_handle[0] is not None:
        try:
            ble.gap_disconnect(conn_handle[0])
        except Exception:
            pass
    if not was_active:
        try:
            ble.active(False)
        except Exception:
            pass

def _irq(event, data):
    if event == _IRQ_CENTRAL_CONNECT:
        handle, addr_type, addr = data
        conn_handle[0] = handle
        peer[0] = ":".join("%02X" % b for b in bytes(addr))
        peer_info[0] = {{
            "conn_handle": handle,
            "addr_type": addr_type,
            "addr_type_label": "random" if addr_type else "public",
            "addr": peer[0],
        }}
    elif event == _IRQ_CENTRAL_DISCONNECT:
        conn_handle[0] = None
        peer[0] = None
        peer_info[0] = None

def _start_advertise(adv_data):
    try:
        ble.gap_advertise(advertise_interval_us, adv_data=adv_data, connectable={str(connectable)})
    except TypeError:
        try:
            ble.gap_advertise(advertise_interval_us, adv_data, None, {str(connectable)})
        except TypeError:
            ble.gap_advertise(advertise_interval_us, adv_data)

try:
    try:
        was_active = ble.active()
    except Exception:
        was_active = False

    _ensure_active()
    ble.irq(_irq)
    adv_data = _adv_payload(name, service_uuid, service_data_uuid, service_data_hex, manufacturer_data_hex)
    adv_hex = "".join("%02X" % b for b in adv_data)
    _start_advertise(adv_data)

    print(json.dumps({{
        "event": "ready",
        "name": name,
        "connectable": {str(connectable)},
        "service_uuid": service_uuid,
        "service_data_uuid": service_data_uuid,
        "service_data_hex": service_data_hex,
        "manufacturer_company_id": manufacturer_company_id,
        "manufacturer_data_hex": manufacturer_data_hex,
        "interval_ms": {duration_ms},
        "payload_len": len(adv_data),
        "payload_hex": adv_hex,
        "active": ble.active(),
    }}))

    last_peer = None
    while True:
        current_peer = peer_info[0]
        if current_peer != last_peer:
            if current_peer is None and last_peer is not None:
                print(json.dumps({{"event": "disconnected", "peer": last_peer}}))
                _start_advertise(adv_data)
            elif current_peer is not None:
                print(json.dumps({{"event": "connected", "peer": current_peer}}))
            last_peer = current_peer
        time.sleep_ms(200)
except KeyboardInterrupt:
    _restore_if_needed()
    print(json.dumps({{"event": "stopped", "active": ble.active()}}))
except Exception as exc:
    _restore_if_needed()
    print(json.dumps({{"error": repr(exc)}}))
'''
    console = OutputHelper.make_console()
    spinner = Spinner("dots")
    state = {
        "status": "starting",
        "payload_len": None,
        "payload_hex": None,
        "peer": None,
        "event": None,
        "error": None,
    }

    def _data_type_label() -> str:
        parts = []
        if service_uuid:
            parts.append("service UUID")
        if service_data_hex:
            parts.append("service data")
        if manufacturer_data_hex:
            parts.append("manufacturer data")
        return " + ".join(parts) if parts else "local name only"

    def _manufacturer_data_label() -> str:
        if not manufacturer_company_id or not manufacturer_data_hex:
            return "-"
        return f"{manufacturer_company_id}:{manufacturer_data_hex[4:]}"

    def _render_panel():
        status_text = Text()
        if state["status"] == "ready":
            status_text.append("Advertising", style="bright_cyan")
        elif state["status"] == "connected":
            status_text.append("Connected", style="green")
            if state["peer"] and state["peer"].get("addr"):
                status_text.append(f" from {state['peer'].get('addr')}", style="bright_cyan")
        elif state["status"] == "stopped":
            status_text.append("Stopped", style="dim")
        elif state["status"] == "error":
            status_text.append("Failed", style="red")
        else:
            status_text.append("Starting advertisement", style="bright_cyan")

        status_line = Table.grid(padding=(0, 1))
        status_line.add_column(width=3)
        status_line.add_column()
        status_line.add_row(spinner, status_text)

        detail = Table.grid(padding=(0, 1))
        detail.add_column(justify="right", style="dim", no_wrap=True)
        detail.add_column()
        detail.add_row("Device", Text(name, style="bright_cyan"))
        detail.add_row("Mode", mode)
        detail.add_row("Interval", f"{duration_ms} ms")
        detail.add_row("Service UUID", service_uuid or "-")
        detail.add_row(
            "Service data",
            f"{service_data_uuid}:{service_data_hex}" if service_data_uuid and service_data_hex else "-",
        )
        detail.add_row("Manufacturer data", _manufacturer_data_label())
        detail.add_row("Data type", _data_type_label())
        if state["payload_len"] is not None:
            detail.add_row("Payload", f"{state['payload_len']} bytes")
        if state["payload_hex"]:
            detail.add_row("Payload hex", state["payload_hex"])
        if state["peer"]:
            peer = state["peer"]
            detail.add_row("Peer addr", Text(peer.get("addr", "?"), style="bright_cyan"))
            detail.add_row("Peer type", f"{peer.get('addr_type', '?')} ({peer.get('addr_type_label', '?')})")
            detail.add_row("Conn handle", str(peer.get("conn_handle", "?")))
        if state["event"]:
            detail.add_row("Event", state["event"])
        if state["error"]:
            detail.add_row("Error", Text(state["error"], style="red"))
        detail.add_row("Stop", "Ctrl+C")

        return Panel(
            Group(status_line, Text(""), detail),
            title="BLE Advertise",
            title_align="left",
            border_style=OutputHelper._resolve_category_color("mode"),
            box=get_panel_box(),
            width=CONSOLE_WIDTH,
        )

    live_ref = [None]
    stop_requested = False
    pending_input: list[bytes] = []
    original_sigint = signal.getsignal(signal.SIGINT)

    def _sigint_handler(signum, frame):
        nonlocal stop_requested
        stop_requested = True
        pending_input.append(CTRL_C)
        state["status"] = "stopped"
        state["event"] = "stopping"

    def _input_provider() -> bytes:
        if pending_input:
            return pending_input.pop(0)
        return b""

    def _stop_check() -> bool:
        return stop_requested

    def _on_output(chunk: bytes, stream_name: str):
        text = chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else str(chunk)
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                state["event"] = line
                continue

            if obj.get("error"):
                state["status"] = "error"
                state["error"] = obj.get("error")
            elif obj.get("event") == "ready":
                state["status"] = "ready"
                state["payload_len"] = obj.get("payload_len")
                state["payload_hex"] = obj.get("payload_hex")
                state["event"] = "advertising"
            elif obj.get("event") == "connected":
                state["status"] = "connected"
                state["peer"] = obj.get("peer") or {"addr": obj.get("addr")}
                state["event"] = "connected"
            elif obj.get("event") == "disconnected":
                peer = obj.get("peer") or {"addr": obj.get("addr")}
                state["status"] = "ready"
                state["peer"] = None
                state["event"] = f"disconnected from {peer.get('addr', '?')}"
            elif obj.get("event") == "stopped":
                state["status"] = "stopped"
                state["event"] = "stopped"

        if live_ref[0] is not None:
            live_ref[0].update(_render_panel())

    try:
        signal.signal(signal.SIGINT, _sigint_handler)
        with Live(_render_panel(), console=console, refresh_per_second=10, transient=False) as live:
            live_ref[0] = live
            client.run_interactive(
                script_content=code,
                echo=False,
                output_callback=_on_output,
                input_provider=_input_provider,
                stop_check=_stop_check,
                ctrl_c_grace_s=2.0,
            )
            if stop_requested and state["status"] != "error":
                state["status"] = "stopped"
                state["event"] = "stopped by user"
                live.update(_render_panel())
        if state["status"] == "error":
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        state["status"] = "stopped"
        state["event"] = "stopped by user"
        try:
            client.send_command("run_stop", timeout=0.3)
        except Exception:
            pass
    except Exception as e:
        OutputHelper.print_panel(f"Advertise failed: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)
    finally:
        signal.signal(signal.SIGINT, original_sigint)
        live_ref[0] = None


def _ble_collect_value_arg(args: list[str], value_index: int) -> tuple[str, int]:
    value = args[value_index]
    encoding = value.split(":", 1)[0].strip().lower()
    if encoding != "text":
        return value, value_index + 1

    fragments = [value]
    index = value_index + 1
    while index < len(args) and not args[index].startswith("--"):
        fragments.append(args[index])
        index += 1
    if len(fragments) == 1:
        return value, index
    tail = " ".join(fragments[1:])
    if value.endswith(":"):
        return value + tail, index
    return value + " " + tail, index


def _ble_parse_value_arg_detail_or_raise(value: str) -> tuple[str, str]:
    text = value.strip()
    if not text:
        raise ValueError("must use hex:DATA or text:TEXT")

    encoding, separator, data_text = text.partition(":")
    if not separator:
        raise ValueError("must use hex:DATA or text:TEXT")

    mode = encoding.strip().lower()
    if mode not in ("hex", "text"):
        raise ValueError("encoding must be hex or text")

    if mode == "hex":
        compact = data_text.strip().replace(" ", "").replace(":", "").replace("-", "")
        if not compact:
            raise ValueError("hex data must not be empty")
        if any(character not in "0123456789abcdefABCDEF" for character in compact):
            raise ValueError("hex data contains non-hex characters")
        if len(compact) % 2:
            raise ValueError("hex data must contain an even number of digits")
        bytes.fromhex(compact)
        return compact.upper(), "hex"

    data = data_text.encode("utf-8")
    if not data:
        raise ValueError("text data must not be empty")
    return data.hex().upper(), "string"


def _ble_parse_value_arg_or_raise(value: str) -> str:
    return _ble_parse_value_arg_detail_or_raise(value)[0]


def _ble_parse_value_arg_detail(value: str) -> tuple[str, str]:
    try:
        return _ble_parse_value_arg_detail_or_raise(value)
    except ValueError as exc:
        _ble_advertise_arg_error(f"[bright_blue]--value[/bright_blue] {exc}.")

    return "", "hex"


def _ble_parse_value_arg(value: str) -> str:
    try:
        return _ble_parse_value_arg_or_raise(value)
    except ValueError as exc:
        _ble_advertise_arg_error(f"[bright_blue]--value[/bright_blue] {exc}.")

    return ""


def _ble_value_string(hex_value: str | None) -> str:
    compact = (hex_value or "").strip().replace(" ", "")
    if not compact:
        return ""
    try:
        data = bytes.fromhex(compact)
    except ValueError:
        return ""
    decoded = data.decode("utf-8", errors="replace")
    return "".join(character if character.isprintable() else "." for character in decoded)


def _ble_value_text(hex_value: str | None, view: str) -> Text:
    hex_text = (hex_value or "").upper() or "-"
    string_text = _ble_value_string(hex_value)
    if string_text == "":
        string_text = '""'
    else:
        string_text = f'"{string_text}"'

    output = Text()
    if view == "string":
        output.append(string_text, style="bright_yellow")
        output.append("  ", style="dim")
        output.append(hex_text, style="dim")
    else:
        output.append(hex_text, style="bright_yellow")
        output.append("  ", style="dim")
        output.append(string_text, style="dim")
    return output


def _ble_serve_from_args(client: AgentClient, args: list[str]):
    svc_uuid = None
    char_uuid = None
    value_hex = None
    name = "replx-ble"
    interval_ms = None
    notify_on_change = False
    value_view = "hex"
    props = []

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--svc" and i + 1 < len(args):
            svc_uuid = args[i + 1]; i += 2
        elif a == "--char" and i + 1 < len(args):
            char_uuid = args[i + 1]; i += 2
        elif a == "--value":
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                _ble_advertise_arg_error("Missing value for [bright_blue]--value[/bright_blue].")
            value_text, i = _ble_collect_value_arg(args, i + 1)
            value_hex, value_view = _ble_parse_value_arg_detail(value_text)
        elif a == "--name" and i + 1 < len(args):
            name = args[i + 1]; i += 2
        elif a == "--interval" and i + 1 < len(args):
            interval_ms = int(args[i + 1]); i += 2
        elif a == "--read":
            props.append("READ"); i += 1
        elif a == "--write":
            props.append("WRITE"); i += 1
        elif a == "--notify":
            props.append("NOTIFY"); i += 1
        elif a == "--indicate":
            props.append("INDICATE"); i += 1
        elif a == "--notify-on-change":
            notify_on_change = True; i += 1
        else:
            i += 1

    if not svc_uuid or not char_uuid:
        OutputHelper.print_panel(
            "Required: [bright_blue]--svc UUID --char UUID[/bright_blue]\n\n"
            "Use [bright_blue]replx ble --help[/bright_blue] for usage.",
            title="BLE Error", border_style="error",
        )
        raise typer.Exit(1)

    if not props:
        props = ["READ", "WRITE", "NOTIFY"]

    if notify_on_change and "NOTIFY" not in props and "INDICATE" not in props:
        OutputHelper.print_panel(
            "[bright_blue]--notify-on-change[/bright_blue] requires [bright_blue]--notify[/bright_blue] "
            "or [bright_blue]--indicate[/bright_blue].",
            title="BLE Error", border_style="error",
        )
        raise typer.Exit(1)

    _ble_serve(client, svc_uuid, char_uuid, value_hex, name, props, interval_ms, notify_on_change, value_view)


def _ble_serve(
    client: AgentClient,
    svc_uuid: str,
    char_uuid: str,
    value_hex: str | None,
    name: str,
    props: list[str],
    interval_ms: int | None,
    notify_on_change: bool = False,
    initial_value_view: str = "hex",
):
    svc_expr = _parse_uuid(svc_uuid)
    char_expr = _parse_uuid(char_uuid)
    name_expr = json.dumps(name)
    server_props = list(props)
    if "WRITE" in server_props and "WRITE_NO_RESPONSE" not in server_props:
        server_props.append("WRITE_NO_RESPONSE")

    flag_parts = []
    if "READ" in server_props:
        flag_parts.append("bluetooth.FLAG_READ")
    if "WRITE" in server_props:
        flag_parts.append("bluetooth.FLAG_WRITE")
    if "WRITE_NO_RESPONSE" in server_props:
        flag_parts.append("getattr(bluetooth, 'FLAG_WRITE_NO_RESPONSE', 0x0004)")
    if "NOTIFY" in server_props:
        flag_parts.append("bluetooth.FLAG_NOTIFY")
    if "INDICATE" in server_props:
        flag_parts.append("bluetooth.FLAG_INDICATE")
    flags_expr = " | ".join(flag_parts) if flag_parts else "bluetooth.FLAG_READ"

    initial_value_hex = (value_hex or "").strip().upper()
    if initial_value_hex:
        init_value_expr = _hex_to_bytes_expr(initial_value_hex)
    else:
        init_value_expr = "b''"

    notify_interval_expr = "None" if not interval_ms else str(int(interval_ms))
    notify_enabled = "NOTIFY" in props
    indicate_enabled = "INDICATE" in props
    service_uuid_text_expr = json.dumps(svc_uuid)

    code = f'''
import bluetooth, json, sys, time

_IRQ_CENTRAL_CONNECT = 1
_IRQ_CENTRAL_DISCONNECT = 2
_IRQ_GATTS_WRITE = 3

ble = bluetooth.BLE()
name = {name_expr}
service_uuid_text = {service_uuid_text_expr}
service_uuid = bluetooth.UUID({svc_expr})
char_uuid = bluetooth.UUID({char_expr})
char_flags = {flags_expr}
initial_value = {init_value_expr}
notify_interval_ms = {notify_interval_expr}
notify_enabled = {str(notify_enabled)}
indicate_enabled = {str(indicate_enabled)}
notify_on_change = {str(notify_on_change)}
was_active = False
conn_handle = [None]
peer_info = [None]
char_handle = [None]
pending_events = []
need_advertise = [False]
last_notify = [time.ticks_ms()]
input_poll = [None]
input_buffer = []

def _emit(event):
    print(json.dumps(event))
    try:
        sys.stdout.flush()
    except Exception:
        pass

def _hex(data):
    return "".join("%02X" % b for b in bytes(data))

def _addr(addr):
    return ":".join("%02X" % b for b in bytes(addr))

def _append_adv(payload, adv_type, value):
    field = bytes((len(value) + 1, adv_type)) + value
    if len(payload) + len(field) > 31:
        raise ValueError("advertising payload exceeds 31 bytes")
    payload.extend(field)

def _le(value, size):
    out = bytearray(size)
    for i in range(size):
        out[i] = (value >> (8 * i)) & 0xFF
    return bytes(out)

def _uuid128_bytes(raw):
    out = bytearray(16)
    for i in range(16):
        out[i] = raw[15 - i]
    return bytes(out)

def _uuid_payload(uuid_text):
    text = str(uuid_text).strip()
    lower = text.lower()
    if lower.startswith("0x"):
        value = int(lower, 16)
        if value <= 0xFFFF:
            return 16, _le(value, 2)
        if value <= 0xFFFFFFFF:
            return 32, _le(value, 4)
        raise ValueError("service UUID integer is too large")
    compact = lower.replace("-", "").replace("{{", "").replace("}}", "")
    if len(compact) == 4:
        return 16, _le(int(compact, 16), 2)
    if len(compact) == 8:
        return 32, _le(int(compact, 16), 4)
    if len(compact) == 32:
        return 128, _uuid128_bytes(bytes.fromhex(compact))
    raise ValueError("service UUID must be 16-bit, 32-bit, or 128-bit")

def _adv_payload(name, service_uuid_text):
    payload = bytearray()
    _append_adv(payload, 0x01, bytes((0x06,)))
    uuid_kind, uuid_bytes = _uuid_payload(service_uuid_text)
    if uuid_kind == 16:
        _append_adv(payload, 0x03, uuid_bytes)
    elif uuid_kind == 32:
        _append_adv(payload, 0x05, uuid_bytes)
    else:
        _append_adv(payload, 0x07, uuid_bytes)
    encoded_name = name.encode()
    available = 31 - len(payload) - 2
    if available > 0:
        if len(encoded_name) <= available:
            _append_adv(payload, 0x09, encoded_name)
        else:
            _append_adv(payload, 0x08, encoded_name[:available])
    return payload

def _ensure_active():
    try:
        if ble.active():
            return
    except Exception:
        pass
    try:
        ble.active(False)
    except Exception:
        pass
    time.sleep_ms(200)
    ble.active(True)
    time.sleep_ms(500)

def _start_advertise(adv_data):
    try:
        ble.gap_advertise(100000, adv_data=adv_data, connectable=True)
    except TypeError:
        try:
            ble.gap_advertise(100000, adv_data, None, True)
        except TypeError:
            ble.gap_advertise(100000, adv_data)

def _restore_if_needed():
    try:
        ble.gap_advertise(None)
    except Exception:
        pass
    if conn_handle[0] is not None:
        try:
            ble.gap_disconnect(conn_handle[0])
        except Exception:
            pass
    if not was_active:
        try:
            ble.active(False)
        except Exception:
            pass

def _queue(event):
    pending_events.append(event)

def _send_value_update(value, reason):
    if conn_handle[0] is None:
        return
    value_hex = _hex(value)
    if notify_enabled:
        try:
            ble.gatts_notify(conn_handle[0], char_handle[0], value)
            _emit({{"event": "notify", "reason": reason, "value": value_hex, "value_hex": value_hex, "bytes": len(value)}})
        except Exception as exc:
            _emit({{"event": "notify_error", "reason": reason, "error": repr(exc)}})
    if indicate_enabled:
        try:
            ble.gatts_indicate(conn_handle[0], char_handle[0], value)
            _emit({{"event": "indicate", "reason": reason, "value": value_hex, "value_hex": value_hex, "bytes": len(value)}})
        except Exception as exc:
            _emit({{"event": "indicate_error", "reason": reason, "error": repr(exc)}})

def _setup_input():
    try:
        try:
            import select as _select
        except ImportError:
            import uselect as _select
        poll = _select.poll()
        poll.register(sys.stdin, _select.POLLIN)
        input_poll[0] = poll
    except Exception as exc:
        input_poll[0] = None
        _queue({{"event": "input_unavailable", "error": repr(exc)}})

def _handle_input_command(command):
    prefix = "@replx:set-value:"
    if not command.startswith(prefix):
        return
    try:
        if char_handle[0] is None:
            raise ValueError("characteristic is not ready")
        value = bytes.fromhex(command[len(prefix):].strip())
        ble.gatts_write(char_handle[0], value)
        value_hex = _hex(value)
        _queue({{"event": "value_set", "value": value_hex, "value_hex": value_hex, "bytes": len(value)}})
    except Exception as exc:
        _queue({{"event": "value_error", "error": repr(exc)}})

def _read_input_commands():
    poll = input_poll[0]
    if poll is None:
        return
    while True:
        try:
            events = poll.poll(0)
        except Exception as exc:
            input_poll[0] = None
            _queue({{"event": "input_error", "error": repr(exc)}})
            return
        if not events:
            return
        try:
            chunk = sys.stdin.read(1)
        except Exception as exc:
            input_poll[0] = None
            _queue({{"event": "input_error", "error": repr(exc)}})
            return
        if not chunk:
            return
        if isinstance(chunk, bytes):
            try:
                chunk = chunk.decode()
            except Exception:
                continue
        if chunk in ("\\r", "\\n"):
            command = "".join(input_buffer)
            del input_buffer[:]
            _handle_input_command(command.strip())
        else:
            input_buffer.append(chunk)
            if len(input_buffer) > 256:
                del input_buffer[:]
                _queue({{"event": "input_error", "error": "input command is too long"}})

def _irq(event, data):
    if event == _IRQ_CENTRAL_CONNECT:
        handle, addr_type, addr = data
        conn_handle[0] = handle
        peer_info[0] = {{
            "conn_handle": handle,
            "addr_type": addr_type,
            "addr_type_label": "random" if addr_type else "public",
            "addr": _addr(addr),
        }}
        _queue({{"event": "connected", "peer": peer_info[0]}})
    elif event == _IRQ_CENTRAL_DISCONNECT:
        handle, addr_type, addr = data
        old_peer = peer_info[0] or {{
            "conn_handle": handle,
            "addr_type": addr_type,
            "addr_type_label": "random" if addr_type else "public",
            "addr": _addr(addr),
        }}
        if conn_handle[0] == handle:
            conn_handle[0] = None
            peer_info[0] = None
        need_advertise[0] = True
        _queue({{"event": "disconnected", "peer": old_peer}})
    elif event == _IRQ_GATTS_WRITE:
        handle, value_handle = data
        if value_handle == char_handle[0]:
            value = ble.gatts_read(char_handle[0])
            peer = peer_info[0] or {{"conn_handle": handle}}
            value_hex = _hex(value)
            _queue({{"event": "write", "peer": peer, "value": value_hex, "value_hex": value_hex, "bytes": len(value)}})

try:
    try:
        was_active = ble.active()
    except Exception:
        was_active = False

    _ensure_active()
    ((handle,),) = ble.gatts_register_services(((service_uuid, ((char_uuid, char_flags),)),))
    char_handle[0] = handle
    ble.gatts_write(char_handle[0], initial_value)
    ble.irq(_irq)
    _setup_input()
    adv_data = _adv_payload(name, service_uuid_text)
    _start_advertise(adv_data)

    _emit({{
        "event": "ready",
        "svc": "{svc_uuid}",
        "char": "{char_uuid}",
        "props": {server_props!r},
        "name": name,
        "value": _hex(initial_value),
        "value_hex": _hex(initial_value),
        "payload_len": len(adv_data),
        "payload_hex": _hex(adv_data),
    }})

    while True:
        _read_input_commands()

        if need_advertise[0]:
            try:
                _start_advertise(adv_data)
            except Exception as exc:
                _queue({{"event": "advertise_error", "error": repr(exc)}})
            need_advertise[0] = False

        while pending_events:
            event = pending_events.pop(0)
            _emit(event)
            if notify_on_change and event.get("event") in ("write", "value_set"):
                value_hex = event.get("value_hex") or event.get("value") or ""
                try:
                    _send_value_update(bytes.fromhex(value_hex), event.get("event"))
                except Exception as exc:
                    _emit({{"event": "notify_error", "reason": event.get("event"), "error": repr(exc)}})

        if conn_handle[0] is not None and notify_interval_ms:
            now = time.ticks_ms()
            if time.ticks_diff(now, last_notify[0]) >= notify_interval_ms:
                value = ble.gatts_read(char_handle[0])
                _send_value_update(value, "interval")
                last_notify[0] = now
        time.sleep_ms(50)
except KeyboardInterrupt:
    _restore_if_needed()
    _emit({{"event": "stopped", "active": ble.active()}})
except Exception as exc:
    _restore_if_needed()
    _emit({{"error": repr(exc)}})
'''

    console = OutputHelper.make_console(width=CONSOLE_WIDTH, emoji=False)
    spinner = Spinner("dots")
    state = {
        "status": "starting",
        "svc": svc_uuid,
        "char": char_uuid,
        "props": list(server_props),
        "name": name,
        "value_hex": initial_value_hex,
        "value_view": initial_value_view if initial_value_hex else "hex",
        "payload_len": None,
        "payload_hex": None,
        "peer": None,
        "event": "starting",
        "error": None,
        "writes": 0,
        "notifies": 0,
        "indicates": 0,
        "last_update_reason": None,
        "notify_on_change": notify_on_change,
        "stopping": False,
        "editing": False,
        "edit_buffer": "",
        "edit_error": None,
    }
    live_ref: list[Live | None] = [None]
    stdout_buffer = bytearray()
    stop_requested = False
    pending_input: list[bytes] = []

    old_settings = None
    fd = None
    if not IS_WINDOWS:
        import termios
        import tty
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except Exception:
            old_settings = None

    def _status_text() -> Text:
        status = Text()
        if state["status"] == "connected":
            status.append("Connected", style="green")
            peer = state.get("peer") or {}
            if peer.get("addr"):
                status.append(f" from {peer.get('addr')}", style="bright_cyan")
        elif state["status"] == "ready":
            status.append("Advertising", style="bright_cyan")
        elif state["status"] == "stopping":
            status.append("Stopping", style="yellow")
        elif state["status"] == "stopped":
            status.append("Stopped", style="dim")
        elif state["status"] == "error":
            status.append("Failed", style="red")
        else:
            status.append("Starting GATT server", style="bright_cyan")
        return status

    def _current_value_input() -> str:
        if state.get("value_view") == "string":
            return "text:" + _ble_value_string(state.get("value_hex"))
        return "hex:" + str(state.get("value_hex") or "")

    def _render_value_editor():
        detail = Table.grid(padding=(0, 1))
        detail.add_column(justify="right", style="dim", no_wrap=True)
        detail.add_column(overflow="fold")
        detail.add_row("Current", _ble_value_text(state.get("value_hex"), state.get("value_view", "hex")))
        detail.add_row("Input", Text(str(state.get("edit_buffer") or "") + "_", style="bright_yellow"))
        detail.add_row("Format", "hex:DATA or text:TEXT")

        try:
            preview_hex = _ble_parse_value_arg_or_raise(str(state.get("edit_buffer") or ""))
            detail.add_row("Preview", _ble_value_text(preview_hex, state.get("value_view", "hex")))
            state["edit_error"] = None
        except ValueError as exc:
            state["edit_error"] = str(exc)

        if state.get("edit_error"):
            detail.add_row("Error", Text(str(state.get("edit_error")), style="red"))

        footer = Text("Enter apply, Space cancel", style="dim")
        return Panel(
            Group(detail, Text(""), footer),
            title="BLE Serve Value",
            title_align="left",
            border_style=OutputHelper._resolve_category_color("mode"),
            box=get_panel_box(),
            width=CONSOLE_WIDTH,
        )

    def _render_panel():
        if state.get("editing"):
            return _render_value_editor()

        status_line = Table.grid(padding=(0, 1))
        status_line.add_column(width=3)
        status_line.add_column()
        icon = spinner if state["status"] in ("starting", "ready", "connected", "stopping") else Text(" ")
        status_line.add_row(icon, _status_text())

        detail = Table.grid(padding=(0, 1))
        detail.add_column(justify="right", style="dim", no_wrap=True)
        detail.add_column(overflow="fold")
        detail.add_row("Device", Text(str(state.get("name") or name), style="bright_cyan"))
        detail.add_row("Service", Text(str(state.get("svc") or svc_uuid), style="bright_cyan"))
        detail.add_row("Characteristic", Text(str(state.get("char") or char_uuid), style="bright_cyan"))
        detail.add_row("Props", ", ".join(state.get("props") or props))
        detail.add_row("Value", _ble_value_text(state.get("value_hex"), state.get("value_view", "hex")))
        detail.add_row("Value view", str(state.get("value_view", "hex")))
        detail.add_row("Notify interval", f"{interval_ms} ms" if interval_ms else "-")
        detail.add_row("Notify on change", "on" if state.get("notify_on_change") else "off")
        if state.get("payload_len") is not None:
            detail.add_row("Payload", f"{state.get('payload_len')} bytes")
        if state.get("payload_hex"):
            detail.add_row("Payload hex", str(state.get("payload_hex")))
        if state.get("peer"):
            peer = state["peer"]
            detail.add_row("Peer addr", Text(peer.get("addr", "?"), style="bright_cyan"))
            detail.add_row("Peer type", f"{peer.get('addr_type', '?')} ({peer.get('addr_type_label', '?')})")
            detail.add_row("Conn handle", str(peer.get("conn_handle", "?")))
        if state.get("writes"):
            detail.add_row("Writes", str(state.get("writes")))
        if state.get("notifies"):
            detail.add_row("Notifies", str(state.get("notifies")))
        if state.get("indicates"):
            detail.add_row("Indicates", str(state.get("indicates")))
        if state.get("last_update_reason"):
            detail.add_row("Last update", str(state.get("last_update_reason")))
        if state.get("event"):
            detail.add_row("Event", str(state.get("event")))
        if state.get("error"):
            detail.add_row("Error", Text(str(state.get("error")), style="red"))

        footer = Text("c change value, v value view, q/Ctrl+C stop", style="dim")
        return Panel(
            Group(status_line, Text(""), detail, Text(""), footer),
            title="BLE Serve",
            title_align="left",
            border_style=OutputHelper._resolve_category_color("mode"),
            box=get_panel_box(),
            width=CONSOLE_WIDTH,
        )

    def _update_live():
        live = live_ref[0]
        if live is not None:
            live.update(_render_panel())

    def _value_from_event(obj: dict) -> str:
        if "value_hex" in obj:
            return str(obj.get("value_hex") or "").upper()
        if "value" in obj:
            return str(obj.get("value") or "").upper()
        return str(state.get("value_hex") or "").upper()

    def _apply_event(obj: dict):
        event_type = obj.get("event", "")
        nonfatal_errors = {"advertise_error", "notify_error", "indicate_error", "input_unavailable", "input_error", "value_error"}
        if obj.get("error") and event_type not in nonfatal_errors:
            state["status"] = "error"
            state["error"] = obj.get("error")
            state["event"] = "error"
        elif event_type == "ready":
            state["status"] = "ready"
            state["svc"] = obj.get("svc", state["svc"])
            state["char"] = obj.get("char", state["char"])
            state["props"] = obj.get("props") or state["props"]
            state["name"] = obj.get("name", state["name"])
            state["value_hex"] = _value_from_event(obj)
            state["payload_len"] = obj.get("payload_len")
            state["payload_hex"] = obj.get("payload_hex")
            state["event"] = "advertising"
        elif event_type == "connected":
            state["status"] = "connected"
            state["peer"] = obj.get("peer") or {}
            state["event"] = "connected"
        elif event_type == "disconnected":
            peer = obj.get("peer") or state.get("peer") or {}
            state["status"] = "ready"
            state["peer"] = None
            state["event"] = f"disconnected from {peer.get('addr', '?')}"
        elif event_type == "write":
            state["value_hex"] = _value_from_event(obj)
            state["writes"] += 1
            state["event"] = "write"
            state["error"] = None
        elif event_type == "value_set":
            state["value_hex"] = _value_from_event(obj)
            state["event"] = "value changed"
            state["error"] = None
        elif event_type == "notify":
            state["value_hex"] = _value_from_event(obj)
            state["notifies"] += 1
            state["last_update_reason"] = obj.get("reason")
            state["event"] = "notify"
        elif event_type == "indicate":
            state["value_hex"] = _value_from_event(obj)
            state["indicates"] += 1
            state["last_update_reason"] = obj.get("reason")
            state["event"] = "indicate"
        elif event_type in nonfatal_errors:
            state["event"] = event_type.replace("_", " ")
            state["error"] = obj.get("error")
        elif event_type == "stopped":
            state["status"] = "stopped"
            state["stopping"] = False
            state["event"] = "stopped"
        elif event_type:
            state["event"] = event_type

    def _request_stop():
        nonlocal stop_requested
        if stop_requested:
            return
        stop_requested = True
        state["status"] = "stopping"
        state["stopping"] = True
        state["editing"] = False
        state["event"] = "stopping"
        pending_input.append(CTRL_C)
        _update_live()

    def _toggle_value_view():
        state["value_view"] = "string" if state.get("value_view") == "hex" else "hex"
        state["event"] = f"value view: {state['value_view']}"
        _update_live()

    def _start_value_edit():
        state["editing"] = True
        state["edit_buffer"] = _current_value_input()
        state["edit_error"] = None
        state["event"] = "editing value"
        _update_live()

    def _cancel_value_edit():
        state["editing"] = False
        state["edit_buffer"] = ""
        state["edit_error"] = None
        state["event"] = "value edit canceled"
        _update_live()

    def _apply_value_edit():
        try:
            new_value_hex = _ble_parse_value_arg_or_raise(str(state.get("edit_buffer") or ""))
        except ValueError as exc:
            state["edit_error"] = str(exc)
            _update_live()
            return

        state["editing"] = False
        state["edit_buffer"] = ""
        state["edit_error"] = None
        state["event"] = "setting value"
        pending_input.append(("@replx:set-value:" + new_value_hex + "\n").encode("ascii"))
        _update_live()

    def _handle_editor_key(key):
        if key is None:
            return
        if key == "\x03" or key.lower() == "q":
            _request_stop()
            return
        if key in ("\r", "\n"):
            _apply_value_edit()
            return
        if key == " ":
            _cancel_value_edit()
            return
        if key in ("\x08", "\x7f"):
            state["edit_buffer"] = str(state.get("edit_buffer") or "")[:-1]
            state["edit_error"] = None
            _update_live()
            return
        if len(key) == 1 and key.isprintable():
            state["edit_buffer"] = str(state.get("edit_buffer") or "") + key
            state["edit_error"] = None
            _update_live()

    def _read_key():
        try:
            if IS_WINDOWS:
                import msvcrt
                if not msvcrt.kbhit():
                    return None
                key = msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    msvcrt.getwch()
                    return None
                return key

            import select
            if fd is None:
                return None
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if not ready:
                return None
            data = os.read(fd, 1)
            if data == CTRL_C:
                return "\x03"
            try:
                return data.decode("utf-8")
            except Exception:
                return None
        except Exception:
            return None

    def _handle_key(key):
        if key is None:
            return
        if state.get("editing"):
            _handle_editor_key(key)
            return
        if key == "\x03" or key.lower() == "q":
            _request_stop()
        elif key.lower() == "v":
            _toggle_value_view()
        elif key.lower() == "c":
            _start_value_edit()

    def _sigint_handler(signum, frame):
        _request_stop()

    def _input_provider() -> bytes:
        if pending_input:
            return pending_input.pop(0)
        _handle_key(_read_key())
        return b""

    def _stop_check() -> bool:
        return stop_requested

    def _on_output(chunk: bytes, stream_name: str):
        if stream_name == "stderr":
            text = chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else str(chunk)
            if text.strip():
                state["status"] = "error"
                state["error"] = text.strip()
                state["event"] = "error"
                _update_live()
            return

        data = chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8", errors="replace")
        stdout_buffer.extend(data.replace(b"\r", b"\n"))
        while b"\n" in stdout_buffer:
            line, _, rest = stdout_buffer.partition(b"\n")
            stdout_buffer[:] = rest
            text = line.decode("utf-8", "replace").strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
                _apply_event(obj)
            except (json.JSONDecodeError, ValueError):
                state["event"] = text
            _update_live()

    original_sigint = signal.getsignal(signal.SIGINT)

    try:
        signal.signal(signal.SIGINT, _sigint_handler)
        if not IS_WINDOWS and old_settings is not None and fd is not None:
            try:
                tty.setraw(fd)
            except Exception:
                pass

        with Live(_render_panel(), console=console, refresh_per_second=10, transient=False) as live:
            live_ref[0] = live
            client.run_interactive(
                script_content=code,
                echo=False,
                output_callback=_on_output,
                input_provider=_input_provider,
                stop_check=_stop_check,
                ctrl_c_grace_s=2.0,
            )
            if state["status"] not in ("error", "stopped"):
                state["status"] = "stopped"
                state["stopping"] = False
                state["event"] = "stopped by user" if stop_requested else "stopped"
                live.update(_render_panel())
        if state["status"] == "error":
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        _request_stop()
    except Exception as e:
        state["status"] = "error"
        state["error"] = str(e)
        state["event"] = "error"
        if live_ref[0] is not None:
            _update_live()
        else:
            OutputHelper.print_panel(f"Serve failed: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)
    finally:
        live_ref[0] = None
        signal.signal(signal.SIGINT, original_sigint)
        if not IS_WINDOWS and old_settings is not None and fd is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass


def _ble_client_from_args(client: AgentClient, args: list[str]):
    if not args:
        OutputHelper.print_panel(
            "Usage: [bright_blue]replx ble client ADDR --svc UUID --char UUID[/bright_blue]",
            title="BLE Error", border_style="error",
        )
        raise typer.Exit(1)

    addr = args[0]
    svc_uuid = None
    char_uuid = None
    value_hex = None
    value_view = "hex"
    auto_notify = False

    index = 1
    while index < len(args):
        arg = args[index]
        if arg == "--svc" and index + 1 < len(args):
            svc_uuid = args[index + 1]
            index += 2
        elif arg == "--char" and index + 1 < len(args):
            char_uuid = args[index + 1]
            index += 2
        elif arg == "--value":
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                _ble_advertise_arg_error("Missing value for [bright_blue]--value[/bright_blue].")
            value_text, index = _ble_collect_value_arg(args, index + 1)
            value_hex, value_view = _ble_parse_value_arg_detail(value_text)
        elif arg == "--notify":
            auto_notify = True
            index += 1
        else:
            index += 1

    if not svc_uuid or not char_uuid:
        OutputHelper.print_panel(
            "Required: [bright_blue]ADDR --svc UUID --char UUID[/bright_blue]\n\n"
            "Use [bright_blue]replx ble --help[/bright_blue] for usage.",
            title="BLE Error", border_style="error",
        )
        raise typer.Exit(1)

    _ble_client(client, addr, svc_uuid, char_uuid, value_hex, value_view, auto_notify)


def _ble_client(
    client: AgentClient,
    addr: str,
    svc_uuid: str,
    char_uuid: str,
    value_hex: str | None,
    initial_value_view: str = "hex",
    auto_notify: bool = False,
):
    addr_bytes_expr, addr_type_expr = _addr_to_parts(addr)
    svc_expr = _parse_uuid(svc_uuid)
    char_expr = _parse_uuid(char_uuid)
    addr_text_expr = json.dumps(addr)
    initial_value_hex = (value_hex or "").strip().upper()
    initial_value_hex_expr = json.dumps(initial_value_hex)

    code = f'''
import bluetooth, json, sys, time

_IRQ_PERIPHERAL_CONNECT = 7
_IRQ_PERIPHERAL_DISCONNECT = 8
_IRQ_GATTC_SERVICE_RESULT = 9
_IRQ_GATTC_SERVICE_DONE = 10
_IRQ_GATTC_CHARACTERISTIC_RESULT = 11
_IRQ_GATTC_CHARACTERISTIC_DONE = 12
_IRQ_GATTC_DESCRIPTOR_RESULT = 13
_IRQ_GATTC_DESCRIPTOR_DONE = 14
_IRQ_GATTC_READ_RESULT = 15
_IRQ_GATTC_READ_DONE = 16
_IRQ_GATTC_WRITE_DONE = 17
_IRQ_GATTC_NOTIFY = 18
_IRQ_GATTC_INDICATE = 19

ble = bluetooth.BLE()
addr_text = {addr_text_expr}
target_addr_type = {addr_type_expr}
target_addr = {addr_bytes_expr}
target_service_uuid = bluetooth.UUID({svc_expr})
target_char_uuid = bluetooth.UUID({char_expr})
initial_value_hex = {initial_value_hex_expr}
auto_notify = {str(auto_notify)}
was_active = False
conn_handle = [None]
connected = [False]
service_range = [None]
char_info = [None]
all_chars = []
descriptor_infos = []
descriptors_discovered = [False]
cccd_handle = [None]
cccd_source = [None]
read_result = [None]
notify_active = [False]
pending_commands = []
pending_events = []
input_poll = [None]
input_buffer = []
wait_flags = {{}}
wait_status = {{}}

def _emit(event):
    print(json.dumps(event))
    try:
        sys.stdout.flush()
    except Exception:
        pass

def _queue(event):
    pending_events.append(event)

def _flush_events():
    while pending_events:
        _emit(pending_events.pop(0))

def _hex(data):
    return "".join("%02X" % value for value in bytes(data))

def _uuid_equal(left, right):
    try:
        if left == right:
            return True
    except Exception:
        pass
    return str(left).lower() == str(right).lower()

def _status(data):
    try:
        return int(data[-1])
    except Exception:
        return 0

def _att_status_text(status):
    try:
        status = int(status)
    except Exception:
        return str(status)
    if status == 0:
        return "success"
    if status == 1:
        return "invalid handle"
    if status == 2:
        return "read not permitted"
    if status == 3:
        return "write not permitted"
    if status == 5:
        return "insufficient authentication"
    if status == 8:
        return "insufficient authorization"
    if status == 10:
        return "attribute not found"
    if status == 13:
        return "invalid attribute value length"
    if status == 15:
        return "insufficient encryption"
    return "status %s" % status

def _status_error(operation, status):
    return "%s failed: %s (%s)" % (operation, status, _att_status_text(status))

def _properties_text(value):
    names = []
    try:
        props = int(value)
    except Exception:
        props = 0
    if props & 0x02:
        names.append("READ")
    if props & 0x04:
        names.append("WRITE_NO_RESPONSE")
    if props & 0x08:
        names.append("WRITE")
    if props & 0x10:
        names.append("NOTIFY")
    if props & 0x20:
        names.append("INDICATE")
    return names

def _char_props():
    if not char_info[0]:
        return 0
    try:
        return int(char_info[0].get("properties") or 0)
    except Exception:
        return 0

def _has_prop(mask):
    return bool(_char_props() & mask)

def _begin_wait(name):
    wait_flags[name] = False
    wait_status[name] = None

def _wait(name, timeout_ms):
    start = time.ticks_ms()
    while not wait_flags.get(name):
        _read_input_commands()
        _flush_events()
        if time.ticks_diff(time.ticks_ms(), start) >= timeout_ms:
            return False
        time.sleep_ms(20)
    return True

def _ensure_active():
    try:
        if ble.active():
            return
    except Exception:
        pass
    try:
        ble.active(False)
    except Exception:
        pass
    time.sleep_ms(200)
    ble.active(True)
    time.sleep_ms(500)

def _setup_input():
    try:
        try:
            import select as _select
        except ImportError:
            import uselect as _select
        poll = _select.poll()
        poll.register(sys.stdin, _select.POLLIN)
        input_poll[0] = poll
    except Exception as exc:
        input_poll[0] = None
        _queue({{"event": "input_unavailable", "error": repr(exc)}})

def _handle_input_command(command):
    prefix = "@replx:client:"
    if command.startswith(prefix):
        pending_commands.append(command[len(prefix):].strip())

def _read_input_commands():
    poll = input_poll[0]
    if poll is None:
        return
    while True:
        try:
            events = poll.poll(0)
        except Exception as exc:
            input_poll[0] = None
            _queue({{"event": "input_error", "error": repr(exc)}})
            return
        if not events:
            return
        try:
            chunk = sys.stdin.read(1)
        except Exception as exc:
            input_poll[0] = None
            _queue({{"event": "input_error", "error": repr(exc)}})
            return
        if not chunk:
            return
        if isinstance(chunk, bytes):
            try:
                chunk = chunk.decode()
            except Exception:
                continue
        if chunk in ("\\r", "\\n"):
            command = "".join(input_buffer)
            del input_buffer[:]
            _handle_input_command(command.strip())
        else:
            input_buffer.append(chunk)
            if len(input_buffer) > 256:
                del input_buffer[:]
                _queue({{"event": "input_error", "error": "input command is too long"}})

def _irq(event, data):
    if event == _IRQ_PERIPHERAL_CONNECT:
        handle, addr_type, addr = data
        conn_handle[0] = handle
        connected[0] = True
        wait_flags["connect"] = True
        _queue({{"event": "connected", "addr": addr_text}})
    elif event == _IRQ_PERIPHERAL_DISCONNECT:
        handle, addr_type, addr = data
        if conn_handle[0] == handle:
            conn_handle[0] = None
            connected[0] = False
        wait_flags["disconnect"] = True
        _queue({{"event": "disconnected", "addr": addr_text}})
    elif event == _IRQ_GATTC_SERVICE_RESULT:
        handle, start_handle, end_handle, uuid = data
        if handle == conn_handle[0] and _uuid_equal(uuid, target_service_uuid):
            service_range[0] = (start_handle, end_handle)
    elif event == _IRQ_GATTC_SERVICE_DONE:
        wait_status["service"] = _status(data)
        wait_flags["service"] = True
    elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
        handle, char_end_handle, value_handle, properties, uuid = data
        if handle == conn_handle[0]:
            try:
                all_chars.append({{
                    "char_end_handle": char_end_handle,
                    "value_handle": value_handle,
                    "uuid": str(uuid),
                }})
            except Exception:
                pass
        if handle == conn_handle[0] and _uuid_equal(uuid, target_char_uuid):
            char_info[0] = {{
                "char_end_handle": char_end_handle,
                "value_handle": value_handle,
                "properties": properties,
                "props": _properties_text(properties),
            }}
    elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
        wait_status["char"] = _status(data)
        wait_flags["char"] = True
    elif event == _IRQ_GATTC_DESCRIPTOR_RESULT:
        handle, dsc_handle, uuid = data
        if handle == conn_handle[0]:
            try:
                descriptor_infos.append({{"handle": dsc_handle, "uuid": str(uuid)}})
            except Exception:
                pass
            if _uuid_equal(uuid, bluetooth.UUID(0x2902)):
                cccd_handle[0] = dsc_handle
                cccd_source[0] = "descriptor"
    elif event == _IRQ_GATTC_DESCRIPTOR_DONE:
        wait_status["descriptor"] = _status(data)
        wait_flags["descriptor"] = True
    elif event == _IRQ_GATTC_READ_RESULT:
        handle, value_handle, value = data
        if handle == conn_handle[0] and char_info[0] and value_handle == char_info[0].get("value_handle"):
            read_result[0] = bytes(value)
    elif event == _IRQ_GATTC_READ_DONE:
        wait_status["read"] = _status(data)
        wait_flags["read"] = True
    elif event == _IRQ_GATTC_WRITE_DONE:
        wait_status["write"] = _status(data)
        wait_flags["write"] = True
    elif event in (_IRQ_GATTC_NOTIFY, _IRQ_GATTC_INDICATE):
        handle, value_handle, value = data
        if handle == conn_handle[0] and char_info[0] and value_handle == char_info[0].get("value_handle"):
            value_hex = _hex(value)
            _queue({{"event": "notify", "kind": "indicate" if event == _IRQ_GATTC_INDICATE else "notify", "value": value_hex, "value_hex": value_hex, "bytes": len(value)}})

def _connect():
    _begin_wait("connect")
    ble.gap_connect(target_addr_type, target_addr)
    if not _wait("connect", 6000):
        raise OSError("connection timeout")
    if conn_handle[0] is None:
        raise OSError("connection failed")

def _disconnect():
    handle = conn_handle[0]
    if handle is None:
        return
    _begin_wait("disconnect")
    try:
        ble.gap_disconnect(handle)
        _wait("disconnect", 1200)
    except Exception:
        pass
    conn_handle[0] = None
    connected[0] = False

def _discover_service():
    service_range[0] = None
    _begin_wait("service")
    ble.gattc_discover_services(conn_handle[0])
    if not _wait("service", 5000):
        raise OSError("service discovery timeout")
    if wait_status.get("service") not in (0, None):
        raise OSError("service discovery failed: %s" % wait_status.get("service"))
    if service_range[0] is None:
        raise ValueError("service not found")

def _discover_char():
    char_info[0] = None
    del all_chars[:]
    start_handle, end_handle = service_range[0]
    _begin_wait("char")
    ble.gattc_discover_characteristics(conn_handle[0], start_handle, end_handle)
    if not _wait("char", 5000):
        raise OSError("characteristic discovery timeout")
    if wait_status.get("char") not in (0, None):
        raise OSError("characteristic discovery failed: %s" % wait_status.get("char"))
    if char_info[0] is None:
        raise ValueError("characteristic not found")

    descriptor_end = None
    try:
        value_handle = int(char_info[0].get("value_handle"))
        result_handle = int(char_info[0].get("char_end_handle"))
        if result_handle >= value_handle:
            descriptor_end = result_handle
    except Exception:
        descriptor_end = None
    if descriptor_end is None:
        next_result = None
        try:
            target_result = int(char_info[0].get("char_end_handle"))
            for item in all_chars:
                candidate = int(item.get("char_end_handle"))
                if candidate > target_result and (next_result is None or candidate < next_result):
                    next_result = candidate
        except Exception:
            next_result = None
        if next_result is not None:
            descriptor_end = next_result - 1
    char_info[0]["descriptor_end"] = descriptor_end if descriptor_end is not None else service_range[0][1]

def _discover_profile():
    last_error = None
    for attempt in range(3):
        try:
            if attempt:
                _emit({{"event": "discovery_retry", "attempt": attempt + 1, "error": repr(last_error)}})
                time.sleep_ms(500)
            _discover_service()
            _discover_char()
            return
        except OSError as exc:
            last_error = exc
            if attempt >= 2:
                raise
            _disconnect()
            time.sleep_ms(500)
            _emit({{"event": "connecting", "addr": addr_text}})
            _connect()
    raise last_error

def _discover_descriptors():
    if descriptors_discovered[0]:
        return
    del descriptor_infos[:]
    cccd_handle[0] = None
    cccd_source[0] = None
    start_handle = char_info[0].get("value_handle") + 1
    end_handle = char_info[0].get("descriptor_end") or service_range[0][1]
    if start_handle > end_handle:
        descriptors_discovered[0] = True
        return
    _begin_wait("descriptor")
    ble.gattc_discover_descriptors(conn_handle[0], start_handle, end_handle)
    if not _wait("descriptor", 5000):
        raise OSError("descriptor discovery timeout")
    descriptors_discovered[0] = True

def _discover_cccd():
    if cccd_handle[0] is not None:
        return
    _discover_descriptors()
    if cccd_handle[0] is not None:
        return
    start_handle = char_info[0].get("value_handle") + 1
    end_handle = char_info[0].get("descriptor_end") or service_range[0][1]
    if start_handle > end_handle:
        raise ValueError("notify descriptor not found")
    if cccd_handle[0] is None:
        fallback_handle = char_info[0].get("value_handle") + 1
        if fallback_handle <= end_handle:
            cccd_handle[0] = fallback_handle
            cccd_source[0] = "fallback"
        else:
            raise ValueError("notify descriptor 0x2902 not found")

def _read_remote_value():
    if not _has_prop(0x02):
        raise ValueError("characteristic does not advertise READ")
    read_result[0] = None
    _begin_wait("read")
    ble.gattc_read(conn_handle[0], char_info[0].get("value_handle"))
    if not _wait("read", 4000):
        raise OSError("read timeout")
    if wait_status.get("read") not in (0, None):
        raise OSError(_status_error("read", wait_status.get("read")))
    return read_result[0] or b""

def _read_value(reason):
    value = _read_remote_value()
    value_hex = _hex(value)
    _emit({{"event": "read", "reason": reason, "value": value_hex, "value_hex": value_hex, "bytes": len(value)}})

def _write_value(value, reason):
    value_handle = char_info[0].get("value_handle")
    if _has_prop(0x08):
        _begin_wait("write")
        try:
            ble.gattc_write(conn_handle[0], value_handle, value, 1)
        except TypeError:
            ble.gattc_write(conn_handle[0], value_handle, value)
        else:
            if not _wait("write", 4000):
                raise OSError("write timeout")
            if wait_status.get("write") not in (0, None):
                raise OSError(_status_error("write", wait_status.get("write")))
    elif _has_prop(0x04):
        try:
            ble.gattc_write(conn_handle[0], value_handle, value, 0)
        except TypeError:
            ble.gattc_write(conn_handle[0], value_handle, value)
        time.sleep_ms(100)
    else:
        raise ValueError("characteristic does not advertise WRITE or WRITE_NO_RESPONSE")
    requested_hex = _hex(value)
    value_hex = requested_hex
    readback_hex = None
    verified = None
    verify_error = None
    if _has_prop(0x02):
        try:
            readback = _read_remote_value()
            readback_hex = _hex(readback)
            value_hex = readback_hex
            verified = readback == value
        except Exception as exc:
            verify_error = repr(exc)
    _emit({{
        "event": "write",
        "reason": reason,
        "requested": requested_hex,
        "requested_hex": requested_hex,
        "readback_hex": readback_hex,
        "verified": verified,
        "verify_error": verify_error,
        "value": value_hex,
        "value_hex": value_hex,
        "bytes": len(value),
    }})

def _set_notify(enabled):
    if enabled and not (_has_prop(0x10) or _has_prop(0x20)):
        raise ValueError("characteristic does not advertise NOTIFY or INDICATE")
    _discover_cccd()
    if enabled and _has_prop(0x20) and not _has_prop(0x10):
        value = b"\\x02\\x00"
    elif enabled:
        value = b"\\x01\\x00"
    else:
        value = b"\\x00\\x00"
    _begin_wait("write")
    ble.gattc_write(conn_handle[0], cccd_handle[0], value, 1)
    if not _wait("write", 4000):
        raise OSError("notify setup timeout")
    if wait_status.get("write") not in (0, None):
        raise OSError(_status_error("notify setup", wait_status.get("write")))
    notify_active[0] = enabled
    _emit({{"event": "notify_state", "enabled": enabled, "cccd_handle": cccd_handle[0], "cccd_source": cccd_source[0]}})

def _handle_client_command(command):
    if command == "read":
        _read_value("manual")
    elif command.startswith("write:"):
        _write_value(bytes.fromhex(command.split(":", 1)[1].strip()), "manual")
    elif command == "notify:on":
        _set_notify(True)
    elif command == "notify:off":
        _set_notify(False)
    elif command == "stop":
        _emit({{"event": "stopped"}})
        return False
    return True

try:
    try:
        was_active = ble.active()
    except Exception:
        was_active = False
    _ensure_active()
    ble.irq(_irq)
    _setup_input()
    _emit({{"event": "connecting", "addr": addr_text}})
    _connect()
    _discover_profile()
    if _has_prop(0x10) or _has_prop(0x20):
        try:
            _discover_descriptors()
        except Exception as exc:
            _emit({{"event": "notify_warning", "error": repr(exc)}})
    _emit({{
        "event": "ready",
        "addr": addr_text,
        "svc": "{svc_uuid}",
        "char": "{char_uuid}",
        "props": char_info[0].get("props") or [],
        "properties": char_info[0].get("properties"),
        "service_start": service_range[0][0],
        "service_end": service_range[0][1],
        "char_end_handle": char_info[0].get("char_end_handle"),
        "value_handle": char_info[0].get("value_handle"),
        "descriptor_end": char_info[0].get("descriptor_end"),
        "descriptors": descriptor_infos,
        "cccd_handle": cccd_handle[0],
        "cccd_source": cccd_source[0],
    }})
    if _has_prop(0x02):
        try:
            _read_value("initial")
        except Exception as exc:
            _emit({{"event": "command_error", "command": "initial read", "error": repr(exc)}})
    if initial_value_hex:
        try:
            _write_value(bytes.fromhex(initial_value_hex), "initial")
        except Exception as exc:
            _emit({{"event": "command_error", "command": "initial write", "error": repr(exc)}})
    if auto_notify:
        try:
            _set_notify(True)
        except Exception as exc:
            _emit({{"event": "command_error", "command": "notify:on", "error": repr(exc)}})
    while conn_handle[0] is not None:
        _read_input_commands()
        while pending_commands:
            command = pending_commands.pop(0)
            try:
                if not _handle_client_command(command):
                    raise KeyboardInterrupt
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                _emit({{"event": "command_error", "command": command, "error": repr(exc)}})
        _flush_events()
        time.sleep_ms(50)
except KeyboardInterrupt:
    _emit({{"event": "stopped"}})
except Exception as exc:
    _emit({{"error": repr(exc)}})
finally:
    if conn_handle[0] is not None:
        try:
            ble.gap_disconnect(conn_handle[0])
        except Exception:
            pass
    if not was_active:
        try:
            ble.active(False)
        except Exception:
            pass
'''

    console = OutputHelper.make_console(width=CONSOLE_WIDTH, emoji=False)
    spinner = Spinner("dots")
    state = {
        "status": "starting",
        "addr": addr,
        "svc": svc_uuid,
        "char": char_uuid,
        "props": [],
        "properties": None,
        "service_start": None,
        "service_end": None,
        "char_end_handle": None,
        "value_handle": None,
        "descriptor_end": None,
        "descriptors": [],
        "cccd_handle": None,
        "cccd_source": None,
        "value_hex": initial_value_hex,
        "value_view": initial_value_view if initial_value_hex else "hex",
        "event": "starting",
        "error": None,
        "hint": None,
        "reads": 0,
        "writes": 0,
        "write_requested_hex": None,
        "write_readback_hex": None,
        "write_verified": None,
        "write_verify_error": None,
        "notifies": 0,
        "notify_enabled": False,
        "stopping": False,
        "editing": False,
        "edit_buffer": "",
        "edit_error": None,
    }
    live_ref: list[Live | None] = [None]
    stdout_buffer = bytearray()
    stop_requested = False
    pending_input: list[bytes] = []

    old_settings = None
    fd = None
    if not IS_WINDOWS:
        import termios
        import tty
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except Exception:
            old_settings = None

    def _status_text() -> Text:
        status = Text()
        if state["status"] == "connected":
            status.append("Connected", style="green")
        elif state["status"] == "ready":
            status.append("Ready", style="bright_cyan")
        elif state["status"] == "stopping":
            status.append("Stopping", style="yellow")
        elif state["status"] == "stopped":
            status.append("Stopped", style="dim")
        elif state["status"] == "error":
            status.append("Failed", style="red")
        else:
            status.append("Connecting", style="bright_cyan")
        return status

    def _current_value_input() -> str:
        if state.get("value_view") == "string":
            return "text:" + _ble_value_string(state.get("value_hex"))
        return "hex:" + str(state.get("value_hex") or "")

    def _write_check_text() -> Text | None:
        requested = state.get("write_requested_hex")
        verified = state.get("write_verified")
        readback = state.get("write_readback_hex")
        verify_error = state.get("write_verify_error")
        if requested is None and verified is None and not verify_error:
            return None
        text = Text()
        if verified is True:
            text.append("verified", style="green")
            text.append(f" sent {requested or '-'}", style="dim")
            text.append(f", read {readback or requested or '-'}", style="dim")
        elif verified is False:
            text.append("mismatch", style="yellow")
            text.append(f" sent {requested or '-'}", style="dim")
            text.append(f", read {readback or '-'}", style="dim")
        elif verify_error:
            text.append("not verified", style="yellow")
            text.append(f" ({verify_error})", style="dim")
        else:
            text.append("not checked", style="dim")
            if requested:
                text.append(f" ({requested})", style="dim")
        return text

    def _render_value_editor():
        detail = Table.grid(padding=(0, 1))
        detail.add_column(justify="right", style="dim", no_wrap=True)
        detail.add_column(overflow="fold")
        detail.add_row("Current", _ble_value_text(state.get("value_hex"), state.get("value_view", "hex")))
        detail.add_row("Input", Text(str(state.get("edit_buffer") or "") + "_", style="bright_yellow"))
        detail.add_row("Format", "hex:DATA or text:TEXT")

        try:
            preview_hex = _ble_parse_value_arg_or_raise(str(state.get("edit_buffer") or ""))
            detail.add_row("Preview", _ble_value_text(preview_hex, state.get("value_view", "hex")))
            state["edit_error"] = None
        except ValueError as exc:
            state["edit_error"] = str(exc)

        if state.get("edit_error"):
            detail.add_row("Error", Text(str(state.get("edit_error")), style="red"))

        footer = Text("Enter write, Space cancel", style="dim")
        return Panel(
            Group(detail, Text(""), footer),
            title="BLE Client Value",
            title_align="left",
            border_style=OutputHelper._resolve_category_color("mode"),
            box=get_panel_box(),
            width=CONSOLE_WIDTH,
        )

    def _render_panel():
        if state.get("editing"):
            return _render_value_editor()

        status_line = Table.grid(padding=(0, 1))
        status_line.add_column(width=3)
        status_line.add_column()
        icon = spinner if state["status"] in ("starting", "connecting", "connected", "ready", "stopping") else Text(" ")
        status_line.add_row(icon, _status_text())

        detail = Table.grid(padding=(0, 1))
        detail.add_column(justify="right", style="dim", no_wrap=True)
        detail.add_column(overflow="fold")
        detail.add_row("Address", Text(str(state.get("addr") or addr), style="bright_cyan"))
        detail.add_row("Service", Text(str(state.get("svc") or svc_uuid), style="bright_cyan"))
        detail.add_row("Characteristic", Text(str(state.get("char") or char_uuid), style="bright_cyan"))
        if state.get("props"):
            detail.add_row("Props", ", ".join(state.get("props") or []))
        if state.get("properties") is not None:
            detail.add_row("Props hex", "0x%02X" % int(state.get("properties") or 0))
        if state.get("service_start") is not None and state.get("service_end") is not None:
            detail.add_row("Service range", f"{state.get('service_start')}..{state.get('service_end')}")
        if state.get("char_end_handle") is not None:
            detail.add_row("Char end", str(state.get("char_end_handle")))
        if state.get("value_handle") is not None:
            detail.add_row("Value handle", str(state.get("value_handle")))
        if state.get("descriptor_end") is not None:
            detail.add_row("Desc end", str(state.get("descriptor_end")))
        if state.get("descriptors"):
            descriptor_text = ", ".join(
                f"{item.get('handle')}:{item.get('uuid')}" for item in state.get("descriptors")[:3]
            )
            if len(state.get("descriptors") or []) > 3:
                descriptor_text += ", ..."
            detail.add_row("Descriptors", descriptor_text)
        if state.get("cccd_handle") is not None:
            detail.add_row("CCCD handle", str(state.get("cccd_handle")))
        if state.get("cccd_source"):
            detail.add_row("CCCD source", str(state.get("cccd_source")))
        detail.add_row("Value", _ble_value_text(state.get("value_hex"), state.get("value_view", "hex")))
        detail.add_row("Value view", str(state.get("value_view", "hex")))
        detail.add_row("Notify", "on" if state.get("notify_enabled") else "off")
        if state.get("reads"):
            detail.add_row("Reads", str(state.get("reads")))
        if state.get("writes"):
            detail.add_row("Writes", str(state.get("writes")))
        write_check = _write_check_text()
        if write_check is not None:
            detail.add_row("Last write", write_check)
        if state.get("notifies"):
            detail.add_row("Notifications", str(state.get("notifies")))
        if state.get("event"):
            detail.add_row("Event", str(state.get("event")))
        if state.get("error"):
            detail.add_row("Error", Text(str(state.get("error")), style="red"))
        if state.get("hint"):
            detail.add_row("Hint", Text(str(state.get("hint")), style="yellow"))

        footer = Text("r read, w write, n notify, v value view, q/Ctrl+C stop", style="dim")
        return Panel(
            Group(status_line, Text(""), detail, Text(""), footer),
            title="BLE Client",
            title_align="left",
            border_style=OutputHelper._resolve_category_color("mode"),
            box=get_panel_box(),
            width=CONSOLE_WIDTH,
        )

    def _update_live():
        live = live_ref[0]
        if live is not None:
            live.update(_render_panel())

    def _value_from_event(obj: dict) -> str:
        if "value_hex" in obj:
            return str(obj.get("value_hex") or "").upper()
        if "value" in obj:
            return str(obj.get("value") or "").upper()
        return str(state.get("value_hex") or "").upper()

    def _hint_for_error(error_text: str | None) -> str | None:
        text = str(error_text or "").lower()
        if "read not permitted" in text:
            return "Remote server denied READ. In nRF Connect, enable read permission as well as the READ property."
        if "write not permitted" in text:
            return "Remote server denied WRITE. In nRF Connect, enable write permission as well as the WRITE property."
        if "service discovery failed: 31" in text:
            return "Discovery returned BLE status 31. This is often transient after reconnect/build; retrying usually recovers."
        if "write verification mismatch" in text:
            return "Remote read-back did not match the sent value. The server acknowledged the write but kept another value."
        if "notify descriptor" in text or "cccd" in text:
            return "NOTIFY needs a CCCD descriptor 0x2902 on the server characteristic."
        return None

    def _apply_event(obj: dict):
        event_type = obj.get("event", "")
        nonfatal_errors = {"input_unavailable", "input_error", "notify_error", "notify_warning", "command_error", "discovery_retry"}
        if obj.get("error") and event_type not in nonfatal_errors:
            state["status"] = "error"
            state["error"] = obj.get("error")
            state["event"] = "error"
        elif event_type == "connecting":
            state["status"] = "connecting"
            state["event"] = "connecting"
        elif event_type == "connected":
            state["status"] = "connected"
            state["event"] = "connected"
        elif event_type == "ready":
            state["status"] = "ready"
            state["addr"] = obj.get("addr", state["addr"])
            state["svc"] = obj.get("svc", state["svc"])
            state["char"] = obj.get("char", state["char"])
            state["props"] = obj.get("props") or state.get("props") or []
            state["properties"] = obj.get("properties", state.get("properties"))
            state["service_start"] = obj.get("service_start", state.get("service_start"))
            state["service_end"] = obj.get("service_end", state.get("service_end"))
            state["char_end_handle"] = obj.get("char_end_handle", state.get("char_end_handle"))
            state["value_handle"] = obj.get("value_handle", state.get("value_handle"))
            state["descriptor_end"] = obj.get("descriptor_end", state.get("descriptor_end"))
            state["descriptors"] = obj.get("descriptors") or state.get("descriptors") or []
            state["cccd_handle"] = obj.get("cccd_handle", state.get("cccd_handle"))
            state["cccd_source"] = obj.get("cccd_source", state.get("cccd_source"))
            state["event"] = "ready"
            state["error"] = None
            state["hint"] = None
        elif event_type == "disconnected":
            state["status"] = "stopped"
            state["notify_enabled"] = False
            state["event"] = "disconnected"
        elif event_type == "read":
            state["value_hex"] = _value_from_event(obj)
            state["reads"] += 1
            state["event"] = "initial read" if obj.get("reason") == "initial" else "read"
            state["error"] = None
            state["hint"] = None
        elif event_type == "write":
            state["value_hex"] = _value_from_event(obj)
            state["writes"] += 1
            state["write_requested_hex"] = obj.get("requested_hex") or obj.get("requested")
            state["write_readback_hex"] = obj.get("readback_hex")
            state["write_verified"] = obj.get("verified")
            state["write_verify_error"] = obj.get("verify_error")
            if obj.get("verified") is False:
                state["event"] = "write verify mismatch"
                state["hint"] = _hint_for_error("write verification mismatch")
            else:
                state["event"] = "initial write" if obj.get("reason") == "initial" else "write"
                state["hint"] = None
            state["error"] = None
        elif event_type == "notify":
            state["value_hex"] = _value_from_event(obj)
            state["notifies"] += 1
            state["event"] = "notify"
            state["error"] = None
        elif event_type == "notify_state":
            state["notify_enabled"] = bool(obj.get("enabled"))
            state["cccd_handle"] = obj.get("cccd_handle", state.get("cccd_handle"))
            state["cccd_source"] = obj.get("cccd_source", state.get("cccd_source"))
            state["event"] = "notify on" if state["notify_enabled"] else "notify off"
            state["error"] = None
            state["hint"] = None
        elif event_type == "notify_warning":
            state["event"] = "notify warning"
            state["hint"] = _hint_for_error(obj.get("error")) or obj.get("error")
        elif event_type in nonfatal_errors:
            state["event"] = event_type.replace("_", " ")
            state["error"] = obj.get("error")
            state["hint"] = _hint_for_error(obj.get("error"))
        elif event_type == "stopped":
            state["status"] = "stopped"
            state["stopping"] = False
            state["event"] = "stopped"
        elif event_type:
            state["event"] = event_type

    def _request_stop():
        nonlocal stop_requested
        if stop_requested:
            return
        stop_requested = True
        state["status"] = "stopping"
        state["stopping"] = True
        state["editing"] = False
        state["event"] = "stopping"
        pending_input.append(CTRL_C)
        _update_live()

    def _request_read():
        state["event"] = "reading"
        pending_input.append(b"@replx:client:read\n")
        _update_live()

    def _toggle_notify():
        desired = not bool(state.get("notify_enabled"))
        state["event"] = "notify on requested" if desired else "notify off requested"
        command = b"@replx:client:notify:on\n" if desired else b"@replx:client:notify:off\n"
        pending_input.append(command)
        _update_live()

    def _toggle_value_view():
        state["value_view"] = "string" if state.get("value_view") == "hex" else "hex"
        state["event"] = f"value view: {state['value_view']}"
        _update_live()

    def _start_value_edit():
        state["editing"] = True
        state["edit_buffer"] = _current_value_input()
        state["edit_error"] = None
        state["event"] = "editing value"
        _update_live()

    def _cancel_value_edit():
        state["editing"] = False
        state["edit_buffer"] = ""
        state["edit_error"] = None
        state["event"] = "value edit canceled"
        _update_live()

    def _apply_value_edit():
        try:
            new_value_hex = _ble_parse_value_arg_or_raise(str(state.get("edit_buffer") or ""))
        except ValueError as exc:
            state["edit_error"] = str(exc)
            _update_live()
            return

        state["editing"] = False
        state["edit_buffer"] = ""
        state["edit_error"] = None
        state["event"] = "writing"
        pending_input.append(("@replx:client:write:" + new_value_hex + "\n").encode("ascii"))
        _update_live()

    def _handle_editor_key(key):
        if key is None:
            return
        if key == "\x03" or key.lower() == "q":
            _request_stop()
            return
        if key in ("\r", "\n"):
            _apply_value_edit()
            return
        if key == " ":
            _cancel_value_edit()
            return
        if key in ("\x08", "\x7f"):
            state["edit_buffer"] = str(state.get("edit_buffer") or "")[:-1]
            state["edit_error"] = None
            _update_live()
            return
        if len(key) == 1 and key.isprintable():
            state["edit_buffer"] = str(state.get("edit_buffer") or "") + key
            state["edit_error"] = None
            _update_live()

    def _read_key():
        try:
            if IS_WINDOWS:
                import msvcrt
                if not msvcrt.kbhit():
                    return None
                key = msvcrt.getwch()
                if key in ("\x00", "\xe0"):
                    msvcrt.getwch()
                    return None
                return key

            import select
            if fd is None:
                return None
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if not ready:
                return None
            data = os.read(fd, 1)
            if data == CTRL_C:
                return "\x03"
            try:
                return data.decode("utf-8")
            except Exception:
                return None
        except Exception:
            return None

    def _handle_key(key):
        if key is None:
            return
        if state.get("editing"):
            _handle_editor_key(key)
            return
        if key == "\x03" or key.lower() == "q":
            _request_stop()
        elif key.lower() == "r":
            _request_read()
        elif key.lower() == "w":
            _start_value_edit()
        elif key.lower() == "n":
            _toggle_notify()
        elif key.lower() == "v":
            _toggle_value_view()

    def _sigint_handler(signum, frame):
        _request_stop()

    def _input_provider() -> bytes:
        if pending_input:
            return pending_input.pop(0)
        _handle_key(_read_key())
        return b""

    def _stop_check() -> bool:
        return stop_requested

    def _on_output(chunk: bytes, stream_name: str):
        if stream_name == "stderr":
            text = chunk.decode("utf-8", errors="replace") if isinstance(chunk, bytes) else str(chunk)
            if text.strip():
                state["status"] = "error"
                state["error"] = text.strip()
                state["event"] = "error"
                _update_live()
            return

        data = chunk if isinstance(chunk, bytes) else str(chunk).encode("utf-8", errors="replace")
        stdout_buffer.extend(data.replace(b"\r", b"\n"))
        while b"\n" in stdout_buffer:
            line, _, rest = stdout_buffer.partition(b"\n")
            stdout_buffer[:] = rest
            text = line.decode("utf-8", "replace").strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
                _apply_event(obj)
            except (json.JSONDecodeError, ValueError):
                state["event"] = text
            _update_live()

    original_sigint = signal.getsignal(signal.SIGINT)

    try:
        signal.signal(signal.SIGINT, _sigint_handler)
        if not IS_WINDOWS and old_settings is not None and fd is not None:
            try:
                tty.setraw(fd)
            except Exception:
                pass

        with Live(_render_panel(), console=console, refresh_per_second=10, transient=False) as live:
            live_ref[0] = live
            client.run_interactive(
                script_content=code,
                echo=False,
                output_callback=_on_output,
                input_provider=_input_provider,
                stop_check=_stop_check,
                ctrl_c_grace_s=2.0,
            )
            if state["status"] not in ("error", "stopped"):
                state["status"] = "stopped"
                state["stopping"] = False
                state["event"] = "stopped by user" if stop_requested else "stopped"
                live.update(_render_panel())
        if state["status"] == "error":
            raise typer.Exit(1)
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        _request_stop()
    except Exception as exc:
        state["status"] = "error"
        state["error"] = str(exc)
        state["event"] = "error"
        if live_ref[0] is not None:
            _update_live()
        else:
            OutputHelper.print_panel(f"Client failed: {exc}", title="BLE Error", border_style="error")
        raise typer.Exit(1)
    finally:
        live_ref[0] = None
        signal.signal(signal.SIGINT, original_sigint)


def _ble_ping(client: AgentClient, addr: str):
    addr_bytes_expr, addr_type_expr = _addr_to_parts(addr)
    addr_expr = json.dumps(addr)
    code = f'''
import bluetooth, json, time

_IRQ_PERIPHERAL_CONNECT = 7
_IRQ_PERIPHERAL_DISCONNECT = 8

ble = bluetooth.BLE()
addr_text = {addr_expr}
target_addr_type = {addr_type_expr}
target_addr = {addr_bytes_expr}
was_active = False
conn_handle = [None]
connected = [False]
disconnected = [False]

def _irq(event, data):
    if event == _IRQ_PERIPHERAL_CONNECT:
        handle, addr_type, addr = data
        conn_handle[0] = handle
        connected[0] = True
    elif event == _IRQ_PERIPHERAL_DISCONNECT:
        handle, addr_type, addr = data
        if conn_handle[0] == handle:
            connected[0] = False
            conn_handle[0] = None
        disconnected[0] = True

def _ensure_active():
    try:
        if ble.active():
            return
    except Exception:
        pass
    try:
        ble.active(False)
    except Exception:
        pass
    time.sleep_ms(200)
    ble.active(True)
    time.sleep_ms(500)

def _wait(predicate, timeout_ms):
    start = time.ticks_ms()
    while not predicate():
        if time.ticks_diff(time.ticks_ms(), start) >= timeout_ms:
            return False
        time.sleep_ms(50)
    return True

try:
    try:
        was_active = ble.active()
    except Exception:
        was_active = False
    _ensure_active()
    ble.irq(_irq)
    ble.gap_connect(target_addr_type, target_addr)
    if not _wait(lambda: connected[0], 6000):
        print(json.dumps({{"ok": False, "error": "connection timeout", "addr": addr_text}}))
    else:
        try:
            ble.gap_disconnect(conn_handle[0])
            _wait(lambda: disconnected[0], 1500)
        except Exception:
            pass
        print(json.dumps({{"ok": True, "addr": addr_text}}))
except Exception as exc:
    print(json.dumps({{"ok": False, "error": str(exc), "addr": addr_text}}))
finally:
    if not was_active:
        try:
            ble.active(False)
        except Exception:
            pass
'''
    console = OutputHelper.make_console(width=CONSOLE_WIDTH, emoji=False)
    spinner = Spinner("dots")
    state = {
        "status": "pinging",
        "addr": addr,
        "addr_type": "random" if str(addr_type_expr) == "1" else "public",
        "error": None,
    }

    def _render_panel():
        status_line = Table.grid(padding=(0, 1))
        status_line.add_column(width=3)
        status_line.add_column()

        if state["status"] == "pinging":
            icon = spinner
            status = Text("Pinging", style="bright_cyan")
        elif state["status"] == "reachable":
            icon = Text(chr(0xf0a50), style="green")
            status = Text("Reachable", style="green")
        else:
            icon = Text("✗", style="red")
            status = Text("Unreachable", style="red")
        status_line.add_row(icon, status)

        detail = Table.grid(padding=(0, 1))
        detail.add_column(justify="right", style="dim", no_wrap=True)
        detail.add_column(overflow="fold")
        detail.add_row("Address", Text(str(state.get("addr") or addr), style="bright_cyan"))
        detail.add_row("Addr type", str(state.get("addr_type") or "?"))
        if state["status"] != "pinging":
            detail.add_row("Result", "reachable" if state["status"] == "reachable" else "unreachable")
        if state.get("error"):
            detail.add_row("Error", Text(str(state.get("error")), style="red"))

        border_style = "mode"
        if state["status"] == "reachable":
            border_style = "success"
        elif state["status"] == "unreachable":
            border_style = "error"

        return Panel(
            Group(status_line, Text(""), detail),
            title="BLE Ping",
            title_align="left",
            border_style=OutputHelper._resolve_category_color(border_style),
            box=get_panel_box(),
            width=CONSOLE_WIDTH,
        )

    try:
        with Live(_render_panel(), console=console, refresh_per_second=10, transient=False) as live:
            try:
                data = _exec(client, code, timeout=12)
            except Exception as exc:
                state["status"] = "unreachable"
                state["error"] = str(exc)
                live.update(_render_panel())
                raise typer.Exit(1)

            if data.get("ok"):
                state["status"] = "reachable"
                state["addr"] = data.get("addr") or addr
                state["error"] = None
                live.update(_render_panel())
            else:
                state["status"] = "unreachable"
                state["addr"] = data.get("addr") or addr
                state["error"] = data.get("error") or "connection failed"
                live.update(_render_panel())
                raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        OutputHelper.print_panel(f"Ping failed: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)


def _ble_gattc_once_code(addr: str, svc_uuid: str, char_uuid: str, operation: str, value_hex: str | None = None) -> str:
    addr_bytes_expr, addr_type_expr = _addr_to_parts(addr)
    svc_expr = _parse_uuid(svc_uuid)
    char_expr = _parse_uuid(char_uuid)
    addr_expr = json.dumps(addr)
    operation_expr = json.dumps(operation)
    value_hex_expr = json.dumps((value_hex or "").strip().upper())
    return f'''
import bluetooth, json, time

_IRQ_PERIPHERAL_CONNECT = 7
_IRQ_PERIPHERAL_DISCONNECT = 8
_IRQ_GATTC_SERVICE_RESULT = 9
_IRQ_GATTC_SERVICE_DONE = 10
_IRQ_GATTC_CHARACTERISTIC_RESULT = 11
_IRQ_GATTC_CHARACTERISTIC_DONE = 12
_IRQ_GATTC_READ_RESULT = 15
_IRQ_GATTC_READ_DONE = 16
_IRQ_GATTC_WRITE_DONE = 17

ble = bluetooth.BLE()
addr_text = {addr_expr}
target_addr_type = {addr_type_expr}
target_addr = {addr_bytes_expr}
target_service_uuid = bluetooth.UUID({svc_expr})
target_char_uuid = bluetooth.UUID({char_expr})
operation = {operation_expr}
write_hex = {value_hex_expr}
was_active = False
conn_handle = [None]
connected = [False]
service_range = [None]
char_info = [None]
read_result = [None]
wait_flags = {{}}
wait_status = {{}}

def _hex(data):
    return "".join("%02X" % value for value in bytes(data))

def _uuid_equal(left, right):
    try:
        if left == right:
            return True
    except Exception:
        pass
    return str(left).lower() == str(right).lower()

def _status(data):
    try:
        return int(data[-1])
    except Exception:
        return 0

def _att_status_text(status):
    try:
        status = int(status)
    except Exception:
        return str(status)
    if status == 0:
        return "success"
    if status == 1:
        return "invalid handle"
    if status == 2:
        return "read not permitted"
    if status == 3:
        return "write not permitted"
    if status == 5:
        return "insufficient authentication"
    if status == 8:
        return "insufficient authorization"
    if status == 10:
        return "attribute not found"
    if status == 13:
        return "invalid attribute value length"
    if status == 15:
        return "insufficient encryption"
    return "status %s" % status

def _status_error(operation, status):
    return "%s failed: %s (%s)" % (operation, status, _att_status_text(status))

def _char_props():
    if not char_info[0]:
        return 0
    try:
        return int(char_info[0].get("properties") or 0)
    except Exception:
        return 0

def _has_prop(mask):
    return bool(_char_props() & mask)

def _begin_wait(name):
    wait_flags[name] = False
    wait_status[name] = None

def _wait(name, timeout_ms):
    start = time.ticks_ms()
    while not wait_flags.get(name):
        if time.ticks_diff(time.ticks_ms(), start) >= timeout_ms:
            return False
        time.sleep_ms(20)
    return True

def _ensure_active():
    try:
        if ble.active():
            return
    except Exception:
        pass
    try:
        ble.active(False)
    except Exception:
        pass
    time.sleep_ms(200)
    ble.active(True)
    time.sleep_ms(500)

def _irq(event, data):
    if event == _IRQ_PERIPHERAL_CONNECT:
        handle, addr_type, addr = data
        conn_handle[0] = handle
        connected[0] = True
        wait_flags["connect"] = True
    elif event == _IRQ_PERIPHERAL_DISCONNECT:
        handle, addr_type, addr = data
        if conn_handle[0] == handle:
            conn_handle[0] = None
            connected[0] = False
        wait_flags["disconnect"] = True
    elif event == _IRQ_GATTC_SERVICE_RESULT:
        handle, start_handle, end_handle, uuid = data
        if handle == conn_handle[0] and _uuid_equal(uuid, target_service_uuid):
            service_range[0] = (start_handle, end_handle)
    elif event == _IRQ_GATTC_SERVICE_DONE:
        wait_status["service"] = _status(data)
        wait_flags["service"] = True
    elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
        handle, char_end_handle, value_handle, properties, uuid = data
        if handle == conn_handle[0] and _uuid_equal(uuid, target_char_uuid):
            char_info[0] = {{"char_end_handle": char_end_handle, "value_handle": value_handle, "properties": properties}}
    elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
        wait_status["char"] = _status(data)
        wait_flags["char"] = True
    elif event == _IRQ_GATTC_READ_RESULT:
        handle, value_handle, value = data
        if handle == conn_handle[0] and char_info[0] and value_handle == char_info[0].get("value_handle"):
            read_result[0] = bytes(value)
    elif event == _IRQ_GATTC_READ_DONE:
        wait_status["read"] = _status(data)
        wait_flags["read"] = True
    elif event == _IRQ_GATTC_WRITE_DONE:
        wait_status["write"] = _status(data)
        wait_flags["write"] = True

def _connect():
    _begin_wait("connect")
    ble.gap_connect(target_addr_type, target_addr)
    if not _wait("connect", 6000):
        raise OSError("connection timeout")
    if conn_handle[0] is None:
        raise OSError("connection failed")

def _disconnect():
    handle = conn_handle[0]
    if handle is None:
        return
    _begin_wait("disconnect")
    try:
        ble.gap_disconnect(handle)
        _wait("disconnect", 1200)
    except Exception:
        pass
    conn_handle[0] = None
    connected[0] = False

def _discover_service():
    service_range[0] = None
    _begin_wait("service")
    ble.gattc_discover_services(conn_handle[0])
    if not _wait("service", 5000):
        raise OSError("service discovery timeout")
    if wait_status.get("service") not in (0, None):
        raise OSError("service discovery failed: %s" % wait_status.get("service"))
    if service_range[0] is None:
        raise ValueError("service not found")

def _discover_char():
    char_info[0] = None
    start_handle, end_handle = service_range[0]
    _begin_wait("char")
    ble.gattc_discover_characteristics(conn_handle[0], start_handle, end_handle)
    if not _wait("char", 5000):
        raise OSError("characteristic discovery timeout")
    if wait_status.get("char") not in (0, None):
        raise OSError("characteristic discovery failed: %s" % wait_status.get("char"))
    if char_info[0] is None:
        raise ValueError("characteristic not found")

def _discover_profile():
    last_error = None
    for attempt in range(3):
        try:
            if attempt:
                time.sleep_ms(500)
            _discover_service()
            _discover_char()
            return
        except OSError as exc:
            last_error = exc
            if attempt >= 2:
                raise
            _disconnect()
            time.sleep_ms(500)
            _connect()
    raise last_error

def _read_value():
    if not _has_prop(0x02):
        raise ValueError("characteristic does not advertise READ")
    read_result[0] = None
    _begin_wait("read")
    ble.gattc_read(conn_handle[0], char_info[0].get("value_handle"))
    if not _wait("read", 4000):
        raise OSError("read timeout")
    if wait_status.get("read") not in (0, None):
        raise OSError(_status_error("read", wait_status.get("read")))
    value = read_result[0] or b""
    print(json.dumps({{"value_hex": _hex(value), "value_bytes": list(value)}}))

def _write_value():
    value = bytes.fromhex(write_hex)
    value_handle = char_info[0].get("value_handle")
    write_mode = None
    if _has_prop(0x08):
        write_mode = "response"
        _begin_wait("write")
        try:
            ble.gattc_write(conn_handle[0], value_handle, value, 1)
        except TypeError:
            ble.gattc_write(conn_handle[0], value_handle, value)
            write_mode = "default"
        else:
            if not _wait("write", 4000):
                raise OSError("write timeout")
            if wait_status.get("write") not in (0, None):
                raise OSError(_status_error("write", wait_status.get("write")))
    elif _has_prop(0x04):
        write_mode = "no-response"
        try:
            ble.gattc_write(conn_handle[0], value_handle, value, 0)
        except TypeError:
            ble.gattc_write(conn_handle[0], value_handle, value)
        time.sleep_ms(100)
    else:
        raise ValueError("characteristic does not advertise WRITE or WRITE_NO_RESPONSE")
    print(json.dumps({{"ok": True, "written_hex": _hex(value), "mode": write_mode}}))

try:
    try:
        was_active = ble.active()
    except Exception:
        was_active = False
    _ensure_active()
    ble.irq(_irq)
    _connect()
    _discover_profile()
    if operation == "read":
        _read_value()
    elif operation == "write":
        _write_value()
    else:
        raise ValueError("unknown operation")
except Exception as exc:
    print(json.dumps({{"error": str(exc)}}))
finally:
    if conn_handle[0] is not None:
        try:
            ble.gap_disconnect(conn_handle[0])
        except Exception:
            pass
    if not was_active:
        try:
            ble.active(False)
        except Exception:
            pass
'''

def _ble_read(client: AgentClient, addr: str, svc_uuid: str, char_uuid: str):
    code = _ble_gattc_once_code(addr, svc_uuid, char_uuid, "read")
    console = OutputHelper.make_console()
    spinner = Spinner("dots", text=Text(f" Reading from {addr}...", style="bright_cyan"))
    try:
        with Live(spinner, console=console, refresh_per_second=10, transient=True):
            data = _exec(client, code, timeout=15)

        if "error" in data:
            OutputHelper.print_panel(
                f"[red]Read failed:[/red] {data['error']}",
                title="BLE Read", border_style="error",
            )
            raise typer.Exit(1)

        hex_val = data.get("value_hex", "?")
        byte_list = data.get("value_bytes", [])
        printable = "".join(chr(b) if 32 <= b < 127 else "." for b in byte_list)
        OutputHelper.print_panel(
            f"  Hex:   [bright_yellow]{hex_val.upper()}[/bright_yellow]\n"
            f"  Bytes: {byte_list}\n"
            f"  ASCII: [dim]{printable}[/dim]",
            title=f"BLE Read  {addr}", border_style="data",
        )
    except typer.Exit:
        raise
    except Exception as e:
        OutputHelper.print_panel(f"Read failed: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)


def _ble_write(client: AgentClient, addr: str, svc_uuid: str, char_uuid: str, hex_value: str):
    code = _ble_gattc_once_code(addr, svc_uuid, char_uuid, "write", hex_value)
    console = OutputHelper.make_console()
    spinner = Spinner("dots", text=Text(f" Writing to {addr}...", style="bright_cyan"))
    try:
        with Live(spinner, console=console, refresh_per_second=10, transient=True):
            data = _exec(client, code, timeout=15)

        if "error" in data:
            OutputHelper.print_panel(
                f"[red]Write failed:[/red] {data['error']}",
                title="BLE Write", border_style="error",
            )
            raise typer.Exit(1)

        OutputHelper.print_panel(
            f"[green]✓ Written[/green]: [bright_yellow]{data.get('written_hex', hex_value.upper())}[/bright_yellow]  →  [bright_cyan]{addr}[/bright_cyan]",
            title="BLE Write", border_style="success",
        )
    except typer.Exit:
        raise
    except Exception as e:
        OutputHelper.print_panel(f"Write failed: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)


def _ble_stream_send(client: AgentClient, addr: str, psm: str, hex_value: str):
    addr_bytes_expr, addr_type_expr = _addr_to_parts(addr)
    psm_val = int(psm, 16) if psm.lower().startswith("0x") else int(psm)
    bytes_expr = _hex_to_bytes_expr(hex_value)
    code = _AIOBLE_CHECK + f'''
import aioble, aioble.l2cap, asyncio, bluetooth, json

async def main():
    device = aioble.Device({addr_type_expr}, {addr_bytes_expr})
    try:
        async with await device.connect(timeout_ms=5000) as conn:
            channel = await aioble.l2cap.connect(conn, {psm_val}, mtu=128, timeout_ms=5000)
            async with channel:
                buf = {bytes_expr}
                await channel.send(buf, timeout_ms=5000)
                print(json.dumps({{"ok": True, "sent_bytes": len(buf), "hex": "{hex_value.upper()}"}}))
    except Exception as e:
        print(json.dumps({{"error": str(e)}}))

asyncio.run(main())
'''
    console = OutputHelper.make_console()
    spinner = Spinner("dots", text=Text(f" L2CAP sending to {addr} (PSM={psm})...", style="bright_cyan"))
    try:
        with Live(spinner, console=console, refresh_per_second=10, transient=True):
            data = _exec(client, code, timeout=20)

        if not _check_aioble(data):
            raise typer.Exit(1)

        if "error" in data:
            OutputHelper.print_panel(
                f"[red]Stream send failed:[/red] {data['error']}",
                title="BLE Stream", border_style="error",
            )
            raise typer.Exit(1)

        OutputHelper.print_panel(
            f"[green]✓ Sent[/green] {data.get('sent_bytes')} bytes: "
            f"[bright_yellow]{data.get('hex')}[/bright_yellow]  →  [bright_cyan]{addr}[/bright_cyan] (PSM={psm})",
            title="BLE Stream Send", border_style="success",
        )
    except typer.Exit:
        raise
    except Exception as e:
        OutputHelper.print_panel(f"Stream send failed: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)


def _ble_stream_recv(client: AgentClient, psm: str):
    psm_val = int(psm, 16) if psm.lower().startswith("0x") else int(psm)
    code = _AIOBLE_CHECK + f'''
import aioble, aioble.l2cap, asyncio, bluetooth, json, binascii

async def main():
    import json as _json
    print(_json.dumps({{"event": "ready", "psm": {psm_val}}}))
    while True:
        channel = await aioble.l2cap.accept(None, {psm_val}, mtu=128)
        async with channel:
            addr = ":".join("%02X" % b for b in bytes(channel.connection.device.addr))
            print(_json.dumps({{"event": "connected", "addr": addr}}))
            buf = bytearray(256)
            while True:
                try:
                    n = await channel.recvinto(buf, timeout_ms=0)
                    if n == 0:
                        break
                    chunk = bytes(buf[:n])
                    print(_json.dumps({{
                        "event": "data",
                        "addr": addr,
                        "hex": binascii.hexlify(chunk).decode(),
                        "bytes": n,
                    }}))
                except Exception:
                    break
            print(_json.dumps({{"event": "disconnected", "addr": addr}}))

asyncio.run(main())
'''

    console = OutputHelper.make_console()

    def _on_event(data: dict):
        evt_str = data.get("output", "").strip() if isinstance(data, dict) else str(data)
        for line in evt_str.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                event_type = obj.get("event", "")
                if event_type == "ready":
                    msg = f"[green]● L2CAP server ready[/green] — PSM={obj.get('psm')}  (Ctrl+C to stop)"
                elif event_type == "connected":
                    msg = f"  [green]→ Connected[/green]: [bright_cyan]{obj.get('addr')}[/bright_cyan]"
                elif event_type == "data":
                    msg = (f"  [yellow]⇩ Data[/yellow] from [bright_cyan]{obj.get('addr')}[/bright_cyan]: "
                           f"[bright_yellow]{obj.get('hex', '').upper()}[/bright_yellow] "
                           f"([dim]{obj.get('bytes')} bytes[/dim])")
                elif event_type == "disconnected":
                    msg = f"  [dim]← Disconnected[/dim]: {obj.get('addr')} — waiting..."
                else:
                    msg = f"  {line}"
            except (json.JSONDecodeError, ValueError):
                msg = f"  {line}"
            console.print(msg)

    try:
        OutputHelper.print_panel(
            f"Starting L2CAP receiver on PSM={psm}. Press [bold]Ctrl+C[/bold] to stop.",
            title="BLE Stream Recv", border_style="mode",
        )
        client.send_command_streaming("exec", code=code, timeout=86400.0, progress_callback=_on_event)
        OutputHelper.print_panel("L2CAP receiver stopped.", title="BLE Stream Recv", border_style="neutral")
    except KeyboardInterrupt:
        OutputHelper.print_panel("L2CAP receiver stopped by user.", title="BLE Stream Recv", border_style="neutral")
    except Exception as e:
        OutputHelper.print_panel(f"Stream recv failed: {e}", title="BLE Error", border_style="error")
        raise typer.Exit(1)
