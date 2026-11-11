import ast
import builtins
import json
import signal
import sys
from typing import Optional

import typer
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from replx.utils.constants import CTRL_C
from ..helpers import OutputHelper, get_panel_box, CONSOLE_WIDTH
from ..connection import _ensure_connected, _create_agent_client
from ..app import app
from ._common import (
    exec_code as _exec, parse_json_strict as _parse_json_strict,
    parse_gp_pin, parse_hardware_pin, pin_label, is_xbee,
)


_READ_ACTIONS = {"read", "wait_h", "wait_l", "pulse_h", "pulse_l"}
_EXPR_FUNCS = {
    'abs': abs,
    'round': round,
    'min': min,
    'max': max,
}


def _parse_gp(token: str) -> tuple[int, str]:
    pin = parse_gp_pin(token, 'GPIO pin')
    return pin, pin_label(pin)


def _make_xbee_gpio_code(subcmd: str, tokens: list[str], repeat: int, interval: int) -> str:
    if repeat < 0 or interval < 0:
        raise ValueError("--repeat and --interval must be >= 0")
    if subcmd not in ('read', 'write', 'seq'):
        raise ValueError("XBee3 GPIO supports read PIN read, write, and seq; not monitor")
    if not tokens:
        raise ValueError("Specify an XBee pin such as D0 or P0")
    pin = parse_hardware_pin(tokens[0], 'GPIO pin')
    if not isinstance(pin, str):
        raise ValueError("XBee3 GPIO requires Digi pin names D0..D9 or P0..P2")
    read_pin = None
    if subcmd == 'write':
        if len(tokens) != 2:
            raise ValueError("Usage: gpio write D0 0|1")
        ops = [('w', _parse_logic(tokens[1]))]
    elif subcmd == 'read':
        if len(tokens) != 2 or tokens[1].lower() != 'read':
            raise ValueError("XBee3 supports gpio read D0 read; pulse/wait actions are excluded")
        ops, read_pin = [], pin
    else:
        seq_tokens = tokens[1:]
        if seq_tokens and seq_tokens[-1].lower() in _READ_ACTIONS:
            if seq_tokens[-1].lower() != 'read':
                raise ValueError("XBee3 GPIO seq supports only the optional PIN read action")
            if len(seq_tokens) >= 2 and seq_tokens[-2].upper().startswith(('D', 'P')):
                read_pin = parse_hardware_pin(seq_tokens[-2], 'read pin')
                seq_tokens = seq_tokens[:-2]
            else:
                read_pin = pin
                seq_tokens = seq_tokens[:-1]
        ops, _, action, _ = _parse_seq_tokens(seq_tokens, pin)
        if action is not None:
            raise ValueError("XBee3 GPIO seq supports only the optional read action")
        if read_pin is not None and not isinstance(read_pin, str):
            raise ValueError("XBee3 GPIO requires Digi pin names D0..D9 or P0..P2")
    value = 'rp.value()' if read_pin is not None else 'wp.value()'
    loop = "while True:" if repeat == 0 else f"for _ in range({repeat}):"
    return (
        "from machine import Pin\nimport time,json\n"
        + f"ops={ops!r}\n{loop}\n"
        + (f" wp=Pin({pin!r},Pin.OUT)\n" if ops else "")
        + " for kind,val in ops:\n"
        "  if kind=='w': wp.value(val)\n"
        "  elif kind=='u': time.sleep_us(val)\n"
        "  elif kind=='m': time.sleep_ms(val)\n"
        + (f" rp=Pin({read_pin!r},Pin.IN)\n" if read_pin is not None else "")
        + f" print(json.dumps({{'pin':{(read_pin or pin)!r},'value':{value},"
        f"'writes':{sum(kind == 'w' for kind, _ in ops)}}}))\n"
        + (f" time.sleep_ms({interval})\n" if interval > 0 else "")
    )


def _run_xbee_gpio(client, subcmd, tokens, repeat, interval, expr) -> None:
    code = _make_xbee_gpio_code(subcmd, tokens, repeat, interval)

    def show(raw):
        data = _parse_json_strict(raw)
        body = f"{data['pin']} = {data['value']}"
        if expr:
            body += f"\nexpr = {_eval_expr(expr, data)}"
        OutputHelper.print_panel(body, title="XBee3 GPIO", border_style="data")

    if repeat == 1:
        show(_exec(client, code))
    else:
        _run_repeat_interactive(client, code, show, ctrl_c_grace_s=1.5)


def _parse_logic(token: str) -> int:
    s = (token or "").strip()
    if s not in ("0", "1"):
        raise ValueError(f"Invalid logic value: {token!r}. Use 0 or 1")
    return int(s)


def _validate_expr_ast(node: ast.AST, allowed_names: set[str]) -> None:
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.UAdd,
        ast.USub,
    )

    for child in ast.walk(node):
        if not isinstance(child, allowed_nodes):
            raise ValueError("--expr supports arithmetic expressions only")
        if isinstance(child, ast.Name) and child.id not in allowed_names:
            raise ValueError(f"Unknown name in --expr: {child.id}")
        if isinstance(child, ast.Call):
            if not isinstance(child.func, ast.Name) or child.func.id not in _EXPR_FUNCS:
                raise ValueError("--expr only allows these functions: abs, round, min, max")


def _eval_expr(expr: str, data: dict) -> object:
    values = {
        'value': int(data.get('value', 0)),
        'writes': int(data.get('writes', 0)),
    }
    if 'pulse_us' in data:
        values['pulse_us'] = int(data['pulse_us'])
    if 'wait_ms' in data:
        values['wait_ms'] = int(data['wait_ms'])

    try:
        tree = ast.parse(expr, mode='eval')
    except SyntaxError:
        raise ValueError("Invalid --expr syntax")

    _validate_expr_ast(tree, set(values) | set(_EXPR_FUNCS))

    try:
        return builtins.eval(
            builtins.compile(tree, '<gpio-expr>', 'eval'),
            {'__builtins__': {}},
            {**_EXPR_FUNCS, **values},
        )
    except Exception as e:
        raise ValueError(f"Failed to evaluate --expr: {e}")


def _run_interactive_script(client, code: str, *, live_output: bool = False, ctrl_c_grace_s: float = 3.0) -> str:
    stop_requested = False
    pending_input: list[bytes] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    original_sigint = signal.getsignal(signal.SIGINT)

    def sigint_handler(signum, frame):
        nonlocal stop_requested
        stop_requested = True
        pending_input.append(CTRL_C)

    def output_callback(data: bytes, stream_type: str = "stdout"):
        text = data.decode('utf-8', errors='replace')
        if stream_type == 'stderr':
            stderr_parts.append(text)
            return
        stdout_parts.append(text)
        if live_output and text:
            sys.stdout.write(text)
            sys.stdout.flush()

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
            ctrl_c_grace_s=ctrl_c_grace_s,
        )
    finally:
        signal.signal(signal.SIGINT, original_sigint)

    if stderr_parts:
        raise RuntimeError(''.join(stderr_parts).strip())

    raw = ''.join(stdout_parts)
    if stop_requested and not raw.strip():
        raise typer.Exit(130)
    return raw.strip()


def _format_seq_ops(ops: list[tuple[str, int]]) -> str:
    parts = []
    for kind, value in ops:
        if kind == 'w':
            parts.append(str(int(value)))
        elif kind == 'u':
            parts.append(f"u{int(value)}")
        elif kind == 'm':
            parts.append(f"m{int(value)}")
    return '-'.join(parts) if parts else '-'


