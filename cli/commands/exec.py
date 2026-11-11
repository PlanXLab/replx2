import os
import sys
import time
import re
import ast
import threading
import posixpath
import signal
import shlex
import hashlib
import subprocess
import shutil
import tempfile
from collections import deque
from pathlib import Path

import typer
from rich.panel import Panel

from replx.terminal import (
    IS_WINDOWS, getch, disable_quick_edit_mode, restore_console_mode,
    LineModeTerminal, utf8_need_follow, read_escape_sequence,
)
from replx.utils.constants import CTRL_C, CTRL_D
from ..helpers import (
    OutputHelper, StoreManager,
    get_panel_box, CONSOLE_WIDTH
)
from ..config import STATE, ConfigManager
from ..connection import (
    _ensure_connected, _create_agent_client,
    _get_current_agent_port, _get_global_options,
)

from ..app import app


def _wrap_trailing_expression_for_print(code: str) -> str:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError:
        return code

    if not tree.body:
        return code

    last_stmt = tree.body[-1]
    if not isinstance(last_stmt, ast.Expr):
        return code

    if isinstance(last_stmt.value, ast.Call):
        fn = last_stmt.value.func
        if isinstance(fn, ast.Name) and fn.id == "print":
            return code

    temp_name = "__replx_expr_result"
    tree.body[-1] = ast.Assign(
        targets=[ast.Name(id=temp_name, ctx=ast.Store())],
        value=last_stmt.value,
    )
    tree.body.append(
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="print", ctx=ast.Load()),
                args=[ast.Name(id=temp_name, ctx=ast.Load())],
                keywords=[],
            )
        )
    )
    ast.fix_missing_locations(tree)

    try:
        return ast.unparse(tree)
    except Exception:
        return code


def _is_repl_enter_key(ch: bytes) -> bool:
    return ch in (b"\r", b"\n", b"\r\n", b"\n\r")


def _setup_readline_for_repl():
    try:
        import readline
    except ImportError:
        return None

    try:
        readline.parse_and_bind("set editing-mode emacs")
    except Exception:
        pass

    try:
        readline.set_auto_history(False)
    except Exception:
        pass

    return readline


def _resolve_vscode_command() -> list[str] | None:
    candidates = ["code", "code-insiders", "codium"]
    comspec = os.environ.get("COMSPEC", "cmd.exe")

    if sys.platform.startswith("win"):
        vscode_cwd = os.environ.get("VSCODE_CWD")
        if vscode_cwd:
            for cmd_name in ("code.cmd", "code-insiders.cmd"):
                cmd_path = Path(vscode_cwd) / "bin" / cmd_name
                if cmd_path.exists():
                    return [comspec, "/c", str(cmd_path)]

    for name in candidates:
        found = shutil.which(name)
        if found:
            lower = found.lower()
            if lower.endswith(".cmd") or lower.endswith(".bat"):
                return [comspec, "/c", found]
            if sys.platform.startswith("win") and lower.endswith(".exe"):
                exe_path = Path(found)
                cmd_name = "code-insiders.cmd" if "insiders" in lower else "code.cmd"
                cmd_path = exe_path.parent / "bin" / cmd_name
                if cmd_path.exists():
                    return [comspec, "/c", str(cmd_path)]
            return [found]

    if sys.platform.startswith("win"):
        win_paths = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code Insiders" / "Code - Insiders.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Microsoft VS Code" / "Code.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Microsoft VS Code Insiders" / "Code - Insiders.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Microsoft VS Code" / "Code.exe",
        ]
        for path in win_paths:
            if str(path) and path.exists():
                cmd_name = "code-insiders.cmd" if "insiders" in path.name.lower() else "code.cmd"
                cmd_path = path.parent / "bin" / cmd_name
                if cmd_path.exists():
                    return [comspec, "/c", str(cmd_path)]
                return [str(path)]

    return None


def _is_missing_file_error(error: Exception | str) -> bool:
    text = str(error).lower()
    missing_markers = ('enoent', 'errno 2', 'no such file', 'file not found', 'not found', 'does not exist')
    return any(marker in text for marker in missing_markers)


