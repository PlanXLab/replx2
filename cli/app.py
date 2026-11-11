import sys
import importlib
from contextlib import contextmanager
from typing import Optional
import typer
from rich.panel import Panel

if __name__ == '__main__':
    sys.modules['replx.cli.app'] = sys.modules[__name__]

from replx import __version__
from .helpers.output import OutputHelper, get_panel_box, CONSOLE_WIDTH
from .config import STATE, _set_global_options, _find_env_file, _get_theme_config


import re

def _preprocess_connection_shortcut():
    if len(sys.argv) < 2:
        return
    
    commands_with_connection = {
        'setup', 'fg', 'close',
        'repl', 'shell', 'exec', 'run',
        'ls', 'cat', 'get', 'put', 'cp', 'mv', 'rm', 'mkdir', 'touch',
        'usage', 'reset', 'format', 'init',
        'install', 'update', 'search', 'i2c', 'gpio', 'adc', 'pwm', 'uart', 'spi',
        'i2s', 'ws2812',
        'mip', 'wifi', 'ble',
    }
    
    commands_without_connection = {
        'scan', 'status', 'whoami', 'agent',
    }
    
    known_commands = commands_with_connection | commands_without_connection | {'connect'}
    
    opts_with_value = {'--port', '-p'}
    
    first_arg_idx = None
    skip_next = False
    for i, arg in enumerate(sys.argv[1:], 1):
        if skip_next:
            skip_next = False
            continue
        if arg in opts_with_value:
            skip_next = True
            continue
        if not arg.startswith('-'):
            first_arg_idx = i
            break
    
    if first_arg_idx is None:
        return
    
    first_arg = sys.argv[first_arg_idx]
    
    if first_arg.lower() in known_commands:
        return
    
    if first_arg_idx + 1 < len(sys.argv):
        next_arg = sys.argv[first_arg_idx + 1]
        if next_arg.lower() in commands_without_connection:
            return
    
    is_port = False
    
    if re.match(r'^com\d+$', first_arg, re.IGNORECASE):
        is_port = True
    elif re.match(r'^/dev/(tty(USB|ACM|AMA|S)\d+|serial/by-(id|path)/.+)$', first_arg, re.IGNORECASE):
        is_port = True
    elif re.match(
        r'^/dev/(cu|tty)\.(usbmodem|usbserial|wchusbserial|slab_usbto[a-z0-9_-]+)$',
        first_arg,
        re.IGNORECASE,
    ):
        is_port = True
    
    if is_port:
        sys.argv.insert(first_arg_idx, '--port')
        return


def _preprocess_cli_aliases():
    if len(sys.argv) < 2:
        return
    
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '-c':
            sys.argv[i] = 'exec'
            return
    
    aliases = {
        'connect': 'setup',
    }
    
    for i, arg in enumerate(sys.argv[1:], 1):
        if not arg.startswith('-'):
            if arg in aliases:
                sys.argv[i] = aliases[arg]
            break

def _apply_workspace_theme() -> None:
    theme = 'dark'
    try:
        env_path = _find_env_file()
        theme = _get_theme_config(env_path) or 'dark'
    except Exception:
        theme = 'dark'

    try:
        OutputHelper.set_theme(theme)
    except Exception:
        OutputHelper.set_theme('dark')


_apply_workspace_theme()


def _get_console():
    return OutputHelper.make_console(width=CONSOLE_WIDTH)


_RICH_HELP_CONFIGURED = False


def _configure_rich_help_rendering() -> None:
    global _RICH_HELP_CONFIGURED
    if _RICH_HELP_CONFIGURED:
        return

    try:
        import typer.rich_utils

        def _patched_get_rich_console():
            return _get_console()

        typer.rich_utils._get_rich_console = _patched_get_rich_console
    except ImportError:
        pass

    try:
        from typer.core import RichCommand

        original_format_help = RichCommand.format_help

        def _format_help_width(self, ctx, formatter):
            old_console = getattr(self, '_rich_console', None)
            try:
                self._rich_console = OutputHelper.make_console(width=CONSOLE_WIDTH)
                return original_format_help(self, ctx, formatter)
            finally:
                if old_console is not None:
                    self._rich_console = old_console

        RichCommand.format_help = _format_help_width
    except ImportError:
        pass

    _RICH_HELP_CONFIGURED = True


import click
from click.exceptions import UsageError

_original_usage_error_format_message = UsageError.format_message

def _custom_context_get_usage(self):
    return ""