def _parse_seq_tokens(tokens: list[str], write_pin_name: str) -> tuple[list[tuple[str, int]], Optional[int], Optional[str], str]:
    if not tokens:
        raise ValueError("gpio seq requires write tokens")

    read_pin_no = None
    read_pin_name = write_pin_name
    read_action = None

    if len(tokens) >= 2:
        maybe_action = tokens[-1].lower()
        maybe_pin = tokens[-2]
        if maybe_action in _READ_ACTIONS:
            try:
                pin_no, pin_name = _parse_gp(maybe_pin)
                read_pin_no = pin_no
                read_pin_name = pin_name
                read_action = maybe_action
                tokens = tokens[:-2]
            except ValueError:
                pass

    if read_action is None and tokens and tokens[-1].lower() in _READ_ACTIONS:
        read_action = tokens[-1].lower()
        tokens = tokens[:-1]

    if not tokens:
        raise ValueError("gpio seq requires one or more write tokens before read_action")

    ops: list[tuple[str, int]] = []
    write_count = 0

    for token in tokens:
        t = token.strip().lower()
        if t in ('0', '1'):
            ops.append(('w', int(t)))
            write_count += 1
            continue
        if len(t) >= 2 and t[0] in ('u', 'm') and t[1:].isdigit():
            value = int(t[1:])
            ops.append((t[0], value))
            continue
        raise ValueError(
            f"Invalid seq token: {token!r}. Use 0, 1, u<N>, m<N> or a final read_action"
        )

    if write_count == 0:
        raise ValueError("gpio seq requires at least one write token (0 or 1)")

    return ops, read_pin_no, read_action, read_pin_name


_GPIO_SCOPE_TEMPLATE = r'''import sys
import time
import array
import select as _sel
from machine import Pin
from termviz import Term, Canvas, Plot, Scope

_PIN_NO      = __PIN_NO__
_INTERVAL_MS = __INTERVAL_MS__
_BUF_SIZE    = 128

_CV_COLS    = 78
_CV_ROWS    = 14
_STATS_ROW  = _CV_ROWS + 1
_CHANGE_ROW = _CV_ROWS + 2
_LOG_N      = 8
_LOG_START  = _CV_ROWS + 3
_HELP_ROW   = _CV_ROWS + 3 + _LOG_N
_REGION     = (0, 4, 6, 4)
_COLORS     = [(80, 255, 120), (80, 180, 255)]
_ARROW_UP   = "\uf062"
_ARROW_DOWN = "\uf063"
_ICON_DELTA = "\uf252"

_ts_buf     = array.array('l', [0] * _BUF_SIZE)
_lv_buf     = array.array('b', [0] * _BUF_SIZE)
_wr         = 0
_rd         = 0
_overflow   = False
_next_level = bytearray(1)


def _isr(pin):
    global _wr, _overflow
    nxt = (_wr + 1) % _BUF_SIZE
    if nxt == _rd:
        _overflow = True
    else:
        _ts_buf[_wr] = time.ticks_us()
        _lv_buf[_wr] = pin.value() if sys.platform == 'esp32' else _next_level[0]
        _next_level[0] ^= 1
        _wr = nxt


def _flush_buf():
    global _rd, _overflow
    edges = []
    while _rd != _wr:
        edges.append((_ts_buf[_rd], int(_lv_buf[_rd])))
        _rd = (_rd + 1) % _BUF_SIZE
    ov = _overflow
    _overflow = False
    return edges, ov


def _make_plot():
    W  = _CV_COLS * 2
    H  = _CV_ROWS * 4
    rl, rt, rr, rb = _REGION
    cv = Canvas(_CV_COLS, _CV_ROWS)
    ax = Plot(cv,
              region_px=(rl, rt, W - rl - rr, H - rt - rb),
              xlim=(0, W), ylim=(-0.1, 1.1),
              color_cycle=[_COLORS[0]])
    ax.title(f"GPIO  GP{_PIN_NO}", color=(180, 220, 180))
    ax.yticks([0.0, 1.0], ["0", "1"])
    ax.grid(False)
    sc = Scope(ax, vmin=-0.1, vmax=1.1, colors=[_COLORS[0]], px_step=2, show_zero=False)
    ax._legend_on = False
    ax.clear_legend_items()
    ax._ylabel = None
    return cv, sc


def _poll_key():
    r, _, _ = _sel.select([sys.stdin], [], [], 0)
    if not r:
        return None
    ch = sys.stdin.read(1)
    if ch == "\x03":
        raise KeyboardInterrupt
    return ch


def _draw_log(w, log_buf, log_pos):
    for i in range(_LOG_N):
        idx = (log_pos - _LOG_N + i) % _LOG_N
        entry = log_buf[idx]
        w(Term.cursor_to(_LOG_START + i, 1) +
          (entry if entry else Term.FG.MUTED + "  ---" + Term.RESET + " " * 60))


def main():
    pin = Pin(_PIN_NO, Pin.IN)
    _next_level[0] = pin.value() ^ 1
    cv, sc = _make_plot()
    w = sys.stdout.write
    last_change_t = time.ticks_us()
    arrow = None
    sweep_idx = 0
    paused = False
    log_buf = [""] * _LOG_N
    log_pos = 0
    log_pair_first_t = None
    log_pair_first_v = None
    last_irq_level = pin.value()
    _draw_log(w, log_buf, log_pos)
    w(Term.cursor_to(_HELP_ROW, 1) +
      Term.FG.MUTED + "  [SPACE] pause   [Ctrl+C] exit              " + Term.RESET + "     ")
    try:
        irq_options = {'handler': _isr, 'trigger': Pin.IRQ_RISING | Pin.IRQ_FALLING}
        if sys.platform != 'esp32':
            irq_options['hard'] = True
        pin.irq(**irq_options)
        while True:
            ch = _poll_key()
            if ch == " ":
                paused = not paused
                if paused:
                    w(Term.cursor_to(_HELP_ROW, 1) +
                      Term.rgb(255, 220, 60) + "  \u23f8 PAUSED  " + Term.RESET + "  [SPACE] resume  [Ctrl+C] exit" + "     ")
                else:
                    w(Term.cursor_to(_HELP_ROW, 1) +
                      Term.FG.MUTED + "  [SPACE] pause   [Ctrl+C] exit              " + Term.RESET + "     ")
            if paused:
                time.sleep_ms(_INTERVAL_MS)
                continue

            edges, overflow = _flush_buf()
            edge_fired = len(edges) > 0

            for t_us, v in edges:
                last_change_t = t_us
                arrow = _ARROW_UP if v else _ARROW_DOWN
                e_name = "rising" if v else "falling"
                e_col = Term.rgb(80, 255, 120) if v else Term.rgb(255, 80, 80)
                t_str = "{:>9}".format(t_us // 1000)
                e_padded = "{:<7}".format(e_name)
                if log_pair_first_t is None:
                    d_str = " " * 16
                    log_pair_first_t = t_us
                    log_pair_first_v = v
                else:
                    delta = time.ticks_diff(t_us, log_pair_first_t)
                    if log_pair_first_v:
                        lv_col = Term.rgb(80, 255, 120)
                        lv_ch = "H"
                    else:
                        lv_col = Term.rgb(255, 80, 80)
                        lv_ch = "L"
                    d_str = _ICON_DELTA + "{:>7} ms  ".format(delta // 1000) + lv_col + lv_ch + Term.FG.MUTED
                    log_pair_first_t = None
                    log_pair_first_v = None
                log_buf[log_pos % _LOG_N] = (
                    Term.rgb(255, 220, 60) + "  " + t_str + Term.RESET +
                    Term.FG.MUTED + " ms   " + Term.RESET +
                    e_col + arrow + "  " + e_padded + Term.RESET +
                    Term.FG.MUTED + "   " + d_str + Term.RESET + "   "
                )
                log_pos += 1

            t_now = time.ticks_us()
            held = time.ticks_diff(t_now, last_change_t)
            if edges:
                last_irq_level = edges[-1][1]
            _pt = sc._t
            sc.tick([float(last_irq_level)])
            if sc._t <= _pt:
                sweep_idx ^= 1
                sc._colors[0] = sc.cv.pack_rgb(_COLORS[sweep_idx])
            v_now = last_irq_level

            val_color = Term.rgb(80, 255, 120) if v_now else Term.rgb(255, 80, 80)
            ov_str = "  \u26a0 OVERFLOW" if overflow else "          "
            w(Term.cursor_to(_STATS_ROW, 1) +
              Term.FG.MUTED + f"  GP{_PIN_NO}  " + Term.RESET +
              Term.FG.MUTED + f"t={t_now // 1000} ms  render={_INTERVAL_MS} ms  " + Term.RESET +
              "Value: " + val_color + str(v_now) + Term.RESET +
              (Term.rgb(255, 80, 80) + ov_str + Term.RESET if overflow else "     "))
            if arrow is None:
                w(Term.cursor_to(_CHANGE_ROW, 1) +
                  Term.FG.MUTED + "  last change: --" + Term.RESET + "                                      ")
            else:
                w(Term.cursor_to(_CHANGE_ROW, 1) +
                  Term.FG.MUTED + f"  last change: {arrow} " + Term.RESET +
                  Term.rgb(255, 220, 60) + f"at {last_change_t // 1000} ms" + Term.RESET +
                  Term.FG.MUTED + f"  held {held // 1000} ms" + Term.RESET + "     ")
            if edge_fired:
                _draw_log(w, log_buf, log_pos)
            time.sleep_ms(_INTERVAL_MS)
    except KeyboardInterrupt:
        pass
    finally:
        pin.irq(handler=None)
        cv.end()


main()
'''


