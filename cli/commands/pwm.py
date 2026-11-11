import json
import math
import shutil
import sys
from typing import Optional

import typer

from ..helpers import OutputHelper
from ..connection import _ensure_connected, _create_agent_client
from ..app import app
from ._common import exec_code as _exec, parse_json_strict as _parse_json_strict
from ._common import parse_gp_pin, require_standard_hardware
from ...terminal import enable_vt_mode, restore_vt_mode

_DUTY_MODES = {"percent", "u16", "pulse_us"}
_BOARD_PWM_STATE = "__replx_pwm_state__"


def _parse_gp(token: str) -> tuple[int, str]:
    pin_no = parse_gp_pin(token, 'PWM pin')
    return pin_no, f"GP{pin_no}"


def _parse_freq(freq: Optional[float]) -> float:
    if freq is None:
        raise ValueError("--freq is required")
    if freq <= 0:
        raise ValueError("--freq must be > 0")
    return float(freq)


def _parse_duty_mode(token: Optional[str]) -> str:
    if token is None:
        raise ValueError("--duty is required and must be one of: percent, u16, pulse_us")
    mode = token.strip().lower()
    if mode not in _DUTY_MODES:
        raise ValueError("--duty must be one of: percent, u16, pulse_us")
    return mode


def _require_finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _period_us(freq: float) -> float:
    return 1_000_000.0 / freq


def _value_to_duty_u16(mode: str, value: float | int, freq: float) -> int:
    if mode == 'percent':
        percent = _require_finite(float(value), 'Duty percent')
        if percent < 0.0 or percent > 100.0:
            raise ValueError("Duty percent must be in range 0..100")
        return max(0, min(65535, int(round(percent * 65535.0 / 100.0))))

    if mode == 'u16':
        duty_u16 = int(value)
        if duty_u16 < 0 or duty_u16 > 65535:
            raise ValueError("Duty u16 must be in range 0..65535")
        return duty_u16

    if mode == 'pulse_us':
        pulse_us = _require_finite(float(value), 'Pulse width')
        if pulse_us < 0.0:
            raise ValueError("Pulse width must be >= 0")
        period_us = _period_us(freq)
        if pulse_us > period_us:
            raise ValueError(
                f"Pulse width must be <= PWM period ({period_us:.3f} us at {freq} Hz)"
            )
        return max(0, min(65535, int(round(pulse_us * 65535.0 / period_us))))

    raise ValueError(f"Unsupported duty mode: {mode}")


def _duty_percent_from_u16(duty_u16: int) -> float:
    return float(duty_u16) * 100.0 / 65535.0


def _pulse_us_from_u16(duty_u16: int, freq: float) -> float:
    return float(duty_u16) * _period_us(freq) / 65535.0


def _format_number(value: float | int, digits: int = 3) -> str:
    if isinstance(value, int):
        return str(value)
    f = float(value)
    if f.is_integer():
        return str(int(f))
    return f"{f:.{digits}f}".rstrip('0').rstrip('.')


def _pick_write_level(
    duty_percent: Optional[float],
    duty_u16: Optional[int],
    pulse_us: Optional[float],
) -> tuple[str, float | int]:
    choices: list[tuple[str, float | int]] = []
    if duty_percent is not None:
        choices.append(('percent', duty_percent))
    if duty_u16 is not None:
        choices.append(('u16', duty_u16))
    if pulse_us is not None:
        choices.append(('pulse_us', pulse_us))

    if len(choices) != 1:
        raise ValueError(
            "Specify exactly one of: --duty-percent, --duty-u16, --pulse-us"
        )
    return choices[0]


def _parse_seq_value(token: str, mode: str) -> float | int:
    text = (token or '').strip()
    if not text:
        raise ValueError("Empty seq token is not allowed")

    if mode == 'u16':
        if not text.isdigit():
            raise ValueError(f"Invalid duty token: {token!r}. Use a decimal integer for --duty u16")
        return int(text)

    try:
        value = float(text)
    except ValueError:
        label = 'percent' if mode == 'percent' else 'pulse_us'
        raise ValueError(f"Invalid duty token: {token!r}. Use a numeric value for --duty {label}")

    return _require_finite(value, 'Duty token')


def _parse_seq_tokens(tokens: list[str], mode: str) -> list[tuple[str, float | int]]:
    if not tokens:
        raise ValueError("pwm seq requires one or more duty/delay tokens")

    ops: list[tuple[str, float | int]] = []
    write_count = 0

    for token in tokens:
        t = token.strip().lower()
        if len(t) >= 2 and t[0] in ('u', 'm') and t[1:].isdigit():
            ops.append((t[0], int(t[1:])))
            continue

        value = _parse_seq_value(token, mode)
        ops.append(('d', value))
        write_count += 1

    if write_count == 0:
        raise ValueError("pwm seq requires at least one duty token")

    return ops


