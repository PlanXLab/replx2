import json
import shutil
import sys
import time
from typing import Optional

import typer

from ..helpers import OutputHelper
from ..connection import _ensure_connected, _create_agent_client
from ..app import app
from ._common import exec_code as _exec, parse_json_strict as _parse_json_strict, parse_gp_pin
from ._common import parse_hardware_pin, is_xbee, get_core
from replx.utils.device_info import normalize_core
from ...terminal import enable_vt_mode, restore_vt_mode

_MAX_CHANNELS = 3
_DEFAULT_SCOPE_PINS = [26, 27, 28]
_SAMPLE_TABLE = [0, 1, 2, 5, 10, 20, 50, 100]


def _parse_gp(token: str) -> int:
    return parse_gp_pin(token, label='ADC pin')


def _parse_gp_pins(tokens: list[str], *, allow_empty: bool = False, default_pins: Optional[list[int]] = None) -> list[int]:
    if not tokens:
        if allow_empty and default_pins is not None:
            return list(default_pins)
        raise ValueError("Specify one or more ADC pins in GP<num> format")

    pins = [_parse_gp(tok) for tok in tokens]
    if len(pins) > _MAX_CHANNELS:
        raise ValueError(f"adc supports up to {_MAX_CHANNELS} channels")
    if len(set(pins)) != len(pins):
        raise ValueError("Duplicate ADC pins are not allowed")
    return pins


def _raw_to_volts(raw: int, vref: float) -> float:
    return float(raw) * float(vref) / 65535.0


def _validate_adc_pins(client, pins: list[int]) -> None:
    if normalize_core(get_core(client, None)) == 'ESP32P4':
        valid = set(range(16, 24)) | set(range(49, 55))
        if any(pin not in valid for pin in pins):
            raise ValueError(
                "ESP32-P4 ADC requires GPIO16..23 or GPIO49..54. On Waveshare P4-WIFI6, "
                "header ADC pins are GPIO20..23 and GPIO49..52; check onboard pin usage."
            )


def _adc_read_code(pins: list[int], repeat: int, interval: int) -> str:
    adcs = ','.join(f"ADC(Pin({pin}))" for pin in pins)
    loop_line = "while True:\n" if repeat == 0 else f"for _ in range({repeat}):\n"
    sleep_stmt = f"    time.sleep_ms({interval})\n" if interval > 0 else ""
    return (
        "from machine import ADC,Pin\n"
        "import json,time\n"
        f"adcs=[{adcs}]\n"
        f"{loop_line}"
        "    print(json.dumps([a.read_u16() for a in adcs]))\n"
        + sleep_stmt
    )


def _format_read_rows(pins: list[int], samples: list[list[int]], vref: float) -> str:
    if len(samples) == 1:
        lines = []
        for pin, raw in zip(pins, samples[0]):
            lines.append(
                f"GP{pin:<2}  raw=[bright_cyan]{raw:5d}[/bright_cyan]  "
                f"V=[bright_green]{_raw_to_volts(raw, vref):.3f}[/bright_green]"
            )
        return '\n'.join(lines)

    lines = []
    for i, row in enumerate(samples, 1):
        parts = []
        for pin, raw in zip(pins, row):
            parts.append(f"GP{pin}={raw:5d}/{_raw_to_volts(raw, vref):.3f}V")
        lines.append(f"[{i:>2}] " + "  ".join(parts))
    return '\n'.join(lines)


def _preflight_scope_libs(client) -> None:
    code = (
        "mods=[]\n"
        "try:\n"
        " import termviz\n"
        " mods.append('termviz')\n"
        "except Exception:\n"
        " pass\n"
        "try:\n"
        " import ufilter\n"
        " mods.append('ufilter')\n"
        "except Exception:\n"
        " pass\n"
        "print(','.join(mods))"
    )
    raw = _exec(client, code, timeout=3.0)
    mods = {m.strip() for m in raw.split(',') if m.strip()}
    missing = [name for name in ('termviz', 'ufilter') if name not in mods]
    if missing:
        raise RuntimeError(
            "adc scope requires these modules on the board: " + ', '.join(missing)
        )