def _preflight_scope_libs(client) -> None:
    code = (
        "try:\n"
        " import termviz\n"
        " print('ok')\n"
        "except Exception as e:\n"
        " print('missing:'+str(e))\n"
    )
    raw = _exec(client, code, timeout=3.0)
    if 'ok' not in raw:
        raise RuntimeError(
            "gpio scope requires termviz on the board.\n"
            f"Board response: {raw}"
        )


def _build_scope_code(pin_no: int, interval_ms: int) -> str:
    return (
        _GPIO_SCOPE_TEMPLATE
        .replace('__PIN_NO__', str(int(pin_no)))
        .replace('__INTERVAL_MS__', str(int(interval_ms)))
    )


def _make_write_code(pin_no: int, pin_name: str, value: int) -> str:
    return (
        "from machine import Pin\n"
        "import json\n"
        f"p=Pin({pin_no},Pin.OUT)\n"
        f"p.value({value})\n"
        f"print(json.dumps({{'pin':{pin_name!r},'value':p.value()}}))"
    )


def _mk_timeout_exit(action: str, read_pin_name: str, indent: int = 12) -> str:
    pad = " " * indent
    return (
        f"{pad}res['read_action']={action!r}\n"
        f"{pad}res['read_pin']={read_pin_name!r}\n"
        f"{pad}res['timeout']=True\n"
        f"{pad}res['timeout_ms']=timeout_ms\n"
        f"{pad}res['value']=rp.value()\n"
        f"{pad}print(json.dumps(res))\n"
        f"{pad}raise SystemExit\n"
    )


def _make_seq_code(write_pin_no: int, write_pin_name: str, ops: list[tuple[str, int]], read_pin_no: Optional[int], read_pin_name: str, read_action: Optional[str], timeout_ms: int) -> str:
    py_ops = repr(ops)
    action_expr = repr(read_action)
    read_pin_expr = 'None' if read_pin_no is None else str(read_pin_no)
    te = {a: _mk_timeout_exit(a, read_pin_name) for a in ('wait_h', 'wait_l')}
    return (
        "from machine import Pin,time_pulse_us\n"
        "import time,json\n"
        f"wp=Pin({write_pin_no},Pin.OUT)\n"
        f"ops={py_ops}\n"
        "writes=0\n"
        "for kind,val in ops:\n"
        "    if kind=='w':\n"
        "        wp.value(val)\n"
        "        writes+=1\n"
        "    elif kind=='u':\n"
        "        time.sleep_us(val)\n"
        "    elif kind=='m':\n"
        "        time.sleep_ms(val)\n"
        f"action={action_expr}\n"
        f"read_pin_no={read_pin_expr}\n"
        f"timeout_ms={int(timeout_ms)}\n"
        "rp=Pin(read_pin_no,Pin.IN) if read_pin_no is not None else None\n"
        f"res={{'write_pin':{write_pin_name!r},'writes':writes,'value':wp.value()}}\n"
        "def _expired(t0):\n"
        "    return timeout_ms > 0 and time.ticks_diff(time.ticks_ms(), t0) >= timeout_ms\n"
        "if action is not None and rp is None:\n"
        f"    rp=Pin({write_pin_no},Pin.IN)\n"
        "if action=='read':\n"
        "    res['read_action']='read'\n"
        f"    res['read_pin']={read_pin_name!r}\n"
        "    res['value']=rp.value()\n"
        "elif action=='wait_h':\n"
        "    t0=time.ticks_ms()\n"
        "    while rp.value()==0:\n"
        "        if _expired(t0):\n"
        + te['wait_h'] +
        "        time.sleep_us(50)\n"
        "    res['read_action']='wait_h'\n"
        f"    res['read_pin']={read_pin_name!r}\n"
        "    res['wait_ms']=time.ticks_diff(time.ticks_ms(),t0)\n"
        "    res['value']=rp.value()\n"
        "elif action=='wait_l':\n"
        "    t0=time.ticks_ms()\n"
        "    while rp.value()==1:\n"
        "        if _expired(t0):\n"
        + te['wait_l'] +
        "        time.sleep_us(50)\n"
        "    res['read_action']='wait_l'\n"
        f"    res['read_pin']={read_pin_name!r}\n"
        "    res['wait_ms']=time.ticks_diff(time.ticks_ms(),t0)\n"
        "    res['value']=rp.value()\n"
        "elif action=='pulse_h':\n"
        "    if timeout_ms>0:\n"
        "        r=time_pulse_us(rp,1,timeout_ms*1000)\n"
        "    else:\n"
        "        while rp.value()==0:\n"
        "            time.sleep_us(10)\n"
        "        r=time_pulse_us(rp,1,60000000)\n"
        "    if r<0:\n"
        "        res['read_action']='pulse_h'\n"
        f"        res['read_pin']={read_pin_name!r}\n"
        "        res['timeout']=True\n"
        "        res['timeout_ms']=timeout_ms\n"
        "        res['value']=rp.value()\n"
        "        print(json.dumps(res))\n"
        "        raise SystemExit\n"
        "    res['read_action']='pulse_h'\n"
        f"    res['read_pin']={read_pin_name!r}\n"
        "    res['pulse_us']=r\n"
        "    res['value']=rp.value()\n"
        "elif action=='pulse_l':\n"
        "    if timeout_ms>0:\n"
        "        r=time_pulse_us(rp,0,timeout_ms*1000)\n"
        "    else:\n"
        "        while rp.value()==1:\n"
        "            time.sleep_us(10)\n"
        "        r=time_pulse_us(rp,0,60000000)\n"
        "    if r<0:\n"
        "        res['read_action']='pulse_l'\n"
        f"        res['read_pin']={read_pin_name!r}\n"
        "        res['timeout']=True\n"
        "        res['timeout_ms']=timeout_ms\n"
        "        res['value']=rp.value()\n"
        "        print(json.dumps(res))\n"
        "        raise SystemExit\n"
        "    res['read_action']='pulse_l'\n"
        f"    res['read_pin']={read_pin_name!r}\n"
        "    res['pulse_us']=r\n"
        "    res['value']=rp.value()\n"
        "print(json.dumps(res))"
    )