def _format_seq_ops(ops: list[tuple[str, float | int]]) -> str:
    parts = []
    for kind, value in ops:
        if kind == 'd':
            parts.append(_format_number(value))
        elif kind == 'u':
            parts.append(f"u{int(value)}")
        elif kind == 'm':
            parts.append(f"m{int(value)}")
    return '-'.join(parts) if parts else '-'


def _check_has_pio(client) -> bool:
    code = (
        "try:\n"
        " import rp2\n"
        " @rp2.asm_pio()\n"
        " def _t2(): nop()\n"
        " _sm=rp2.StateMachine(7,_t2)\n"
        " _sm.active(0)\n"
        " print('pio:yes')\n"
        "except Exception:\n"
        " print('pio:no')\n"
    )
    try:
        raw = _exec(client, code, timeout=4.0)
        return 'pio:yes' in raw
    except Exception:
        return False


def _pwm_init_snippet(error_line: str) -> str:
    return (
        f"_state=globals().setdefault({_BOARD_PWM_STATE!r}, {{}})\n"
        "p=_state.get(pin_no)\n"
        "if p is None:\n"
        "    p=PWM(Pin(pin_no))\n"
        "    _state[pin_no]=p\n"
        "try:\n"
        "    p.freq(int(round(freq)))\n"
        "except Exception as _e:\n"
        "    p.deinit()\n"
        "    _state.pop(pin_no,None)\n"
        f"    {error_line}\n"
        "    raise SystemExit\n"
    )


def _make_write_code(pin_no: int, pin_name: str, freq: float, mode: str, value: float | int, duty_u16: int) -> str:
    pulse_ns_line = ""
    if mode == 'pulse_us':
        pulse_ns_line = (
            f"pulse_ns=int(round(float({float(value)!r})*1000.0))\n"
            "try:\n"
            "    p.duty_ns(pulse_ns)\n"
            "except Exception:\n"
            f"    p.duty_u16({int(duty_u16)})\n"
        )
    else:
        pulse_ns_line = f"p.duty_u16({int(duty_u16)})\n"

    return (
        "from machine import Pin,PWM\n"
        "import json\n"
        f"pin_no={pin_no}\n"
        f"freq={float(freq)!r}\n"
        f"input_mode={mode!r}\n"
        f"input_value={repr(value)}\n"
        f"duty_u16={int(duty_u16)}\n"
        "period_us=1000000.0/freq\n"
        + _pwm_init_snippet("print(json.dumps({'error':str(_e)}))")
        + pulse_ns_line +
        "pulse_us=(duty_u16*period_us)/65535.0\n"
        f"print(json.dumps({{'pin':{pin_name!r},'freq':freq,'input_mode':input_mode,'input_value':input_value,'duty_u16':duty_u16,'pulse_us':pulse_us,'active':True}}))"
    )


def _make_seq_code(pin_no: int, pin_name: str, freq: float, mode: str, ops: list[tuple[str, float | int]]) -> str:
    py_ops = repr(ops)
    return (
        "from machine import Pin,PWM\n"
        "import time,json\n"
        f"pin_no={pin_no}\n"
        f"freq={float(freq)!r}\n"
        f"mode={mode!r}\n"
        f"ops={py_ops}\n"
        "period_us=1000000.0/freq\n"
        + _pwm_init_snippet("print(json.dumps({'error':str(_e)}))")
        + "writes=0\n"
        "last_value=None\n"
        "last_u16=0\n"
        "last_pulse_ns=0\n"
        "def _u16(v):\n"
        "    if mode=='percent': return max(0,min(65535,int(round(v*65535.0/100.0))))\n"
        "    if mode=='u16': return int(v)\n"
        "    return max(0,min(65535,int(round(v*65535.0/period_us))))\n"
        "for kind,val in ops:\n"
        "    if kind=='d':\n"
        "        last_u16=_u16(val)\n"
        "        if mode=='pulse_us':\n"
        "            last_pulse_ns=int(round(float(val)*1000.0))\n"
        "            try:\n"
        "                p.duty_ns(last_pulse_ns)\n"
        "            except Exception:\n"
        "                p.duty_u16(last_u16)\n"
        "        else:\n"
        "            p.duty_u16(last_u16)\n"
        "        last_value=val\n"
        "        writes+=1\n"
        "    elif kind=='u':\n"
        "        time.sleep_us(int(val))\n"
        "    elif kind=='m':\n"
        "        time.sleep_ms(int(val))\n"
        "pulse_us=(last_u16*period_us)/65535.0\n"
        f"print(json.dumps({{'pin':{pin_name!r},'freq':freq,'mode':mode,'writes':writes,'final_value':last_value,'duty_u16':last_u16,'pulse_us':pulse_us,'active':True}}))"
    )


def _make_stop_code(pin_no: int, pin_name: str) -> str:
    return (
        "from machine import Pin,PWM\n"
        "import json\n"
        f"pin_no={pin_no}\n"
        f"_state=globals().setdefault({_BOARD_PWM_STATE!r}, {{}})\n"
        "p=_state.pop(pin_no,None)\n"
        "if p is None:\n"
        "    p=PWM(Pin(pin_no))\n"
        "p.deinit()\n"
        "pin=Pin(pin_no,Pin.OUT)\n"
        "pin.value(0)\n"
        f"print(json.dumps({{'pin':{pin_name!r},'stopped':True,'value':pin.value()}}))"
    )