_SCOPE_TEMPLATE = r'''import sys
import time
import select as _sel
from machine import Pin, ADC
from termviz import Term, Canvas, Plot, Scope

_CHANNELS = __CHANNELS__
_MAX_CHANNELS = 3
_SAMPLE_MS = __SAMPLE_MS__
_INTERNAL_SAMPLE_MS = 1
_SAMPLE_TABLE = [0, 1, 2, 5, 10, 20, 50, 100]

_CV_COLS = 78
_CV_ROWS = 20
_STATS_ROW = _CV_ROWS + 1
_HELP_ROW  = _CV_ROWS + 2
_REGION    = (0, 8, 10, 10)

_BOARD_VREF = __BOARD_VREF__
_RAW_OVERLAY_RGB = (150, 150, 150)
_SCOPE_PALETTE = [
    (255, 80, 80),
    (80, 255, 120),
    (80, 160, 255),
    (255, 200, 80),
    (200, 80, 255),
    (80, 255, 255),
    (255, 128, 170),
    (128, 255, 128),
]

_FILTER_ITEMS = [
    ('raw',     'RAW'),
    ('ema',     'EMA'),
    ('mv',      'MV'),
    ('med',     'MED'),
    ('rms',     'RMS'),
    ('kalman',  'KAL'),
    ('kalman1d','K1D'),
    ('adaptive','ADP'),
    ('lpf',     'LPF'),
    ('hpf',     'HPF'),
    ('bw_lpf',  'BWL'),
    ('bw_hpf',  'BWH'),
    ('tau',     'TAU'),
]

_FILTER_FULL_NAMES = {
    'raw': 'Raw',
    'ema': 'ExponentialMovingAverage',
    'mv': 'MovingAverage',
    'med': 'Medium',
    'rms': 'RootMeanSquare',
    'kalman': 'Kalman',
    'kalman1d': 'Kalman1D',
    'adaptive': 'Adaptive',
    'lpf': 'LowPass',
    'hpf': 'HighPass',
    'bw_lpf': 'ButterworthLowPass',
    'bw_hpf': 'ButterworthHighPass',
    'tau': 'TauLowPass',
}

_FILTER_GROUPS = [
    ('FILT1', [1, 2, 3, 4]),
    ('FILT2', [5, 6, 7, 12]),
    ('FILT3', [8, 9, 10, 11]),
]

_SEL_ITEMS = ['RAW', 'FILT1', 'FILT2', 'FILT3']


def _hex_digit(n):
    if n < 10:
        return str(n)
    return chr(ord('A') + n - 10)


def _clamp(v, lo, hi):
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _sample_hz(sample_ms):
    if sample_ms <= 0:
        return 1000.0
    return 1000.0 / float(sample_ms)


def _default_filter_cfg(sample_ms):
    fs = _sample_hz(sample_ms)
    nyq = max(1.0, fs * 0.5 - 0.01)
    lpf_fc = _clamp(fs * 0.10, 1.0, nyq * 0.95)
    hpf_fc = _clamp(fs * 0.02, 0.5, nyq * 0.95)
    return {
        'ema_alpha': 0.20,
        'mv_n': 8,
        'med_n': 5,
        'rms_n': 8,
        'kal_q': 0.01,
        'kal_r': 0.10,
        'k1d_q': 4.0,
        'k1d_r': 25.0,
        'adp_a_min': 0.01,
        'adp_a_max': 0.90,
        'adp_th': 50.0,
        'lpf_fc': lpf_fc,
        'hpf_fc': hpf_fc,
        'bwl_fc': lpf_fc,
        'bwh_fc': hpf_fc,
        'tau_s': 0.05,
    }


def _clamp_filter_cfg(cfg, sample_ms):
    fs = _sample_hz(sample_ms)
    nyq = max(1.0, fs * 0.5 - 0.01)
    cfg['ema_alpha'] = _clamp(cfg['ema_alpha'], 0.01, 1.0)
    cfg['mv_n'] = int(_clamp(int(cfg['mv_n']), 1, 64))
    cfg['med_n'] = int(_clamp(int(cfg['med_n']), 1, 31))
    cfg['rms_n'] = int(_clamp(int(cfg['rms_n']), 1, 64))
    cfg['kal_q'] = _clamp(cfg['kal_q'], 0.0001, 10.0)
    cfg['kal_r'] = _clamp(cfg['kal_r'], 0.001, 100.0)
    cfg['k1d_q'] = _clamp(cfg['k1d_q'], 0.0, 100.0)
    cfg['k1d_r'] = _clamp(cfg['k1d_r'], 0.001, 1000.0)
    cfg['adp_a_min'] = _clamp(cfg['adp_a_min'], 0.001, 0.99)
    cfg['adp_a_max'] = _clamp(cfg['adp_a_max'], cfg['adp_a_min'] + 0.001, 1.0)
    cfg['adp_th'] = _clamp(cfg['adp_th'], 0.0, 65535.0)
    cfg['lpf_fc'] = _clamp(cfg['lpf_fc'], 1.0, nyq * 0.95)
    cfg['hpf_fc'] = _clamp(cfg['hpf_fc'], 0.5, nyq * 0.95)
    cfg['bwl_fc'] = _clamp(cfg['bwl_fc'], 1.0, nyq * 0.95)
    cfg['bwh_fc'] = _clamp(cfg['bwh_fc'], 0.5, nyq * 0.95)
    cfg['tau_s'] = _clamp(cfg['tau_s'], 0.001, 5.0)
    return cfg


def _filter_param_specs(name, sample_ms):
    fs = _sample_hz(sample_ms)
    nyq = max(1.0, fs * 0.5 - 0.01)
    if name == 'ema':
        return [('ema_alpha', 'a', 0.01, 1.0, 0.01, False)]
    if name == 'mv':
        return [('mv_n', 'n', 1, 64, 1, True)]
    if name == 'med':
        return [('med_n', 'n', 1, 31, 1, True)]
    if name == 'rms':
        return [('rms_n', 'n', 1, 64, 1, True)]
    if name == 'kalman':
        return [('kal_q', 'q', 0.0001, 10.0, 0.01, False), ('kal_r', 'r', 0.001, 100.0, 0.1, False)]
    if name == 'kalman1d':
        return [('k1d_q', 'q', 0.0, 100.0, 0.5, False), ('k1d_r', 'r', 0.001, 1000.0, 1.0, False)]
    if name == 'adaptive':
        return [('adp_a_min', 'amin', 0.001, 0.99, 0.01, False), ('adp_a_max', 'amax', 0.01, 1.0, 0.01, False), ('adp_th', 'th', 0.0, 65535.0, 1.0, False)]
    if name == 'lpf':
        return [('lpf_fc', 'fc', 1.0, nyq * 0.95, 1.0, False)]
    if name == 'hpf':
        return [('hpf_fc', 'fc', 0.5, nyq * 0.95, 0.5, False)]
    if name == 'bw_lpf':
        return [('bwl_fc', 'fc', 1.0, nyq * 0.95, 1.0, False)]
    if name == 'bw_hpf':
        return [('bwh_fc', 'fc', 0.5, nyq * 0.95, 0.5, False)]
    if name == 'tau':
        return [('tau_s', 'tau', 0.001, 5.0, 0.005, False)]
    return []


def _fmt_cfg_value(v, is_int=False):
    if is_int:
        return str(int(v))
    if v >= 100:
        return f"{v:.1f}"
    if v >= 10:
        return f"{v:.2f}"
    return f"{v:.3f}"


def _selected_filter_idx(focus_idx, group_slots):
    if focus_idx == 0:
        return 0
    if 1 <= focus_idx <= 3:
        grp = focus_idx - 1
        slot = group_slots[grp]
        return _FILTER_GROUPS[grp][1][slot]
    return 0


def _sanitize_channel_state(state, ch_idx):
    if state['ch_mode_idxs'][ch_idx] < 0 or state['ch_mode_idxs'][ch_idx] > 3:
        state['ch_mode_idxs'][ch_idx] = 0
    slots = state['ch_group_slots'][ch_idx]
    for grp, (_, items) in enumerate(_FILTER_GROUPS):
        if slots[grp] < 0 or slots[grp] >= len(items):
            slots[grp] = 0


def _step_focus(current_focus, step):
    return (current_focus + step) % 4


def _step_group_slot(focus_idx, current_slot, step):
    if not (1 <= focus_idx <= 3):
        return current_slot
    items = _FILTER_GROUPS[focus_idx - 1][1]
    return (current_slot + step) % len(items)


def _apply_visual_reset(sc, n):
    INF = float('inf')
    sc.reset()
    return [INF] * n, [-INF] * n


def _scope_header_text(sample_ms):
    sample_label = 'max' if sample_ms == 0 else f"{sample_ms}ms"
    return f"VRef: {_BOARD_VREF:.1f}V    Sample: {sample_label}"


def _get_channel_count_checked():
    n = len(_CHANNELS)
    if n < 1:
        raise ValueError('_CHANNELS must contain at least 1 channel')
    if n > _MAX_CHANNELS:
        raise ValueError(f'_CHANNELS supports up to {_MAX_CHANNELS} channels (current: {n})')
    return n


def _make_filter(name, sample_ms, cfg):
    fs = _sample_hz(sample_ms)
    if name == 'ema':
        from ufilter import Alpha
        return Alpha(cfg['ema_alpha'], 0)
    if name == 'mv':
        from ufilter import MovingAverage
        return MovingAverage(cfg['mv_n'], 0)
    if name == 'med':
        from ufilter import Median
        return Median(cfg['med_n'], 0)
    if name == 'rms':
        from ufilter import RMS
        return RMS(cfg['rms_n'])
    if name == 'kalman':
        from ufilter import Kalman
        return Kalman(process_noise=cfg['kal_q'], measurement_noise=cfg['kal_r'])
    if name == 'kalman1d':
        from ufilter import Kalman1D
        return Kalman1D(R=cfg['k1d_r'], Q=cfg['k1d_q'])
    if name == 'adaptive':
        from ufilter import Adaptive
        return Adaptive(alpha_min=cfg['adp_a_min'], alpha_max=cfg['adp_a_max'], threshold=cfg['adp_th'])
    if name == 'lpf':
        from ufilter import LowPass
        return LowPass(cfg['lpf_fc'], fs, 0)
    if name == 'hpf':
        from ufilter import HighPass
        return HighPass(cfg['hpf_fc'], fs, 0)
    if name == 'bw_lpf':
        from ufilter import Butterworth
        return Butterworth(cfg['bwl_fc'], fs, 'lowpass')
    if name == 'bw_hpf':
        from ufilter import Butterworth
        return Butterworth(cfg['bwh_fc'], fs, 'highpass')
    if name == 'tau':
        from ufilter import TauLowPass
        return TauLowPass(cfg['tau_s'], 0, fs=fs)
    return None


def _poll_key():
    r, _, _ = _sel.select([sys.stdin], [], [], 0)
    if r:
        ch = sys.stdin.read(1)
        if ch != '\x1b':
            return ch
        r2, _, _ = _sel.select([sys.stdin], [], [], 0.002)
        if not r2:
            return ch
        ch2 = sys.stdin.read(1)
        if ch2 != '[':
            return ch
        r3, _, _ = _sel.select([sys.stdin], [], [], 0.002)
        if not r3:
            return ch
        ch3 = sys.stdin.read(1)
        if ch3 == 'A':
            return 'UP'
        if ch3 == 'B':
            return 'DOWN'
        if ch3 == 'C':
            return 'RIGHT'
        if ch3 == 'D':
            return 'LEFT'
        return ch
    return None


def _resolve_vref(vref):
    if vref == 'auto':
        return _BOARD_VREF
    if isinstance(vref, (int, float)) and float(vref) > 0:
        return float(vref)
    return None


def _ch_label(ch):
    return f"GP{ch['pin']}"


def _ch_unit(_ch):
    return 'V'


def _ch_yrange(ch):
    vref = _resolve_vref(ch.get('vref'))
    return (0.0, vref) if vref is not None else (0.0, 65535.0)


def _ch_scale(ch):
    vref = _resolve_vref(ch.get('vref'))
    return (vref / 65535.0) if vref is not None else 1.0


def _ch_color_ansi(index):
    r, g, b = _SCOPE_PALETTE[index % len(_SCOPE_PALETTE)]
    return Term.rgb(r, g, b)


def _filter_is_signed_idx(idx):
    name = _FILTER_ITEMS[idx][0]
    return name in ('hpf', 'bw_hpf')


def _scope_trace_colors(state):
    return [_SCOPE_PALETTE[i % len(_SCOPE_PALETTE)] for i in range(len(_CHANNELS))]


def _scope_trace_values(state):
    return list(state['vals_disp'])


def _scope_view_config(state):
    n = len(_CHANNELS)
    if n > 1:
        return (0.0, 1.0, [0.0, 0.5, 1.0], ['0', '0.5', '1'], 'norm')

    ch0 = _CHANNELS[0]
    vref = _resolve_vref(ch0.get('vref'))
    effective_idx = state['channel_filter_effective_idxs'][0]
    if vref is not None and _filter_is_signed_idx(effective_idx):
        return (-vref, vref, [-vref, 0.0, vref], [f"-{vref:.1f}", '0', f"{vref:.1f}"], 'V')

    ymin, ymax = _ch_yrange(ch0)
    if vref is None:
        return (ymin, ymax, [0, 32768, 65535], ['0', '32k', '65k'], 'raw')
    mid = round(vref / 2.0, 2)
    return (ymin, ymax, [0.0, mid, vref], ['0', f"{mid:.2f}", f"{vref:.1f}"], 'V')


def _scope_reconfigure_if_needed(state, sc):
    colors = _scope_trace_colors(state)
    ymin, ymax, ytick_vals, ytick_labels, ylabel = _scope_view_config(state)
    sig = (tuple(colors), ymin, ymax, tuple(ytick_vals), tuple(ytick_labels), ylabel)
    if state.get('trace_sig') != sig:
        state['trace_sig'] = sig
        sc._colors_user = list(colors)
        sc.ax._ylabel = None
        sc.ax.yticks(ytick_vals, [''] * len(ytick_vals))
        sc.show_zero = ymin < 0.0 < ymax
        sc.set_range(ymin, ymax)
        sc._nch = 0
        sc._ensure_channels(len(colors))
        sc.reset()


def _scope_right_axis_labels(ylabel, labels):
    out = list(labels)
    if ylabel == 'V' and len(out) == 3:
        out[1] = f"{out[1]}V"
    return out


def _write_plot_axis_labels(w, ax, ytick_vals, ytick_labels, ylabel):
    right_col = ((ax.vx + ax.vw - 1) >> 1) + 2
    labels = _scope_right_axis_labels(ylabel, ytick_labels)
    for i, v in enumerate(ytick_vals):
        py = ax._wy(v)
        row = py >> 2
        if row < 0:
            continue
        label = labels[i] if i < len(labels) else ''
        w(
            Term.cursor_save() +
            Term.cursor_to(row + 1, right_col + 1) +
            Term.rgb(210, 210, 210) +
            f"{label:<8}" +
            Term.RESET +
            Term.cursor_restore()
        )


def _fmt_val(v, unit):
    if unit == 'V':
        return f"{v:.3f}"
    return f"{int(v):5}"


def _write_statsbar(w, row, label, filt_abbr, v_cur, v_min, v_max, unit, label_color=None):
    vpp = v_max - v_min
    clr = Term.rgb(255, 255, 180)
    cur_s = _fmt_val(v_cur, unit)
    min_s = _fmt_val(v_min, unit)
    max_s = _fmt_val(v_max, unit)
    vpp_s = _fmt_val(vpp, unit)
    w(
        Term.cursor_save() +
        Term.cursor_to(row, 1) +
        (label_color if label_color is not None else Term.FG.MUTED) + f" {label:<8}" +
        Term.FG.MUTED + f" {filt_abbr:<4} " +
        clr + f"Now:{cur_s}{unit}" +
        Term.FG.MUTED + f"  Min:{min_s}{unit}  Max:{max_s}{unit}  Vpp:{vpp_s}{unit}" +
        Term.RESET +
        Term.cursor_restore()
    )


def _write_helpbar(w, filt_idx, sample_ms, sample_idx, focus_idx, active_ch, menu_on, menu_mode, menu_idx, cfg, error_text=None, row=None):
    if row is None:
        row = _HELP_ROW
    filt_name, filt_abbr = _FILTER_ITEMS[filt_idx]
    filt_key = _hex_digit(filt_idx)
    sample_label = 'max' if sample_ms == 0 else f"{sample_ms}ms"
    active_color = _ch_color_ansi(active_ch)
    sample_parts = []
    for i, ms in enumerate(_SAMPLE_TABLE):
        label = 'max' if ms == 0 else f"{ms}"
        if i == sample_idx:
            sample_parts.append(Term.FG.PRIMARY + Term.BOLD + f"[{label}]" + Term.RESET)
        else:
            sample_parts.append(Term.FG.MUTED + label + Term.RESET)
    sample_line = Term.FG.MUTED + ' SAMP ' + Term.RESET + ' '.join(sample_parts)
    if len(_CHANNELS) > 1:
        sample_line += '    ' + Term.FG.MUTED + '[1/2/3]Ch [LF/RG]Sample [ENTER]Filter' + Term.RESET
    else:
        sample_line += '    ' + Term.FG.MUTED + '[LF/RG]Sample [ENTER]Filter' + Term.RESET
    sel_parts = []
    for i, name in enumerate(_SEL_ITEMS):
        if i == focus_idx:
            sel_parts.append(active_color + Term.BOLD + name + Term.RESET)
        else:
            sel_parts.append(Term.FG.MUTED + name + Term.RESET)
    sel_text = '/'.join(sel_parts)
    filt_full = _FILTER_FULL_NAMES.get(filt_name, filt_name)
    line1 = active_color + ' SEL:' + Term.RESET + sel_text + '  ' + f"F:{filt_key} {filt_abbr}  " + f"S:{sample_label}  " + active_color + Term.BOLD + f"{filt_full}" + Term.RESET
    specs = _filter_param_specs(filt_name, _INTERNAL_SAMPLE_MS)
    if menu_on:
        if menu_mode == 'filt':
            if not specs:
                line2 = Term.FG.MUTED + ' MENU: no params for this filter  [ESC]back' + Term.RESET
            else:
                parts = []
                for i, (key, label, _, _, _, is_int) in enumerate(specs):
                    val_s = _fmt_cfg_value(cfg[key], is_int)
                    text = f"{label}={val_s}"
                    if i == menu_idx:
                        parts.append(Term.FG.PRIMARY + Term.BOLD + f"[{text}]" + Term.RESET)
                    else:
                        parts.append(Term.FG.MUTED + text + Term.RESET)
                line2 = ' MENU ' + '  '.join(parts) + '   ' + Term.FG.MUTED + '[LF/RG]edit [ESC]back' + Term.RESET
        else:
            line2 = Term.FG.MUTED + ' [UP/DN]SEL [LF/RG]change  Edit: ENTER  Close: ESC ' + Term.RESET
    else:
        line1 = ''
        line2 = ''
    ctrl_row = row + 1
    extra_row = row + 2
    row_text = line1 if menu_on else sample_line
    ctrl_text = line2 if menu_on else ''
    extra_text = ''
    if error_text:
        extra_text = Term.FG.WARNING + error_text + Term.RESET
    w(Term.cursor_save() + Term.cursor_to(row, 1) + row_text + ' ' * 80 + Term.cursor_to(ctrl_row, 1) + ctrl_text + ' ' * 80 + Term.cursor_to(extra_row, 1) + extra_text + ' ' * 80 + Term.cursor_restore())


def _make_scope_plot(ymin, ymax, ytick_vals, ytick_labels, header_text, ylabel):
    W = _CV_COLS * 2
    H = _CV_ROWS * 4
    rl, rt, rr, rb = _REGION
    cv = Canvas(_CV_COLS, _CV_ROWS)
    ax = Plot(cv, region_px=(rl, rt, W - rl - rr, H - rt - rb), xlim=(0, W), ylim=(ymin, ymax), color_cycle=_SCOPE_PALETTE)
    ax.title(header_text, color=(180, 220, 180))
    ax.ylabel(None)
    ax.xlabel('← sample via keys →', color=(170, 170, 170))
    ax.yticks(ytick_vals, [''] * len(ytick_vals))
    ax.grid(True)
    sc = Scope(ax, vmin=ymin, vmax=ymax, colors=_SCOPE_PALETTE, px_step=2, show_zero=False)
    ax._legend_on = False
    ax.clear_legend_items()
    ax._ylabel = None
    sc._grid_y_py = set()
    return cv, ax, sc


def _find_sample_idx(sample_ms):
    for i, ms in enumerate(_SAMPLE_TABLE):
        if ms == sample_ms:
            return i
    return 0


def _make_scope_samplers():
    return [ADC(Pin(ch['pin'])) for ch in _CHANNELS]


def _get_scope_plot_config():
    n = len(_CHANNELS)
    multi = n > 1
    if multi:
        return multi, 0.0, 1.0, [0.0, 0.5, 1.0], ['0', '0.5', '1'], 'norm'
    ch0 = _CHANNELS[0]
    ymin, ymax = _ch_yrange(ch0)
    vref = _resolve_vref(ch0.get('vref'))
    if vref is None:
        return multi, ymin, ymax, [0, 32768, 65535], ['0', '32k', '65k'], 'raw'
    mid = round(vref / 2.0, 2)
    return multi, ymin, ymax, [0.0, mid, vref], ['0', f"{mid:.2f}", f"{vref:.1f}"], 'V'


def _init_scope_state(n):
    sample_idx = _find_sample_idx(_SAMPLE_MS)
    now = time.ticks_ms()
    return {
        'active_ch': 0,
        'ch_group_slots': [[0, 0, 0] for _ in _CHANNELS],
        'ch_mode_idxs': [0] * n,
        'focus_idx': 0,
        'filt_idx': 0,
        'sample_idx': sample_idx,
        'render_ms': _SAMPLE_TABLE[sample_idx],
        'menu_on': False,
        'menu_mode': 'top',
        'menu_idx': 0,
        'filter_cfg': _clamp_filter_cfg(_default_filter_cfg(_INTERNAL_SAMPLE_MS), _INTERNAL_SAMPLE_MS),
        'channel_filter_idxs': [0] * n,
        'channel_filter_effective_idxs': [0] * n,
        'channel_filter_errors': [None] * n,
        'v_mins': [float('inf')] * n,
        'v_maxs': [-float('inf')] * n,
        'vals_raw_actual': [0.0] * n,
        'vals_raw_disp': [0.0] * n,
        'vals_disp': [0.0] * n,
        'vals_actual': [0.0] * n,
        'trace_sig': None,
        'next_sample_at': now,
        'next_render_at': now,
    }


def _refresh_channel_filter_idx(state, ch_idx):
    _sanitize_channel_state(state, ch_idx)
    state['channel_filter_idxs'][ch_idx] = _selected_filter_idx(state['ch_mode_idxs'][ch_idx], state['ch_group_slots'][ch_idx])


def _sync_active_channel_state(state):
    active_ch = state['active_ch']
    _sanitize_channel_state(state, active_ch)
    state['focus_idx'] = state['ch_mode_idxs'][active_ch]
    state['filt_idx'] = state['channel_filter_idxs'][active_ch]


def _rebuild_filters(state, n):
    filters = []
    for i in range(n):
        desired_idx = state['channel_filter_idxs'][i]
        name = _FILTER_ITEMS[desired_idx][0]
        state['channel_filter_errors'][i] = None
        state['channel_filter_effective_idxs'][i] = desired_idx
        if desired_idx == 0:
            filters.append(None)
            continue
        try:
            filt = _make_filter(name, _INTERNAL_SAMPLE_MS, state['filter_cfg'])
            if filt is None:
                state['channel_filter_effective_idxs'][i] = 0
                state['channel_filter_errors'][i] = f"{_FILTER_ITEMS[desired_idx][1]} unavailable; using RAW"
                filters.append(None)
            else:
                filters.append(filt)
        except Exception as e:
            state['channel_filter_effective_idxs'][i] = 0
            state['channel_filter_errors'][i] = f"{_FILTER_ITEMS[desired_idx][1]} failed: {e}"
            filters.append(None)
    return filters


def _reset_scope_runtime(state, sc, n, reset_timers=False):
    state['v_mins'], state['v_maxs'] = _apply_visual_reset(sc, n)
    state['trace_sig'] = None
    if reset_timers:
        now = time.ticks_ms()
        state['next_sample_at'] = now
        state['next_render_at'] = now


def _set_render_sample(state, sample_idx, ax):
    state['sample_idx'] = sample_idx
    state['render_ms'] = _SAMPLE_TABLE[sample_idx]
    ax.title(_scope_header_text(state['render_ms']), color=(180, 220, 180))
    state['next_render_at'] = time.ticks_ms()


def _write_scope_ui(w, state, help_row):
    err = state['channel_filter_errors'][state['active_ch']]
    _write_helpbar(w, state['filt_idx'], state['render_ms'], state['sample_idx'], state['focus_idx'], state['active_ch'], state['menu_on'], state['menu_mode'], state['menu_idx'], state['filter_cfg'], err, help_row)


def _sample_scope_once(state, samplers, filts, multi):
    vals_raw_disp = []
    vals_raw_actual = []
    vals_disp = []
    vals_actual = []
    for i, sampler in enumerate(samplers):
        ch = _CHANNELS[i]
        raw = float(sampler.read_u16())
        filt = filts[i]
        v_raw_actual = raw * _ch_scale(ch)
        raw_f = filt.update(raw) if filt is not None else raw
        v_actual = raw_f * _ch_scale(ch)
        vals_raw_actual.append(v_raw_actual)
        vals_actual.append(v_actual)
        if v_actual < state['v_mins'][i]:
            state['v_mins'][i] = v_actual
        if v_actual > state['v_maxs'][i]:
            state['v_maxs'][i] = v_actual
        if multi:
            yr = _ch_yrange(ch)
            span = yr[1] - yr[0]
            vals_raw_disp.append((v_raw_actual - yr[0]) / span if span > 0 else 0.0)
            vals_disp.append((v_actual - yr[0]) / span if span > 0 else 0.0)
        else:
            vals_raw_disp.append(v_raw_actual)
            vals_disp.append(v_actual)
    state['vals_raw_actual'] = vals_raw_actual
    state['vals_raw_disp'] = vals_raw_disp
    state['vals_disp'] = vals_disp
    state['vals_actual'] = vals_actual


def _render_scope_once(state, w, sc, ch_names):
    _scope_reconfigure_if_needed(state, sc)
    _, _, ytick_vals, ytick_labels, ylabel = _scope_view_config(state)
    _write_plot_axis_labels(w, sc.ax, ytick_vals, ytick_labels, ylabel)
    n = len(_CHANNELS)
    if n == 1:
        label = f"[{ch_names[0]}]" if state['active_ch'] == 0 else ch_names[0]
        filt_abbr = _FILTER_ITEMS[state['channel_filter_effective_idxs'][0]][1]
        if state['channel_filter_errors'][0]:
            filt_abbr += '!'
        _write_statsbar(w, _STATS_ROW, label, filt_abbr, state['vals_actual'][0], state['v_mins'][0], state['v_maxs'][0], _ch_unit(_CHANNELS[0]), label_color=_ch_color_ansi(0))
    else:
        for i in range(n):
            label = f"[{ch_names[i]}]" if i == state['active_ch'] else ch_names[i]
            filt_abbr = _FILTER_ITEMS[state['channel_filter_effective_idxs'][i]][1]
            if state['channel_filter_errors'][i]:
                filt_abbr += '!'
            _write_statsbar(w, _STATS_ROW + i, label, filt_abbr, state['vals_actual'][i], state['v_mins'][i], state['v_maxs'][i], _ch_unit(_CHANNELS[i]), label_color=_ch_color_ansi(i))
    sc.tick(_scope_trace_values(state))


def _handle_scope_key(key, state, ax, sc, n, filts):
    changed = False
    if not state['menu_on']:
        if key in ('1', '2', '3'):
            new_active = ord(key) - ord('1')
            if new_active >= n:
                return False, filts
            if new_active != state['active_ch']:
                state['active_ch'] = new_active
                _sync_active_channel_state(state)
                _reset_scope_runtime(state, sc, n)
            changed = True
        elif key in ('LEFT', 'RIGHT'):
            step = -1 if key == 'LEFT' else 1
            new_sample_idx = _clamp(state['sample_idx'] + step, 0, len(_SAMPLE_TABLE) - 1)
            if new_sample_idx != state['sample_idx']:
                _set_render_sample(state, new_sample_idx, ax)
            changed = True
        elif key in ('\r', '\n'):
            state['menu_on'] = True
            state['menu_mode'] = 'top'
            state['menu_idx'] = 0
            _sync_active_channel_state(state)
            changed = True
        return changed, filts
    if key == '\x1b':
        if state['menu_mode'] == 'top':
            state['menu_on'] = False
        else:
            state['menu_mode'] = 'top'
            state['menu_idx'] = 0
        return True, filts
    if state['menu_mode'] == 'top':
        if key in ('UP', 'DOWN'):
            step = -1 if key == 'UP' else 1
            new_focus_idx = _step_focus(state['focus_idx'], step)
            if new_focus_idx != state['focus_idx']:
                state['focus_idx'] = new_focus_idx
                state['ch_mode_idxs'][state['active_ch']] = new_focus_idx
                _refresh_channel_filter_idx(state, state['active_ch'])
                _sync_active_channel_state(state)
                filts = _rebuild_filters(state, n)
                _reset_scope_runtime(state, sc, n)
            changed = True
        elif key in ('LEFT', 'RIGHT'):
            if 1 <= state['focus_idx'] <= 3:
                step = -1 if key == 'LEFT' else 1
                grp = state['focus_idx'] - 1
                slots = state['ch_group_slots'][state['active_ch']]
                slots[grp] = _step_group_slot(state['focus_idx'], slots[grp], step)
                _refresh_channel_filter_idx(state, state['active_ch'])
                _sync_active_channel_state(state)
                filts = _rebuild_filters(state, n)
                _reset_scope_runtime(state, sc, n, reset_timers=True)
                state['menu_idx'] = 0
            changed = True
        elif key in ('\r', '\n'):
            if 1 <= state['focus_idx'] <= 3:
                state['menu_mode'] = 'filt'
                state['menu_idx'] = 0
            changed = True
        return changed, filts
    cur_name = _FILTER_ITEMS[state['filt_idx']][0]
    specs = _filter_param_specs(cur_name, _INTERNAL_SAMPLE_MS)
    if specs:
        if key in ('UP', 'DOWN'):
            step = -1 if key == 'UP' else 1
            state['menu_idx'] = (state['menu_idx'] + step) % len(specs)
            changed = True
        elif key in ('LEFT', 'RIGHT'):
            step = -1 if key == 'LEFT' else 1
            k, _, lo, hi, inc, is_int = specs[state['menu_idx']]
            v = state['filter_cfg'][k] + (inc * step)
            v = _clamp(v, lo, hi)
            if is_int:
                v = int(round(v))
            state['filter_cfg'][k] = v
            state['filter_cfg'] = _clamp_filter_cfg(state['filter_cfg'], _INTERNAL_SAMPLE_MS)
            filts = _rebuild_filters(state, n)
            _reset_scope_runtime(state, sc, n, reset_timers=True)
            changed = True
    return changed, filts


def main():
    try:
        n = _get_channel_count_checked()
    except ValueError as e:
        sys.stdout.write(Term.FG.DANGER + f"  {e}\n" + Term.RESET)
        return
    multi = n > 1
    samplers = _make_scope_samplers()
    ch_names = [_ch_label(ch) for ch in _CHANNELS]
    multi, ymin, ymax, ytick_vals, ytick_labels, ylabel = _get_scope_plot_config()
    cv, ax, sc = _make_scope_plot(ymin, ymax, ytick_vals, ytick_labels, _scope_header_text(_SAMPLE_MS), ylabel)
    w = sys.stdout.write
    help_row = _STATS_ROW + n
    state = _init_scope_state(n)
    for i in range(n):
        _refresh_channel_filter_idx(state, i)
    _sync_active_channel_state(state)
    filts = _rebuild_filters(state, n)
    _write_scope_ui(w, state, help_row)
    try:
        while True:
            key = _poll_key()
            changed, filts = _handle_scope_key(key, state, ax, sc, n, filts)
            if changed:
                _write_scope_ui(w, state, help_row)
            now = time.ticks_ms()
            sample_loops = 0
            while time.ticks_diff(now, state['next_sample_at']) >= 0 and sample_loops < 32:
                _sample_scope_once(state, samplers, filts, multi)
                state['next_sample_at'] = time.ticks_add(state['next_sample_at'], _INTERNAL_SAMPLE_MS)
                sample_loops += 1
                now = time.ticks_ms()
            render_due = changed or state['render_ms'] == 0 or time.ticks_diff(now, state['next_render_at']) >= 0
            if render_due:
                _render_scope_once(state, w, sc, ch_names)
                if state['render_ms'] > 0 and time.ticks_diff(now, state['next_render_at']) >= 0:
                    state['next_render_at'] = time.ticks_add(state['next_render_at'], state['render_ms'])
                    if time.ticks_diff(now, state['next_render_at']) >= 0:
                        state['next_render_at'] = time.ticks_add(now, state['render_ms'])
            if sample_loops == 0 and not render_due and _INTERNAL_SAMPLE_MS > 0:
                time.sleep_ms(1)
    except KeyboardInterrupt:
        pass
    finally:
        cv.end()

main()
'''