def _make_seq_repeat_code(
    write_pin_no: int, write_pin_name: str,
    ops: list[tuple[str, int]],
    read_pin_no: Optional[int], read_pin_name: str,
    read_action: Optional[str],
    timeout_ms: int,
    repeat: int,
    interval_ms: int = 0,
) -> str:
    n_expr = '0' if repeat == 0 else str(repeat)
    py_ops = repr(ops)
    pn_w = repr(write_pin_name)
    pn_r = repr(read_pin_name)
    read_pin_expr = str(write_pin_no) if read_pin_no is None else str(read_pin_no)
    use_read_pin = read_action is not None

    header = (
        "from machine import Pin,time_pulse_us\n"
        "import time,json\n"
        f"wp=Pin({write_pin_no},Pin.OUT)\n"
        f"ops={py_ops}\n"
    )
    if use_read_pin:
        header += f"rp=Pin({read_pin_expr},Pin.IN)\n"
    header += (
        f"_n={n_expr}\n"
        "_i=0\n"
        "while _n==0 or _i<_n:\n"
        "    _i+=1\n"
    )

    write_body = (
        "    writes=0\n"
        "    for kind,val in ops:\n"
        "        if kind=='w':\n"
        "            wp.value(val)\n"
        "            writes+=1\n"
        "        elif kind=='u':\n"
        "            time.sleep_us(val)\n"
        "        elif kind=='m':\n"
        "            time.sleep_ms(val)\n"
    )

    if read_action is None:
        read_body = f"    print(json.dumps({{'write_pin':{pn_w},'writes':writes,'value':wp.value()}}))\n"
    elif read_action == 'read':
        read_body = f"    print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'read','writes':writes,'value':rp.value()}}))\n"
    elif read_action == 'wait_h':
        if timeout_ms > 0:
            read_body = (
                "    t0=time.ticks_ms()\n"
                f"    while rp.value()==0 and time.ticks_diff(time.ticks_ms(),t0)<{timeout_ms}:\n"
                "        time.sleep_us(50)\n"
                "    if rp.value()==0:\n"
                f"        print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'wait_h','timeout':True,'value':rp.value()}}))\n"
                "        continue\n"
                "    wms=time.ticks_diff(time.ticks_ms(),t0)\n"
                f"    print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'wait_h','wait_ms':wms,'value':rp.value()}}))\n"
            )
        else:
            read_body = (
                "    t0=time.ticks_ms()\n"
                "    while rp.value()==0:\n"
                "        time.sleep_us(50)\n"
                "    wms=time.ticks_diff(time.ticks_ms(),t0)\n"
                f"    print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'wait_h','wait_ms':wms,'value':rp.value()}}))\n"
            )
    elif read_action == 'wait_l':
        if timeout_ms > 0:
            read_body = (
                "    t0=time.ticks_ms()\n"
                f"    while rp.value()==1 and time.ticks_diff(time.ticks_ms(),t0)<{timeout_ms}:\n"
                "        time.sleep_us(50)\n"
                "    if rp.value()==1:\n"
                f"        print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'wait_l','timeout':True,'value':rp.value()}}))\n"
                "        continue\n"
                "    wms=time.ticks_diff(time.ticks_ms(),t0)\n"
                f"    print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'wait_l','wait_ms':wms,'value':rp.value()}}))\n"
            )
        else:
            read_body = (
                "    t0=time.ticks_ms()\n"
                "    while rp.value()==1:\n"
                "        time.sleep_us(50)\n"
                "    wms=time.ticks_diff(time.ticks_ms(),t0)\n"
                f"    print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'wait_l','wait_ms':wms,'value':rp.value()}}))\n"
            )
    elif read_action == 'pulse_h':
        if timeout_ms > 0:
            read_body = (
                f"    r=time_pulse_us(rp,1,{timeout_ms * 1000})\n"
                "    if r<0:\n"
                f"        print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'pulse_h','timeout':True,'value':rp.value()}}))\n"
                "        continue\n"
                f"    print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'pulse_h','pulse_us':r,'value':rp.value()}}))\n"
            )
        else:
            read_body = (
                "    _acc=0\n"
                "    while True:\n"
                "        _r=time_pulse_us(rp,1,100000)\n"
                "        if _r>=0:\n"
                "            _acc+=_r\n"
                "            break\n"
                "        if rp.value()==0:\n"
                "            if _acc>0:\n"
                "                _acc=-1\n"
                "                break\n"
                "        else:\n"
                "            _acc+=100000\n"
                "    r=_acc\n"
                "    if r<0:\n"
                f"        print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'pulse_h','timeout':True,'value':rp.value()}}))\n"
                "        continue\n"
                f"    print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'pulse_h','pulse_us':r,'value':rp.value()}}))\n"
            )
    elif read_action == 'pulse_l':
        if timeout_ms > 0:
            read_body = (
                f"    r=time_pulse_us(rp,0,{timeout_ms * 1000})\n"
                "    if r<0:\n"
                f"        print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'pulse_l','timeout':True,'value':rp.value()}}))\n"
                "        continue\n"
                f"    print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'pulse_l','pulse_us':r,'value':rp.value()}}))\n"
            )
        else:
            read_body = (
                "    _acc=0\n"
                "    while True:\n"
                "        _r=time_pulse_us(rp,0,100000)\n"
                "        if _r>=0:\n"
                "            _acc+=_r\n"
                "            break\n"
                "        if rp.value()==1:\n"
                "            if _acc>0:\n"
                "                _acc=-1\n"
                "                break\n"
                "        else:\n"
                "            _acc+=100000\n"
                "    r=_acc\n"
                "    if r<0:\n"
                f"        print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'pulse_l','timeout':True,'value':rp.value()}}))\n"
                "        continue\n"
                f"    print(json.dumps({{'write_pin':{pn_w},'read_pin':{pn_r},'read_action':'pulse_l','pulse_us':r,'value':rp.value()}}))\n"
            )
    else:
        raise ValueError(f"Unsupported seq repeat action: {read_action}")

    sleep_stmt = f"    time.sleep_ms({interval_ms})\n" if interval_ms > 0 else ""
    return header + write_body + read_body + sleep_stmt