def _build_command_help(ctx) -> str:
    if not ctx or not ctx.command:
        return None
    
    cmd = ctx.command
    cmd_name = ctx.info_name
    
    lines = []
    
    if cmd.help:
        lines.append(cmd.help.split('\n')[0])
        lines.append("")
    
    params_str = ""
    options = []
    arguments = []
    
    for param in cmd.params:
        if isinstance(param, click.Option):
            if not param.hidden:
                options.append(param)
        elif isinstance(param, click.Argument):
            arguments.append(param)
    
    if options:
        params_str += "[[cyan]OPTIONS[/cyan]] "
    for arg in arguments:
        arg_name = arg.name.upper()
        if arg.required:
            params_str += f"[yellow]{arg_name}[/yellow] "
        else:
            params_str += f"[yellow][{arg_name}][/yellow] "
    
    lines.append("[bold cyan]Usage:[/bold cyan]")
    lines.append(f"  replx {cmd_name} {params_str.strip()}")
    lines.append("")
    
    if options:
        lines.append("[bold cyan]Options:[/bold cyan]")
        for opt in options:
            opt_str = ", ".join(opt.opts)
            if opt.metavar:
                opt_str += f" [green]{opt.metavar}[/green]"
            elif opt.type and opt.type.name.upper() not in ('BOOL', 'BOOLEAN'):
                opt_str += f" [green]{opt.type.name.upper()}[/green]"
            
            help_text = opt.help or ""
            if len(help_text) > 40:
                help_text = help_text[:37] + "..."
            
            lines.append(f"  {opt_str:<25} {help_text}")
        lines.append("")
    
    if arguments:
        lines.append("[bold cyan]Arguments:[/bold cyan]")
        for arg in arguments:
            req = "[red][required][/red]" if arg.required else "[dim][optional][/dim]"
            lines.append(f"  [yellow]{arg.name}[/yellow]  {req}")
    
    return "\n".join(lines)


def _custom_usage_error_show(self, output_file=None):
    console = OutputHelper.make_console(width=CONSOLE_WIDTH, file=sys.stderr)
    
    error_msg = _original_usage_error_format_message(self)
    error_lines = []
    
    cmd_name = None
    if self.ctx and self.ctx.info_name and self.ctx.info_name != 'replx':
        cmd_name = self.ctx.info_name
    
    is_option_error = any(x in error_msg.lower() for x in ['no such option', 'missing option', 'missing argument', 'invalid value', 'requires an argument', 'got unexpected'])
    
    if cmd_name and is_option_error:
        help_text = _build_command_help(self.ctx)
        if help_text:
            error_lines.append(help_text)
            error_lines.append("")
            error_lines.append(f"[red]{error_msg}[/red]")
        else:
            error_lines.append(f"[bold cyan]Usage:[/bold cyan] replx {cmd_name} [OPTIONS] [ARGS]...")
            error_lines.append("")
            error_lines.append(f"[red]{error_msg}[/red]")
    else:
        error_lines.append("[bold cyan]Usage:[/bold cyan] replx [OPTIONS] COMMAND [ARGS]...")
        error_lines.append("")
        error_lines.append(f"[red]{error_msg}[/red]")
    
    console.print(Panel(
        "\n".join(error_lines),
        title="Error",
        border_style=OutputHelper._resolve_category_color('error'),
        box=get_panel_box(),
        width=CONSOLE_WIDTH
    ))


def _handle_usage_error(e):
    console = OutputHelper.make_console(width=CONSOLE_WIDTH, file=sys.stderr)
    
    error_msg = str(e.format_message()) if hasattr(e, 'format_message') else str(e)
    error_lines = []
    
    cmd_name = None
    if e.ctx and e.ctx.info_name and e.ctx.info_name != 'replx':
        cmd_name = e.ctx.info_name
    
    is_option_error = any(x in error_msg.lower() for x in ['no such option', 'missing option', 'missing argument', 'invalid value', 'requires an argument', 'got unexpected'])
    
    if cmd_name and is_option_error:
        help_text = _build_command_help(e.ctx)
        if help_text:
            error_lines.append(help_text)
            error_lines.append("")
            error_lines.append(f"[red]{error_msg}[/red]")
        else:
            error_lines.append(f"[bold cyan]Usage:[/bold cyan] replx {cmd_name} [OPTIONS] [ARGS]...")
            error_lines.append("")
            error_lines.append(f"[red]{error_msg}[/red]")
    else:
        error_lines.append("[bold cyan]Usage:[/bold cyan] replx [OPTIONS] COMMAND [ARGS]...")
        error_lines.append("")
        error_lines.append(f"[red]{error_msg}[/red]")
    
    console.print(Panel(
        "\n".join(error_lines),
        title="Error",
        border_style=OutputHelper._resolve_category_color('error'),
        box=get_panel_box(),
        width=CONSOLE_WIDTH
    ))

