import json
import math
import sys
import time
from typing import Optional

import typer

from ..app import app
from ..connection import _create_agent_client, _ensure_connected
from ..helpers import OutputHelper
from ._common import exec_code as _exec, parse_gp_pin, require_standard_hardware
from .adc import _run_adc_stream, _setup_adc_scroll_screen, _teardown_adc_scroll_screen

_SAMPLE_TABLE = (0, 1, 2, 5, 10, 20, 50, 100)
_I2S_D = '\033[38;2;150;150;150m'
_I2S_C = '\033[38;2;80;200;255m'
_I2S_G = '\033[38;2;80;255;120m'
_I2S_Y = '\033[38;2;255;220;80m'
_I2S_RST = '\033[0m'


def _parse_tone_tokens(tokens: list[str], rate: int) -> list[tuple[float, int]]:
    if not tokens or len(tokens) % 2:
        raise ValueError("tone requires FREQ m<DURATION> pairs, e.g. 440 m500")
    tones = []
    for index in range(0, len(tokens), 2):
        try:
            frequency = float(tokens[index])
        except ValueError:
            raise ValueError(f"Invalid frequency: {tokens[index]!r}")
        duration = tokens[index + 1].lower()
        if not duration.startswith('m') or not duration[1:].isdigit():
            raise ValueError(f"Invalid duration: {tokens[index + 1]!r}. Use m<N> milliseconds")
        duration_ms = int(duration[1:])
        if not math.isfinite(frequency) or frequency <= 0 or frequency >= rate / 2:
            raise ValueError(f"Frequency must be finite and between 0 and Nyquist ({rate / 2:g} Hz)")
        if duration_ms <= 0:
            raise ValueError("Tone duration must be > 0 ms")
        tones.append((frequency, duration_ms))
    return tones


def _parse_config(sck: Optional[str], ws: Optional[str], sd: Optional[str], i2s_id: int,
                  rate: int, ibuf: int) -> dict:
    if sck is None or ws is None or sd is None:
        raise ValueError("--sck, --ws, and --sd are required")
    pins = {
        'sck': parse_gp_pin(sck, 'I2S SCK pin'),
        'ws': parse_gp_pin(ws, 'I2S WS pin'),
        'sd': parse_gp_pin(sd, 'I2S SD pin'),
    }
    if len(set(pins.values())) != 3:
        raise ValueError("--sck, --ws, and --sd must use distinct pins")
    if i2s_id < 0:
        raise ValueError("--id must be >= 0")
    if rate < 1000:
        raise ValueError("--rate must be >= 1000")
    if ibuf < 256:
        raise ValueError("--ibuf must be >= 256")
    return {**pins, 'id': i2s_id, 'rate': rate, 'ibuf': ibuf}


def _i2s_init(cfg: dict, mode: str, bits: int = 16) -> str:
    return (
        "from machine import I2S,Pin\n"
        f"audio=I2S({cfg['id']},sck=Pin({cfg['sck']}),ws=Pin({cfg['ws']}),"
        f"sd=Pin({cfg['sd']}),mode=I2S.{mode},bits={bits},format=I2S.MONO,"
        f"rate={cfg['rate']},ibuf={cfg['ibuf']})"
    )