def _build_scope_script(pins: list[int], sample_ms: int, vref: float) -> str:
    channels = [{'pin': pin, 'type': 'adc', 'vref': float(vref)} for pin in pins]
    return (
        _SCOPE_TEMPLATE
        .replace('__CHANNELS__', repr(channels))
        .replace('__SAMPLE_MS__', str(int(sample_ms)))
        .replace('__BOARD_VREF__', repr(float(vref)))
    )


def _print_adc_help() -> None:
    help_text = """\
ADC read/scope command for board analog inputs.

[bold cyan]Usage:[/bold cyan]
  replx adc [yellow]SUBCOMMAND[/yellow] ...

[bold cyan]Subcommands:[/bold cyan]
  [green]read[/green]   Read one or more ADC pins.
  [green]scope[/green]  Run the board-side ADC scope UI.

[bold cyan]Pin Format:[/bold cyan]
  [yellow]GP<num>[/yellow], [yellow]GPIO<num>[/yellow], or numeric GPIO id.
  Standard boards: up to [cyan]3[/cyan] channels.
  XBee3: read D0..D3 as native ADC counts; no --vref conversion or scope.

[bold cyan]Read:[/bold cyan]
  replx adc read [yellow]GP<num>[/yellow]... [green]--repeat N[/green] [green]--interval MS[/green] [green]--vref V[/green]

[bold cyan]Scope:[/bold cyan]
  replx adc scope [[yellow]GP<num>[/yellow]...]

  [dim]RP2 only: defaults to GP26 GP27 GP28. Other boards require explicit pins.[/dim]
  [dim]Interactive keys:[/dim]
    [cyan]1/2/3[/cyan]      select active channel [dim](when 2+ channels)[/dim]
    [cyan]LEFT/RIGHT[/cyan] sample rate or selected item change
    [cyan]ENTER[/cyan]      open filter parameter editor
    [cyan]ESC[/cyan]        back/close menu
    [cyan]Ctrl+C[/cyan]     exit scope

[bold cyan]Options:[/bold cyan]
  [yellow]--repeat N[/yellow]        Repeat count for adc read [dim](0=infinite, default: 1)[/dim]
  [yellow]--interval MS[/yellow]     Delay between repeated reads [dim](default: 1000)[/dim]
  [yellow]--vref V[/yellow]          ADC reference voltage [dim](default: 3.3)[/dim]
  [yellow]--sample MS[/yellow]       Initial scope render rate [dim](0,1,2,5,10,20,50,100 · default: 10)[/dim]

[bold cyan]Examples:[/bold cyan]
  replx COM3 adc read GP26
  replx COM3 adc read GP26 GP27 GP28 --repeat 5 --interval 200
  replx COM3 adc read GP26 --vref 3.3
  replx COM3 adc scope
  replx COM3 adc scope GP26
  replx COM3 adc scope GP26 GP27 --sample 20

[bold cyan]Notes:[/bold cyan]
  • [green]scope[/green] requires [yellow]termviz[/yellow] and [yellow]ufilter[/yellow] on the board.
  • Scope sampling runs internally at high rate; [yellow]SAMP[/yellow] controls render refresh.
  • Multi-channel scope normalizes each channel to its own 0..Vref range."""
    OutputHelper.print_panel(help_text, title="adc", border_style="help")