def _make_repeat_code(pin_no: int, pin_name: str, action: str, repeat: int) -> str:
    n_expr = '0' if repeat == 0 else str(repeat)
    pn = repr(pin_name)
    if action == 'pulse_h':
        body = (
            "    _acc=0\n"
            "    while True:\n"
            "        _r=time_pulse_us(rp,1,100000)\n"
            "        if _r>=0:\n"
            "            _acc+=_r\n"
            "            break\n"
            "        if rp.value()==0:\n"
            "            if _acc>0:\n"
            "                _acc=-1\n"
            "                break\n"
            "        else:\n"
            "            _acc+=100000\n"
            "    r=_acc\n"
            "    if r<0:\n"
            f"        print(json.dumps({{'read_pin':{pn},'read_action':'pulse_h','timeout':True,'value':rp.value()}}))\n"
            "        continue\n"
            f"    print(json.dumps({{'read_pin':{pn},'read_action':'pulse_h','pulse_us':r,'value':rp.value()}}))\n"
        )
    elif action == 'pulse_l':
        body = (
            "    _acc=0\n"
            "    while True:\n"
            "        _r=time_pulse_us(rp,0,100000)\n"
            "        if _r>=0:\n"
            "            _acc+=_r\n"
            "            break\n"
            "        if rp.value()==1:\n"
            "            if _acc>0:\n"
            "                _acc=-1\n"
            "                break\n"
            "        else:\n"
            "            _acc+=100000\n"
            "    r=_acc\n"
            "    if r<0:\n"
            f"        print(json.dumps({{'read_pin':{pn},'read_action':'pulse_l','timeout':True,'value':rp.value()}}))\n"
            "        continue\n"
            f"    print(json.dumps({{'read_pin':{pn},'read_action':'pulse_l','pulse_us':r,'value':rp.value()}}))\n"
        )
    elif action == 'wait_h':
        body = (
            "    while rp.value()==1:\n"
            "        time.sleep_us(50)\n"
            "    t0=time.ticks_ms()\n"
            "    while rp.value()==0:\n"
            "        time.sleep_us(50)\n"
            "    wms=time.ticks_diff(time.ticks_ms(),t0)\n"
            f"    print(json.dumps({{'read_pin':{pn},'read_action':'wait_h','wait_ms':wms,'value':rp.value()}}))\n"
        )
    elif action == 'wait_l':
        body = (
            "    while rp.value()==0:\n"
            "        time.sleep_us(50)\n"
            "    t0=time.ticks_ms()\n"
            "    while rp.value()==1:\n"
            "        time.sleep_us(50)\n"
            "    wms=time.ticks_diff(time.ticks_ms(),t0)\n"
            f"    print(json.dumps({{'read_pin':{pn},'read_action':'wait_l','wait_ms':wms,'value':rp.value()}}))\n"
        )
    else:
        raise ValueError(f"Unsupported repeat action: {action}")
    return (
        "from machine import Pin,time_pulse_us\n"
        "import time,json\n"
        f"rp=Pin({pin_no},Pin.IN)\n"
        f"_n={n_expr}\n"
        "_i=0\n"
        "while _n==0 or _i<_n:\n"
        "    _i+=1\n"
        + body
    )


def _make_multi_stream_code(pins: list[tuple[int, str]], action: str, repeat: int) -> str:
    # each pin is monitored concurrently via edge IRQs so a result is printed
    # the instant that pin's own action completes, instead of waiting on all pins.
    pin_nos = [pin_no for pin_no, _ in pins]
    pin_names = [pin_name for _, pin_name in pins]
    n_expr = '0' if repeat == 0 else str(repeat)
    is_pulse = action in ('pulse_h', 'pulse_l')
    level = (1 if action in ('pulse_h', 'wait_h') else 0)
    opposite = 1 - level

    header = (
        "from machine import Pin\n"
        "import time,json\n"
        f"pins={pin_nos!r}\n"
        f"names={pin_names!r}\n"
        "rps=[Pin(p,Pin.IN) for p in pins]\n"
        "n=len(rps)\n"
        "state=[0]*n\n"
        "t0=[0]*n\n"
        "dur=[0]*n\n"
        "ready=[False]*n\n"
        f"_LEVEL={level}\n"
        f"_OPP={opposite}\n"
    )
    if is_pulse:
        header += (
            "def _mk(k):\n"
            "    def _h(pin):\n"
            "        v=pin.value()\n"
            "        if state[k]==0:\n"
            "            if v==_LEVEL:\n"
            "                t0[k]=time.ticks_us()\n"
            "                state[k]=1\n"
            "        elif v==_OPP:\n"
            "            dur[k]=time.ticks_diff(time.ticks_us(),t0[k])\n"
            "            state[k]=0\n"
            "            ready[k]=True\n"
            "    return _h\n"
        )
    else:
        header += (
            "def _mk(k):\n"
            "    def _h(pin):\n"
            "        v=pin.value()\n"
            "        if state[k]==0:\n"
            "            if v==_OPP:\n"
            "                t0[k]=time.ticks_ms()\n"
            "                state[k]=1\n"
            "        elif v==_LEVEL:\n"
            "            dur[k]=time.ticks_diff(time.ticks_ms(),t0[k])\n"
            "            state[k]=0\n"
            "            ready[k]=True\n"
            "    return _h\n"
        )
    header += (
        "for k in range(n):\n"
        "    rps[k].irq(trigger=Pin.IRQ_RISING|Pin.IRQ_FALLING,handler=_mk(k))\n"
        f"_n={n_expr}\n"
        "cnt=[0]*n\n"
    )

    field = 'pulse_us' if is_pulse else 'wait_ms'
    body = (
        "try:\n"
        "    while True:\n"
        "        for k in range(n):\n"
        "            if ready[k]:\n"
        "                ready[k]=False\n"
        "                if _n==0 or cnt[k]<_n:\n"
        "                    cnt[k]+=1\n"
        f"                    print(json.dumps({{'pin':names[k],'read_action':{action!r},{field!r}:dur[k],'value':rps[k].value()}}))\n"
        "        if _n>0 and min(cnt)>=_n:\n"
        "            break\n"
        "        time.sleep_ms(5)\n"
        "finally:\n"
        "    for rp in rps:\n"
        "        rp.irq(handler=None)\n"
    )
    return header + body


def _run_repeat_interactive(client, code: str, on_line, ctrl_c_grace_s: float = 3.0) -> None:
    stop_requested = False
    pending_input: list[bytes] = []
    line_buf = bytearray()
    stderr_parts: list[bytes] = []
    original_sigint = signal.getsignal(signal.SIGINT)

    def sigint_handler(signum, frame):
        nonlocal stop_requested
        stop_requested = True
        pending_input.append(CTRL_C)

    def output_callback(data: bytes, stream_type: str = "stdout"):
        nonlocal line_buf
        if stream_type == 'stderr':
            stderr_parts.append(data)
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
            ctrl_c_grace_s=ctrl_c_grace_s,
        )
    finally:
        signal.signal(signal.SIGINT, original_sigint)

    error = b''.join(stderr_parts).decode('utf-8', errors='replace').strip()
    if error and not (stop_requested and error.splitlines()[-1] in ('KeyboardInterrupt', 'KeyboardInterrupt:')):
        raise RuntimeError(error)
    if line_buf.strip():
        on_line(line_buf.decode('utf-8', errors='replace').strip())