@contextmanager
def _patched_click_error_rendering():
    original_get_usage = click.Context.get_usage
    original_usage_error_show = UsageError.show
    click.Context.get_usage = _custom_context_get_usage
    UsageError.show = _custom_usage_error_show
    try:
        yield
    finally:
        click.Context.get_usage = original_get_usage
        UsageError.show = original_usage_error_show


app = typer.Typer(
    rich_markup_mode="rich",
    add_completion=False,
    no_args_is_help=False,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
    help="MicroPython REPL tool for device management."
)


_COMMAND_MODULES = {
    'get': 'file',
    'cat': 'file',
    'put': 'file',
    'ls': 'file',
    'cp': 'file',
    'mv': 'file',
    'rm': 'file',
    'mkdir': 'file',
    'touch': 'file',
    'setup': 'device',
    'usage': 'device',
    'scan': 'device',
    'theme': 'device',
    'exec': 'exec',
    'run': 'exec',
    'repl': 'exec',
    'shell': 'exec',
    'reset': 'exec',
    'pkg': 'package',
    'mpy': 'package',
    'mip': 'mip',
    'version': 'utility',
    'status': 'utility',
    'fg': 'utility',
    'whoami': 'utility',
    'close': 'utility',
    'agent': 'utility',
    'format': 'utility',
    'init': 'utility',
    'firmware': 'firmware',
    'i2c': 'i2c',
    'gpio': 'gpio',
    'adc': 'adc',
    'pwm': 'pwm',
    'uart': 'uart',
    'spi': 'spi',
    'i2s': 'i2s',
    'ws2812': 'ws2812',
    'wifi': 'wifi',
    'ble': 'ble',
}
_KNOWN_COMMANDS = set(_COMMAND_MODULES) | {'connect', 'help'}
_LOADED_COMMAND_MODULES: set[str] = set()


def _load_command_module(module_name: str) -> None:
    if module_name in _LOADED_COMMAND_MODULES:
        return

    importlib.import_module(f'replx.cli.commands.{module_name}')
    _LOADED_COMMAND_MODULES.add(module_name)


def _load_required_command_module(command_name: Optional[str]) -> None:
    if not command_name:
        return

    module_name = _COMMAND_MODULES.get(command_name)
    if module_name:
        _load_command_module(module_name)


