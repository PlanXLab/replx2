import json
import re
import sys
from typing import Optional
from replx.utils.device_info import normalize_core

PinId = int | str


def exec_code(client, code: str, timeout: float = 5.0) -> str:
    result = client.send_command('exec', code=code, timeout=timeout, max_retries=1)
    return ((result or {}).get('output') or '').strip()


def parse_json_strict(raw: str):
    if not raw:
        raise RuntimeError('No output from device')
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'Device error:\n{raw}') from exc


def normalize_port(port: Optional[str]) -> Optional[str]:
    if port and sys.platform.startswith('win'):
        return port.upper()
    return port


def parse_gp_pin(token: str, label: str = 'pin') -> int:
    """Parse numeric MCU pins, preserving the original GP notation."""
    s = (token or '').strip()
    match = re.fullmatch(r'(?:GPIO|GP)?([0-9]+)', s, re.IGNORECASE)
    if not match:
        raise ValueError(f"Invalid {label}: {token!r}. Use GP2, GPIO2, or 2")
    return int(match.group(1))


def parse_hardware_pin(token: str, label: str = 'pin') -> PinId:
    s = (token or '').strip().upper()
    if re.fullmatch(r'D[0-9]|P[0-2]', s):
        return s
    return parse_gp_pin(token, label)


def pin_label(pin: PinId) -> str:
    return pin if isinstance(pin, str) else f"GP{pin}"


def is_xbee(client) -> bool:
    return normalize_core(get_core(client, None)) == 'EFR32MG'


def require_standard_hardware(client, feature: str) -> None:
    if is_xbee(client):
        raise ValueError(
            f"{feature} is not supported by replx on Digi XBee3 Zigbee. "
            "Use the supported GPIO, ADC read, or I2C controller commands; "
            "see the platform support table in the manual."
        )
    if feature in ('wifi', 'ble'):
        module, attribute = ('network', 'WLAN') if feature == 'wifi' else ('bluetooth', 'BLE')
        code = (
            "try:\n"
            f" import {module}\n"
            f" print(hasattr({module},{attribute!r}))\n"
            "except ImportError:\n"
            " print(False)"
        )
        if exec_code(client, code, timeout=3.0) != 'True':
            raise ValueError(
                f"{feature} requires firmware exposing {module}.{attribute}. "
                "On ESP32-P4-WIFI6, use a compatible C6 Wi-Fi/BLE firmware "
                "variant and coprocessor firmware, not a standalone P4 build."
            )


def parse_text_bytes(tokens: list[str]) -> list[int]:
    """Encode text as UTF-8 while preserving common escapes and raw \\xHH bytes."""
    text = ' '.join(tokens)
    result = bytearray()
    plain: list[str] = []

    def flush_plain() -> None:
        if plain:
            result.extend(''.join(plain).encode('utf-8'))
            plain.clear()

    index = 0
    escapes = {'n': '\n', 'r': '\r', 't': '\t', '\\': '\\'}
    while index < len(text):
        if text[index] != '\\' or index + 1 >= len(text):
            plain.append(text[index])
            index += 1
            continue
        code = text[index + 1]
        if code in escapes:
            plain.append(escapes[code])
            index += 2
        elif code == 'x' and index + 3 < len(text):
            pair = text[index + 2:index + 4]
            try:
                value = int(pair, 16)
            except ValueError:
                plain.append('\\')
                index += 1
                continue
            flush_plain()
            result.append(value)
            index += 4
        else:
            plain.append('\\')
            index += 1
    flush_plain()
    return list(result)


def get_connection_info(client, port: Optional[str] = None) -> Optional[dict]:
    try:
        info = client.send_command('session_info', timeout=1.5)
    except Exception:
        return None

    if not info:
        return None

    connections = info.get('connections', [])
    if not connections:
        return None

    if port is None:
        return connections[0]

    normalized_port = normalize_port(port)
    for connection in connections:
        if normalize_port(connection.get('port', '')) == normalized_port:
            return connection
    return None


def get_connection_field(client, port: Optional[str], field: str) -> str:
    connection = (
        client.send_command('status') if port is None
        else get_connection_info(client, port)
    )
    if not connection:
        return ''

    value = connection.get(field, '')
    if value is None:
        return ''
    return value if isinstance(value, str) else str(value)


def get_core(client, port: Optional[str]) -> str:
    return get_connection_field(client, port, 'core')


def get_device(client, port: Optional[str]) -> str:
    return get_connection_field(client, port, 'device')


def _ascii_char(b: int) -> str:
    return chr(b) if 0x20 <= b <= 0x7E else '.'


def render_hex_row(data: bytes, offset: int, width: int = 16) -> str:
    half = width // 2
    if len(data) > half:
        left = ' '.join(f'{b:02X}' for b in data[:half])
        right = ' '.join(f'{b:02X}' for b in data[half:])
        hex_str = left + '  ' + right
    else:
        hex_str = ' '.join(f'{b:02X}' for b in data)

    padded_width = (half * 3 - 1) + 2 + (half * 3 - 1)
    hex_padded = hex_str.ljust(padded_width)
    ascii_str = ''.join(_ascii_char(b) for b in data).ljust(width)

    return (
        f'[dim]{offset:06X}[/dim]  '
        f'[bright_cyan]{hex_padded}[/bright_cyan]  '
        f'[dim]{ascii_str}[/dim]'
    )


def render_hex_dump(data: bytes, width: int = 16) -> str:
    if not data:
        return '[dim](no data)[/dim]'

    half = width // 2
    header_hex = (
        ' '.join(f'{i:02X}' for i in range(half))
        + '  '
        + ' '.join(f'{i:02X}' for i in range(half, width))
    )
    padded_width = (half * 3 - 1) + 2 + (half * 3 - 1)
    separator_width = 8 + padded_width + 2 + width

    lines = [
        f'[dim]Offset  {header_hex}  ASCII[/dim]',
        '[dim]' + '─' * separator_width + '[/dim]',
    ]
    for offset in range(0, len(data), width):
        lines.append(render_hex_row(data[offset:offset + width], offset, width))
    return '\n'.join(lines)