def _print_gpio_help() -> None:
    help_text = """\
GPIO monitor/read/write/sequence command for a single pin.

[bold cyan]Usage:[/bold cyan]
  replx gpio [yellow]SUBCOMMAND[/yellow] ...

[bold cyan]Subcommands:[/bold cyan]
  [green]monitor[/green]  Live scope — sample one GPIO in input mode until Ctrl+C.
  [green]read[/green]     Read action (pulse/wait) on one or more input pins.
  [green]write[/green]    Drive one GPIO in output mode.
  [green]seq[/green]      Execute a write+delay sequence with an optional read_action.

[bold cyan]Pin Format:[/bold cyan]
  [yellow]GP<num>[/yellow], [yellow]GPIO<num>[/yellow], or numeric GPIO id.
  XBee3: D0..D9/P0..P2; level read/write and write/delay seq only.
  Examples: gpio read D0 read; gpio seq D0 1 m10 0 D1 read.
  XBee3 pulse/wait actions and monitor are excluded.

[bold cyan]Monitor:[/bold cyan]
  replx gpio monitor [yellow]GP<num>[/yellow] [[green]--interval MS[/green]]
  [dim]--interval MS[/dim]  render interval in milliseconds [dim](default 10, min 1)[/dim]
                   [dim]Edges are captured by IRQ (~10-50 µs accuracy) independent of[/dim]
                   [dim]this interval. Renders scope + edge log at --interval rate.[/dim]
                   [dim]Requires termviz on board.[/dim]

[bold cyan]Read:[/bold cyan]
  replx gpio read [yellow]GP<num>[/yellow] [[yellow]GP<num> ...[/yellow]] [magenta]ACTION[/magenta] [[green]--repeat N[/green]] [[green]--expr EXPR[/green]]

  [bold]ACTION[/bold]
    [magenta]wait_h[/magenta]   block until pin goes High
    [magenta]wait_l[/magenta]   block until pin goes Low
    [magenta]pulse_h[/magenta]  wait for a High pulse and report its width in µs
    [magenta]pulse_l[/magenta]  wait for a Low  pulse and report its width in µs

  [dim]--repeat N     repeat N times; 0 = infinite until Ctrl+C (default 1)[/dim]
  [dim]--expr EXPR    post-process result; variables: pulse_us, wait_ms[/dim]
  [dim]               functions: abs, round, min, max[/dim]
  [dim]gpio read waits until the action completes (Ctrl+C to cancel); --timeout is seq-only.[/dim]
  [dim]Multiple pins may be given before ACTION; each pin reports as soon as its action completes.[/dim]

[bold cyan]Write:[/bold cyan]
  replx gpio write [yellow]GP<num>[/yellow] [yellow]0|1[/yellow]

[bold cyan]Sequence:[/bold cyan]
  replx gpio seq [yellow]GP<num>[/yellow] [cyan]TOKEN[/cyan]... [[magenta]read_action[/magenta]]
  replx gpio seq [yellow]WRITE_GP[/yellow] [cyan]TOKEN[/cyan]... [[yellow]READ_GP[/yellow] [magenta]read_action[/magenta]]
                              [[green]--expr EXPR[/green]] [[green]--timeout MS[/green]] [[green]--repeat N[/green]] [[green]--interval MS[/green]]

  [bold]Write Tokens[/bold]
    [cyan]0[/cyan] [cyan]1[/cyan]      drive low/high
    [cyan]u<N>[/cyan]     delay in microseconds
    [cyan]m<N>[/cyan]     delay in milliseconds

  [bold]read_action[/bold] [dim](optional, final token only)[/dim]
    [magenta]read[/magenta]     read final pin value
    [magenta]wait_h[/magenta]   wait until value becomes 1
    [magenta]wait_l[/magenta]   wait until value becomes 0
    [magenta]pulse_h[/magenta]  wait for high pulse and report width
    [magenta]pulse_l[/magenta]  wait for low pulse and report width

    [dim]If only read_action is given, the write pin is also used as the read pin.[/dim]
    [dim]If READ_GP read_action is given, the write pin and read pin can be different.[/dim]
    [dim]wait_* and pulse_* honor --timeout in ms (default 100). Use 0 for infinite wait.[/dim]
    [dim]--repeat N     repeat the full seq N times; 0 = infinite until Ctrl+C (default 1)[/dim]
    [dim]               N > 1 or 0: runs as a single on-board loop (no round-trip per iteration)[/dim]
    [dim]--interval MS  delay in ms between iterations (requires --repeat; default 10)[/dim]
    [dim]--expr can use: value, writes, pulse_us, wait_ms and functions abs, round, min, max.[/dim]

[bold cyan]Examples:[/bold cyan]
  replx COM3 gpio monitor GP1
  replx COM3 gpio monitor GP1 --interval 50
  replx COM3 gpio read GP2 pulse_h
  replx COM3 gpio read GP2 pulse_h --repeat 0
  replx COM3 gpio read GP14 GP15 GP16 GP17 pulse_h --repeat 0
  replx COM3 gpio read GP2 pulse_h --expr "pulse_us/58"
  replx COM3 gpio read GP2 wait_h
  replx COM3 gpio write GP1 1
  replx COM3 gpio seq GP20 1 u10 0 pulse_h
  replx COM3 gpio seq GP20 0 u5 1 u10 0 GP21 pulse_h
  replx COM3 gpio seq GP20 0 u5 1 u10 0 GP21 pulse_h --timeout 100
  replx COM3 gpio seq GP20 0 u5 1 u10 0 GP21 pulse_h --expr "pulse_us/58"
  replx COM3 gpio seq GP20 0 u5 1 u10 0 GP21 pulse_h --expr "pulse_us/58" --repeat 5
  replx COM3 gpio seq GP20 0 u5 1 u10 0 GP21 pulse_h --expr "pulse_us/58" --repeat 0
  replx COM3 gpio seq GP1 1 u50 0 m1 1 read
  replx COM3 gpio seq GP1 1 u10 0 wait_h
  replx COM3 gpio seq GP1 0 u10 1 pulse_l

[bold cyan]Notes:[/bold cyan]
  • write/seq/monitor drive or sample one GPIO; read accepts multiple pins.
  • [yellow]gpio monitor[/yellow] uses IRQ edge capture (~10-50 µs). [yellow]--interval[/yellow] sets render rate only. Requires [yellow]termviz[/yellow].
  • [yellow]gpio read[/yellow] supports [yellow]--repeat[/yellow] and [yellow]--expr[/yellow]; [yellow]--timeout[/yellow] applies to [yellow]seq[/yellow] only.
  • [yellow]seq[/yellow] requires at least one write token.
  • [yellow]seq --repeat[/yellow] runs the full seq+read loop on-board; no round-trip per iteration."""
    OutputHelper.print_panel(help_text, title="gpio", border_style="help")


def _subcmd_monitor(client, pos_args: list[str], interval_ms: int) -> None:
    if len(pos_args) != 1:
        raise ValueError("Usage: replx gpio monitor GP<num> [--interval MS]")

    if interval_ms < 1:
        raise ValueError("--interval must be >= 1 (ms)")

    pin_no, pin_name = _parse_gp(pos_args[0])

    _preflight_scope_libs(client)
    code = _build_scope_code(pin_no, interval_ms)
    from .exec import _run_interactive_mode
    _run_interactive_mode(client, code, None, False)


_READ_ONLY_ACTIONS = {"pulse_h", "pulse_l", "wait_h", "wait_l"}


def _read_panel(pin_name: str, action: str, data: Optional[dict], expr: Optional[str], title: str) -> Panel:
    is_pulse = action.startswith('pulse')
    label = "Pulse" if is_pulse else "Wait"

    grid = Table.grid(padding=0)
    grid.add_column()
    grid.add_row(Text.from_markup(f"Read pin: [bright_green]{pin_name}[/bright_green]"))
    grid.add_row(Text.from_markup(f"Action: [magenta]{action}[/magenta]"))

    if data is None:
        spin_row = Table.grid(padding=0)
        spin_row.add_column()
        spin_row.add_column()
        spin_row.add_row(Text(f"{label}: "), Spinner("dots", style="cyan"))
        grid.add_row(spin_row)
    else:
        if data.get('timeout'):
            grid.add_row(Text.from_markup(f"Timeout: [bright_red]{int(data.get('timeout_ms', 0))} ms[/bright_red]"))
        elif is_pulse:
            grid.add_row(Text.from_markup(f"Pulse: [bright_cyan]{int(data.get('pulse_us', 0))} us[/bright_cyan]"))
            if expr is not None:
                result = _eval_expr(expr, data)
                grid.add_row(Text.from_markup(f"Expr: [magenta]{expr}[/magenta] = [bright_cyan]{result}[/bright_cyan]"))
        else:
            grid.add_row(Text.from_markup(f"Wait: [bright_cyan]{int(data.get('wait_ms', 0))} ms[/bright_cyan]"))
            if expr is not None:
                result = _eval_expr(expr, data)
                grid.add_row(Text.from_markup(f"Expr: [magenta]{expr}[/magenta] = [bright_cyan]{result}[/bright_cyan]"))

    return Panel(
        grid,
        title=title,
        border_style=OutputHelper._resolve_category_color('data'),
        box=get_panel_box(),
        expand=True,
        width=CONSOLE_WIDTH,
        title_align="left",
    )