def _make_seq_repeat_code(pin_no: int, pin_name: str, freq: float, mode: str, ops: list[tuple[str, float | int]], repeat: int, num_row: int) -> str:
    py_ops = repr(ops)
    loop_line = "    while True:\n" if repeat == 0 else f"    for _r in range({repeat}):\n"
    return (
        "import sys,select as _sel,time\n"
        "from machine import Pin,PWM\n"
        f"pin_no={pin_no}\n"
        f"freq={float(freq)!r}\n"
        f"mode={mode!r}\n"
        f"ops={py_ops}\n"
        "period_us=1000000.0/freq\n"
        + _pwm_init_snippet("print('Error:',_e)")
        + "def _u16(v):\n"
        "    if mode=='percent': return max(0,min(65535,int(round(v*65535.0/100.0))))\n"
        "    if mode=='u16': return int(v)\n"
        "    return max(0,min(65535,int(round(v*65535.0/period_us))))\n"
        "def _pk():\n"
        "    r,_,_=_sel.select([sys.stdin],[],[],0)\n"
        "    if r:\n"
        "        if sys.stdin.read(1)=='\\x03': raise KeyboardInterrupt\n"
        "def _slm(ms):\n"
        "    _e=time.ticks_add(time.ticks_ms(),ms)\n"
        "    while time.ticks_diff(_e,time.ticks_ms())>0:\n"
        "        _pk()\n"
        "        time.sleep_ms(min(50,max(1,time.ticks_diff(_e,time.ticks_ms()))))\n"
        "_fl=getattr(sys.stdout,'flush',lambda:None)\n"
        "w=sys.stdout.write\n"
        "_n=1\n"
        "try:\n"
        + loop_line +
        f"        w('\\033[{num_row};8H#'+str(_n))\n"
        "        _fl()\n"
        "        for kind,val in ops:\n"
        "            if kind=='d':\n"
        "                _v=_u16(val)\n"
        "                if mode=='pulse_us':\n"
        "                    try: p.duty_ns(int(round(float(val)*1000.0)))\n"
        "                    except Exception: p.duty_u16(_v)\n"
        "                else: p.duty_u16(_v)\n"
        "            elif kind=='u': time.sleep_us(int(val))\n"
        "            elif kind=='m': _slm(int(val))\n"
        "        _n+=1\n"
        "except KeyboardInterrupt:\n"
        "    pass\n"
    )


_MONITOR_SHARED = r'''
_Y  = '\033[38;2;255;255;100m'
_G  = '\033[38;2;80;255;120m'
_D  = '\033[38;2;150;150;150m'
_O  = '\033[38;2;255;160;80m'
_R  = '\033[0m'
_EL = '\033[K'
_I_HZ  = '\U000F095B'
_I_PER = '\uF0B6'
_I_HI  = '\uF2FA'
_I_LO  = '\uF2F8'
_I_D16 = '\uE84A'
_I_PCT = '\uF295'
_V  = '\uE621'
_flush = getattr(sys.stdout, 'flush', lambda: None)


def _poll_key():
    r, _, _ = _sel.select([sys.stdin], [], [], 0)
    if r:
        ch = sys.stdin.read(1)
        if ch == '\x03':
            raise KeyboardInterrupt


def _ts(start_ms):
    s = time.ticks_diff(time.ticks_ms(), start_ms) // 1000
    return f'{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}'


def _fmt_pwm(freq, duty, period_us, high_us, low_us):
    d16 = round(duty * 65535 / 100)
    return (
        _V + ' ' + _I_HZ + ' ' + _Y + f'{freq:6d} Hz' + _R
        + ' ' + _V + ' ' + _I_PER + f' {period_us:7d} us'
        + ' ' + _V + ' ' + _I_HI  + f' {high_us:9.1f} us'
        + ' ' + _V + ' ' + _I_LO  + f' {low_us:9.1f} us'
        + ' ' + _V + ' ' + _I_D16 + ' ' + _Y + f'{d16:5d}/65535' + _R
        + ' ' + _V + ' ' + _I_PCT + ' ' + _G + f'{duty:6.2f}%' + _R
        + ' ' + _V
    )


def _fmt_dc(high):
    if high:
        label = _Y + 'DC HIGH' + _R
        d16_str = _Y + '65535/65535' + _R
        duty_str = _G + '100.00%' + _R
    else:
        label = _O + 'DC LOW ' + _R
        d16_str = _D + '    0/65535' + _R
        duty_str = _D + '  0.00%' + _R
    return (
        _V + '  ' + label + '   '
        + ' ' + _V + '             '
        + ' ' + _V + '               '
        + ' ' + _V + '               '
        + ' ' + _V + '   ' + d16_str
        + ' ' + _V + ' ' + _I_PCT + ' ' + duty_str
        + ' ' + _V
    )
'''