_ADC_D   = '\033[38;2;150;150;150m'
_ADC_C   = '\033[38;2;80;200;255m'
_ADC_G   = '\033[38;2;80;255;120m'
_ADC_RST = '\033[0m'


def _setup_adc_scroll_screen(header: str, sep_w: int) -> None:
    enable_vt_mode()
    _, rows = shutil.get_terminal_size(fallback=(80, 24))
    w = sys.stdout.buffer.write
    w(b'\033[?1049h')
    w(b'\033[2J\033[H\033[?25l')
    w((header + '\n').encode())
    w(('  ' + '\u2500' * sep_w + '\n').encode())
    w(f'\033[3;{rows}r\033[3;1H'.encode())
    sys.stdout.buffer.flush()


def _teardown_adc_scroll_screen() -> None:
    try:
        w = sys.stdout.buffer.write
        w(b'\033[r\033[?25h')
        w(b'\033[?1049l')
        sys.stdout.buffer.flush()
    finally:
        restore_vt_mode()


def _run_adc_stream(client, code: str, on_line) -> None:
    from .gpio import _run_repeat_interactive
    _run_repeat_interactive(client, code, on_line, ctrl_c_grace_s=1.5)


def _subcmd_read(client, pos_args: list[str], repeat: int, interval: int, vref: float) -> None:
    pins = _parse_gp_pins(pos_args)
    _validate_adc_pins(client, pins)
    if repeat < 0:
        raise ValueError("--repeat must be >= 0")
    if interval < 0:
        raise ValueError("--interval must be >= 0")
    if vref <= 0:
        raise ValueError("--vref must be > 0")

    if repeat == 1:
        raw = _exec(client, _adc_read_code(pins, 1, 0), timeout=3.0)
        samples = [_parse_json_strict(raw)]
        body = _format_read_rows(pins, samples, vref)
        OutputHelper.print_panel(body, title="ADC Read", border_style="data")
        return

    code = _adc_read_code(pins, repeat, interval)
    n_ch = len(pins)
    sep_width = 14 + n_ch * 19 + (n_ch - 1) * 7

    def fmt_ch_col(pin, raw):
        volt = _raw_to_volts(raw, vref)
        return (
            _ADC_D + f'GP{pin:<2}' + _ADC_RST
            + '  ' + _ADC_C + f'{raw:5d}' + _ADC_RST
            + '  ' + _ADC_G + f'{volt:5.3f}V' + _ADC_RST
        )

    pins_str = '  '.join(f'GP{p}' for p in pins)
    repeat_str = '\u221e' if repeat == 0 else f'\u00d7{repeat}'
    hint = 'Ctrl+C exit' if repeat == 0 else 'Ctrl+C cancel'
    hdr = (
        f'  {_ADC_D}ADC Read{_ADC_RST}  {pins_str}  {repeat_str}  '
        f'interval={interval} ms  {_ADC_D}[{hint}]{_ADC_RST}'
    )
    _setup_adc_scroll_screen(hdr, sep_width)

    start_t = time.monotonic()
    counter = [0]

    def on_line(json_str):
        try:
            raw_vals = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return
        counter[0] += 1
        s = int(time.monotonic() - start_t)
        ts = f'{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}'
        ch_sep = '   ' + _ADC_D + '\u2502' + _ADC_RST + '   '
        cols = ch_sep.join(fmt_ch_col(p, r) for p, r in zip(pins, raw_vals))
        sys.stdout.write(f'  {_ADC_D}{ts}{_ADC_RST}    {cols}\n')
        sys.stdout.flush()

    try:
        _run_adc_stream(client, code, on_line)
    except KeyboardInterrupt:
        pass
    finally:
        _teardown_adc_scroll_screen()
    total = counter[0]
    done_msg = f'Stopped: {total} samples' if repeat == 0 else f'Done: {total}/{repeat} samples'
    sys.stdout.write(f'  {done_msg}\n')
    sys.stdout.flush()