def _make_tone_code(cfg: dict, tones: list[tuple[float, int]], amplitude: float) -> str:
    init = _i2s_init(cfg, 'TX')
    chunk_frames = 1024
    sine_bits = 10
    frac_bits = 8
    fade_n = 256

    return f'''import math,json,time,micropython
from array import array
from uctypes import addressof
rate={cfg['rate']}
amp={int(round(32767 * amplitude))}
tone_specs={tones!r}
CHUNK={chunk_frames}
{init}
_SINE_BITS={sine_bits}
_FRAC_BITS={frac_bits}
_SHIFT=32-_SINE_BITS
_IDX_MASK=(1<<_SINE_BITS)-1
_FRAC_MASK=(1<<_FRAC_BITS)-1
_BIAS=32768
_N=1<<_SINE_BITS
sine_table=array('H',[0]*_N)
for _i in range(_N):
 _ang=2*math.pi*_i/_N
 sine_table[_i]=(int(round(math.sin(_ang)*32767))+_BIAS)&0xFFFF
_FADE_N={fade_n}
fade_curve=array('H',[0]*_FADE_N)
for _i in range(_FADE_N):
 fade_curve[_i]=int(round((1-math.cos(math.pi*_i/_FADE_N))*0.5*32767))
chunk=bytearray(CHUNK*2)
chunk_mv=memoryview(chunk)

@micropython.viper
def _render(todo:int, sent:int, total:int, fade_samples:int, amp_q15:int, phase:int, step:int,
            shift:int, idx_mask:int, frac_bits:int, frac_mask:int, sine_bias:int, fade_n:int,
            tbl, fade_tbl, buf) -> int:
 buf_ptr=ptr8(addressof(buf))
 tbl_ptr=ptr16(addressof(tbl))
 fade_ptr=ptr16(addressof(fade_tbl))
 off=0
 for i in range(todo):
  phase=phase+step
  idx=(phase>>shift)&idx_mask
  frac=(phase>>(shift-frac_bits))&frac_mask
  v1=int(tbl_ptr[idx])-sine_bias
  v2=int(tbl_ptr[(idx+1)&idx_mask])-sine_bias
  base=v1+(((v2-v1)*frac)>>frac_bits)
  s16=(base*amp_q15+16384)>>15
  p=sent+i
  if p<fade_samples:
   fi=(p*fade_n)//fade_samples
   if fi>=fade_n: fi=fade_n-1
   g=int(fade_ptr[fi])
   s16=(s16*g+16384)>>15
  else:
   rem=total-p
   if rem<=fade_samples:
    fi2=(rem*fade_n)//fade_samples
    if fi2>=fade_n: fi2=fade_n-1
    g2=int(fade_ptr[fi2])
    s16=(s16*g2+16384)>>15
  buf_ptr[off]=s16&0xFF
  buf_ptr[off+1]=(s16>>8)&0xFF
  off+=2
 return phase

def _write_all(mv):
 off=0
 n=len(mv)
 stall=50
 write=audio.write
 while off<n:
  w=write(mv[off:])
  if not w:
   time.sleep_us(stall)
   if stall<1000: stall<<=1
   continue
  stall=50
  off+=w

try:
 for freq,duration_ms in tone_specs:
  total=max(1,int(round(rate*duration_ms/1000)))
  fade_samples=max(1,rate//200)
  if fade_samples*2>total: fade_samples=max(1,total//2)
  step=int((freq*(1<<32))/rate)
  phase=0
  sent=0
  while sent<total:
   todo=min(CHUNK,total-sent)
   phase=_render(todo,sent,total,fade_samples,amp,phase,step,_SHIFT,_IDX_MASK,_FRAC_BITS,_FRAC_MASK,_BIAS,_FADE_N,sine_table,fade_curve,chunk)
   _write_all(chunk_mv[:todo*2])
   sent+=todo
 time.sleep_ms(({cfg['ibuf']}*1000)//(rate*2)+10)
 print(json.dumps({{'tones':{len(tones)},'duration_ms':{sum(d for _, d in tones)}}}))
finally:
 audio.deinit()
'''