_MONITOR_TEMPLATE_PIO = (r'''import sys
import select as _sel
import time
import rp2
from machine import Pin, freq as _mfreq

_PIN_NO     = __PIN_NO__
_TIMEOUT_MS = __TIMEOUT_MS__

_TARGET_COUNTS = 625_000
_DC_POLL_MS    = 100
''' + _MONITOR_SHARED + r'''

@rp2.asm_pio()
def _measure():
    wrap_target()
    wait(0, pin, 0)
    wait(1, pin, 0)
    mov(x, invert(null))
    label("_hl")
    jmp(pin, "_hd")
    jmp("_he")
    label("_hd")
    jmp(x_dec, "_hl")
    label("_he")
    mov(y, x)
    mov(x, invert(null))
    label("_ll")
    jmp(pin, "_ld")
    jmp(x_dec, "_ll")
    label("_ld")
    jmp("_le")
    label("_le")
    mov(isr, invert(y))
    push(block)
    mov(isr, invert(x))
    push(block)
    wrap()


def _wait_any(sm, timeout_ms):
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    _i = 0
    while True:
        if sm.rx_fifo() > 0:
            return True
        _i += 1
        if _i >= 2000:
            _i = 0
            _poll_key()
            if time.ticks_diff(time.ticks_ms(), deadline) >= 0:
                return False


def _sm_restart(sm):
    sm.active(0)
    sm.active(1)
    while sm.rx_fifo() > 0:
        sm.get()


def main():
    pin = Pin(_PIN_NO, Pin.IN)
    sm = rp2.StateMachine(0, _measure, freq=125_000_000,
                          in_base=pin, jmp_pin=pin)
    sm.active(1)
    while sm.rx_fifo() > 0:
        sm.get()
    _f = _mfreq()
    _d256 = _f * 256 // 125_000_000
    _ns_tick = _d256 * 2_000_000_000.0 / (_f * 256)
    w = sys.stdout.write
    start_ms = time.ticks_ms()
    h_acc = 0
    l_acc = 0
    n_acc = 0
    _last_freq = None
    _last_duty = None
    _last_dc = None
    _no_data_ms = 0
    _cand_freq = None
    _cand_duty = None
    try:
        while True:
            _poll_key()
            while sm.rx_fifo() >= 2:
                h_acc += sm.get()
                l_acc += sm.get()
                n_acc += 1
            if n_acc >= 1 and h_acc + l_acc >= _TARGET_COUNTS:
                h_avg = h_acc / n_acc
                l_avg = l_acc / n_acc
                h_acc = l_acc = n_acc = 0
                _no_data_ms = 0
                p = h_avg + l_avg
                if p <= 0:
                    continue
                period_ns = (p + 3.0) * _ns_tick
                if period_ns > _TIMEOUT_MS * 1_000_000:
                    _sm_restart(sm)
                    continue
                freq = round(1_000_000_000.0 / period_ns)
                if freq < 20 or freq > 20000:
                    h_acc = l_acc = n_acc = 0
                    continue
                duty = h_avg * 100.0 / p
                high_us = (h_avg + 1.0) * _ns_tick / 1000.0
                low_us  = (l_avg + 2.0) * _ns_tick / 1000.0
                period_us = int(period_ns / 1000.0 + 0.5)
                line = _fmt_pwm(freq, duty, period_us, high_us, low_us)
                if (_last_dc is not False or _last_freq != freq
                        or _last_duty is None or abs(duty - _last_duty) >= 0.5):
                    if _last_duty is None:
                        _last_freq = freq
                        _last_duty = duty
                        _last_dc = False
                        _cand_freq = None
                        _cand_duty = None
                        w(f'  {_ts(start_ms)}  {line}{_EL}\n')
                        _flush()
                    elif (_cand_freq == freq and _cand_duty is not None
                              and abs(duty - _cand_duty) < 1.0):
                        _last_freq = freq
                        _last_duty = duty
                        _last_dc = False
                        _cand_freq = None
                        _cand_duty = None
                        w(f'  {_ts(start_ms)}  {line}{_EL}\n')
                        _flush()
                    else:
                        _cand_freq = freq
                        _cand_duty = duty
                else:
                    _cand_freq = None
                    _cand_duty = None
                continue
            if not _wait_any(sm, _DC_POLL_MS):
                _no_data_ms += _DC_POLL_MS
                pv = pin.value()
                dv = 100.0 if pv else 0.0
                if _last_dc is not True or _last_duty != dv:
                    _last_duty = dv
                    _last_dc = True
                    _cand_freq = None
                    _cand_duty = None
                    w(f'  {_ts(start_ms)}  {_fmt_dc(pv)}{_EL}\n')
                    _flush()
                if _no_data_ms >= _TIMEOUT_MS:
                    _no_data_ms = 0
                    h_acc = l_acc = n_acc = 0
                    _cand_freq = None
                    _cand_duty = None
                    _sm_restart(sm)
    except KeyboardInterrupt:
        pass
    finally:
        sm.active(0)
        _flush()


main()
''')