def _multi_wait_panel(pin_names: list[str], action: str, title: str) -> Panel:
    label = "Pulse" if action.startswith('pulse') else "Wait"

    grid = Table.grid(padding=0)
    grid.add_column()
    grid.add_row(Text.from_markup(f"Read pins: [bright_green]{', '.join(pin_names)}[/bright_green]"))
    grid.add_row(Text.from_markup(f"Action: [magenta]{action}[/magenta]"))

    spin_row = Table.grid(padding=0)
    spin_row.add_column()
    spin_row.add_column()
    spin_row.add_row(Text(f"{label}: "), Spinner("dots", style="cyan"))
    grid.add_row(spin_row)

    return Panel(
        grid,
        title=title,
        border_style=OutputHelper._resolve_category_color('data'),
        box=get_panel_box(),
        expand=True,
        width=CONSOLE_WIDTH,
        title_align="left",
    )


def _seq_repeat_panel(
    write_pin_name: str, seq_str: str,
    read_pin_name: Optional[str], read_action: Optional[str],
    data: Optional[dict], expr: Optional[str], title: str,
) -> Panel:
    grid = Table.grid(padding=0)
    grid.add_column()
    grid.add_row(Text.from_markup(f"Write pin: [bright_green]{write_pin_name}[/bright_green]"))
    grid.add_row(Text.from_markup(f"Seq: [bright_cyan]{seq_str}[/bright_cyan]"))

    if read_action is not None:
        grid.add_row(Text.from_markup(f"Read pin: [bright_green]{read_pin_name}[/bright_green]"))
        grid.add_row(Text.from_markup(f"Action: [magenta]{read_action}[/magenta]"))

    if data is None:
        if read_action in ('pulse_h', 'pulse_l', 'wait_h', 'wait_l'):
            label = "Pulse" if read_action.startswith('pulse') else "Wait"
            spin_row = Table.grid(padding=0)
            spin_row.add_column()
            spin_row.add_column()
            spin_row.add_row(Text(f"{label}: "), Spinner("dots", style="cyan"))
            grid.add_row(spin_row)
    else:
        if data.get('timeout'):
            grid.add_row(Text.from_markup(f"Timeout: [bright_red]{int(data.get('timeout_ms', 0))} ms[/bright_red]"))
        elif read_action in ('pulse_h', 'pulse_l'):
            grid.add_row(Text.from_markup(f"Pulse: [bright_cyan]{int(data.get('pulse_us', 0))} us[/bright_cyan]"))
            if expr is not None:
                result = _eval_expr(expr, data)
                grid.add_row(Text.from_markup(f"Expr: [magenta]{expr}[/magenta] = [bright_cyan]{result}[/bright_cyan]"))
        elif read_action in ('wait_h', 'wait_l'):
            grid.add_row(Text.from_markup(f"Wait: [bright_cyan]{int(data.get('wait_ms', 0))} ms[/bright_cyan]"))
        else:
            grid.add_row(Text.from_markup(f"Value: [bright_cyan]{int(data.get('value', 0))}[/bright_cyan]"))

    return Panel(
        grid,
        title=title,
        border_style=OutputHelper._resolve_category_color('success'),
        box=get_panel_box(),
        expand=True,
        width=CONSOLE_WIDTH,
        title_align="left",
    )


def _subcmd_read(client, pos_args: list[str], expr: Optional[str], repeat: int) -> None:
    if len(pos_args) < 2:
        raise ValueError(
            "Usage: replx gpio read GP<num> [GP<num> ...] pulse_h|pulse_l|wait_h|wait_l"
        )
    if repeat < 0:
        raise ValueError("--repeat must be >= 0")

    action = pos_args[-1].lower()
    if action not in _READ_ONLY_ACTIONS:
        raise ValueError(
            f"gpio read action must be one of: {', '.join(sorted(_READ_ONLY_ACTIONS))}"
        )

    pins = [_parse_gp(token) for token in pos_args[:-1]]
    pin_nos = [pin_no for pin_no, _ in pins]
    if len(set(pin_nos)) != len(pin_nos):
        raise ValueError("gpio read pins must be distinct")

    if len(pins) > 1:
        _subcmd_read_multi(client, pins, action, expr, repeat)
        return

    pin_no, pin_name = pins[0]

    if repeat == 1:
        code = _make_seq_code(pin_no, pin_name, [], pin_no, pin_name, action, 0)
        placeholder = _read_panel(pin_name, action, None, expr, "GPIO Read")
        with Live(placeholder, console=OutputHelper._console, refresh_per_second=4) as live:
            try:
                raw = _run_interactive_script(client, code, live_output=False, ctrl_c_grace_s=1.5)
                data = _parse_json_strict(raw)
                live.update(_read_panel(pin_name, action, data, expr, "GPIO Read"))
            except KeyboardInterrupt:
                pass
        return

    code = _make_repeat_code(pin_no, pin_name, action, repeat)
    counter = [0]
    with Live(_read_panel(pin_name, action, None, expr, "GPIO Read #1"), console=OutputHelper._console, refresh_per_second=4) as live:
        def on_line(json_str: str) -> None:
            counter[0] += 1
            idx = counter[0]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                return
            live.console.print(_read_panel(pin_name, action, data, expr, f"GPIO Read #{idx}"))
            live.update(_read_panel(pin_name, action, None, expr, f"GPIO Read #{idx + 1}"))
        try:
            _run_repeat_interactive(client, code, on_line, ctrl_c_grace_s=1.5)
        except KeyboardInterrupt:
            pass


def _subcmd_read_multi(client, pins: list[tuple[int, str]], action: str, expr: Optional[str], repeat: int) -> None:
    pin_names = [pin_name for _, pin_name in pins]
    code = _make_multi_stream_code(pins, action, repeat)
    counter = [0]
    with Live(_multi_wait_panel(pin_names, action, "GPIO Read #1"), console=OutputHelper._console, refresh_per_second=4) as live:
        def on_line(json_str: str) -> None:
            counter[0] += 1
            idx = counter[0]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                return
            pin_name = data.get('pin', '?')
            live.console.print(_read_panel(pin_name, action, data, expr, f"GPIO Read #{idx}"))
            live.update(_multi_wait_panel(pin_names, action, f"GPIO Read #{idx + 1}"))
        try:
            _run_repeat_interactive(client, code, on_line, ctrl_c_grace_s=1.5)
        except KeyboardInterrupt:
            pass


def _subcmd_write(client, pos_args: list[str]) -> None:
    if len(pos_args) != 2:
        raise ValueError("Usage: replx gpio write GP<num> 0|1")

    pin_no, pin_name = _parse_gp(pos_args[0])
    value = _parse_logic(pos_args[1])
    raw = _exec(client, _make_write_code(pin_no, pin_name, value), timeout=5.0)
    data = _parse_json_strict(raw)

    OutputHelper.print_panel(
        f"[bright_green]{pin_name}[/bright_green] <= [bright_cyan]{int(data.get('value', value))}[/bright_cyan]",
        title="GPIO Write",
        border_style="success",
    )