def _make_read_code(cfg: dict, repeat: int, interval_ms: int, frames: int,
                    rx_bits: int = 32, gain: float = 16.0) -> str:
    init = _i2s_init(cfg, 'RX', rx_bits)
    loop = "while True:" if repeat == 0 else f"for _ in range({repeat}):"
    sample_bytes = rx_bits // 8
    unpack = "struct.unpack_from('<i',buf,i*4)[0]>>16" if rx_bits == 32 else "struct.unpack_from('<h',buf,i*2)[0]"
    return f'''import json,math,struct,time
{init}
buf=bytearray({frames * sample_bytes})
try:
 {loop}
  n=audio.readinto(buf)
  count=(n or 0)//{sample_bytes}
  if count:
   raw_vals=[{unpack} for i in range(count)]
   dc=sum(raw_vals)/count
   vals=[max(-32768,min(32767,int((value-dc)*{gain!r}))) for value in raw_vals]
   rms=math.sqrt(sum(v*v for v in vals)/count)
   print(json.dumps({{'samples':count,'min':min(vals),'max':max(vals),'peak':max(abs(v) for v in vals),'rms':rms,'last':vals[-1],'dc':dc}}))
  else:
   print(json.dumps({{'samples':0}}))
  if {interval_ms}>0: time.sleep_ms({interval_ms})
finally:
 audio.deinit()
'''


def _format_read_panel(data: dict) -> str:
    if not data.get('samples'):
        return '[yellow]No samples received[/yellow]'
    return (
        f"[dim]Samples[/dim]  [cyan]{int(data['samples'])}[/cyan]\n"
        f"[dim]RMS[/dim]      [green]{float(data['rms']):.1f}[/green]\n"
        f"[dim]Peak[/dim]     [yellow]{int(data['peak'])}[/yellow]\n"
        f"[dim]Range[/dim]    {int(data['min'])} .. {int(data['max'])}\n"
        f"[dim]DC[/dim]       {float(data['dc']):.1f}\n"
        f"[dim]Last[/dim]     {int(data['last'])}"
    )


def _format_read_stream_row(data: dict, elapsed_s: int) -> str:
    timestamp = f'{elapsed_s // 3600:02d}:{(elapsed_s % 3600) // 60:02d}:{elapsed_s % 60:02d}'
    if not data.get('samples'):
        return f'  {_I2S_D}{timestamp}{_I2S_RST}    {_I2S_Y}no samples{_I2S_RST}'
    return (
        f'  {_I2S_D}{timestamp}{_I2S_RST}    '
        f'{_I2S_D}RMS{_I2S_RST} {_I2S_G}{float(data["rms"]):7.1f}{_I2S_RST}   '
        f'{_I2S_D}Peak{_I2S_RST} {_I2S_Y}{int(data["peak"]):6d}{_I2S_RST}   '
        f'{_I2S_D}Min{_I2S_RST} {int(data["min"]):6d}   '
        f'{_I2S_D}Max{_I2S_RST} {int(data["max"]):6d}   '
        f'{_I2S_D}DC{_I2S_RST} {_I2S_C}{float(data["dc"]):8.1f}{_I2S_RST}   '
        f'{_I2S_D}Last{_I2S_RST} {int(data["last"]):6d}   '
        f'{_I2S_D}n={int(data["samples"])}{_I2S_RST}'
    )


def _run_read(client, cfg: dict, repeat: int, interval_ms: int, frames: int,
              rx_bits: int, gain: float) -> None:
    if repeat == 1:
        raw = _exec(client, _make_read_code(cfg, 1, 0, frames, rx_bits, gain), timeout=3)
        data = json.loads(raw)
        OutputHelper.print_panel(_format_read_panel(data), title='I2S Read', border_style='data')
        return

    code = _make_read_code(cfg, repeat, interval_ms, frames, rx_bits, gain)
    repeat_label = '\u221e' if repeat == 0 else f'\u00d7{repeat}'
    hint = 'Ctrl+C exit' if repeat == 0 else 'Ctrl+C cancel'
    header = (
        f'  {_I2S_D}I2S Read{_I2S_RST}  '
        f'SCK=GP{cfg["sck"]}  WS=GP{cfg["ws"]}  SD=GP{cfg["sd"]}  '
        f'{rx_bits}-bit  {cfg["rate"]} Hz  gain={gain:g}x  {repeat_label}  '
        f'interval={interval_ms} ms  {_I2S_D}[{hint}]{_I2S_RST}'
    )
    _setup_adc_scroll_screen(header, 113)
    started_at = time.monotonic()
    count = [0]

    def on_line(line):
        try:
            data = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return
        if not isinstance(data, dict):
            return
        count[0] += 1
        elapsed_s = int(time.monotonic() - started_at)
        sys.stdout.write(_format_read_stream_row(data, elapsed_s) + '\n')
        sys.stdout.flush()

    try:
        _run_adc_stream(client, code, on_line)
    except KeyboardInterrupt:
        pass
    finally:
        _teardown_adc_scroll_screen()
    done = f'Stopped: {count[0]} blocks' if repeat == 0 else f'Done: {count[0]}/{repeat} blocks'
    sys.stdout.write(f'  {done}\n')
    sys.stdout.flush()