_MONITOR_TEMPLATE = (r'''import sys
import select as _sel
import time
from machine import Pin, time_pulse_us

_PIN_NO     = __PIN_NO__
_TIMEOUT_US = __TIMEOUT_US__
''' + _MONITOR_SHARED + r'''

def main():
    pin = Pin(_PIN_NO, Pin.IN)
    w = sys.stdout.write
    start_ms = time.ticks_ms()
    _last_freq = None
    _last_duty = None
    _last_dc = None
    try:
        while True:
            _poll_key()
            h = time_pulse_us(pin, 1, _TIMEOUT_US)
            if h < 0:
                pv = pin.value()
                dv = 100.0 if pv else 0.0
                if _last_dc is not True or _last_duty != dv:
                    _last_duty = dv
                    _last_dc = True
                    w(f'  {_ts(start_ms)}  {_fmt_dc(pv)}{_EL}\n')
                    _flush()
                continue
            l = time_pulse_us(pin, 0, _TIMEOUT_US)
            if l < 0:
                continue
            period = h + l
            if period == 0:
                continue
            freq = round(1_000_000.0 / period)
            duty = 100.0 * h / period
            line = _fmt_pwm(freq, duty, period, h, l)
            if (_last_dc is not False or _last_freq != freq
                    or _last_duty is None or abs(duty - _last_duty) >= 0.5):
                _last_freq = freq
                _last_duty = duty
                _last_dc = False
                w(f'  {_ts(start_ms)}  {line}{_EL}\n')
                _flush()
    except KeyboardInterrupt:
        pass
    finally:
        _flush()


main()
''')


def _build_monitor_script(pin_no: int, timeout_ms: int) -> str:
    timeout_us = max(200_000, timeout_ms * 1_000)
    return (
        _MONITOR_TEMPLATE
        .replace('__PIN_NO__', str(int(pin_no)))
        .replace('__TIMEOUT_US__', str(int(timeout_us)))
    )


def _build_monitor_script_pio(pin_no: int, timeout_ms: int) -> str:
    return (
        _MONITOR_TEMPLATE_PIO
        .replace('__PIN_NO__', str(int(pin_no)))
        .replace('__TIMEOUT_MS__', str(int(timeout_ms)))
    )


_MONITOR_SEP_W = 109
_DIM = '\033[38;2;150;150;150m'
_RST = '\033[0m'


def _setup_scroll_screen(header: str, sep_w: int) -> None:
    enable_vt_mode()
    _, rows = shutil.get_terminal_size(fallback=(80, 24))
    w = sys.stdout.buffer.write
    w(b'\033[?1049h')
    w(b'\033[2J\033[H\033[?25l')
    w((header + _DIM + '   [Ctrl+C] exit' + _RST + '\n').encode())
    w(('  ' + '\u2500' * sep_w + '\n').encode())
    w(f'\033[3;{rows}r\033[3;1H'.encode())
    sys.stdout.buffer.flush()


def _teardown_scroll_screen() -> None:
    try:
        w = sys.stdout.buffer.write
        w(b'\033[r\033[?25h')
        w(b'\033[?1049l')
        sys.stdout.buffer.flush()
    finally:
        restore_vt_mode()


def _setup_seq_screen(pin_name: str, freq_str: str, mode: str, seq_label: str, writes_per: int, repeat: int) -> int:
    import io
    from rich.console import Console
    from rich.panel import Panel
    from ...cli.helpers import get_panel_box, CONSOLE_WIDTH
    enable_vt_mode()
    content = (
        f"Pin: [bright_green]{pin_name}[/bright_green]\n"
        f"Freq: [bright_cyan]{freq_str} Hz[/bright_cyan]\n"
        f"Basis: [magenta]{mode}[/magenta]\n"
        f"Seq: [bright_cyan]{seq_label}[/bright_cyan]\n"
        f"Writes: [bright_cyan]{writes_per}[/bright_cyan]\n"
        f"Num:"
    )
    panel = Panel(
        content, title="PWM Seq", border_style=OutputHelper._resolve_category_color('success'),
        box=get_panel_box(), expand=True, width=CONSOLE_WIDTH, title_align="left",
    )
    buf = io.StringIO()
    OutputHelper.make_console(file=buf, width=CONSOLE_WIDTH, force_terminal=True).print(panel)
    rendered = buf.getvalue()
    hint = _DIM + '  [Ctrl+C] ' + ('exit' if repeat == 0 else 'cancel') + _RST + '\n'
    num_row = 0
    for i, line in enumerate(rendered.split('\n'), 1):
        if 'Num:' in line:
            num_row = i
            break
    if not num_row:
        num_row = 7
    w = sys.stdout.buffer.write
    w(b'\033[?1049h')
    w(b'\033[2J\033[H\033[?25l')
    w(rendered.encode())
    w(hint.encode())
    sys.stdout.buffer.flush()
    return num_row