def _print_main_help():
    lines = []
    lines.append("[bold]MicroPython development tool for VSCode[/bold]")
    lines.append("[dim]Connect, manage files, run code, and develop on MicroPython boards[/dim]")
    lines.append("")
    lines.append("[bold cyan]Usage:[/bold cyan]")
    lines.append("  replx [yellow][OPTIONS][/yellow] [green]COMMAND[/green] [[dim]ARGS[/dim]]...")
    lines.append("")
    lines.append("[bold cyan]Global Options:[/bold cyan]")
    lines.append("  [yellow]-p, --port[/yellow] [cyan]PORT[/cyan]             Serial port [dim](COM3, /dev/ttyUSB0, /dev/serial/by-id/...)[/dim]")
    lines.append("  [dim] 󱞩 [cyan]PORT[/cyan] can be used alone without the -p flag[/dim]")

    command_groups = [
        ("Connection & Session", [
            ("setup", "Initialize MicroPython development environment for VSCode"),
            ("scan", "Find and list all connected MicroPython boards"),
            ("status", "Show all active sessions and their board connections"),
            ("fg", "Switch foreground connection to another board"),
            ("whoami", "Show which board your commands are currently talking to"),
            ("close", "Close a board connection"),
            ("agent", "Manage agent endpoints, client sessions, and lifecycle"),
            ("theme", "Show or configure the UI theme, panel colors, and box style"),
        ]),
        ("Interactive", [
            ("repl", "Enter interactive MicroPython mode on the connected board"),
            ("shell", "Enter interactive shell for managing files on the device"),
        ]),
        ("Execution", [
            ("exec, -c", "Run a single MicroPython command on the connected board"),
            ("run", "Run a MicroPython script on the connected board"),
        ]),
        ("File Operations", [
            ("ls", "List files and directories on the connected device"),
            ("cat", "Display the contents of a file on the connected device"),
            ("get", "Download files or directories from the device to your computer"),
            ("put", "Upload files or directories from your computer to the device"),
            ("cp", "Copy files or directories on the connected device"),
            ("mv", "Move or rename files and directories on the connected device"),
            ("rm", "Delete files or directories from the connected device"),
            ("mkdir", "Create directories on the connected device"),
            ("touch", "Create files if missing (existing contents are preserved)"),
        ]),
        ("Device Management", [
            ("usage", "Show memory and storage usage of the connected device"),
            ("reset", "Reset the device (soft or hard with auto-reconnect)"),
            ("format", "Format (erase) the filesystem on the connected device"),
            ("init", "Completely reset device: format filesystem and install all libraries"),
            ("wifi", "Configure and manage WiFi settings on the device"),
            ("ble", "Configure and manage BLE (Bluetooth Low Energy) on the device"),
            ("firmware", "Download and update device firmware (UF2 / ESP32-P4 esptool)"),
        ]),
        ("Package Management", [
            ("pkg", "Manage libraries: search, download, update"),
            ("mip", "Install MicroPython community packages (micropython.org)"),
            ("mpy", "Compile Python files to .mpy bytecode"),
        ]),
        ("Hardware", [
            ("gpio", "Read, write, and run GPIO sequences on the connected board"),
            ("pwm", "Generate and monitor PWM signals on the connected board"),
            ("adc", "Read ADC pins and run the board-side ADC scope UI"),
            ("uart", "Open, write, read, monitor UART on the connected board"),
            ("spi", "Open, write, read, xfer SPI devices on the connected board"),
            ("i2c", "Scan, read, write, dump I2C devices on the connected board"),
            ("i2s", "Generate and capture I2S audio on the connected board"),
            ("ws2812", "Write pixels and regions on WS2812 LED matrices"),
        ]),
    ]
    
    for group_name, commands in command_groups:
        lines.append("")
        lines.append(f"[bold cyan]{group_name}:[/bold cyan]")
        for cmd, desc in commands:
            lines.append(f"  [green]{cmd:<12}[/green] {desc}")
    
    lines.append("")
    lines.append("[dim]Use 'replx COMMAND --help' for detailed help on each command.[/dim]")
    
    OutputHelper.print_panel(
        "\n".join(lines),
        title="replx",
        border_style="help"
    )


def _get_known_commands() -> set[str]:
    return set(_KNOWN_COMMANDS)


@app.callback(invoke_without_command=True)
def cli(
    ctx: typer.Context,
    global_port: Optional[str] = typer.Option(
        None,
        "--port", "-p",
        help="Serial port to use (e.g., COM3)",
        is_eager=True
    ),
    show_help: bool = typer.Option(
        False,
        "--help",
        is_eager=True,
        expose_value=True,
        help="Show this message and exit."
    )
):
    _set_global_options(global_port)
    
    ctx.ensure_object(dict)
    ctx.obj['global_port'] = global_port
    
    if show_help:
        _print_main_help()
        raise typer.Exit()
    
    if ctx.invoked_subcommand is None:
        _print_main_help()
        raise typer.Exit()