def _preflight_scope_lib(client) -> None:
    raw = _exec(client, "import termviz;print('ok')", timeout=3)
    if raw != 'ok':
        raise RuntimeError('i2s scope requires termviz on the board')


def _build_scope_script(cfg: dict, sample_ms: int, rx_bits: int = 32,
                        gain: float = 16.0) -> str:
    sample_bytes = rx_bits // 8
    unpack = "struct.unpack_from('<i',buf,i*4)[0]>>16" if rx_bits == 32 else "struct.unpack_from('<h',buf,i*2)[0]"
    render_ms = max(1, sample_ms)
    return f'''import math,select as _sel,struct,sys,time
from machine import I2S,Pin
from termviz import Term,Canvas,Plot,Scope

RATE={cfg['rate']}
BITS={rx_bits}
GAIN={gain!r}
FRAMES=256
SAMPLE_BYTES={sample_bytes}
RENDER_MS={render_ms}
FLOOR_DB=-60.0
CV_COLS=78
CV_ROWS=20
STATS_ROW=CV_ROWS+1
REGION=(0,8,10,10)
TRACE_COLOR=(80,255,120)

audio=I2S({cfg['id']},sck=Pin({cfg['sck']}),ws=Pin({cfg['ws']}),sd=Pin({cfg['sd']}),mode=I2S.RX,bits=BITS,format=I2S.MONO,rate=RATE,ibuf={cfg['ibuf']})
buf=bytearray(FRAMES*SAMPLE_BYTES)
buf_mv=memoryview(buf)

def _make_plot():
 w=CV_COLS*2
 h=CV_ROWS*4
 left,top,right,bottom=REGION
 cv=Canvas(CV_COLS,CV_ROWS)
 ax=Plot(cv,region_px=(left,top,w-left-right,h-top-bottom),xlim=(0,w),ylim=(FLOOR_DB,0.0),color_cycle=[TRACE_COLOR])
 ax.title('I2S Microphone Level  %d-bit  %d Hz' % (BITS,RATE),color=(180,220,180))
 ax.yticks([-60.0,-50.0,-40.0,-30.0,-20.0,-10.0,0.0],['-60','-50','-40','-30','-20','-10','0'])
 ax.grid(True)
 sc=Scope(ax,vmin=FLOOR_DB,vmax=0.0,colors=[TRACE_COLOR],px_step=2,show_zero=False)
 ax._legend_on=False
 ax.clear_legend_items()
 ax._ylabel='dBFS'
 return cv,sc

def _read_full():
 off=0
 while off<len(buf):
  n=audio.readinto(buf_mv[off:])
  if n:
   off+=n
  else:
   time.sleep_us(50)

def _measure(gain):
 _read_full()
 values=[{unpack} for i in range(FRAMES)]
 dc=sum(values)/FRAMES
 sum_sq=0.0
 peak=0
 for value in values:
  ac=value-dc
  sum_sq+=ac*ac
  absolute=abs(ac)
  if absolute>peak: peak=absolute
 rms=math.sqrt(sum_sq/FRAMES)*gain
 peak*=gain
 if rms>32767: rms=32767
 if peak>32767: peak=32767
 db=20.0*math.log10(max(1.0,rms)/32768.0)
 peak_db=20.0*math.log10(max(1.0,peak)/32768.0)
 return db,peak_db,rms,peak,dc

def _poll_key():
 ready,_,_=_sel.select([sys.stdin],[],[],0)
 if not ready:
  return None
 ch=sys.stdin.read(1)
 if ch==chr(3):
  raise KeyboardInterrupt
 if ch!=chr(27):
  return ch
 ready,_,_=_sel.select([sys.stdin],[],[],0.002)
 if not ready or sys.stdin.read(1)!='[':
  return ch
 ready,_,_=_sel.select([sys.stdin],[],[],0.002)
 if not ready:
  return ch
 code=sys.stdin.read(1)
 if code=='A': return 'UP'
 if code=='B': return 'DOWN'
 return ch

cv,sc=_make_plot()
w=sys.stdout.write
next_render=time.ticks_ms()
try:
 while True: key=_poll_key();GAIN=min(256.0,GAIN*2.0) if key=='UP' else max(0.25,GAIN/2.0) if key=='DOWN' else GAIN;db,peak_db,rms,peak,dc=_measure(GAIN);now=time.ticks_ms();due=time.ticks_diff(now,next_render)>=0;sc.tick([max(FLOOR_DB,min(0.0,db))]) if due else None;w(Term.cursor_to(STATS_ROW,1)+Term.FG.MUTED+'  Gain: '+Term.RESET+Term.rgb(255,220,60)+('%.2fx' % GAIN)+Term.RESET+Term.FG.MUTED+('   Level: %6.1f dBFS   Peak: %6.1f dBFS   RMS: %7.1f   DC: %8.1f' % (db,peak_db,rms,dc))+Term.RESET+'   ') if due else None;next_render=time.ticks_add(now,RENDER_MS) if due else next_render
except KeyboardInterrupt:
 pass
finally:
 audio.deinit()
 cv.end()
'''