def _subcmd_seq(client, pos_args: list[str], expr: Optional[str], timeout_ms: int, repeat: int, interval_ms: int = 0) -> None:
    if len(pos_args) < 2:
        raise ValueError("Usage: replx gpio seq GP<num> TOKEN... [read_action]")
    if timeout_ms < 0:
        raise ValueError("--timeout must be >= 0")

    write_pin_no, write_pin_name = _parse_gp(pos_args[0])
    ops, read_pin_no, read_action, read_pin_name = _parse_seq_tokens(pos_args[1:], write_pin_name)

    if repeat == 1:
        code = _make_seq_code(write_pin_no, write_pin_name, ops, read_pin_no, read_pin_name, read_action, timeout_ms)

        if read_action in {'wait_h', 'wait_l', 'pulse_h', 'pulse_l'}:
            raw = _run_interactive_script(client, code, live_output=False)
        else:
            timeout = 10.0 + sum(value / 1000.0 for kind, value in ops if kind == 'm') + sum(value / 1_000_000.0 for kind, value in ops if kind == 'u')
            raw = _exec(client, code, timeout=min(max(timeout, 5.0), 120.0))

        data = _parse_json_strict(raw)
        lines = [
            f"Write pin: [bright_green]{data.get('write_pin', write_pin_name)}[/bright_green]",
            f"Seq: [bright_cyan]{_format_seq_ops(ops)}[/bright_cyan]",
        ]
        if read_action is None:
            lines.append(f"Final value: [bright_cyan]{int(data.get('value', 0))}[/bright_cyan]")
        if read_action:
            lines.append(f"Read pin: [bright_green]{data.get('read_pin', read_pin_name)}[/bright_green]")
            lines.append(f"Action: [magenta]{read_action}[/magenta]")
        if data.get('timeout'):
            lines.append(f"Timeout: [bright_red]{int(data.get('timeout_ms', timeout_ms))} ms[/bright_red]")
        if 'wait_ms' in data:
            lines.append(f"Wait: [bright_cyan]{int(data['wait_ms'])} ms[/bright_cyan]")
        if 'pulse_us' in data:
            lines.append(f"Pulse: [bright_cyan]{int(data['pulse_us'])} us[/bright_cyan]")
        if expr is not None and not data.get('timeout'):
            result = _eval_expr(expr, data)
            lines.append(f"Expr: [magenta]{expr}[/magenta] = [bright_cyan]{result}[/bright_cyan]")

        OutputHelper.print_panel('\n'.join(lines), title="GPIO Seq", border_style="success")
        return

    seq_str = _format_seq_ops(ops)
    code = _make_seq_repeat_code(write_pin_no, write_pin_name, ops, read_pin_no, read_pin_name, read_action, timeout_ms, repeat, interval_ms)
    counter = [0]
    with Live(_seq_repeat_panel(write_pin_name, seq_str, read_pin_name, read_action, None, expr, "GPIO Seq #1"), console=OutputHelper._console, refresh_per_second=4) as live:
        def on_line(json_str: str) -> None:
            counter[0] += 1
            idx = counter[0]
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                return
            live.console.print(_seq_repeat_panel(write_pin_name, seq_str, read_pin_name, read_action, data, expr, f"GPIO Seq #{idx}"))
            live.update(_seq_repeat_panel(write_pin_name, seq_str, read_pin_name, read_action, None, expr, f"GPIO Seq #{idx + 1}"))
        try:
            _run_repeat_interactive(client, code, on_line, ctrl_c_grace_s=1.5)
        except KeyboardInterrupt:
            pass


@app.command(name="gpio", rich_help_panel="Hardware")
def gpio_cmd(
    args: Optional[list[str]] = typer.Argument(
        None, help="Subcommand: read  write  seq"
    ),
    expr: Optional[str] = typer.Option(None, "--expr", metavar="EXPR", help="Post-process gpio seq/read result with an arithmetic expression"),
    timeout: int = typer.Option(100, "--timeout", metavar="MS", help="Timeout in ms for gpio seq wait/pulse actions (0=infinite). Not used by gpio read (always infinite)."),
    interval: int = typer.Option(10, "--interval-ms", "--interval", metavar="MS", help="Render interval in milliseconds for gpio monitor (default 10, min 1 ms). Canvas window = interval × 78 ms. Edges are captured by IRQ independently."),
    repeat: int = typer.Option(1, "--repeat", metavar="N", help="Repeat gpio read N times (0=infinite until Ctrl+C, default 1)"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True),
):
    if show_help:
        _print_gpio_help()
        raise typer.Exit()
    if not args:
        OutputHelper.print_panel(
            "Subcommands: [bright_blue]monitor[/bright_blue]  [bright_blue]read[/bright_blue]  [bright_blue]write[/bright_blue]  [bright_blue]seq[/bright_blue]\n\n"
            "  [bright_green]replx PORT gpio read GP1[/bright_green]\n"
            "  [bright_green]replx PORT gpio write GP25 1[/bright_green]\n"
            "  [bright_green]replx PORT gpio monitor GP1[/bright_green]\n\n"
            "Use [bright_blue]replx gpio --help[/bright_blue] for details.",
            title="GPIO",
            border_style="help",
        )
        raise typer.Exit(1)

    subcmd = args[0].lower()
    pos_args = args[1:]

    if subcmd not in ('monitor', 'read', 'write', 'seq'):
        OutputHelper.print_panel(
            f"Unknown subcommand: {subcmd!r}\n\n"
            "Valid subcommands: monitor  read  write  seq",
            title="GPIO Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if interval != 10 and subcmd not in ('monitor', 'seq'):
        OutputHelper.print_panel(
            "--interval is supported only for gpio monitor (render rate) and gpio seq --repeat (inter-iteration delay)",
            title="GPIO Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if interval != 10 and subcmd == 'seq' and repeat == 1:
        OutputHelper.print_panel(
            "--interval requires --repeat N (N > 1 or 0) for gpio seq",
            title="GPIO Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if subcmd not in ('seq', 'read') and expr is not None:
        OutputHelper.print_panel(
            "--expr is supported only for gpio read and gpio seq",
            title="GPIO Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if subcmd != 'seq' and timeout != 100:
        OutputHelper.print_panel(
            "--timeout is supported only for gpio seq",
            title="GPIO Error",
            border_style="error",
        )
        raise typer.Exit(1)

    if subcmd not in ('read', 'seq') and repeat != 1:
        OutputHelper.print_panel(
            "--repeat is supported only for gpio read and gpio seq",
            title="GPIO Error",
            border_style="error",
        )
        raise typer.Exit(1)

    _ensure_connected()

    try:
        with _create_agent_client() as client:
            if is_xbee(client):
                _run_xbee_gpio(client, subcmd, pos_args, repeat, interval if repeat != 1 else 0, expr)
            elif subcmd == 'monitor':
                _subcmd_monitor(client, pos_args, interval)
            elif subcmd == 'read':
                _subcmd_read(client, pos_args, expr, repeat)
            elif subcmd == 'write':
                _subcmd_write(client, pos_args)
            elif subcmd == 'seq':
                _subcmd_seq(client, pos_args, expr, timeout, repeat, interval if repeat != 1 else 0)
    except typer.Exit:
        raise
    except (ValueError, RuntimeError) as e:
        OutputHelper.print_panel(str(e), title="GPIO Error", border_style="error")
        raise typer.Exit(1)