def _file_md5(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return None


def _open_editor_and_wait(local_path: str, original_hash: str | None = None) -> tuple[bool, str | None]:
    vscode_cmd = _resolve_vscode_command()

    if vscode_cmd:
        start_ts = time.monotonic()
        try:
            proc = subprocess.Popen(vscode_cmd + ["--reuse-window", "--wait", local_path])
        except Exception as e:
            return False, str(e)

        while True:
            rc = proc.poll()
            if rc is not None:
                if rc != 0:
                    return False, f"Editor exited with code {rc}"
                if time.monotonic() - start_ts < 1.0:
                    input("After saving and closing the VSCode tab, press Enter to continue...")
                return True, None

            time.sleep(0.1)

    try:
        if sys.platform.startswith("win"):
            os.startfile(local_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", local_path], check=False)
        else:
            subprocess.run(["xdg-open", local_path], check=False)
        print("Editor command not found in PATH. Opened file with default editor.")
        input("After saving and closing the file, press Enter to continue...")
        return True, None
    except Exception as e:
        return False, str(e)


def _make_edit_temp_dir() -> str:
    try:
        vscode_dir = ConfigManager.find_or_create_vscode_dir()
        edit_root = os.path.join(vscode_dir, ".replx-edit")
        os.makedirs(edit_root, exist_ok=True)
        return tempfile.mkdtemp(prefix="session_", dir=edit_root)
    except Exception:
        return tempfile.mkdtemp(prefix='replx_edit_')


@app.command(name="exec", rich_help_panel="Execution")
def exec_cmd(
    command: str = typer.Argument("", help="MicroPython command to execute"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Run a single MicroPython command on the connected board.

Quick way to execute code without creating a file.

[bold cyan]Usage:[/bold cyan]
  replx exec [yellow]"CODE"[/yellow]
  replx -c [yellow]"CODE"[/yellow]          [dim]# Short form (like python -c)[/dim]

[bold cyan]Arguments:[/bold cyan]
  [yellow]CODE[/yellow]     MicroPython code to execute [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  [dim]# Simple expressions[/dim]
  replx -c "print('hello')"              [dim]# Print message[/dim]
  replx -c "1 + 2 * 3"                   [dim]# Math (prints result)[/dim]

  [dim]# Import and use modules[/dim]
  replx -c "import os; print(os.listdir())"      [dim]# List files[/dim]
  replx -c "import machine; print(machine.freq())"  [dim]# CPU frequency[/dim]

  [dim]# Multi-line with semicolons[/dim]
  replx -c "import time; time.sleep(1); print('done')"

  [dim]# Hardware control[/dim]
  replx -c "from machine import Pin; Pin(25, Pin.OUT).on()"  [dim]# LED on[/dim]

[bold cyan]Tips:[/bold cyan]
  • Use quotes around the code: "..." or '...'
  • Separate multiple statements with semicolons
  • For longer code, use [yellow]replx run script.py[/yellow] instead
  • For interactive work, use [yellow]replx repl[/yellow]

[bold cyan]Related:[/bold cyan]
  replx run script.py     [dim]# Run script file instead[/dim]
  replx repl              [dim]# Interactive MicroPython prompt[/dim]"""
        OutputHelper.print_panel(help_text, title="exec", border_style="help")
        console.print()
        raise typer.Exit()
    
    if not command:
        OutputHelper.print_panel(
            "Missing required argument.\n\n"
            "[bold cyan]Usage:[/bold cyan] replx exec [yellow]COMMAND[/yellow]\n"
            "       replx -c [yellow]COMMAND[/yellow]",
            title="Execution Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    _ensure_connected()
    with _create_agent_client() as client:
        normalized_command = _wrap_trailing_expression_for_print(command)
        try:
            result = client.send_command('exec', code=normalized_command)
        except RuntimeError as e:
            error_msg = str(e)
            prefix = "ProtocolError: "
            if error_msg.startswith(prefix):
                error_msg = error_msg[len(prefix):]
            OutputHelper.print_panel(error_msg, title="Execution Error", border_style="error")
            raise typer.Exit(1)
        if result.get('output'):
            print(result['output'], end='')


def _display_execution_error(stderr_data: bytearray, local_file: str | None) -> None:
    if not stderr_data:
        return
    stderr_text = stderr_data.decode('utf-8', errors='replace').strip()
    if not stderr_text:
        return
    script_abs_path = os.path.abspath(local_file) if local_file else None

    def _make_link(match):
        file_ref = match.group(1)
        line_num = match.group(2)
        if file_ref == "<stdin>":
            if script_abs_path:
                return f'File "{script_abs_path}", line {line_num}'
            return match.group(0)
        replx_home = StoreManager.pkg_root()
        possible_paths = [
            os.path.join(replx_home, "core", STATE.core or "", "src", file_ref.lstrip('/')),
            os.path.join(replx_home, "device", STATE.device or "", "src", file_ref.lstrip('/')),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return f'File "{path}", line {line_num}'
        return match.group(0)

    linked_text = re.sub(r'File "([^"]+)", line (\d+)', _make_link, stderr_text)
    OutputHelper.print_panel(linked_text, title="Execution Error", border_style="error")


def _run_line_mode(client, device_exec_code: str | None, local_file: str | None, hex_mode: bool) -> None:
    lmt = LineModeTerminal(hex_mode=hex_mode)
    stop_requested = False
    ctrl_c_count = 0
    pending: list[bytes] = []
    stderr_data = bytearray()

    old_settings = None
    fd = None
    if not IS_WINDOWS:
        import tty
        import termios
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except Exception:
            pass

    def output_callback(data: bytes, stream_type: str = "stdout") -> None:
        nonlocal ctrl_c_count
        ctrl_c_count = 0
        if stream_type == "stderr":
            stderr_data.extend(data)
        else:
            lmt.write_output(data)

    def input_provider() -> bytes | None:
        nonlocal ctrl_c_count, stop_requested
        if pending:
            return pending.pop(0)
        try:
            if IS_WINDOWS:
                import msvcrt as _ms
                if not _ms.kbhit():
                    return None
                w = _ms.getwch()
                if w == '\x03':
                    if not hex_mode:
                        stop_requested = True
                        pending.append(CTRL_C)
                        return None
                    ctrl_c_count += 1
                    if ctrl_c_count >= 2:
                        stop_requested = True
                        return None
                    pending.append(CTRL_C)
                    return None
                if w == '\x04':
                    return CTRL_D
                if w in ('\x00', '\xe0'):
                    ext = _ms.getwch()
                    _arrows = {'H': b'\x1b[A', 'P': b'\x1b[B',
                               'M': b'\x1b[C', 'K': b'\x1b[D'}
                    mapped = _arrows.get(ext)
                    if mapped is not None:
                        return lmt.handle_key(mapped)
                    return None
                ctrl_c_count = 0
                return lmt.handle_key(w.encode('utf-8'))
            else:
                import select as _sel
                r, _, _ = _sel.select([sys.stdin], [], [], 0)
                if not r:
                    return None
                ch = os.read(fd, 1)
                if ch == CTRL_C:
                    if not hex_mode:
                        stop_requested = True
                        pending.append(CTRL_C)
                        return None
                    ctrl_c_count += 1
                    if ctrl_c_count >= 2:
                        stop_requested = True
                        return None
                    pending.append(CTRL_C)
                    return None
                if ch == CTRL_D:
                    return CTRL_D
                if ch == b'\x1b':
                    ch = read_escape_sequence(fd, ch)
                ctrl_c_count = 0
                return lmt.handle_key(ch)
        except Exception:
            pass
        return None

    def stop_check() -> bool:
        return stop_requested

    original_sigint = signal.getsignal(signal.SIGINT)

    def sigint_handler(signum, frame) -> None:
        nonlocal ctrl_c_count, stop_requested
        if not hex_mode:
            stop_requested = True
            pending.append(CTRL_C)
            return
        ctrl_c_count += 1
        if ctrl_c_count >= 2:
            stop_requested = True
        else:
            pending.append(CTRL_C)

    try:
        signal.signal(signal.SIGINT, sigint_handler)
        if not IS_WINDOWS and old_settings is not None:
            try:
                tty.setraw(fd)
            except Exception:
                pass
        lmt.setup()
        try:
            if device_exec_code:
                client.run_interactive(
                    script_content=device_exec_code,
                    echo=False,
                    output_callback=output_callback,
                    input_provider=input_provider,
                    stop_check=stop_check,
                )
            else:
                client.run_interactive(
                    script_path=local_file,
                    echo=False,
                    output_callback=output_callback,
                    input_provider=input_provider,
                    stop_check=stop_check,
                )
        except KeyboardInterrupt:
            stop_requested = True
            try:
                client.send_command('run_stop', timeout=0.3)
            except Exception:
                pass
    finally:
        lmt.restore()
        signal.signal(signal.SIGINT, original_sigint)
        if not IS_WINDOWS:
            try:
                import termios
                if old_settings is not None and fd is not None:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass

    _display_execution_error(stderr_data, local_file)


def _run_interactive_mode(client, device_exec_code: str | None, local_file: str | None, echo: bool) -> None:
    stop_requested = False
    pending_input = []
    stderr_buffer = bytearray()
    stdout_ended_with_newline = True

    old_settings = None
    fd = None
    if not IS_WINDOWS:
        import tty
        import termios
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)
        except Exception:
            pass

    def output_callback(data: bytes, stream_type: str = "stdout"):
        nonlocal stdout_ended_with_newline
        try:
            if stream_type == "stderr":
                stderr_buffer.extend(data)
            else:
                if not IS_WINDOWS:
                    data = data.replace(b'\r\n', b'\n')
                    data = data.replace(b'\r', b'\n')
                    data = data.replace(b'\n', b'\r\n')
                else:
                    data = data.replace(b'\r', b'')

                if data:
                    stdout_ended_with_newline = data.endswith(b'\n')
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
        except Exception:
            pass

    def input_provider() -> bytes:
        nonlocal stop_requested

        if pending_input:
            return pending_input.pop(0)

        try:
            if IS_WINDOWS:
                import msvcrt
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch == '\x03':
                        stop_requested = True
                        return CTRL_C
                    elif ch == '\x04':
                        return CTRL_D
                    elif ch == '\r':
                        if echo:
                            sys.stdout.write('\r\n')
                            sys.stdout.flush()
                        return b'\r'
                    elif ch == '\n':
                        if echo:
                            sys.stdout.write('\r\n')
                            sys.stdout.flush()
                        return b'\r'
                    elif ch == '\x08':
                        if echo:
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                        return b'\x08'
                    elif ch in ('\x00', '\xe0'):
                        ext = msvcrt.getwch()
                        ext_map = {
                            'H': b'\x1b[A',
                            'P': b'\x1b[B',
                            'M': b'\x1b[C',
                            'K': b'\x1b[D',
                        }
                        return ext_map.get(ext, b'')
                    else:
                        if echo:
                            sys.stdout.write(ch)
                            sys.stdout.flush()
                        return ch.encode('utf-8')
            else:
                import select
                r, _, _ = select.select([sys.stdin], [], [], 0)
                if r:
                    ch = os.read(sys.stdin.fileno(), 1)
                    if ch == CTRL_C:
                        stop_requested = True
                        return CTRL_C
                    elif ch == b'\n':
                        if echo:
                            sys.stdout.buffer.write(b'\r\n')
                            sys.stdout.buffer.flush()
                        return b'\r'
                    else:
                        if echo:
                            sys.stdout.buffer.write(ch)
                            sys.stdout.buffer.flush()
                        return ch
        except Exception:
            pass
        return None

    def stop_check() -> bool:
        return stop_requested

    original_sigint = signal.getsignal(signal.SIGINT)

    def sigint_handler(signum, frame):
        nonlocal stop_requested
        stop_requested = True
        pending_input.append(CTRL_C)

    try:
        signal.signal(signal.SIGINT, sigint_handler)

        if not IS_WINDOWS:
            if old_settings is not None:
                try:
                    tty.setraw(fd)
                except Exception:
                    pass

        try:
            if device_exec_code:
                client.run_interactive(
                    script_content=device_exec_code,
                    echo=echo,
                    output_callback=output_callback,
                    input_provider=input_provider,
                    stop_check=stop_check
                )
            else:
                client.run_interactive(
                    script_path=local_file,
                    echo=echo,
                    output_callback=output_callback,
                    input_provider=input_provider,
                    stop_check=stop_check
                )
        except KeyboardInterrupt:
            stop_requested = True
            try:
                client.send_command('run_stop', timeout=0.3)
            except Exception:
                pass
            if not stdout_ended_with_newline:
                print("\n[Interrupted]")
            return

        if not stdout_ended_with_newline:
            print()

        _display_execution_error(stderr_buffer, local_file)

    except KeyboardInterrupt:
        stop_requested = True
        try:
            client.send_command('run_stop', timeout=0.1)
        except Exception:
            pass
        print("\n[Interrupted by user]")
    except Exception as e:
        error_msg = str(e)
        if 'Not connected' in error_msg:
            OutputHelper.print_panel(
                "Not connected to any device.\n\nRun [bright_green]replx --port COM3 setup[/bright_green] first.",
                title="Connection Required",
                border_style="error"
            )
        elif 'busy' in error_msg.lower():
            OutputHelper.print_panel(
                f"{error_msg}",
                title="Device Busy",
                border_style="warning"
            )
        else:
            OutputHelper.print_panel(
                f"Error: {str(e)}",
                title="Execution Failed",
                border_style="error"
            )
        raise typer.Exit(1)
    finally:
        signal.signal(signal.SIGINT, original_sigint)

        if not IS_WINDOWS:
            try:
                import termios
                if old_settings is not None and fd is not None:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass


@app.command(rich_help_panel="Execution")
def run(
    script_file: str = typer.Argument("", help="Script file to run"),
    non_interactive: bool = typer.Option(False, "--non-interactive", "-n", help="Non-interactive execution"),
    echo: bool = typer.Option(False, "--echo", "-e", help="Turn on echo for interactive"),
    device: bool = typer.Option(False, "--device", "-d", help="Run from device storage"),
    line_text: bool = typer.Option(False, "--text", help="Line input mode: text"),
    line_hex: bool = typer.Option(False, "--hex", help="Line input mode: hex bytes"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Run a MicroPython script on the connected board.

By default, runs a file from your computer. Use -d to run from device.

[bold cyan]Usage:[/bold cyan]
  replx run [yellow]SCRIPT[/yellow]           [dim]# Run local file[/dim]
  replx run -d [yellow]SCRIPT[/yellow]        [dim]# Run file from device[/dim]
  replx [yellow]SCRIPT[/yellow]               [dim]# Shortcut (if .py file)[/dim]

[bold cyan]Options:[/bold cyan]
  [yellow]-d, --device[/yellow]           Run from device storage (not local)
  [yellow]-n, --non-interactive[/yellow]  Detached mode (don't wait for output)
  [yellow]-e, --echo[/yellow]             Show what's being sent
  [yellow]--text[/yellow]                 Line input mode: send text lines
  [yellow]--hex[/yellow]                  Line input mode: send hex bytes

[bold cyan]Arguments:[/bold cyan]
  [yellow]SCRIPT[/yellow]      Script file to run [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  [dim]# Run local files[/dim]
  replx run main.py               [dim]# Run ./main.py on device[/dim]
  replx main.py                   [dim]# Same (shortcut)[/dim]
  replx run ./tests/test_led.py   [dim]# Run from subdirectory[/dim]

  [dim]# Run files stored on device[/dim]
  replx run -d main.py            [dim]# Run /main.py from device[/dim]
  replx run -d /lib/test.py       [dim]# Run specific path[/dim]

  [dim]# Background execution[/dim]
  replx run -n server.py          [dim]# Start and detach[/dim]
  replx run -dn main.py           [dim]# Run from device, detached[/dim]

  [dim]# Line input mode (send one line at a time)[/dim]
  replx run --text main.py        [dim]# Type text, Enter to send[/dim]
  replx run --hex main.py         [dim]# Type hex bytes (e.g. 0102ff)[/dim]
  replx run -d --text main.py     [dim]# Line mode with device-side script[/dim]
  replx run -d --hex main.py      [dim]# Hex mode with device-side script[/dim]
  replx main.py --hex             [dim]# Shortcut form[/dim]

[bold cyan]How it works:[/bold cyan]
  • Local files: uploaded to device RAM and executed
  • Device files (-d): executed directly from flash storage
  • Interactive: Ctrl+C to interrupt, output shown in real-time
  • Line mode: split-screen layout — output scrolls above, input stays at bottom

[bold cyan]Line mode keys:[/bold cyan]
  [yellow]Enter[/yellow]       Send the typed line to the board
  [yellow]Backspace[/yellow]   Delete last character
  [yellow]Up/Down[/yellow]     Recall previous input (history)
  [yellow]Ctrl+U[/yellow]      Clear input line
  [yellow]Ctrl+T[/yellow]      Toggle EOL: [yellow]CR[/yellow] → [yellow]LF[/yellow] → [yellow]CRLF[/yellow] → ... (shown in prompt)
  [yellow]Ctrl+C[/yellow]      Interrupt and exit (--hex: twice; all other modes: once)

[bold cyan]Note (--hex):[/bold cyan]
  MicroPython interprets 0x03 bytes as Ctrl+C (KeyboardInterrupt).
  Use [yellow]micropython.kbd_intr(-1)[/yellow] in your script to disable this,
  and restore it with [yellow]micropython.kbd_intr(3)[/yellow] on exit.

[bold cyan]Related:[/bold cyan]
  replx -c "code"         [dim]# Run single command instead[/dim]
  replx repl              [dim]# Interactive mode[/dim]"""
        OutputHelper.print_panel(help_text, title="run", border_style="help")
        console.print()
        raise typer.Exit()
    
    if not script_file:
        OutputHelper.print_panel(
            "Missing required argument 'SCRIPT_FILE'.",
            title="Run Error",
            title_align="left",
            border_style="error"
        )
        raise typer.Exit(1)
    
    if non_interactive and echo:
        OutputHelper.print_panel(
            "--non-interactive and --echo cannot be used together.",
            title="Run Error",
            title_align="left",
            border_style="error"
        )
        raise typer.Exit(1)

    line_mode = "text" if line_text else ("hex" if line_hex else None)

    if line_mode is not None:
        if non_interactive:
            OutputHelper.print_panel(
                "--text/--hex cannot be used with --non-interactive.",
                title="Run Error",
                title_align="left",
                border_style="error"
            )
            raise typer.Exit(1)
        if echo:
            OutputHelper.print_panel(
                "--text/--hex cannot be used with --echo.",
                title="Run Error",
                title_align="left",
                border_style="error"
            )
            raise typer.Exit(1)

    _ensure_connected()
    
    client = None
    
    local_file = None
    remote_path = None
    device_exec_code = None
    
    if device:
        if script_file.startswith('/'):
            remote_path = script_file
        else:
            remote_path = '/' + script_file
        
        device_root_fs = STATE.device_root_fs or "/"
        if device_root_fs != "/" and not remote_path.startswith(device_root_fs):
            real_path = device_root_fs.rstrip('/') + remote_path
        else:
            real_path = remote_path
        
        try:
            with _create_agent_client() as check_client:
                check_code = f"f=open('{real_path}','rb');f.close();print('OK')"
                result = check_client.send_command('exec', code=check_code)
                output = result.get('output', '').strip()
                if output != 'OK' or result.get('error'):
                    raise FileNotFoundError()
        except Exception:
            OutputHelper.print_panel(
                f"File not found on device: [red]{remote_path}[/red]",
                title="File Not Found",
                border_style="error"
            )
            raise typer.Exit(1)
        
        if remote_path.endswith('.mpy'):
            mod_path = remote_path[1:-4]
            mod_name = mod_path.replace('/', '.')
            if mod_name.startswith('lib.'):
                mod_name = mod_name[4:]
            device_exec_code = f"import sys; sys.modules.pop('{mod_name}', None); import {mod_name}"
        else:
            device_exec_code = f"exec(open('{real_path}').read())"
    else:
        if not os.path.exists(script_file):
            OutputHelper.print_panel(
                f"File not found: [red]{script_file}[/red]\n\n"
                "Check the file path on your PC.\n"
                "To run from device storage: [bright_blue]replx run -d /path/file.py[/bright_blue]",
                title="File Not Found",
                border_style="error"
            )
            raise typer.Exit(1)
        local_file = os.path.abspath(script_file)
    
    client = _create_agent_client()

    try:
        if not non_interactive:
            if line_mode is not None:
                hex_mode = (line_mode == "hex")
                lmt = LineModeTerminal(hex_mode=hex_mode)

                lmt_stop_requested = False
                lmt_ctrl_c_count = 0
                lmt_pending: list[bytes] = []
                lmt_stderr = bytearray()

                old_settings = None
                fd = None
                if not IS_WINDOWS:
                    import tty
                    import termios
                    fd = sys.stdin.fileno()
                    try:
                        old_settings = termios.tcgetattr(fd)
                    except Exception:
                        pass

                def lmt_output_callback(data: bytes, stream_type: str = "stdout") -> None:
                    nonlocal lmt_ctrl_c_count
                    lmt_ctrl_c_count = 0
                    if stream_type == "stderr":
                        lmt_stderr.extend(data)
                    else:
                        lmt.write_output(data)

                def lmt_input_provider() -> bytes | None:
                    nonlocal lmt_ctrl_c_count, lmt_stop_requested
                    if lmt_pending:
                        return lmt_pending.pop(0)
                    try:
                        if IS_WINDOWS:
                            import msvcrt as _ms
                            if not _ms.kbhit():
                                return None
                            w = _ms.getwch()
                            if w == '\x03':
                                if not hex_mode:
                                    lmt_stop_requested = True
                                    lmt_pending.append(CTRL_C)
                                    return None
                                lmt_ctrl_c_count += 1
                                if lmt_ctrl_c_count >= 2:
                                    lmt_stop_requested = True
                                    return None
                                lmt_pending.append(CTRL_C)
                                return None
                            if w == '\x04':
                                return CTRL_D
                            if w in ('\x00', '\xe0'):
                                ext = _ms.getwch()
                                _arrows = {'H': b'\x1b[A', 'P': b'\x1b[B',
                                           'M': b'\x1b[C', 'K': b'\x1b[D'}
                                mapped = _arrows.get(ext)
                                if mapped is not None:
                                    return lmt.handle_key(mapped)
                                return None
                            lmt_ctrl_c_count = 0
                            return lmt.handle_key(w.encode('utf-8'))
                        else:
                            import select as _sel
                            r, _, _ = _sel.select([sys.stdin], [], [], 0)
                            if not r:
                                return None
                            ch = os.read(fd, 1)
                            if ch == CTRL_C:
                                if not hex_mode:
                                    lmt_stop_requested = True
                                    lmt_pending.append(CTRL_C)
                                    return None
                                lmt_ctrl_c_count += 1
                                if lmt_ctrl_c_count >= 2:
                                    lmt_stop_requested = True
                                    return None
                                lmt_pending.append(CTRL_C)
                                return None
                            if ch == CTRL_D:
                                return CTRL_D
                            if ch == b'\x1b':
                                ch = read_escape_sequence(fd, ch)
                            lmt_ctrl_c_count = 0
                            return lmt.handle_key(ch)
                    except Exception:
                        pass
                    return None

                def lmt_stop_check() -> bool:
                    return lmt_stop_requested

                lmt_original_sigint = signal.getsignal(signal.SIGINT)

                def lmt_sigint_handler(signum, frame) -> None:
                    nonlocal lmt_ctrl_c_count, lmt_stop_requested
                    if not hex_mode:
                        lmt_stop_requested = True
                        lmt_pending.append(CTRL_C)
                        return
                    lmt_ctrl_c_count += 1
                    if lmt_ctrl_c_count >= 2:
                        lmt_stop_requested = True
                    else:
                        lmt_pending.append(CTRL_C)

                try:
                    signal.signal(signal.SIGINT, lmt_sigint_handler)
                    if not IS_WINDOWS and old_settings is not None:
                        try:
                            tty.setraw(fd)
                        except Exception:
                            pass
                    lmt.setup()
                    try:
                        if device_exec_code:
                            client.run_interactive(
                                script_content=device_exec_code,
                                echo=False,
                                output_callback=lmt_output_callback,
                                input_provider=lmt_input_provider,
                                stop_check=lmt_stop_check,
                            )
                        else:
                            client.run_interactive(
                                script_path=local_file,
                                echo=False,
                                output_callback=lmt_output_callback,
                                input_provider=lmt_input_provider,
                                stop_check=lmt_stop_check,
                            )
                    except KeyboardInterrupt:
                        lmt_stop_requested = True
                        try:
                            client.send_command('run_stop', timeout=0.3)
                        except Exception:
                            pass
                finally:
                    lmt.restore()
                    signal.signal(signal.SIGINT, lmt_original_sigint)
                    if not IS_WINDOWS:
                        try:
                            import termios
                            if old_settings is not None and fd is not None:
                                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                        except Exception:
                            pass

                if lmt_stderr:
                    stderr_text = lmt_stderr.decode('utf-8', errors='replace').strip()
                    if stderr_text:
                        script_abs_path = os.path.abspath(local_file) if local_file else None

                        def lmt_make_file_link(match):
                            file_ref = match.group(1)
                            line_num = match.group(2)
                            if file_ref == "<stdin>":
                                if script_abs_path:
                                    return f'File "{script_abs_path}", line {line_num}'
                                return match.group(0)
                            replx_home = StoreManager.pkg_root()
                            possible_paths = [
                                os.path.join(replx_home, "core", STATE.core or "", "src", file_ref.lstrip('/')),
                                os.path.join(replx_home, "device", STATE.device or "", "src", file_ref.lstrip('/')),
                            ]
                            for path in possible_paths:
                                if os.path.exists(path):
                                    return f'File "{path}", line {line_num}'
                            return match.group(0)

                        linked_text = re.sub(
                            r'File "([^"]+)", line (\d+)',
                            lmt_make_file_link,
                            stderr_text
                        )
                        OutputHelper.print_panel(
                            linked_text,
                            title="Execution Error",
                            border_style="error"
                        )
                return

            stop_requested = False
            pending_input = []
            stderr_buffer = bytearray()
            stdout_ended_with_newline = True
            
            old_settings = None
            fd = None
            if not IS_WINDOWS:
                import tty
                import termios
                fd = sys.stdin.fileno()
                try:
                    old_settings = termios.tcgetattr(fd)
                except Exception:
                    pass
            
            def output_callback(data: bytes, stream_type: str = "stdout"):
                nonlocal stdout_ended_with_newline
                try:
                    if stream_type == "stderr":
                        stderr_buffer.extend(data)
                    else:
                        if not IS_WINDOWS:
                            data = data.replace(b'\r\n', b'\n')
                            data = data.replace(b'\r', b'\n')
                            data = data.replace(b'\n', b'\r\n')
                        else:
                            data = data.replace(b'\r', b'')

                        if data:
                            stdout_ended_with_newline = data.endswith(b'\n')
                            sys.stdout.buffer.write(data)
                            sys.stdout.buffer.flush()
                except Exception:
                    pass
            
            def input_provider() -> bytes:
                nonlocal stop_requested
                
                if pending_input:
                    return pending_input.pop(0)
                
                try:
                    if IS_WINDOWS:
                        import msvcrt
                        if msvcrt.kbhit():
                            ch = msvcrt.getwch()
                            if ch == '\x03':
                                stop_requested = True
                                return CTRL_C
                            elif ch == '\x04':
                                return CTRL_D
                            elif ch == '\r':
                                if echo:
                                    sys.stdout.write('\r\n')
                                    sys.stdout.flush()
                                return b'\r'
                            elif ch == '\n':
                                if echo:
                                    sys.stdout.write('\r\n')
                                    sys.stdout.flush()
                                return b'\r'
                            elif ch == '\x08':
                                if echo:
                                    sys.stdout.write('\b \b')
                                    sys.stdout.flush()
                                return b'\x08'
                            elif ch in ('\x00', '\xe0'):
                                ext = msvcrt.getwch()
                                ext_map = {
                                    'H': b'\x1b[A',
                                    'P': b'\x1b[B',
                                    'M': b'\x1b[C',
                                    'K': b'\x1b[D',
                                }
                                return ext_map.get(ext, b'')
                            else:
                                if echo:
                                    sys.stdout.write(ch)
                                    sys.stdout.flush()
                                return ch.encode('utf-8')
                    else:
                        import select
                        r, _, _ = select.select([sys.stdin], [], [], 0)
                        if r:
                            ch = os.read(sys.stdin.fileno(), 1)
                            if ch == CTRL_C:
                                stop_requested = True
                                return CTRL_C
                            elif ch == b'\n':
                                if echo:
                                    sys.stdout.buffer.write(b'\r\n')
                                    sys.stdout.buffer.flush()
                                return b'\r'
                            else:
                                if echo:
                                    sys.stdout.buffer.write(ch)
                                    sys.stdout.buffer.flush()
                                return ch
                except Exception:
                    pass
                return None
            
            def stop_check() -> bool:
                return stop_requested
            
            original_sigint = signal.getsignal(signal.SIGINT)
            
            def sigint_handler(signum, frame):
                nonlocal stop_requested
                stop_requested = True
                pending_input.append(CTRL_C)
            
            try:
                signal.signal(signal.SIGINT, sigint_handler)
                
                if not IS_WINDOWS:
                    if old_settings is not None:
                        try:
                            tty.setraw(fd)
                        except Exception:
                            pass
                
                try:
                    if device_exec_code:
                        result = client.run_interactive(
                            script_content=device_exec_code,
                            echo=echo,
                            output_callback=output_callback,
                            input_provider=input_provider,
                            stop_check=stop_check
                        )
                    else:
                        result = client.run_interactive(
                            script_path=local_file,
                            echo=echo,
                            output_callback=output_callback,
                            input_provider=input_provider,
                            stop_check=stop_check
                        )
                except KeyboardInterrupt:
                    stop_requested = True
                    try:
                        client.send_command('run_stop', timeout=0.3)
                    except Exception:
                        pass
                    if not stdout_ended_with_newline:
                        print("\n[Interrupted]")
                    return
                
                if not stdout_ended_with_newline:
                    print()
                
                if stderr_buffer:
                    stderr_text = stderr_buffer.decode('utf-8', errors='replace').strip()
                    if stderr_text:
                        script_abs_path = os.path.abspath(local_file) if local_file else None
                        
                        def make_file_link(match):
                            file_ref = match.group(1)
                            line_num = match.group(2)
                            
                            if file_ref == "<stdin>":
                                if script_abs_path:
                                    return f'File "{script_abs_path}", line {line_num}'
                                else:
                                    return match.group(0)
                            else:
                                replx_home = StoreManager.pkg_root()
                                possible_paths = [
                                    os.path.join(replx_home, "core", STATE.core or "", "src", file_ref.lstrip('/')),
                                    os.path.join(replx_home, "device", STATE.device or "", "src", file_ref.lstrip('/')),
                                ]
                                for path in possible_paths:
                                    if os.path.exists(path):
                                        return f'File "{path}", line {line_num}'
                                return match.group(0)
                        
                        linked_text = re.sub(
                            r'File "([^"]+)", line (\d+)',
                            make_file_link,
                            stderr_text
                        )
                        
                        OutputHelper.print_panel(
                            linked_text,
                            title="Execution Error",
                            border_style="error"
                        )
                
            except KeyboardInterrupt:
                stop_requested = True
                try:
                    client.send_command('run_stop', timeout=0.1)
                except Exception:
                    pass
                print("\n[Interrupted by user]")
            except Exception as e:
                error_msg = str(e)
                if 'Not connected' in error_msg:
                    OutputHelper.print_panel(
                        "Not connected to any device.\n\nRun [bright_green]replx --port COM3 setup[/bright_green] first.",
                        title="Connection Required",
                        border_style="error"
                    )
                elif 'busy' in error_msg.lower():
                    OutputHelper.print_panel(
                        f"{error_msg}",
                        title="Device Busy",
                        border_style="warning"
                    )
                else:
                    OutputHelper.print_panel(
                        f"Error: {str(e)}",
                        title="Execution Failed",
                        border_style="error"
                    )
                raise typer.Exit(1)
            finally:
                signal.signal(signal.SIGINT, original_sigint)
                
                if not IS_WINDOWS:
                    try:
                        import termios
                        if old_settings is not None and fd is not None:
                            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    except Exception:
                        pass
            
            return
        
        if device_exec_code:
            result = client.send_command('run', script_content=device_exec_code, detach=True)
        else:
            result = client.send_command('run', script_path=local_file, detach=True)
        
        display_name = remote_path if remote_path else local_file
        OutputHelper.print_panel(
            f"Script [bright_blue]{display_name}[/bright_blue] sent to device.\n\n"
            "[yellow]⚠ Detached mode:[/yellow] Device may still be executing.\n"
            "Other commands may fail until script completes.",
            title="Script Sent",
            border_style="success"
        )
    except typer.Exit:
        raise
    except Exception as e:
        error_msg = str(e)
        if 'Not connected' in error_msg:
            OutputHelper.print_panel(
                "Not connected to any device.\n\nRun [bright_green]replx --port COM3 setup[/bright_green] first.",
                title="Connection Required",
                border_style="error"
            )
        else:
            OutputHelper.format_error_output(error_msg.strip().split('\n'), local_file if local_file else script_file)
        raise typer.Exit(1)
    finally:
        if client:
            try:
                client.__exit__(None, None, None)
            except Exception:
                pass


@app.command(rich_help_panel="Interactive")
def repl(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Enter interactive MicroPython mode on the connected board.

Start a live MicroPython session where you can type code line by line.

[bold cyan]Usage:[/bold cyan]
  replx repl

[bold cyan]In REPL mode:[/bold cyan]
  • Type MicroPython code and press Enter to execute
  • [yellow]>>>>[/yellow] = ready for input
  • [yellow]....[/yellow] = waiting for more (multi-line)
  • Results are printed immediately

[bold cyan]Exit REPL:[/bold cyan]
  Type [cyan]exit()[/cyan] and press Enter

[bold cyan]Example session:[/bold cyan]
  >>> print("hello")
  hello
  >>> 1 + 2
  3
  >>> import os
  >>> os.listdir()
  ['boot.py', 'main.py', 'lib']
  >>> exit()

[bold cyan]Keyboard shortcuts:[/bold cyan]
  [yellow]Ctrl+C[/yellow]    Interrupt running code
  [yellow]Ctrl+D[/yellow]    Soft reset (restart MicroPython)

[bold cyan]Tips:[/bold cyan]
  • REPL = Read-Eval-Print Loop
  • Great for testing and exploring
  • Changes to variables persist until reset
  • For file editing, use [yellow]replx shell[/yellow] instead

[bold cyan]Related:[/bold cyan]
  replx shell             [dim]# Interactive file management[/dim]
  replx -c "code"         [dim]# Single command instead[/dim]"""
        OutputHelper.print_panel(help_text, title="repl", border_style="help")
        console.print()
        raise typer.Exit()
    
    status = _ensure_connected()
    
    port = status.get('port')
    if not port:
        OutputHelper.print_panel(
            "Could not determine port from agent status.",
            title="REPL Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    initial_output = ""
    try:
        with _create_agent_client() as client:
            result = client.send_command('repl_enter')
            if result is None:
                OutputHelper.print_panel(
                    "Failed to enter Friendly REPL.\nNo response from agent.",
                    title="REPL Error",
                    border_style="error"
                )
                raise typer.Exit(1)
            if result.get('error'):
                error_msg = result.get('error', 'Unknown error')
                OutputHelper.print_panel(
                    f"Failed to enter Friendly REPL.\n{error_msg}",
                    title="REPL Error",
                    border_style="error"
                )
                raise typer.Exit(1)
            if not result.get('entered'):
                OutputHelper.print_panel(
                    "Failed to enter Friendly REPL.\nNo prompt received from device.",
                    title="REPL Error",
                    border_style="error"
                )
                raise typer.Exit(1)
            initial_output = result.get('output', '')
    except typer.Exit:
        raise
    except Exception as e:
        OutputHelper.print_panel(
            f"Failed to enter Friendly REPL.\nError: {e}",
            title="REPL Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    OutputHelper.print_panel(
        f"Connected to [bright_yellow]{STATE.device}[/bright_yellow] on [bright_green]{STATE.core}[/bright_green]\n"
        f"Type [cyan]exit()[/cyan] and press Enter to exit REPL mode.",
        title="REPL Mode",
        border_style="mode"
    )
    
    YELLOW = "\033[33m"
    RESET = "\033[0m"
    
    def colorize_prompt(text: str) -> str:
        text = re.sub(r'^(>>>|\.\.\.)', f'{YELLOW}\\1{RESET}', text, flags=re.MULTILINE)
        return text
    
    if initial_output:
        print(colorize_prompt(initial_output), end="", flush=True)
    
    repl_running = [True]
    reader_client = [None]
    pending_echoes = deque()
    pending_echo_lock = threading.Lock()
    pending_output_fragment = [""]

    def _queue_pending_echo(line: str) -> None:
        with pending_echo_lock:
            pending_echoes.append(line + "\r\n")

    def _strip_pending_echo(output: str) -> str:
        if not output:
            return output

        with pending_echo_lock:
            text = pending_output_fragment[0] + output
            normalized = text.replace("\r\n", "\n")
            pending_output_fragment[0] = ""

            if not normalized:
                return ""

            trailing_fragment = "" if normalized.endswith("\n") else normalized.split("\n")[-1]
            lines = normalized.splitlines(keepends=True)
            if trailing_fragment and lines:
                lines = lines[:-1]

            kept: list[str] = []
            for line in lines:
                if pending_echoes and line == pending_echoes[0].replace("\r\n", "\n"):
                    pending_echoes.popleft()
                    continue
                kept.append(line)

            if trailing_fragment:
                if pending_echoes and pending_echoes[0].replace("\r\n", "\n").startswith(trailing_fragment):
                    pending_output_fragment[0] = trailing_fragment
                else:
                    kept.append(trailing_fragment)

            return "".join(kept)
    
    def reader_thread_func():
        try:
            reader_client[0] = _create_agent_client()
            sleep_time = 0.005
            while repl_running[0]:
                try:
                    result = reader_client[0].send_command('repl_read', timeout=0.5)
                    output = result.get('output', '')
                    if output:
                        sleep_time = 0.005
                        if sys.platform == 'darwin':
                            output = _strip_pending_echo(output)
                            if not output:
                                continue
                        output = colorize_prompt(output)
                        if IS_WINDOWS:
                            sys.stdout.buffer.write(output.encode('utf-8').replace(b'\r', b''))
                        else:
                            sys.stdout.buffer.write(output.encode('utf-8'))
                        sys.stdout.buffer.flush()
                    else:
                        sleep_time = min(sleep_time * 1.5, 0.05)
                except Exception:
                    if not repl_running[0]:
                        break
                    sleep_time = 0.05
                time.sleep(sleep_time)
        finally:
            if reader_client[0]:
                try:
                    reader_client[0].__exit__(None, None, None)
                except Exception:
                    pass
    
    reader = threading.Thread(target=reader_thread_func, daemon=True, name='REPL-Output')
    reader.start()
    
    writer_client = _create_agent_client()
    repl_enter_data = '\r'

    _old_console_mode = disable_quick_edit_mode()

    _repl_fd = None
    _repl_old_settings = None
    if not IS_WINDOWS:
        import tty, termios
        _repl_fd = sys.stdin.fileno()
        try:
            _repl_old_settings = termios.tcgetattr(_repl_fd)
            tty.setraw(_repl_fd)
        except Exception:
            pass

    def _repl_getch() -> bytes:
        if IS_WINDOWS:
            return getch()
        try:
            first = os.read(_repl_fd, 1)
            if not first:
                return b''
            need = utf8_need_follow(first[0])
            if need:
                return first + os.read(_repl_fd, need)
            return first
        except Exception:
            return b''

    def _restore_console():
        if _repl_old_settings is not None:
            try:
                termios.tcsetattr(_repl_fd, termios.TCSADRAIN, _repl_old_settings)
            except Exception:
                pass
        restore_console_mode(_old_console_mode)

    import atexit as _atexit
    _atexit.register(_restore_console)

    input_buffer = ""

    try:
        if sys.platform == 'darwin':
            readline_mod = _setup_readline_for_repl()
            while True:
                try:
                    line = input()
                except EOFError:
                    break
                except KeyboardInterrupt:
                    try:
                        writer_client.send_command('repl_write', data='\x03', timeout=1.5, max_retries=1)
                    except Exception:
                        break
                    continue

                if line.strip() == 'exit()':
                    break

                try:
                    if readline_mod and line and (readline_mod.get_current_history_length() == 0 or readline_mod.get_history_item(readline_mod.get_current_history_length()) != line):
                        readline_mod.add_history(line)
                    _queue_pending_echo(line)
                    writer_client.send_command('repl_write', data=line + repl_enter_data, timeout=1.5, max_retries=1)
                except Exception:
                    break
        else:
            while True:
                char = _repl_getch()
                
                if char == b'\x00' or not char:
                    continue
                
                if char == CTRL_D:
                    break
                
                if _is_repl_enter_key(char):
                    if input_buffer.strip() == 'exit()':
                        repl_running[0] = False
                        reader.join(timeout=0.3)
                        try:
                            writer_client.send_command('repl_write', data='\x03', timeout=1.5, max_retries=1)
                        except Exception:
                            pass
                        break
                    input_buffer = ""
                    try:
                        writer_client.send_command('repl_write', data=repl_enter_data, timeout=1.5, max_retries=1)
                    except Exception:
                        break
                elif char == b'\x7f' or char == b'\x08':
                    if input_buffer:
                        input_buffer = input_buffer[:-1]
                    try:
                        writer_client.send_command('repl_write', data=char.decode('utf-8', errors='replace'), timeout=1.5, max_retries=1)
                    except Exception:
                        break
                else:
                    if char >= b' ':
                        try:
                            input_buffer += char.decode('utf-8', errors='ignore')
                        except UnicodeDecodeError:
                            pass
                    try:
                        writer_client.send_command('repl_write', data=char.decode('utf-8', errors='replace'), timeout=1.5, max_retries=1)
                    except Exception:
                        break
                
    except KeyboardInterrupt:
        pass
    finally:
        repl_running[0] = False
        if _repl_old_settings is not None:
            try:
                import termios
                termios.tcsetattr(_repl_fd, termios.TCSADRAIN, _repl_old_settings)
            except Exception:
                pass
        restore_console_mode(_old_console_mode)
        _atexit.unregister(_restore_console)
        reader.join(timeout=0.5)
        
        try:
            writer_client.__exit__(None, None, None)
        except Exception:
            pass
        
        try:
            with _create_agent_client() as client:
                client.send_command('repl_exit')
        except Exception:
            pass
    
    print()


@app.command(rich_help_panel="Interactive")
def shell(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Enter interactive shell for managing files on the device.

Use familiar commands (ls, cd, cat, etc.) without typing "replx" each time.

[bold cyan]Usage:[/bold cyan]
  replx shell

[bold cyan]File commands (same as replx commands):[/bold cyan]
  [yellow]ls[/yellow] [path]              List directory contents
  [yellow]cat[/yellow] file               Show file contents
  [yellow]cp[/yellow] src dest            Copy file/directory
  [yellow]mv[/yellow] src dest            Move/rename
  [yellow]rm[/yellow] [-rf] file          Remove file/directory
  [yellow]mkdir[/yellow] dir              Create directory
  [yellow]touch[/yellow] file             Create empty file

[bold cyan]Board commands:[/bold cyan]
  [yellow]usage[/yellow]                  Show memory/storage usage
  [yellow]exec[/yellow] "code"            Run MicroPython code
  [yellow]run[/yellow] script.py [--text|--hex]  Run script from device
  [yellow]repl[/yellow]                   Enter Python REPL
  [yellow]edit[/yellow] file              Open file in VSCode

[bold cyan]Hardware commands (same as replx commands):[/bold cyan]
  [yellow]whoami[/yellow]                 Show current connection info
  [yellow]wifi[/yellow] [args]                  Manage WiFi
  [yellow]ble[/yellow] [args]                   Manage BLE
  [yellow]gpio[/yellow] [args]                  GPIO read/write/monitor
  [yellow]adc[/yellow] [args]                   ADC read/scope
  [yellow]pwm[/yellow] [args]                   PWM write/monitor
  [yellow]uart[/yellow] [args]                  UART open/read/write
  [yellow]spi[/yellow] [args]                   SPI open/read/write
  [yellow]i2c[/yellow] [args]                   I2C scan/read/write

[bold cyan]Navigation commands (shell-only):[/bold cyan]
  [yellow]cd[/yellow] [path]              Change directory (no arg → root /)
  [yellow]pwd[/yellow]                    Print current directory
  [yellow]clear[/yellow]                  Clear screen

[bold cyan]Other:[/bold cyan]
  [yellow]exit[/yellow]                   Exit shell
  [yellow]help[/yellow] [command]         Show help

[bold cyan]Example session:[/bold cyan]
  [ticle]:/ > ls
  [dim]  boot.py  main.py  lib/[/dim]
  [ticle]:/ > cat main.py
  [ticle]:/ > exec "import sys; print(sys.version)"
  [ticle]:/ > run main.py
  [ticle]:/ > exit

[bold cyan]Tips:[/bold cyan]
  • Shell stays connected - faster than running replx repeatedly
  • Tab key not supported (use full filenames)
  • Type 'help cmd' for help on any command
  • Current directory is remembered until you exit
  • Use 'replx get/put' outside shell for file transfers between PC and device

[bold cyan]Related:[/bold cyan]
  replx repl             [dim]# Interactive MicroPython instead[/dim]"""
        OutputHelper.print_panel(help_text, title="shell", border_style="help")
        console.print()
        raise typer.Exit()

    _ensure_connected()

    # shell은 항상 fg 연결이 필요하다. --port가 명시된 경우 해당 포트를 fg로 전환한다.
    _global_opts = _get_global_options()
    _explicit_port = _global_opts.get('port')
    if _explicit_port:
        from ..agent.client import AgentClient as _AgentClient
        _agent_port = _get_current_agent_port()
        try:
            _result = _AgentClient(port=_agent_port).send_command(
                'session_switch_fg', port=_explicit_port, timeout=3.0
            )
            if not (_result and _result.get('success')):
                _err = (_result or {}).get('error', 'Unknown error')
                OutputHelper.print_panel(
                    f"Failed to switch foreground to [bright_blue]{_explicit_port}[/bright_blue]: {_err}",
                    title="Shell Error",
                    border_style="error"
                )
                raise typer.Exit(1)
            STATE.core = _result.get('core', STATE.core)
            STATE.device = _result.get('device', STATE.device)
            STATE.version = _result.get('version', STATE.version)
            STATE.device_root_fs = _result.get('device_root_fs', STATE.device_root_fs)
        except typer.Exit:
            raise
        except Exception as _e:
            OutputHelper.print_panel(
                f"Failed to switch foreground: {_e}",
                title="Shell Error",
                border_style="error"
            )
            raise typer.Exit(1)

    from .device import usage
    from .file import cat, cp, ls, mkdir, mv, rm, touch
    from .gpio import gpio_cmd
    from .adc import adc_cmd
    from .pwm import pwm_cmd
    from .uart import uart_cmd
    from .spi import spi_cmd
    from .i2c import i2c_cmd
    from .i2s import i2s_cmd
    from .ws2812 import ws2812_cmd
    from .ble import ble
    from .utility import whoami

    SHELL_COMMANDS = {
        'ls', 'cat', 'cp', 'mv', 'rm', 'mkdir', 'touch', 'usage', 'exec', 'repl', 'run',
        'cd', 'pwd', 'clear', 'edit', 'exit', 'help', '?', 'wifi',
        'whoami', 'ble', 'gpio', 'adc', 'pwm', 'uart', 'spi', 'i2c', 'i2s', 'ws2812',
    }

    EXCLUDED_COMMANDS = {
        'version', 'setup', 'scan', 'shell', 'format',
        'init', 'install', 'update', 'search',
        'get', 'put', 'reset', 'mip',
    }

    def _hw_parse(tokens):
        """Split shlex tokens into (pos_args, opts) where opts maps '--flag' -> value_or_True."""
        boolean_options = {
            '--addr16', '--any', '--chunk', '--hex', '--lsb', '--slave', '--target', '--text',
        }
        pos = []
        opts = {}
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t.startswith('-'):
                if t in boolean_options:
                    opts[t] = True
                    i += 1
                    continue
                if '=' in t:
                    key, val = t.split('=', 1)
                    opts[key] = val
                    i += 1
                else:
                    nxt = tokens[i + 1] if i + 1 < len(tokens) else None
                    if nxt is not None and not nxt.startswith('-'):
                        opts[t] = nxt
                        i += 2
                    else:
                        opts[t] = True
                        i += 1
            else:
                pos.append(t)
                i += 1
        return pos, opts
    
    current_path = '/'

    def _cleanup_windows_batch_prompt_artifacts() -> None:
        if not IS_WINDOWS:
            return
        try:
            import msvcrt
            while msvcrt.kbhit():
                msvcrt.getwch()
        except Exception:
            pass
        try:
            # Remove any lingering "Terminate batch job (Y/N)?" artifact line.
            sys.stdout.write('\r\x1b[2K\r')
            sys.stdout.flush()
        except Exception:
            pass
    
    def print_prompt():
        print(f"\n[{STATE.device}]:{current_path} > ", end="", flush=True)

    def print_shell_help(cmd: str):
        shell_console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        
        shell_only_help = {
            "cd": """\
[bold cyan]Usage:[/bold cyan]
  cd [yellow]DIRECTORY[/yellow]

[bold cyan]Description:[/bold cyan]
  Change current working directory

[bold cyan]Examples:[/bold cyan]
  cd /lib      [dim]# Change to /lib[/dim]
  cd ..        [dim]# Go to parent directory[/dim]
  cd subdir    [dim]# Enter subdirectory[/dim]""",
            
            "pwd": """\
[bold cyan]Usage:[/bold cyan]
  pwd

[bold cyan]Description:[/bold cyan]
  Print current working directory""",
            
            "clear": """\
[bold cyan]Usage:[/bold cyan]
  clear

[bold cyan]Description:[/bold cyan]
  Clear the terminal screen""",
            
            "exit": """\
[bold cyan]Usage:[/bold cyan]
  exit

[bold cyan]Description:[/bold cyan]
  Exit the shell and return to normal terminal""",
            
            "edit": """\
[bold cyan]Usage:[/bold cyan]
    edit [yellow]FILE[/yellow]

[bold cyan]Description:[/bold cyan]
  Edit a file from device in VSCode
  - Downloads file to .temp folder
  - Opens in VSCode and waits for close
  - Prompts to upload if file was modified

[bold cyan]Examples:[/bold cyan]
    edit main.py        [dim]# Edit main.py[/dim]
    edit /lib/utils.py  [dim]# Edit with absolute path[/dim]""",
            
            "help": """\
[bold cyan]Usage:[/bold cyan]
  help [yellow][COMMAND][/yellow]
  ? [yellow][COMMAND][/yellow]

[bold cyan]Description:[/bold cyan]
  Show help information

[bold cyan]Examples:[/bold cyan]
  help       [dim]# Show all commands[/dim]
  help ls    [dim]# Show help for ls command[/dim]""",
        }
        shell_only_help["?"] = shell_only_help["help"]
        
        if cmd in shell_only_help:
            shell_console.print(Panel(shell_only_help[cmd], border_style=OutputHelper._resolve_category_color('neutral'), box=get_panel_box(), width=CONSOLE_WIDTH))
            return
        
        try:
            if cmd == "ls":
                ls(path="/", recursive=False, show_help=True)
            elif cmd == "cat":
                cat(remote="", show_help=True)
            elif cmd == "cp":
                cp(args=None, recursive=False, show_help=True)
            elif cmd == "mv":
                mv(args=None, recursive=False, show_help=True)
            elif cmd == "rm":
                rm(args=None, recursive=False, show_help=True)
            elif cmd == "mkdir":
                mkdir(remotes=None, show_help=True)
            elif cmd == "touch":
                touch(remotes=None, show_help=True)
            elif cmd == "usage":
                usage(show_help=True)
            elif cmd == "exec":
                exec_cmd(command="", show_help=True)
            elif cmd == "repl":
                repl(show_help=True)
            elif cmd == "run":
                shell_console.print(Panel("""\
Run a script from device storage.
In shell mode, 'run' always runs from device (equivalent to 'replx run -d').

[bold cyan]Usage:[/bold cyan]
  run [yellow]SCRIPT_FILE[/yellow] [[yellow]--text[/yellow]|[yellow]--hex[/yellow]]

[bold cyan]Arguments:[/bold cyan]
  [yellow]SCRIPT_FILE[/yellow]  Script file path on device [red][required][/red]

[bold cyan]Options:[/bold cyan]
  [yellow]--text[/yellow]       Line input mode: display output as text
  [yellow]--hex[/yellow]        Line input mode: display output as hex bytes

[bold cyan]Examples:[/bold cyan]
  run main.py           [dim]# Run /main.py from device[/dim]
  run main.py --text    [dim]# Run and show output as text lines[/dim]
  run lib/test.py --hex [dim]# Run and show output as hex[/dim]
  run t1.mpy            [dim]# Run .mpy file from device[/dim]

[bold yellow]Note:[/bold yellow]
  In shell mode, -e/--echo and -n/--non-interactive are not available.
  Use 'replx run' directly for those options.""", border_style=OutputHelper._resolve_category_color('neutral'), box=get_panel_box(), width=CONSOLE_WIDTH))
            elif cmd == "wifi":
                shell_console.print(Panel("""\
Manage WiFi connection.

[bold cyan]Usage:[/bold cyan]
  wifi                          [dim]# Show WiFi status[/dim]
  wifi connect [yellow]SSID PW[/yellow]         [dim]# Connect and save config[/dim]
  wifi connect                  [dim]# Connect using saved credentials[/dim]
  wifi off                      [dim]# Disable WiFi[/dim]
  wifi scan                     [dim]# Scan for networks[/dim]
  wifi boot on                  [dim]# Enable auto-connect on boot[/dim]
  wifi boot off                 [dim]# Disable auto-connect on boot[/dim]

[bold cyan]Examples:[/bold cyan]
  wifi                               [dim]# Check status[/dim]
  wifi connect MyNetwork secret123   [dim]# Connect[/dim]
  wifi scan                          [dim]# Find networks[/dim]""", border_style=OutputHelper._resolve_category_color('neutral'), box=get_panel_box(), width=CONSOLE_WIDTH))
            elif cmd == "whoami":
                whoami(show_help=True)
            elif cmd == "ble":
                ble(args=None, show_help=True)
            elif cmd == "gpio":
                gpio_cmd(args=None, show_help=True)
            elif cmd == "adc":
                adc_cmd(args=None, show_help=True)
            elif cmd == "pwm":
                pwm_cmd(args=None, show_help=True)
            elif cmd == "uart":
                uart_cmd(args=None, show_help=True)
            elif cmd == "spi":
                spi_cmd(args=None, show_help=True)
            elif cmd == "i2c":
                i2c_cmd(args=None, show_help=True)
            elif cmd == "i2s":
                i2s_cmd(args=None, show_help=True)
            elif cmd == "ws2812":
                ws2812_cmd(args=None, show_help=True)
            else:
                shell_console.print(f"No help available for '{cmd}'")
        except typer.Exit:
            pass 

    def run_shell_cmd(cmdline):
        nonlocal current_path

        args = shlex.split(cmdline)
        if not args:
            return
        cmd = args[0]
        
        if cmd in EXCLUDED_COMMANDS:
            _suggestions = {
                'get': "replx get",
                'put': "replx put",
                'reset': "replx reset",
                'mip': "replx mip",
            }
            _hint = f"\n\nUse [bright_blue]{_suggestions[cmd]}[/bright_blue] instead." if cmd in _suggestions else ""
            OutputHelper.print_panel(
                f"[yellow]'{cmd}'[/yellow] is not available in shell mode.{_hint}",
                title="Command Not Available",
                border_style="warning"
            )
            return
        
        if cmd not in SHELL_COMMANDS:
            OutputHelper.print_panel(
                f"[red]'{cmd}'[/red] is not a valid command.\n\nType [bright_blue]help[/bright_blue] or [bright_blue]?[/bright_blue] to see available commands.",
                title="Unknown Command",
                border_style="error"
            )
            return

        try:
            if cmd == "help" or cmd == "?":
                if len(args) > 1:
                    print_shell_help(args[1])
                else:
                    shell_console = OutputHelper.make_console(width=CONSOLE_WIDTH)
                    help_text = """\
[bold cyan]Commands:[/bold cyan]
  [yellow]ls[/yellow] [path] [-r]            List files/directories
  [yellow]cat[/yellow] <file>          Display file contents
  [yellow]cp[/yellow] <src...> <dst>   Copy files (use -r for directories)
  [yellow]mv[/yellow] <src...> <dst>   Move/rename files (use -r for directories)
  [yellow]rm[/yellow] <files...>       Remove files (use -r for directories)
  [yellow]mkdir[/yellow] <dirs...>     Create directories
  [yellow]touch[/yellow] <files...>    Create empty files
  [yellow]usage[/yellow]               Show memory/storage usage
  [yellow]exec[/yellow] <code>         Execute MicroPython code
  [yellow]repl[/yellow]                Enter Python REPL
  [yellow]run[/yellow] <script> [--text|--hex]  Run script from device
  [yellow]wifi[/yellow] [args]               Manage WiFi
  [yellow]whoami[/yellow]              Show current connection info
  [yellow]ble[/yellow] [args]                Manage BLE
  [yellow]gpio[/yellow] [args]               GPIO read/write/monitor
  [yellow]adc[/yellow] [args]                ADC read/scope
  [yellow]pwm[/yellow] [args]                PWM write/monitor
  [yellow]uart[/yellow] [args]               UART open/read/write
  [yellow]spi[/yellow] [args]                SPI open/read/write
  [yellow]i2c[/yellow] [args]                I2C scan/read/write
  [yellow]i2s[/yellow] [args]                I2S tone/read/scope
  [yellow]ws2812[/yellow] [args]             WS2812 matrix write
  [yellow]cd[/yellow] [dir]                 Change directory (no arg → /)
  [yellow]pwd[/yellow]                 Print current directory
  [yellow]clear[/yellow]               Clear screen
  [yellow]edit[/yellow] <file>         Edit file in VSCode
  [yellow]exit[/yellow]                Exit shell

[dim]Type 'help <command>' for detailed help on a specific command.[/dim]"""
                    shell_console.print(Panel(help_text, title="Available Commands", title_align="left", border_style=OutputHelper._resolve_category_color('data'), box=get_panel_box(), width=CONSOLE_WIDTH))
                return
                
            elif cmd == "exit":
                raise SystemExit()
                
            elif cmd == "pwd":
                if "--help" in args or "-h" in args:
                    print_shell_help("pwd")
                    return
                print(current_path)
                return
                
            elif cmd == "clear":
                if "--help" in args or "-h" in args:
                    print_shell_help("clear")
                    return
                OutputHelper._console.clear()
                return
                
            elif cmd == "cd":
                if "--help" in args or "-h" in args:
                    print_shell_help("cd")
                    return

                if len(args) == 1:
                    current_path = '/'
                    return

                if len(args) != 2:
                    OutputHelper.print_panel(
                        "[bold cyan]Usage:[/bold cyan] cd [yellow]DIRECTORY[/yellow]",
                        title="cd",
                        border_style="warning"
                    )
                    return
                
                new_path = posixpath.normpath(posixpath.join(current_path, args[1]))
                try:
                    client = _create_agent_client()
                    result = client.send_command('is_dir', path=new_path)
                    is_dir = result if isinstance(result, bool) else result.get('is_dir', False)
                    if is_dir:
                        current_path = new_path
                    else:
                        OutputHelper.print_panel(
                            f"[yellow]{args[1]}[/yellow]: Not a directory",
                            title="cd",
                            border_style="error"
                        )
                except Exception:
                    OutputHelper.print_panel(
                        f"[yellow]{args[1]}[/yellow]: No such directory",
                        title="cd",
                        border_style="error"
                    )
                return
                
            elif cmd == "ls":
                if "--help" in args or "-h" in args:
                    print_shell_help("ls")
                    return
                    
                path_arg = current_path
                recursive = False
                
                for arg in args[1:]:
                    if arg in ("-r", "--recursive"):
                        recursive = True
                    elif not arg.startswith('-'):
                        path_arg = posixpath.normpath(posixpath.join(current_path, arg))
                
                ls(path=path_arg, recursive=recursive, show_help=False)
                return
                
            elif cmd == "cat":
                if "--help" in args or "-h" in args:
                    print_shell_help("cat")
                    return
                    
                number = False
                lines_opt = None
                file_arg = None
                
                i = 1
                while i < len(args):
                    arg = args[i]
                    if arg in ("-n", "--number"):
                        number = True
                    elif arg in ("-L", "--lines"):
                        if i + 1 < len(args):
                            lines_opt = args[i + 1]
                            i += 1
                    elif not arg.startswith('-'):
                        file_arg = arg
                    i += 1
                
                if not file_arg:
                    print("Usage: cat <file>")
                    return
                    
                remote = posixpath.normpath(posixpath.join(current_path, file_arg))
                cat(remote=remote, number=number, lines=lines_opt, show_help=False)
                return
                
            elif cmd == "cp":
                if "--help" in args or "-h" in args:
                    print_shell_help("cp")
                    return

                recursive = False
                file_args = []

                for arg in args[1:]:
                    if arg.startswith('-'):
                        if 'r' in arg:
                            recursive = True
                    else:
                        file_args.append(arg)

                if len(file_args) < 2:
                    OutputHelper.print_panel(
                        "[bold cyan]Usage:[/bold cyan] cp [yellow][-r][/yellow] [yellow]SRC...[/yellow] [yellow]DST[/yellow]",
                        title="cp",
                        border_style="warning"
                    )
                    return

                abs_args = [posixpath.normpath(posixpath.join(current_path, arg)) for arg in file_args]
                cp(args=abs_args, recursive=recursive, show_help=False)
                return
                
            elif cmd == "mv":
                if "--help" in args or "-h" in args:
                    print_shell_help("mv")
                    return

                recursive = False
                file_args = []

                for arg in args[1:]:
                    if arg.startswith('-'):
                        if 'r' in arg:
                            recursive = True
                    else:
                        file_args.append(arg)

                if len(file_args) < 2:
                    OutputHelper.print_panel(
                        "[bold cyan]Usage:[/bold cyan] mv [yellow][-r][/yellow] [yellow]SRC...[/yellow] [yellow]DST[/yellow]",
                        title="mv",
                        border_style="warning"
                    )
                    return

                abs_args = [posixpath.normpath(posixpath.join(current_path, arg)) for arg in file_args]
                mv(args=abs_args, recursive=recursive, show_help=False)
                return
                
            elif cmd == "rm":
                if "--help" in args or "-h" in args:
                    print_shell_help("rm")
                    return
                    
                recursive = False
                force = False
                file_args = []

                for arg in args[1:]:
                    if arg.startswith('-'):
                        if 'r' in arg:
                            recursive = True
                        if 'f' in arg:
                            force = True
                    else:
                        file_args.append(arg)

                if not file_args:
                    OutputHelper.print_panel(
                        "[bold cyan]Usage:[/bold cyan] rm [yellow][-rf][/yellow] [yellow]FILES...[/yellow]",
                        title="rm",
                        border_style="warning"
                    )
                    return

                abs_args = [posixpath.normpath(posixpath.join(current_path, arg)) for arg in file_args]
                rm(args=abs_args, recursive=recursive, force=force, show_help=False)
                return
                
            elif cmd == "mkdir":
                if "--help" in args or "-h" in args:
                    print_shell_help("mkdir")
                    return
                    
                if len(args) < 2:
                    OutputHelper.print_panel(
                        "[bold cyan]Usage:[/bold cyan] mkdir [yellow]DIRS...[/yellow]",
                        title="mkdir",
                        border_style="warning"
                    )
                    return
                
                abs_args = [posixpath.normpath(posixpath.join(current_path, arg)) for arg in args[1:]]
                mkdir(remotes=abs_args, show_help=False)
                return
                
            elif cmd == "touch":
                if "--help" in args or "-h" in args:
                    print_shell_help("touch")
                    return
                    
                if len(args) < 2:
                    OutputHelper.print_panel(
                        "[bold cyan]Usage:[/bold cyan] touch [yellow]FILES...[/yellow]",
                        title="touch",
                        border_style="warning"
                    )
                    return
                
                abs_args = [posixpath.normpath(posixpath.join(current_path, arg)) for arg in args[1:]]
                touch(remotes=abs_args, show_help=False)
                return
                
            elif cmd == "usage":
                if "--help" in args or "-h" in args:
                    print_shell_help("usage")
                    return
                usage(show_help=False)
                return
                
            elif cmd == "exec":
                if "--help" in args or "-h" in args:
                    print_shell_help("exec")
                    return
                    
                if len(args) < 2:
                    OutputHelper.print_panel(
                        "[bold cyan]Usage:[/bold cyan] exec [yellow]\"CODE\"[/yellow]",
                        title="exec",
                        border_style="warning"
                    )
                    return
                
                code = ' '.join(args[1:])
                exec_cmd(command=code, show_help=False)
                return
                
            elif cmd == "repl":
                if "--help" in args or "-h" in args:
                    print_shell_help("repl")
                    return
                repl(show_help=False)
                _cleanup_windows_batch_prompt_artifacts()
                return
                
            elif cmd == "run":
                if "--help" in args or "-h" in args:
                    print_shell_help("run")
                    return

                _run_unsupported = [
                    ("-e", "--echo"),
                    ("-n", "--non-interactive"),
                ]
                for _flags in _run_unsupported:
                    if any(f in args for f in _flags):
                        _flag_str = '/'.join(_flags)
                        OutputHelper.print_panel(
                            f"[yellow]{_flag_str}[/yellow] is not available in shell mode.",
                            title="run",
                            border_style="warning"
                        )
                        return

                _line_text = "--text" in args
                _line_hex = "--hex" in args
                script_file = next((a for a in args[1:] if not a.startswith('-')), None)
                if not script_file:
                    OutputHelper.print_panel(
                        "Missing script file.\n\n"
                        "[bold cyan]Usage:[/bold cyan] run [yellow]SCRIPT_FILE[/yellow]",
                        title="run",
                        border_style="warning"
                    )
                    return
                if script_file.startswith('/'):
                    remote_path = script_file
                else:
                    remote_path = posixpath.normpath(posixpath.join(current_path, script_file))
                
                run(
                    script_file=remote_path,
                    non_interactive=False,
                    echo=False,
                    device=True,
                    line_text=_line_text,
                    line_hex=_line_hex,
                    show_help=False,
                )
                _cleanup_windows_batch_prompt_artifacts()
                return
                
            elif cmd == "edit":
                if "--help" in args or "-h" in args:
                    print_shell_help("edit")
                    return

                if len(args) != 2:
                    OutputHelper.print_panel(
                        "[bold cyan]Usage:[/bold cyan] edit [yellow]FILE[/yellow]",
                        title="edit",
                        border_style="warning"
                    )
                    return

                file_arg = args[1]
                if file_arg.startswith('/'):
                    remote_path = file_arg
                else:
                    remote_path = posixpath.normpath(posixpath.join(current_path, file_arg))
                
                temp_dir = _make_edit_temp_dir()
                
                filename = posixpath.basename(remote_path)
                local_path = os.path.join(temp_dir, filename)
                
                try:
                    client = _create_agent_client()

                    try:
                        result = client.send_command('stat', path=remote_path)
                        file_exists_on_device = True
                        is_dir = result.get('is_dir', False) if isinstance(result, dict) else False
                    except Exception as e:
                        stat_error = str(e)
                        if not _is_missing_file_error(stat_error):
                            OutputHelper.print_panel(
                                f"Could not check [yellow]{remote_path}[/yellow]: {stat_error}",
                                title="edit",
                                border_style="error"
                            )
                            return
                        file_exists_on_device = False
                        is_dir = False

                    if is_dir:
                        OutputHelper.print_panel(
                            f"[yellow]'{remote_path}'[/yellow] is a directory, not a file.",
                            title="edit",
                            border_style="error"
                        )
                        return

                    if file_exists_on_device:
                        try:
                            result = client.send_command('get_to_local', remote_path=remote_path, local_path=local_path)
                            if isinstance(result, dict) and result.get('error'):
                                raise RuntimeError(result.get('error'))
                            OutputHelper.print_panel(
                                f"Downloaded: [yellow]{remote_path}[/yellow]",
                                title="edit",
                                border_style="success"
                            )
                        except Exception as e:
                            if not _is_missing_file_error(e):
                                OutputHelper.print_panel(
                                    f"Could not download [yellow]{remote_path}[/yellow]: {e}",
                                    title="edit",
                                    border_style="error"
                                )
                                return
                            file_exists_on_device = False
                            with open(local_path, 'w', encoding='utf-8') as f:
                                pass
                            OutputHelper.print_panel(
                                f"Creating new file: [yellow]{remote_path}[/yellow]",
                                title="edit",
                                border_style='neutral'
                            )
                    else:
                        with open(local_path, 'w', encoding='utf-8') as f:
                            pass
                        OutputHelper.print_panel(
                            f"Creating new file: [yellow]{remote_path}[/yellow]",
                            title="edit",
                            border_style='neutral'
                        )
                    
                    with open(local_path, 'rb') as f:
                        original_hash = hashlib.md5(f.read()).hexdigest()
                    
                    OutputHelper.print_panel(
                        "Opening in VSCode... (close the file tab to continue)",
                        title="edit",
                        border_style='neutral'
                    )
                    opened, editor_error = _open_editor_and_wait(local_path, original_hash)
                    if not opened:
                        detail = editor_error or "Unknown error"
                        OutputHelper.print_panel(
                            f"Could not open editor: {detail}",
                            title="edit",
                            border_style="error"
                        )
                        return
                    
                    with open(local_path, 'rb') as f:
                        new_hash = hashlib.md5(f.read()).hexdigest()

                    should_offer_upload = (new_hash != original_hash) or (not file_exists_on_device)

                    if not should_offer_upload:
                        OutputHelper.print_panel(
                            "No changes detected.",
                            title="edit",
                            border_style='neutral'
                        )
                    else:
                        prompt = (
                            "File was modified. Save changes to board? [y/N]: "
                            if file_exists_on_device
                            else "Save new file to board? [y/N]: "
                        )
                        print(prompt, end="", flush=True)
                        response = sys.stdin.buffer.readline().decode(errors='replace').strip().lower()

                        if response in ('y', 'yes'):
                            result = client.send_command('put_from_local', local_path=local_path, remote_path=remote_path)
                            if isinstance(result, dict) and result.get('error'):
                                OutputHelper.print_panel(
                                    f"Upload failed: {result.get('error')}",
                                    title="edit",
                                    border_style="error"
                                )
                            else:
                                file_size = os.path.getsize(local_path)
                                OutputHelper.print_panel(
                                    f"Uploaded: [yellow]{remote_path}[/yellow] ({file_size} bytes)",
                                    title="edit",
                                    border_style="success"
                                )
                        else:
                            OutputHelper.print_panel(
                                "Changes discarded.",
                                title="edit",
                                border_style='neutral'
                            )
                
                finally:
                    try:
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)
                    except Exception:
                        pass
                    _cleanup_windows_batch_prompt_artifacts()
                return
            
            elif cmd == "wifi":
                if "--help" in args or "-h" in args:
                    print_shell_help("wifi")
                    return

                from replx.cli.commands.wifi import wifi

                wifi(args=args[1:] if len(args) > 1 else None, show_help=False)
                return

            elif cmd == "whoami":
                if "--help" in args or "-h" in args:
                    print_shell_help("whoami")
                    return
                whoami(show_help=False)
                return

            elif cmd == "ble":
                if "--help" in args or "-h" in args:
                    print_shell_help("ble")
                    return
                ble(args=args[1:] if len(args) > 1 else None, show_help=False)
                return

            elif cmd == "gpio":
                if "--help" in args or "-h" in args:
                    print_shell_help("gpio")
                    return
                pos, opts = _hw_parse(args[1:])
                gpio_cmd(
                    args=pos or None,
                    expr=opts.get('--expr') or None,
                    timeout=int(opts.get('--timeout', 100)),
                    interval=int(opts.get('--interval-ms', opts.get('--interval', 10))),
                    repeat=int(opts.get('--repeat', 1)),
                    show_help=False,
                )
                return

            elif cmd == "adc":
                if "--help" in args or "-h" in args:
                    print_shell_help("adc")
                    return
                pos, opts = _hw_parse(args[1:])
                adc_cmd(
                    args=pos or None,
                    repeat=int(opts.get('--repeat', 1)),
                    interval=int(opts.get('--interval-ms', opts.get('--interval', 1000))),
                    vref=float(opts.get('--vref', 3.3)),
                    sample=int(opts.get('--sample', 10)),
                    show_help=False,
                )
                return

            elif cmd == "pwm":
                if "--help" in args or "-h" in args:
                    print_shell_help("pwm")
                    return
                pos, opts = _hw_parse(args[1:])
                _freq = opts.get('--freq')
                _duty = opts.get('--duty')
                _duty_pct = opts.get('--duty-percent')
                _duty_u16 = opts.get('--duty-u16')
                _pulse_us = opts.get('--pulse-us')
                _repeat = opts.get('--repeat') or opts.get('-n')
                pwm_cmd(
                    args=pos or None,
                    freq=float(_freq) if _freq is not None and _freq is not True else None,
                    duty=str(_duty) if _duty is not None and _duty is not True else None,
                    duty_percent=float(_duty_pct) if _duty_pct is not None and _duty_pct is not True else None,
                    duty_u16=int(_duty_u16) if _duty_u16 is not None and _duty_u16 is not True else None,
                    pulse_us=float(_pulse_us) if _pulse_us is not None and _pulse_us is not True else None,
                    timeout_ms=int(opts.get('--timeout', 2000)),
                    repeat=int(_repeat) if _repeat is not None and _repeat is not True else 1,
                    show_help=False,
                )
                return

            elif cmd == "uart":
                if "--help" in args or "-h" in args:
                    print_shell_help("uart")
                    return
                pos, opts = _hw_parse(args[1:])
                _timeout = opts.get('--timeout')
                _rx_bytes = opts.get('--rx-bytes')
                uart_cmd(
                    args=pos or None,
                    tx=opts.get('--tx') or None,
                    rx=opts.get('--rx') or None,
                    baud=int(opts.get('--baud', 115200)),
                    bits=int(opts.get('--bits', 8)),
                    parity=opts.get('--parity', 'none') if opts.get('--parity') is not True else 'none',
                    stop=int(opts.get('--stop', 1)),
                    timeout_ms=int(_timeout) if _timeout is not None and _timeout is not True else None,
                    any_mode=bool(opts.get('--any', False)),
                    count_n=int(_rx_bytes) if _rx_bytes is not None and _rx_bytes is not True else None,
                    width=int(opts.get('--width', 16)),
                    idle_ms=int(opts.get('--idle', 0)),
                    text_mode=bool(opts.get('--text', False)),
                    chunk_mode=bool(opts.get('--chunk', False)),
                    hex_mode=bool(opts.get('--hex', False)),
                    show_help=False,
                )
                return

            elif cmd == "spi":
                if "--help" in args or "-h" in args:
                    print_shell_help("spi")
                    return
                pos, opts = _hw_parse(args[1:])
                _slave_buf = opts.get('--slave-buf')
                spi_cmd(
                    args=pos or None,
                    sck=opts.get('--sck') or None,
                    mosi=opts.get('--mosi') or None,
                    miso=opts.get('--miso') or None,
                    baud=int(opts.get('--baud', 1_000_000)),
                    mode=int(opts.get('--mode', 0)),
                    bits=int(opts.get('--bits', 8)),
                    lsb=bool(opts.get('--lsb', False)),
                    cs=opts.get('--cs') or None,
                    fill=opts.get('--fill', '00') if opts.get('--fill') is not True else '00',
                    text_mode=bool(opts.get('--text', False)),
                    slave=bool(opts.get('--slave', False)),
                    slave_buf=int(_slave_buf) if _slave_buf is not None and _slave_buf is not True else 8192,
                    timeout_ms=int(opts.get('--timeout', 10_000)),
                    show_help=False,
                )
                return

            elif cmd == "i2c":
                if "--help" in args or "-h" in args:
                    print_shell_help("i2c")
                    return
                pos, opts = _hw_parse(args[1:])
                _repeat = opts.get('--repeat') or opts.get('-n')
                _mem_size = opts.get('--mem-size')
                i2c_cmd(
                    args=pos or None,
                    sda=opts.get('--sda') or None,
                    scl=opts.get('--scl') or None,
                    freq=int(opts.get('--freq', 400000)),
                    target=bool(opts.get('--target', False)),
                    addr=opts.get('--addr') or None,
                    mem_size=int(_mem_size) if _mem_size is not None and _mem_size is not True else 256,
                    addr16=bool(opts.get('--addr16', False)),
                    repeat=int(_repeat) if _repeat is not None and _repeat is not True else 1,
                    interval=int(opts.get('--interval-ms', opts.get('--interval', 1000))),
                    show_help=False,
                )
                return

            elif cmd == "i2s":
                if "--help" in args or "-h" in args:
                    print_shell_help("i2s")
                    return
                pos, opts = _hw_parse(args[1:])
                i2s_cmd(
                    args=pos or None,
                    sck=opts.get('--sck') or None,
                    ws=opts.get('--ws') or None,
                    sd=opts.get('--sd') or None,
                    i2s_id=int(opts.get('--id', 0)),
                    rate=int(opts.get('--rate', 16000)),
                    ibuf=int(opts.get('--ibuf', 4096)),
                    frames=int(opts.get('--frames', 256)),
                    rx_bits=int(opts.get('--rx-bits', 32)),
                    gain=float(opts.get('--gain', 16.0)),
                    repeat=int(opts.get('--repeat', opts.get('-n', 1))),
                    interval_ms=int(opts.get('--interval', opts.get('--interval-ms', 20))),
                    amplitude=float(opts.get('--amplitude', 0.25)),
                    sample=int(opts.get('--sample', 20)),
                    show_help=False,
                )
                return

            elif cmd == "ws2812":
                if "--help" in args or "-h" in args:
                    print_shell_help("ws2812")
                    return
                pos, opts = _hw_parse(args[1:])
                ws2812_cmd(
                    args=pos or None,
                    width=int(opts.get('--width', 16)),
                    height=int(opts.get('--height', 16)),
                    layout=str(opts.get('--layout', 'row-major')),
                    state_machine=int(opts.get('--sm', 0)),
                    show_help=False,
                )
                return

        except typer.Exit:
            pass
        except SystemExit:
            raise
        except Exception as e:
            OutputHelper.print_panel(
                str(e),
                title="Error",
                border_style="error"
            )
    
    header_content = f"Connected to [bright_yellow]{STATE.device}[/bright_yellow] on [bright_green]{STATE.core}[/bright_green]\n\n"
    header_content += "Type [bright_blue]help[/bright_blue] or [bright_blue]?[/bright_blue] to see available commands\n"
    header_content += "Type [bright_blue]exit[/bright_blue] to quit shell"
    
    OutputHelper.print_panel(
        header_content,
        title="Interactive Shell",
        border_style="mode"
    )

    shell_running = True
    
    def signal_handler(sig, frame):
        print("\nType 'exit' to quit shell.")
    
    old_handler = signal.signal(signal.SIGINT, signal_handler)
    
    try:
        while shell_running:
            try:
                _cleanup_windows_batch_prompt_artifacts()
                print_prompt()
                line = sys.stdin.buffer.readline().decode(errors='replace').rstrip()
                if not line:
                    continue
                try:
                    run_shell_cmd(line)
                except SystemExit:
                    break
                except Exception as e:
                    OutputHelper.print_panel(
                        str(e),
                        title="Error",
                        border_style="error"
                    )
            except EOFError:
                break
            
    finally:
        signal.signal(signal.SIGINT, old_handler)
        OutputHelper.print_panel(
            "Shell session ended.",
            title="Exit Shell",
            border_style="mode"
        )


@app.command(rich_help_panel="Device Management")
def reset(
    hard: bool = typer.Option(False, "--hard", help="Hard reset (full hardware reset)"),
    soft: bool = typer.Option(False, "--soft", help="Soft reset (default, restarts interpreter)"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Reset the connected MicroPython device.

[bold cyan]Usage:[/bold cyan] replx reset [yellow][OPTIONS][/yellow]

[bold cyan]Options:[/bold cyan]
  [yellow]--soft[/yellow]      Soft reset (default) - restarts Python interpreter
  [yellow]--hard[/yellow]      Hard reset - full hardware reset like RESET button

[bold cyan]Examples:[/bold cyan]
  replx reset               [dim]Soft reset (default)[/dim]
  replx reset --soft        [dim]Soft reset explicitly[/dim]
  replx reset --hard        [dim]Hard reset with auto-reconnect[/dim]

[bold cyan]When to use:[/bold cyan]
  • [yellow]--soft[/yellow]: After uploading code, to restart cleanly
    • Clears all Python variables, objects, imported modules
    • Frees all Python memory and restarts interpreter
    • Resets most peripherals (Pin.irq, Bluetooth, sockets, etc.)
    • [dim]Preserves:[/dim] Wi-Fi/network connections, RTC, CPU clock, Pin modes
    • [dim]Wi-Fi:[/dim] Stays connected - no reconnect needed
  • [yellow]--hard[/yellow]: When soft reset doesn't respond
    • Complete reset like pushing physical RESET button
    • Clears all hardware state (except RTC)
    • USB disconnects briefly, then auto-reconnects
    • [dim]Wi-Fi:[/dim] Disconnects - must call wlan.connect() again
  
[bold cyan]Note:[/bold cyan]
  Both resets run boot.py → main.py sequence after restart."""
        OutputHelper.print_panel(help_text, title="reset", border_style="help")
        console.print()
        raise typer.Exit()
    
    if hard and soft:
        OutputHelper.print_panel(
            "Cannot use both [yellow]--hard[/yellow] and [yellow]--soft[/yellow] at the same time.",
            title="Reset Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    reset_type = "hard" if hard else "soft"
    
    status = _ensure_connected()
    device = status.get('device', 'unknown')
    
    if reset_type == "hard":
        _reset_hard(device, status)
    else:
        _reset_soft(device, status)


def _reset_soft(device: str, status: dict):
    try:
        with _create_agent_client() as client:
            client.send_command('reset')
        
        if status.get('core') == 'EFR32MG':
            try:
                client = _create_agent_client()
                client.send_command('release')
            except Exception:
                pass
        
        OutputHelper.print_panel(
            f"Device [bright_yellow]{device}[/bright_yellow] has been soft reset.",
            title="Soft Reset",
            border_style="success"
        )
    except Exception as e:
        error_msg = str(e)
        if "soft reset failed" in error_msg.lower():
            OutputHelper.print_panel(
                f"Soft reset failed: {error_msg}\n\n"
                "[yellow]Tip:[/yellow] If code catches KeyboardInterrupt, soft reset cannot work.\n"
                "Try [bright_blue]replx reset hard[/bright_blue] instead.",
                title="Reset Error",
                border_style="error"
            )
        else:
            OutputHelper.print_panel(
                f"Soft reset failed: {error_msg}",
                title="Reset Error",
                border_style="error"
            )
        raise typer.Exit(1)


def _reset_hard(device: str, status: dict):
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.text import Text
    
    port = status.get('port', '')
    console = OutputHelper.make_console()
    
    spinner = Spinner("dots", text=Text(" Executing hard reset...", style="bright_cyan"))
    
    try:
        with Live(spinner, console=console, refresh_per_second=10, transient=True):
            with _create_agent_client() as client:
                try:
                    client.send_command('exec', code='import machine; machine.reset()', timeout=2.0)
                except Exception:
                    pass
        
        spinner = Spinner("dots", text=Text(" Waiting for device to restart...", style="yellow"))
        with Live(spinner, console=console, refresh_per_second=10, transient=True):
            time.sleep(2.0)
        
        spinner = Spinner("dots", text=Text(" Reconnecting...", style="bright_cyan"))
        with Live(spinner, console=console, refresh_per_second=10, transient=True):
            try:
                with _create_agent_client() as client:
                    client.send_command('disconnect_port', port=port, timeout=2.0)
            except Exception:
                pass
            
            time.sleep(1.0)
            
            reconnect_attempts = 5
            reconnected = False
            
            for attempt in range(reconnect_attempts):
                try:
                    time.sleep(1.0)
                    with _create_agent_client() as client:
                        result = client.send_command(
                            'session_setup',
                            port=port,
                            as_foreground=True,
                            timeout=5.0
                        )
                        if result.get('connected'):
                            reconnected = True
                            break
                except Exception:
                    continue
            
            if not reconnected:
                try:
                    _ensure_connected()
                    reconnected = True
                except Exception:
                    pass
        
        if reconnected:
            OutputHelper.print_panel(
                f"Device [bright_yellow]{device}[/bright_yellow] has been hard reset and reconnected.",
                title="Hard Reset",
                border_style="success"
            )
        else:
            OutputHelper.print_panel(
                f"Device [bright_yellow]{device}[/bright_yellow] was reset but auto-reconnect failed.\n\n"
                f"Please reconnect manually with [bright_blue]replx --port {port} setup[/bright_blue]",
                title="Hard Reset",
                border_style="warning"
            )
    except Exception as e:
        OutputHelper.print_panel(
            f"Hard reset failed: {str(e)}",
            title="Reset Error",
            border_style="error"
        )
        raise typer.Exit(1)