def _print_help() -> None:
    OutputHelper.print_panel("""Generate I2S tones or capture an I2S microphone on the connected board.

[bold cyan]Usage:[/bold cyan]
  replx PORT i2s tone  [yellow]FREQ mMS...[/yellow] --sck GPn --ws GPn --sd GPn [--amplitude A]
  replx PORT i2s read  --sck GPn --ws GPn --sd GPn [--repeat N] [--interval-ms MS] [--frames N]
  replx PORT i2s scope --sck GPn --ws GPn --sd GPn [--sample MS]

[bold cyan]Subcommands:[/bold cyan]
  [green]tone[/green]   Play FREQ/duration pairs on an I2S DAC/amplifier (16-bit mono TX).
  [green]read[/green]   Capture microphone blocks and print RMS/peak/min/max/DC/last.
  [green]scope[/green]  Board-side dBFS level history (requires termviz). UP/DOWN change gain.

[bold cyan]Common options:[/bold cyan]
  --sck/--ws/--sd GPn  I2S pins (required, must be distinct)
  --id N               I2S peripheral id (default: 0)
  --rate HZ            Sample rate (default: 16000, min: 1000)
  --ibuf N             Internal buffer bytes (default: 4096, min: 256)

[bold cyan]tone options:[/bold cyan]
  FREQ mMS             Frequency in Hz (0 < FREQ < rate/2) followed by duration, e.g. 440 m500
  --amplitude A        Output level 0 < A <= 1 (default: 0.25)

[bold cyan]read/scope options:[/bold cyan]
  --rx-bits 16|32      Microphone sample width (default: 32)
  --gain N             Software gain 0 < N <= 256 (default: 16)
  --repeat N           read blocks; 0 = until Ctrl+C (default: 0)
  --interval-ms MS     Delay between read blocks (alias: --interval, default: 20)
  --frames N           Samples per read block (default: 256)
  --sample MS          scope render interval: 0,1,2,5,10,20,50,100 (default: 20)

[bold cyan]Examples:[/bold cyan]
  replx COM3 i2s tone --sck GP4 --ws GP5 --sd GP7 440 m100 660 m500
  replx COM3 i2s read --sck GP4 --ws GP5 --sd GP6 --repeat 1
  replx COM3 i2s read --sck GP4 --ws GP5 --sd GP6 --repeat 10 --interval-ms 100
  replx COM3 i2s scope --sck GP4 --ws GP5 --sd GP6

[dim]m100 means 100 milliseconds. scope displays block RMS/peak as a -60..0 dBFS noise-level history.[/dim]""",
                             title="i2s", border_style="help")