def _subcmd_monitor(client, pos_args: list[str], timeout_ms: int) -> None:
    if len(pos_args) != 1:
        raise ValueError("Usage: replx pwm monitor GP<num> [--timeout MS]")
    pin_no, pin_name = _parse_gp(pos_args[0])
    use_pio = _check_has_pio(client)
    if use_pio:
        code = _build_monitor_script_pio(pin_no, timeout_ms)
        method = 'PIO 125 MHz'
    else:
        code = _build_monitor_script(pin_no, timeout_ms)
        method = 'time_pulse_us'
    from .exec import _run_interactive_mode
    hdr = f'  PWM Monitor  {pin_name}   {method}'
    _setup_scroll_screen(hdr, _MONITOR_SEP_W)
    try:
        _run_interactive_mode(client, code, None, False)
    finally:
        _teardown_scroll_screen()


def _print_pwm_help() -> None:
    help_text = """\
PWM write/sequence/stop command for a single pin.

[bold cyan]Usage:[/bold cyan]
  replx pwm [yellow]SUBCOMMAND[/yellow] ...

[bold cyan]Subcommands:[/bold cyan]
  [green]write[/green]    Start/update PWM on one pin.
  [green]seq[/green]      Execute a duty+delay pattern in one board call.
  [green]stop[/green]     Stop PWM on one pin and drive it low.
  [green]monitor[/green]  Live scrolling log of PWM measurements on an input pin.
             RP2350/RP2040: PIO 125 MHz. Other boards: time_pulse_us fallback.

[bold cyan]Pin Format:[/bold cyan]
  [yellow]GP<num>[/yellow], [yellow]GPIO<num>[/yellow], or numeric GPIO id.
  Digi XBee3 Zigbee is not supported by this PWM command.

[bold cyan]Write:[/bold cyan]
  replx pwm write [yellow]GP<num>[/yellow] [green]--freq HZ[/green] [[green]--duty-percent P[/green] | [green]--duty-u16 N[/green] | [green]--pulse-us US[/green]]

[bold cyan]Sequence:[/bold cyan]
  replx pwm seq [yellow]GP<num>[/yellow] [green]--freq HZ[/green] [green]--duty MODE[/green] [cyan]TOKEN[/cyan]... [[green]--repeat N[/green]]

  [bold]MODE[/bold]
    [cyan]percent[/cyan]   duty tokens are 0..100
    [cyan]u16[/cyan]       duty tokens are 0..65535
    [cyan]pulse_us[/cyan]  duty tokens are pulse width in microseconds

  [bold]TOKEN[/bold]
    [cyan]VALUE[/cyan]   duty value in the selected MODE
    [cyan]u<N>[/cyan]    delay in microseconds
    [cyan]m<N>[/cyan]    delay in milliseconds

  [green]--repeat N[/green]  repeat the sequence N times [dim](default 1, 0=infinite)[/dim]

[bold cyan]Stop:[/bold cyan]
  replx pwm stop [yellow]GP<num>[/yellow]

[bold cyan]Monitor:[/bold cyan]
  replx pwm monitor [yellow]GP<num>[/yellow] [[green]--timeout MS[/green]]

  Fixed header + scrolling change log. Shows freq, period, duty on each change.
  Frequency range: [yellow]20 – 20000 Hz[/yellow]. Signals outside this range are ignored.
  [dim]--timeout MS[/dim]  no-signal wait timeout [dim](default 2000 ms)[/dim]

[bold cyan]Examples:[/bold cyan]
  replx COM3 pwm write GP15 --freq 50 --pulse-us 1500
  replx COM3 pwm write GP15 --freq 1000 --duty-percent 25
  replx COM3 pwm write GP15 --freq 20000 --duty-u16 32768
  replx COM3 pwm seq GP15 --freq 100 --duty percent 0 m200 25 m200 50 m200 75 m200 100
  replx COM3 pwm seq GP15 --freq 50 --duty pulse_us 1000 m500 1500 m500 2000
  replx COM3 pwm seq GP15 --freq 50 --duty pulse_us 1000 m500 1500 m500 2000 --repeat 5
  replx COM3 pwm seq GP15 --freq 50 --duty pulse_us 1000 m500 1500 m500 2000 --repeat 0
  replx COM3 pwm stop GP15
  replx COM4 pwm monitor GP2
  replx COM4 pwm monitor GP2 --timeout 5000

[bold cyan]Notes:[/bold cyan]
  • One PWM pin only.
  • [yellow]write[/yellow] requires [yellow]--freq[/yellow] and exactly one duty option.
  • [yellow]seq[/yellow] requires [yellow]--freq[/yellow], [yellow]--duty[/yellow], and at least one duty token.
  • [yellow]seq --repeat 0[/yellow]: infinite repeat, Ctrl+C to stop. PWM stays at last duty until [yellow]pwm stop[/yellow].
  • [yellow]pulse_us[/yellow] values must not exceed the PWM period for the selected frequency.
  • [yellow]monitor[/yellow] frequency range: 20 – 20000 Hz. Out-of-range signals are silently ignored.
  • [yellow]monitor[/yellow] on RP2350/RP2040: Use PIO state machine 0. 
                              [dim]Cannot coexist with other PIO programs using the same SM.[/dim]
  • [yellow]monitor[/yellow] on other boards: uses [cyan]time_pulse_us()[/cyan]."""
    OutputHelper.print_panel(help_text, title="pwm", border_style="help")