def _subcmd_scope(client, pos_args: list[str], sample: int, vref: float) -> None:
    if not pos_args and not get_core(client, None).upper().startswith(('RP2350', 'RP2040')):
        raise ValueError("Specify ADC-capable pins on this board; GP26/27/28 defaults are RP2-only")
    pins = _parse_gp_pins(pos_args, allow_empty=True, default_pins=_DEFAULT_SCOPE_PINS)
    _validate_adc_pins(client, pins)
    if sample not in _SAMPLE_TABLE:
        raise ValueError("--sample must be one of: 0, 1, 2, 5, 10, 20, 50, 100")
    if vref <= 0:
        raise ValueError("--vref must be > 0")

    _preflight_scope_libs(client)
    code = _build_scope_script(pins, sample, vref)

    OutputHelper.print_panel(
        "Channels: " + ', '.join(f"GP{pin}" for pin in pins) + "\n"
        "Controls: 1/2/3 select channel, LEFT/RIGHT change, ENTER edit, ESC back, Ctrl+C exit",
        title="ADC Scope",
        border_style="mode",
    )

    from .exec import _run_interactive_mode
    _run_interactive_mode(client, code, None, False)


def _make_xbee_read_code(tokens: list[str], repeat: int, interval: int) -> str:
    pins = [parse_hardware_pin(token, 'ADC pin') for token in tokens]
    if not pins or any(pin not in ('D0', 'D1', 'D2', 'D3') for pin in pins):
        raise ValueError("XBee3 ADC read requires pins D0..D3")
    if len(set(pins)) != len(pins) or repeat < 0 or interval < 0:
        raise ValueError("ADC pins must be distinct; --repeat and --interval must be >= 0")
    loop = "while True:" if repeat == 0 else f"for _ in range({repeat}):"
    return (
        "from machine import ADC\nimport time,json\n"
        f"adcs=[ADC(p) for p in {pins!r}]\n"
        f"{loop}\n print(json.dumps([a.read() for a in adcs]))\n"
        + (f" time.sleep_ms({interval})\n" if interval else "")
    )