@app.command(name='i2s', rich_help_panel='Hardware')
def i2s_cmd(
    args: Optional[list[str]] = typer.Argument(None),
    sck: Optional[str] = typer.Option(None, '--sck'),
    ws: Optional[str] = typer.Option(None, '--ws'),
    sd: Optional[str] = typer.Option(None, '--sd'),
    i2s_id: int = typer.Option(0, '--id'),
    rate: int = typer.Option(16000, '--rate'),
    ibuf: int = typer.Option(4096, '--ibuf'),
    frames: int = typer.Option(256, '--frames'),
    rx_bits: int = typer.Option(32, '--rx-bits'),
    gain: float = typer.Option(16.0, '--gain'),
    repeat: int = typer.Option(0, '--repeat'),
    interval_ms: int = typer.Option(20, '--interval-ms', '--interval'),
    amplitude: float = typer.Option(0.25, '--amplitude'),
    sample: int = typer.Option(20, '--sample'),
    show_help: bool = typer.Option(False, '--help', '-h', is_eager=True, hidden=True),
):
    if show_help:
        _print_help()
        raise typer.Exit()
    if not args:
        _print_help()
        raise typer.Exit(1)
    try:
        subcmd, tokens = args[0].lower(), args[1:]
        if subcmd not in ('tone', 'read', 'scope'):
            raise ValueError("Subcommand must be tone, read, or scope")
        cfg = _parse_config(sck, ws, sd, i2s_id, rate, ibuf)
        if repeat < 0 or interval_ms < 0:
            raise ValueError("--repeat and --interval-ms must be >= 0")
        if frames < 1:
            raise ValueError("--frames must be >= 1")
        if rx_bits not in (16, 32):
            raise ValueError("--rx-bits must be 16 or 32")
        if not math.isfinite(gain) or gain <= 0 or gain > 256:
            raise ValueError("--gain must be finite and in range (0, 256]")
        if not math.isfinite(amplitude) or not 0 < amplitude <= 1:
            raise ValueError("--amplitude must be in (0, 1]")
        _ensure_connected()
        with _create_agent_client() as client:
            require_standard_hardware(client, 'i2s')
            if subcmd == 'tone':
                tones = _parse_tone_tokens(tokens, rate)
                timeout = 5 + sum(duration for _, duration in tones) / 1000
                result = json.loads(_exec(client, _make_tone_code(cfg, tones, amplitude), timeout=timeout))
                OutputHelper.print_panel(f"Played {result['tones']} tone(s), {result['duration_ms']} ms", title='I2S Tone', border_style='success')
            elif subcmd == 'read':
                if tokens:
                    raise ValueError("i2s read does not accept positional arguments")
                _run_read(client, cfg, repeat, interval_ms, frames, rx_bits, gain)
            else:
                if tokens:
                    raise ValueError("i2s scope does not accept positional arguments")
                if sample not in _SAMPLE_TABLE:
                    raise ValueError("--sample must be one of: 0, 1, 2, 5, 10, 20, 50, 100")
                raw = _exec(client, "from machine import I2S;print('ok')", timeout=3)
                if raw != 'ok':
                    raise RuntimeError('machine.I2S is unavailable')
                _preflight_scope_lib(client)
                from .exec import _run_interactive_mode
                _run_interactive_mode(client, _build_scope_script(cfg, sample, rx_bits, gain), None, False)
    except typer.Exit:
        raise
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        OutputHelper.print_panel(str(exc), title='I2S Error', border_style='error')
        raise typer.Exit(1)