def main():
    _preprocess_connection_shortcut()
    _preprocess_cli_aliases()

    if len(sys.argv) == 1:
        OutputHelper.print_panel(
            "Use [bright_blue]replx --help[/bright_blue] to see available commands.",
            title="Replx",
            border_style="success"
        )
        raise SystemExit()
    
    if len(sys.argv) == 2 and sys.argv[1] in ('--version', '-v'):
        OutputHelper.print_panel(
            f"[bright_blue]replx[/bright_blue] version [bright_green]{__version__}[/bright_green]",
            title="Version",
            border_style="success"
        )
        sys.exit(0)
    
    if sys.argv[1] == '--command':
        if len(sys.argv) < 3:
            OutputHelper.print_panel(
                "Missing required argument: [yellow]COMMAND[/yellow]\n\n"
                "[bold cyan]Usage:[/bold cyan]\n"
                "  replx -c [yellow]COMMAND[/yellow]\n\n"
                "[bold cyan]Examples:[/bold cyan]\n"
                "  replx -c \"print('hello')\"",
                title="Command Required",
                border_style="error"
            )
            sys.exit(1)
        
        command_str = sys.argv[2]
        
        try:
            from .connection import _ensure_connected, _create_agent_client

            _ensure_connected()
            client = _create_agent_client()
            result = client.send_command('exec', code=command_str)
            output = result.get('output', '')
            if output:
                print(output, end='')
                if not output.endswith('\n'):
                    print()
        except Exception as e:
            error_msg = str(e)
            if 'Not connected' in error_msg:
                OutputHelper.print_panel(
                    "Not connected to any device.\n\nRun [bright_green]replx connect --port COM3[/bright_green] first.",
                    title="Connection Required",
                    border_style="error"
                )
            else:
                typer.echo(f"Error: {error_msg}", err=True)
            sys.exit(1)
        sys.exit(0)
    
    if len(sys.argv) == 2 and sys.argv[1] in ('--help', '-h'):
        _print_main_help()
        sys.exit(0)

    try:
        out = [sys.argv[0]]
        for tok in sys.argv[1:]:
            if not tok.startswith('-') or tok.startswith('--') or len(tok) <= 2:
                out.append(tok)
                continue

            if tok in ('-ne', '-en'):
                out.extend(['-n', '-e'])
                continue

            if tok.startswith('-') and set(tok[1:]).issubset({'n', 'e'}) and len(tok) > 2:
                typer.echo("Error: Option chaining error: -n and -e can only be used once, not multiple times.", err=True)
                sys.exit(2)
            
            out.append(tok)
        sys.argv = out
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(2)

    args = sys.argv[1:]

    known = _get_known_commands()

    opts_with_value = {'--port', '-p'}
    
    first_nonopt_idx = None
    skip_next = False
    for i, a in enumerate(sys.argv[1:], 1):
        if skip_next:
            skip_next = False
            continue
        if a in opts_with_value:
            skip_next = True
            continue
        if not a.startswith('-'):
            first_nonopt_idx = i
            break
    first_nonopt = sys.argv[first_nonopt_idx] if first_nonopt_idx is not None else None

    run_opts = {'-n', '--non-interactive', '-e', '--echo', '-d', '--device', '--line', '--hex', '--text'}
    has_device_opt = bool(run_opts & {'-d', '--device'} & set(args))
    
    script_files = []
    skip_next = False
    for i, a in enumerate(sys.argv[1:], 1):
        if skip_next:
            skip_next = False
            continue
        if a in opts_with_value:
            skip_next = True
            continue
        if a.endswith('.py') or (has_device_opt and a.endswith('.mpy')):
            script_files.append((i, a))
    
    script_arg_idx = script_files[0][0] if script_files else None

    should_inject_run = (
        ('run' not in args) and
        (len(script_files) == 1) and
        (first_nonopt is None or first_nonopt not in known)
    )

    if should_inject_run:
        opt_idx = next((i for i, a in enumerate(sys.argv[1:], 1) if a in run_opts), None)
        insert_at = min(opt_idx, script_arg_idx) if opt_idx is not None else script_arg_idx
        sys.argv.insert(insert_at, 'run')

        first_nonopt_idx = next((i for i, a in enumerate(sys.argv[1:], 1) if not a.startswith('-')), None)
        first_nonopt = sys.argv[first_nonopt_idx] if first_nonopt_idx is not None else None

    _load_required_command_module(first_nonopt)

    suppressed = {'scan'}
    if any(x in sys.argv for x in ('--help', '-h')):
        _configure_rich_help_rendering()

    if not any(x in sys.argv for x in ('--help','-h','--version','-v')):
        if (first_nonopt is None) or (first_nonopt not in suppressed):
            from .helpers.updater import UpdateChecker

            UpdateChecker.check_for_updates(__version__)
        
    try:
        from .helpers.environment import EnvironmentManager

        EnvironmentManager.load_env_from_rep()
        with _patched_click_error_rendering():
            # standalone_mode=False makes click *return* typer.Exit codes.
            rv = app(standalone_mode=False)
        exit_code = rv if isinstance(rv, int) and not isinstance(rv, bool) else 0
    except click.exceptions.UsageError as e:
        _handle_usage_error(e)
        exit_code = 2
    except click.exceptions.Abort:
        print()
        exit_code = 1
    except KeyboardInterrupt:
        try:
            if STATE.repl_protocol:
                STATE.repl_protocol.request_interrupt()
        except Exception:
            pass
        print()
        exit_code = 130
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
    except Exception as e:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH, file=sys.stderr)
        cmd_name = None
        for arg in sys.argv[1:]:
            if not arg.startswith('-'):
                cmd_name = arg
                break
        hint = f"replx {cmd_name} --help" if cmd_name else "replx --help"
        console.print(Panel(
            f"[red]{e}[/red]\n\n[dim]Run [bright_blue]{hint}[/bright_blue] for usage.[/dim]",
            title="Error",
            border_style=OutputHelper._resolve_category_color('error'),
            box=get_panel_box(),
            width=CONSOLE_WIDTH,
        ))
        exit_code = 1
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