def _subcmd_xbee_read(client, tokens: list[str], repeat: int, interval: int) -> None:
    code = _make_xbee_read_code(tokens, repeat, interval)

    def show(raw):
        samples = _parse_json_strict(raw)
        OutputHelper.print_panel(
            '\n'.join(f"{pin.upper()}: raw={value}" for pin, value in zip(tokens, samples))
            + "\nNative ADC counts; no voltage conversion.",
            title="XBee3 ADC Read", border_style="data",
        )

    if repeat == 1:
        show(_exec(client, code, timeout=3.0))
    else:
        _run_adc_stream(client, code, show)


@app.command(name="adc", rich_help_panel="Hardware")
def adc_cmd(
    args: Optional[list[str]] = typer.Argument(None, help="Subcommand: read  scope"),
    repeat: int = typer.Option(1, "--repeat", metavar="N", help="Repeat count for adc read (0=infinite)"),
    interval: int = typer.Option(1000, "--interval-ms", "--interval", metavar="MS", help="Delay between repeated adc reads in ms"),
    vref: float = typer.Option(3.3, "--vref", metavar="V", help="ADC reference voltage"),
    sample: int = typer.Option(10, "--sample", metavar="MS", help="Initial scope render rate"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True),
):
    if show_help:
        _print_adc_help()
        raise typer.Exit()
    if not args:
        OutputHelper.print_panel(
            "Subcommands: [bright_blue]read[/bright_blue]  [bright_blue]scope[/bright_blue]\n\n"
            "  [bright_green]replx PORT adc read GP26[/bright_green]\n"
            "  [bright_green]replx PORT adc scope GP26 GP27 GP28[/bright_green]\n\n"
            "Use [bright_blue]replx adc --help[/bright_blue] for details.",
            title="ADC",
            border_style="help",
        )
        raise typer.Exit(1)

    subcmd = args[0].lower()
    pos_args = args[1:]

    if subcmd not in ('read', 'scope'):
        OutputHelper.print_panel(
            f"Unknown subcommand: {subcmd!r}\n\nValid subcommands: read  scope",
            title="ADC Error",
            border_style="error",
        )
        raise typer.Exit(1)

    try:
        _ensure_connected()
        with _create_agent_client() as client:
            if is_xbee(client):
                if subcmd != 'read':
                    raise ValueError("adc scope is not supported on XBee3; use adc read D0")
                if vref != 3.3:
                    raise ValueError("XBee3 ADC reports native counts; --vref conversion is not supported")
                _subcmd_xbee_read(client, pos_args, repeat, interval)
            elif subcmd == 'read':
                _subcmd_read(client, pos_args, repeat, interval, vref)
            else:
                _subcmd_scope(client, pos_args, sample, vref)
    except typer.Exit:
        raise
    except ValueError as e:
        OutputHelper.print_panel(str(e), title="ADC Error", border_style="error")
        raise typer.Exit(1)
    except RuntimeError as e:
        OutputHelper.print_panel(str(e), title="ADC Error", border_style="error")
        raise typer.Exit(1)