def _subcmd_write(client, pos_args: list[str], freq: Optional[float], duty_percent: Optional[float], duty_u16: Optional[int], pulse_us: Optional[float]) -> None:
    if len(pos_args) != 1:
        raise ValueError(
            "Usage: replx pwm write GP<num> --freq HZ (--duty-percent P | --duty-u16 N | --pulse-us US)"
        )

    pin_no, pin_name = _parse_gp(pos_args[0])
    freq_value = _parse_freq(freq)
    mode, value = _pick_write_level(duty_percent, duty_u16, pulse_us)
    duty_value = _value_to_duty_u16(mode, value, freq_value)
    raw = _exec(client, _make_write_code(pin_no, pin_name, freq_value, mode, value, duty_value), timeout=5.0)
    data = _parse_json_strict(raw)
    if 'error' in data:
        raise ValueError(str(data['error']))
    actual_u16 = int(data.get('duty_u16', duty_value))
    actual_pulse_us = float(data.get('pulse_us', _pulse_us_from_u16(actual_u16, freq_value)))

    OutputHelper.print_panel(
        f"Pin: [bright_green]{pin_name}[/bright_green]\n"
        f"Freq: [bright_cyan]{_format_number(freq_value)} Hz[/bright_cyan]\n"
        f"Input: [magenta]{mode}[/magenta] = [bright_cyan]{_format_number(value)}[/bright_cyan]\n"
        f"Duty: [bright_cyan]{actual_u16}[/bright_cyan] / 65535\n"
        f"Percent: [bright_cyan]{_format_number(_duty_percent_from_u16(actual_u16))}%[/bright_cyan]\n"
        f"Pulse: [bright_cyan]{_format_number(actual_pulse_us)} us[/bright_cyan]\n"
        f"Active: [bright_cyan]{bool(data.get('active', True))}[/bright_cyan]",
        title="PWM Write",
        border_style="success",
    )


def _subcmd_seq(client, pos_args: list[str], freq: Optional[float], duty_mode: Optional[str], repeat: int = 1) -> None:
    if len(pos_args) < 2:
        raise ValueError("Usage: replx pwm seq GP<num> --freq HZ --duty MODE TOKEN...")

    pin_no, pin_name = _parse_gp(pos_args[0])
    freq_value = _parse_freq(freq)
    mode = _parse_duty_mode(duty_mode)
    ops = _parse_seq_tokens(pos_args[1:], mode)

    for kind, value in ops:
        if kind == 'd':
            _value_to_duty_u16(mode, value, freq_value)

    if repeat != 1:
        writes_per = sum(1 for k, _ in ops if k == 'd')
        seq_label = _format_seq_ops(ops)
        freq_str = _format_number(freq_value)
        num_row = _setup_seq_screen(pin_name, freq_str, mode, seq_label, writes_per, repeat)
        code = _make_seq_repeat_code(pin_no, pin_name, freq_value, mode, ops, repeat, num_row)
        from .exec import _run_interactive_mode
        try:
            _run_interactive_mode(client, code, None, False)
        finally:
            _teardown_scroll_screen()
        if repeat > 0:
            writes_total = writes_per * repeat
            OutputHelper.print_panel(
                f"Done: {repeat} cycles, {writes_total} writes",
                title="PWM Seq",
                border_style="success",
            )
        return

    timeout = 5.0
    timeout += sum(int(value) / 1000.0 for kind, value in ops if kind == 'm')
    timeout += sum(int(value) / 1_000_000.0 for kind, value in ops if kind == 'u')
    timeout = min(max(timeout, 5.0), 120.0)

    raw = _exec(client, _make_seq_code(pin_no, pin_name, freq_value, mode, ops), timeout=timeout)
    data = _parse_json_strict(raw)
    if 'error' in data:
        raise ValueError(str(data['error']))
    final_u16 = int(data.get('duty_u16', 0))
    final_pulse_us = float(data.get('pulse_us', _pulse_us_from_u16(final_u16, freq_value)))
    writes = int(data.get('writes', 0))

    OutputHelper.print_panel(
        f"Pin: [bright_green]{pin_name}[/bright_green]\n"
        f"Freq: [bright_cyan]{_format_number(freq_value)} Hz[/bright_cyan]\n"
        f"Basis: [magenta]{mode}[/magenta]\n"
        f"Seq: [bright_cyan]{_format_seq_ops(ops)}[/bright_cyan]\n"
        f"Writes: [bright_cyan]{writes}[/bright_cyan]\n"
        f"Final duty: [bright_cyan]{final_u16}[/bright_cyan] / 65535\n"
        f"Final percent: [bright_cyan]{_format_number(_duty_percent_from_u16(final_u16))}%[/bright_cyan]\n"
        f"Final pulse: [bright_cyan]{_format_number(final_pulse_us)} us[/bright_cyan]\n"
        f"Active: [bright_cyan]{bool(data.get('active', True))}[/bright_cyan]",
        title="PWM Seq",
        border_style="success",
    )


def _subcmd_stop(client, pos_args: list[str]) -> None:
    if len(pos_args) != 1:
        raise ValueError("Usage: replx pwm stop GP<num>")

    pin_no, pin_name = _parse_gp(pos_args[0])
    raw = _exec(client, _make_stop_code(pin_no, pin_name), timeout=5.0)
    data = _parse_json_strict(raw)

    OutputHelper.print_panel(
        f"Pin: [bright_green]{pin_name}[/bright_green]\n"
        f"Stopped: [bright_cyan]{bool(data.get('stopped', True))}[/bright_cyan]\n"
        f"Level: [bright_cyan]{int(data.get('value', 0))}[/bright_cyan]",
        title="PWM Stop",
        border_style="success",
    )


@app.command(name="pwm", rich_help_panel="Hardware")
def pwm_cmd(
    args: Optional[list[str]] = typer.Argument(
        None, help="Subcommand: write  seq  stop  monitor"
    ),
    freq: Optional[float] = typer.Option(None, "--freq", metavar="HZ", help="PWM frequency in Hz"),
    duty: Optional[str] = typer.Option(None, "--duty", metavar="MODE", help="Duty basis for pwm seq: percent, u16, pulse_us"),
    duty_percent: Optional[float] = typer.Option(None, "--duty-percent", metavar="P", help="Duty percent for pwm write (0..100)"),
    duty_u16: Optional[int] = typer.Option(None, "--duty-u16", metavar="N", help="Duty u16 for pwm write (0..65535)"),
    pulse_us: Optional[float] = typer.Option(None, "--pulse-us", metavar="US", help="Pulse width in microseconds for pwm write"),
    timeout_ms: int = typer.Option(2000, "--timeout", metavar="MS", help="No-signal timeout ms for pwm monitor (default 2000)"),
    repeat: int = typer.Option(1, "--repeat", "-n", metavar="N", help="Repeat count for pwm seq (0=infinite, default 1)"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True),
):
    if show_help:
        _print_pwm_help()
        raise typer.Exit()
    if not args:
        OutputHelper.print_panel(
            "Subcommands: [bright_blue]write[/bright_blue]  [bright_blue]seq[/bright_blue]  [bright_blue]stop[/bright_blue]  [bright_blue]monitor[/bright_blue]\n\n"
            "  [bright_green]replx PORT pwm write GP15 --freq 1000 --duty-percent 50[/bright_green]\n"
            "  [bright_green]replx PORT pwm monitor GP15[/bright_green]\n"
            "  [bright_green]replx PORT pwm stop GP15[/bright_green]\n\n"
            "Use [bright_blue]replx pwm --help[/bright_blue] for details.",
            title="PWM",
            border_style="help",
        )
        raise typer.Exit(1)

    subcmd = args[0].lower()
    pos_args = args[1:]

    _VALID_SUBCMDS = ('write', 'seq', 'stop', 'monitor')
    if subcmd not in _VALID_SUBCMDS:
        OutputHelper.print_panel(
            f"Unknown subcommand: {subcmd!r}\n\n"
            "Valid subcommands: write  seq  stop  monitor",
            title="PWM Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if subcmd != 'seq' and duty is not None:
        OutputHelper.print_panel(
            "--duty is supported only for pwm seq",
            title="PWM Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if subcmd != 'write' and any(v is not None for v in (duty_percent, duty_u16, pulse_us)):
        OutputHelper.print_panel(
            "--duty-percent, --duty-u16, and --pulse-us are supported only for pwm write",
            title="PWM Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if subcmd != 'monitor' and timeout_ms != 2000:
        OutputHelper.print_panel(
            "--timeout is supported only for pwm monitor",
            title="PWM Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if subcmd != 'seq' and repeat != 1:
        OutputHelper.print_panel(
            "--repeat is supported only for pwm seq",
            title="PWM Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if repeat < 0:
        OutputHelper.print_panel(
            "--repeat must be >= 0 (0=infinite, 1=default)",
            title="PWM Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if subcmd == 'stop' and freq is not None:
        OutputHelper.print_panel(
            "--freq is not used for pwm stop",
            title="PWM Error",
            border_style="error",
        )
        raise typer.Exit(1)

    _ensure_connected()

    try:
        with _create_agent_client() as client:
            require_standard_hardware(client, 'pwm')
            if subcmd == 'write':
                _subcmd_write(client, pos_args, freq, duty_percent, duty_u16, pulse_us)
            elif subcmd == 'seq':
                _subcmd_seq(client, pos_args, freq, duty, repeat)
            elif subcmd == 'stop':
                _subcmd_stop(client, pos_args)
            elif subcmd == 'monitor':
                _subcmd_monitor(client, pos_args, timeout_ms)
    except typer.Exit:
        raise
    except (ValueError, RuntimeError) as e:
        OutputHelper.print_panel(str(e), title="PWM Error", border_style="error")
        raise typer.Exit(1)
