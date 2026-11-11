import os
import sys
import time
import re
import json
import subprocess
from io import StringIO

import typer
from rich.table import Table
from rich.text import Text

from replx.terminal import IS_WINDOWS
from replx.utils import device_name_to_path
from ..agent.client import AgentClient
from ..helpers import (
    OutputHelper, DeviceScanner,
    StoreManager,
    CONSOLE_WIDTH, get_panel_box,
)
from ..config import (
    STATE,
    _find_env_file, _find_or_create_vscode_dir,
    _read_env_ini,
    _update_connection_config, _find_available_agent_port, _find_running_agent_ports,
    _get_global_options, AgentPortManager
)
from ..connection import (
    _ensure_connected, _create_agent_client
)
from ..app import app


def _normalize_path_for_comparison(path: str) -> str:
    path = os.path.normpath(path)
    if sys.platform.startswith("win"):
        return path.lower()
    else:
        return path


def _serial_port_cmp_key(port: str) -> str:
    if port is None:
        return ""
    return DeviceScanner.port_compare_key(port)


def _serial_port_display(port: str) -> str:
    if port is None:
        return ""
    p = str(port).strip()
    return p.upper() if IS_WINDOWS else p


def _resolve_os_serial_port_name(port: str) -> str:
    if not port:
        return port
    p = str(port).strip()
    return p.upper() if IS_WINDOWS and re.fullmatch(r"(?i)com\d+", p) else p


def _check_vscode_version(vscode_dir: str) -> bool:
    settings_file = os.path.join(vscode_dir, "settings.json")
    
    for item in os.listdir(vscode_dir):
        if item.endswith('.pyi'):
            return True
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            extra_paths = settings.get("python.analysis.extraPaths", [])
            
            if not extra_paths:
                return False
            
            has_replx_typehints = False
            for path in extra_paths:
                norm_path = os.path.normpath(path)
                if 'replx' in norm_path and 'typehints' in norm_path:
                    has_replx_typehints = True
                    break
            
            vscode_norm = _normalize_path_for_comparison(vscode_dir)
            for path in extra_paths:
                norm_path = _normalize_path_for_comparison(path)
                if norm_path.startswith(vscode_norm):
                    return True
            
            if extra_paths and not has_replx_typehints:
                return True
                
        except (json.JSONDecodeError, IOError):
            return True
    
    return False


def _load_jsonc(path: str) -> dict | None:
    if not path or not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception:
        return None

    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    # Best-effort JSONC support for VS Code settings.
    try:
        no_block_comments = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
        no_line_comments = re.sub(r"(^|\s)//.*$", "", no_block_comments, flags=re.M)
        no_trailing_commas = re.sub(r",\s*([}\]])", r"\1", no_line_comments)
        data = json.loads(no_trailing_commas)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _get_portable_vscode_root_from_pshome() -> str | None:
    pshome = os.environ.get("PSHOME", "").strip()
    if not pshome:
        try:
            run_kwargs = {
                "capture_output": True,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "timeout": 2,
                "check": False,
            }
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0
                run_kwargs["startupinfo"] = startupinfo
                run_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                ["pwsh", "-NoLogo", "-NoProfile", "-Command", "$PSHOME"],
                **run_kwargs,
            )
            pshome = result.stdout.strip()
        except Exception:
            return None

    if not pshome:
        return None
    vscode_root = os.path.dirname(os.path.dirname(os.path.dirname(pshome)))
    vscode_root = os.path.dirname(os.path.dirname(os.path.dirname(pshome)))
    return vscode_root


def _map_vscode_theme_to_replx(vscode_theme: str | None) -> str | None:
    if not vscode_theme:
        return None

    t = vscode_theme.strip().lower()

    if "github" in t and "light" in t:
        return "github-light"
    if "github" in t and "dark" in t:
        return "github-dark"
    if "one dark" in t:
        return "one-dark-pro"
    if "atom" in t and "one" in t and "light" in t:
        return "atom-one-light"
    if "light" in t or "white" in t:
        return "white"
    if "dark" in t:
        return "dark"

    return None


def _detect_vscode_theme_for_setup() -> str | None:
    vscode_root = _get_portable_vscode_root_from_pshome()
    if not vscode_root:
        return None

    portable_settings = os.path.join(vscode_root, "data", "user-data", "User", "settings.json")

    data = _load_jsonc(portable_settings)
    if not isinstance(data, dict):
        return None

    vscode_theme = data.get("workbench.colorTheme")
    if isinstance(vscode_theme, str):
        vscode_theme = vscode_theme.strip()
        if vscode_theme:
            return vscode_theme

    return None


def _create_vscode_files_and_typehints(vscode_dir: str, core: str, device: str, overwrite: bool = False):
    task_file = os.path.join(vscode_dir, "tasks.json")
    settings_file = os.path.join(vscode_dir, "settings.json")
    launch_file = os.path.join(vscode_dir, "launch.json")
    
    task_file_contents = """{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Run micropython with replx",
            "type": "shell",
            "command": "replx",
            "args": ["${file}"],
            "problemMatcher": [],
            "group": { "kind": "build", "isDefault": true }
        }
    ]
}
"""
    
    extra_paths = []
    
    from replx.utils.device_info import is_std_micropython
    if is_std_micropython(core):
        comm_path = StoreManager.comm_typehints_path()
    else:
        comm_path = StoreManager.comm_separate_typehints_path(core)
    if comm_path and os.path.isdir(comm_path):
        extra_paths.append(comm_path)
    
    if core:
        core_builtin = StoreManager.core_typehints_path(core)
        if core_builtin and os.path.isdir(core_builtin):
            extra_paths.append(core_builtin)
    
    if core:
        core_lib_typehints = os.path.join(StoreManager.pkg_root(), "core", core, "typehints")
        if os.path.isdir(core_lib_typehints):
            extra_paths.append(core_lib_typehints)
    
    if device:
        device_path = device_name_to_path(device)
        device_builtin = StoreManager.device_typehints_path(device_path)
        if device_builtin and os.path.isdir(device_builtin):
            extra_paths.append(device_builtin)
    
    if device:
        device_path = device_name_to_path(device)
        device_typehints = os.path.join(StoreManager.pkg_root(), "device", device_path, "typehints")
        if os.path.isdir(device_typehints):
            extra_paths.append(device_typehints)
    
    settings_dict = {
        "python.languageServer": "Pylance",
        "python.analysis.diagnosticSeverityOverrides": {
            "reportMissingModuleSource": "none"
        },
        "python.analysis.extraPaths": extra_paths
    }

    if comm_path and os.path.isdir(comm_path):
        settings_dict["python.analysis.stubPath"] = comm_path
    settings_file_contents = json.dumps(settings_dict, indent=4) + "\n"
    
    launch_file_contents = """{
    "version": "0.2.0",
    "configurations": [
      {
        "name": "Python: Current file debug",
        "type": "debugpy",
        "request": "launch",
        "program": "${file}",
        "console": "integratedTerminal"
      }
    ]
}
"""

    if overwrite or not os.path.exists(task_file):
        with open(task_file, "w", encoding="utf-8") as f:
            f.write(task_file_contents)
    if overwrite or not os.path.exists(settings_file):
        with open(settings_file, "w", encoding="utf-8") as f:
            f.write(settings_file_contents)
    if overwrite or not os.path.exists(launch_file):
        with open(launch_file, "w", encoding="utf-8") as f:
            f.write(launch_file_contents)
    
    return extra_paths


@app.command(rich_help_panel="Connection & Session")
def setup(
    clean: bool = typer.Option(False, "--clean", help="Delete .vscode folder in current project"),
    theme: str = typer.Option(
        None,
        "--theme",
        help="UI theme: dark, white, one-dark-pro, atom-one-light, github-dark, github-light",
    ),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Initialize MicroPython development environment for VSCode.

Run this once per project folder to set up your workspace.

[bold cyan]What this command does:[/bold cyan]
  1. Connects to your MicroPython board
  2. Creates [yellow].vscode/[/yellow] folder with configuration files:
     • [dim]settings.json[/dim] - Python/Pylance settings
     • [dim]tasks.json[/dim]    - Build task (Ctrl+Shift+B to run)
     • [dim]launch.json[/dim]   - Debug configuration
  3. Copies [yellow]typehints (.pyi)[/yellow] for IntelliSense/autocomplete
  4. Saves connection info for subsequent commands

[bold cyan]Usage:[/bold cyan]
  replx [yellow]PORT[/yellow] setup                       [dim]# Serial: COM3, /dev/ttyUSB0, /dev/serial/by-id/...[/dim]
  replx setup [yellow]--clean[/yellow]                    [dim]# Delete .vscode folder (no PORT needed)[/dim]

[bold cyan]Options:[/bold cyan]
  [yellow]--clean[/yellow]   Delete the [yellow].vscode[/yellow] folder in the current project directory.
            All configuration and typehints will be removed.
  [yellow]--theme[/yellow]   UI theme preset. If omitted, try VSCode theme auto-detect, fallback [yellow]dark[/yellow].
            Supported: [dim]dark, white, one-dark-pro, atom-one-light, github-dark, github-light[/dim]

[bold cyan]Agent Port:[/bold cyan]
    replx automatically selects a free TCP port from the dynamic range
    [cyan]49153-65535[/cyan] and stores it in [dim]~/.replx/.config[/dim] as [dim]AGENT_PORT=...[/dim].
    If that port is already used by another program, replx chooses a new one automatically.

[bold cyan]Examples:[/bold cyan]
  replx COM3 setup                         [dim]# Windows serial port[/dim]
  replx /dev/ttyACM0 setup                 [dim]# Linux serial port[/dim]
  replx /dev/serial/by-id/usb-MicroPython_board setup [dim]# Stable Linux port[/dim]
  replx COM3 setup --theme white           [dim]# Light UI preset[/dim]
  replx COM3 setup --theme github-light    [dim]# GitHub light preset[/dim]
  replx setup --clean                      [dim]# Remove .vscode folder[/dim]

[bold cyan]After setup, you can:[/bold cyan]
  replx ls                      [dim]# List files on device[/dim]
  replx run main.py             [dim]# Run local script on device[/dim]
  replx -c "print('hello')"     [dim]# Execute single command[/dim]
  replx repl                    [dim]# Enter interactive Python[/dim]
  [dim]Press Ctrl+Shift+B[/dim]            [dim]# Run current file (VSCode)[/dim]

[bold cyan]Note:[/bold cyan]
  Connection is remembered. After setup, just use [green]replx ls[/green] without port.
  To switch boards, run setup again with the new port."""
        OutputHelper.print_panel(help_text, title="setup", border_style="help")
        console.print()
        raise typer.Exit()

    selected_theme = 'dark'
    display_theme = 'one-dark-pro'
    auto_theme = None
    configured_theme = theme or 'dark'
    if not theme:
        auto_theme = _detect_vscode_theme_for_setup()
        if auto_theme:
            configured_theme = 'vscode-auto'

    try:
        selected_theme = OutputHelper.set_theme(configured_theme)
        display_theme = OutputHelper.get_theme_display_name()
    except ValueError as e:
        OutputHelper.print_panel(
            f"{str(e)}",
            title="Invalid Theme",
            border_style="error"
        )
        raise typer.Exit(1)

    stored_theme = selected_theme
    theme_mode = None
    if auto_theme and not theme:
        stored_theme = display_theme
        theme_mode = 'vscode-auto'

    if clean:
        _port = _get_global_options().get('port')
        if _port:
            OutputHelper.print_panel(
                "[yellow]--clean[/yellow] does not take a PORT argument.\n\n"
                "Usage: [bright_green]replx setup --clean[/bright_green]",
                title="Invalid Usage",
                border_style="error"
            )
            raise typer.Exit(1)
        import shutil
        current = os.path.realpath(os.getcwd())
        root = os.path.abspath(os.sep)
        vscode_dir = None
        search_dir = current
        visited = set()
        while search_dir not in visited:
            visited.add(search_dir)
            candidate = os.path.join(search_dir, ".vscode")
            if os.path.isdir(candidate):
                vscode_dir = candidate
                break
            parent = os.path.dirname(search_dir)
            if parent == search_dir or parent == root:
                break
            search_dir = parent
        if vscode_dir:
            shutil.rmtree(vscode_dir)
            OutputHelper.print_panel(
                "All settings have been removed.",
                title="Clean Complete",
                border_style="success"
            )
        else:
            OutputHelper.print_panel(
                "No [yellow].vscode[/yellow] folder found in current project.",
                title="Nothing to Clean",
                border_style="neutral"
            )
        raise typer.Exit()

    global_opts = _get_global_options()
    port = global_opts.get('port')

    port = _resolve_os_serial_port_name(port)

    if not port:
        OutputHelper.print_panel(
            "[bright_blue]--port[/bright_blue] is required for setup.\n\n"
            "Examples:\n"
            "  [bright_green]replx --port COM3 setup[/bright_green]\n"
            "  [bright_green]replx --port /dev/ttyACM0 setup[/bright_green]",
            title="Connection Required",
            border_style="warning"
        )
        raise typer.Exit(1)
    
    env_path = _find_env_file()
    agent_port = _find_available_agent_port(env_path)
    
    if AgentClient.is_agent_running(port=agent_port):
        try:
            # Pass device_port=port so _cmd_status checks the specific port being
            # set up, not the session's current foreground connection.
            with AgentClient(port=agent_port, device_port=port) as client:
                status = client.send_command('status', timeout=1.0)
            
            if status.get('connected'):
                current_port = status.get('port', '')
                
                if IS_WINDOWS:
                    same_config = current_port.upper() == port.upper()
                else:
                    same_config = current_port == port
                
                if same_config:
                    device = status.get('device', 'unknown')
                    core = status.get('core', 'unknown')
                    version = status.get('version', '?')
                    manufacturer = status.get('manufacturer', '')
                    
                    vscode_dir = _find_or_create_vscode_dir()
                    env_path = os.path.join(vscode_dir, ".replx")
                    workspace = os.path.dirname(vscode_dir)
                    
                    _update_connection_config(
                        env_path, port,
                        version=version, core=core, device=device,
                        manufacturer=manufacturer,
                        theme=stored_theme,
                        theme_mode=theme_mode,
                        set_default=True
                    )

                    default_sync_warning = None
                    try:
                        with AgentClient(port=agent_port) as client:
                            result = client.send_command('set_default', port=port, update_session=True, timeout=1.0)
                        if result and not result.get('set'):
                            default_sync_warning = "Agent did not confirm the default session update."
                        elif result is None:
                            default_sync_warning = "Agent did not respond to the default session update request."
                    except Exception as e:
                        default_sync_warning = str(e)
                    
                    typehint_paths = _create_vscode_files_and_typehints(vscode_dir, core, device)
                    
                    content = f"Connection: [bright_blue]{_serial_port_display(current_port)}[/bright_blue] [dim](Default)[/dim]\n"
                    content += f"Version: [yellow]{version}[/yellow]\n"
                    content += f"Core: [bright_green]{core}[/bright_green]\n"
                    content += f"Device: [bright_yellow]{device}[/bright_yellow]\n"
                    if manufacturer:
                        content += f"Manufacturer: [bright_magenta]{manufacturer}[/bright_magenta]\n"
                    content += f"Agent Port: [cyan]{agent_port}[/cyan] [dim](TCP, saved to ~/.replx/.config as AGENT_PORT)[/dim]\n"
                    content += f"Workspace: [dim]{workspace}[/dim]\n"
                    if auto_theme and not theme:
                        content += f"Theme: [bright_cyan]{display_theme}[/bright_cyan] [dim](auto-detected from VSCode theme)[/dim]\n"
                    if typehint_paths:
                        content += f"\nTypehints: [dim]{len(typehint_paths)} path(s) configured[/dim]\n"
                    if default_sync_warning:
                        content += (
                            "\n[bright_yellow]Warning:[/bright_yellow] Workspace default was saved, "
                            "but the live agent session default was not updated.\n"
                            f"[dim]{default_sync_warning}[/dim]\n"
                        )
                    content += "\n[dim]Already connected with same configuration.[/dim]"
                    
                    OutputHelper.print_panel(
                        content,
                        title="Setup Complete",
                        border_style="success"
                    )
                    raise typer.Exit()
                else:
                    try:
                        with AgentClient(port=agent_port, device_port=port) as client:
                            result = client.send_command(
                                'session_setup',
                                as_foreground=True,
                                set_default=True, 
                                local_default=port,
                                timeout=10.0
                            )
                        
                        STATE.core = result.get('core', '')
                        STATE.device = result.get('device', 'unknown')
                        STATE.version = result.get('version', '?')
                        STATE.manufacturer = result.get('manufacturer', '')
                        
                        vscode_dir = _find_or_create_vscode_dir()
                        env_path = os.path.join(vscode_dir, ".replx")
                        
                        _update_connection_config(
                            env_path, port,
                            version=STATE.version, core=STATE.core, device=STATE.device,
                            manufacturer=STATE.manufacturer,
                            theme=stored_theme,
                            theme_mode=theme_mode,
                            set_default=True 
                        )
                        
                        typehint_paths = _create_vscode_files_and_typehints(vscode_dir, STATE.core, STATE.device)
                        
                        workspace = os.path.dirname(vscode_dir)
                        content = f"Connection: [bright_blue]{_serial_port_display(port)}[/bright_blue] [dim](Default)[/dim]\n"
                        content += f"Version: [yellow]{STATE.version}[/yellow]\n"
                        content += f"Core: [bright_green]{STATE.core}[/bright_green]\n"
                        content += f"Device: [bright_yellow]{STATE.device}[/bright_yellow]\n"
                        if STATE.manufacturer:
                            content += f"Manufacturer: [bright_magenta]{STATE.manufacturer}[/bright_magenta]\n"
                        content += f"Agent Port: [cyan]{agent_port}[/cyan] [dim](TCP, saved to ~/.replx/.config as AGENT_PORT)[/dim]\n"
                        content += f"Workspace: [dim]{workspace}[/dim]\n"
                        if auto_theme and not theme:
                            content += f"Theme: [bright_cyan]{display_theme}[/bright_cyan] [dim](auto-detected from VSCode theme)[/dim]\n"
                        if typehint_paths:
                            content += f"Typehints: [dim]{len(typehint_paths)} path(s) configured[/dim]\n"
                        content += f"Previous fg: [dim]{_serial_port_display(current_port)}[/dim] → bg"
                        
                        OutputHelper.print_panel(
                            content,
                            title="Connection Added",
                            border_style="success"
                        )
                        raise typer.Exit()
                    except typer.Exit:
                        raise
                    except Exception:
                        pass
        except typer.Exit:
            raise
        except Exception:
            pass
    
    if not AgentClient.is_agent_running(port=agent_port):
        try:
            AgentClient.start_agent(port=agent_port)
        except Exception as e:
            OutputHelper.print_panel(
                f"Failed to start agent: {str(e)}",
                title="Agent Error",
                border_style="error"
            )
            raise typer.Exit(1)
    
    try:
        with AgentClient(port=agent_port, device_port=port) as client:
            result = client.send_command('session_setup', 
                                        port=port,
                                        as_foreground=True,
                                        local_default=port)
        
        STATE.core = result.get('core', '')
        STATE.device = result.get('device', 'unknown')
        STATE.version = result.get('version', '?')
        STATE.manufacturer = result.get('manufacturer', '')
    except Exception as e:
        conn_info = port

        OutputHelper.print_panel(
            f"Connection failure on configured device ([bright_blue]{conn_info}[/bright_blue]).\n\n"
            f"Error details: [red]{str(e)}[/red]\n\n"
            "Please check:\n"
            "  • Device is powered on and connected\n"
            "  • Serial cable is properly attached\n\n"
            "[dim]Run 'replx --port PORT setup' to reconfigure if needed.[/dim]",
            title="Connection Error",
            border_style="error"
        )
        raise typer.Exit(1)

    vscode_dir = _find_or_create_vscode_dir()
    env_path = os.path.join(vscode_dir, ".replx")
    
    need_recreate = False
    if os.path.exists(env_path):
        existing_data = _read_env_ini(env_path)
        existing_default = existing_data.get('default')
        if existing_default:
            existing_config = existing_data['connections'].get(existing_default, {})
            existing_core = existing_config.get('core', '')
            existing_device = existing_config.get('device', '')
            
            if existing_core and existing_device:
                if existing_core != STATE.core or existing_device != STATE.device:
                    need_recreate = True
    
    if not need_recreate and os.path.isdir(vscode_dir):
        if _check_vscode_version(vscode_dir):
            need_recreate = True
    
    if need_recreate:
        import shutil
        for item in os.listdir(vscode_dir):
            item_path = os.path.join(vscode_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except Exception:
                pass
    
    set_as_default = True
    
    _update_connection_config(
        env_path,
        port,
        version=STATE.version,
        core=STATE.core,
        device=STATE.device,
        manufacturer=STATE.manufacturer,
        theme=stored_theme,
        theme_mode=theme_mode,
        set_default=set_as_default
    )
    
    typehint_paths = _create_vscode_files_and_typehints(vscode_dir, STATE.core, STATE.device, overwrite=True)
    
    display_conn = port
    workspace = os.path.dirname(vscode_dir)
    content = f"Connection: [bright_blue]{_serial_port_display(display_conn)}[/bright_blue] [dim](Default)[/dim]\n"
    content += f"Version: [yellow]{STATE.version}[/yellow]\n"
    content += f"Core: [bright_green]{STATE.core}[/bright_green]\n"
    content += f"Device: [bright_yellow]{STATE.device}[/bright_yellow]\n"
    if STATE.manufacturer:
        content += f"Manufacturer: [bright_magenta]{STATE.manufacturer}[/bright_magenta]\n"
    content += f"Agent Port: [cyan]{agent_port}[/cyan] [dim](TCP, saved to ~/.replx/.config as AGENT_PORT)[/dim]\n"
    content += f"Workspace: [dim]{workspace}[/dim]\n"
    if auto_theme and not theme:
        content += f"Theme: [bright_cyan]{display_theme}[/bright_cyan] [dim](auto-detected from VSCode theme)[/dim]\n"
    else:
        content += f"Theme: [bright_cyan]{display_theme}[/bright_cyan]\n"
    if typehint_paths:
        content += f"Typehints: [dim]{len(typehint_paths)} path(s) configured[/dim]"

    OutputHelper.print_panel(
        content,
        title="Setup Complete",
        border_style="success"
    )


@app.command(rich_help_panel="Device Management")
def usage(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Show memory and storage usage of the connected device.

[bold cyan]Usage:[/bold cyan]
  replx usage
  replx COM3 usage              [dim]# Usage for specific board[/dim]

[bold cyan]Information displayed:[/bold cyan]
  [bold]Memory (RAM)[/bold]
    • Used / Free / Total
    • Visual usage bar with percentage

  [bold]Storage (Flash)[/bold]
    • Used / Free / Total
    • Visual usage bar with percentage

[bold cyan]Example output:[/bold cyan]
  󰍛 Memory
     ████████░░░░░░░░░░░░ 38.2%
     Used: 156 KB  Free: 252 KB  Total: 408 KB

  󰋊 Storage
     ██░░░░░░░░░░░░░░░░░░  8.5%
     Used:  68 KB  Free: 732 KB  Total: 800 KB

[bold cyan]Related:[/bold cyan]
  replx whoami              [dim]# See connected device info[/dim]
  replx ls -r               [dim]# See what's using storage[/dim]"""
        OutputHelper.print_panel(help_text, title="usage", border_style="help")
        console.print()
        raise typer.Exit()
    
    _ensure_connected()
    
    try:
        client = _create_agent_client()
        mem_result = client.send_command('mem')
        mem = mem_result.get('mem') if mem_result else None
        df_result = client.send_command('df')
        lines = []
        
        def make_bar(used_pct, width=30):
            filled = int(width * used_pct / 100)
            empty = width - filled
            if used_pct < 50:
                color = "green"
            elif used_pct < 80:
                color = "yellow"
            else:
                color = "red"
            return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"
        
        if mem:
            mem_total = mem[2]
            mem_used = mem[1]
            mem_free = mem[0]
            mem_pct = mem[3]
            lines.append("[bold cyan][#87C05A]󰍛[/#87C05A] Memory[/bold cyan]")
            lines.append(f"   {make_bar(mem_pct)} [bold]{mem_pct:.1f}%[/bold]")
            lines.append(f"   [dim]Used:[/dim]  {mem_used//1024:>5} KB  [dim]Free:[/dim] {mem_free//1024:>5} KB  [dim]Total:[/dim] {mem_total//1024:>5} KB")
        else:
            lines.append("[bold cyan][#87C05A]󰍛[/#87C05A] Memory[/bold cyan]  [dim]unavailable[/dim]")
        
        lines.append("")
        
        if df_result:
            fs_total = df_result.get('total', 0)
            fs_used = df_result.get('used', 0)
            fs_free = df_result.get('free', 0)
            fs_pct = df_result.get('percent', 0)
            lines.append("[bold cyan][#D98C53]󰋊[/#D98C53] Storage[/bold cyan]")
            lines.append(f"   {make_bar(fs_pct)} [bold]{fs_pct:.1f}%[/bold]")
            lines.append(f"   [dim]Used:[/dim]  {fs_used//1024:>5} KB  [dim]Free:[/dim] {fs_free//1024:>5} KB  [dim]Total:[/dim] {fs_total//1024:>5} KB")
        else:
            lines.append("[bold cyan][#D98C53]󰋊[/#D98C53] Storage[/bold cyan]  [dim]unavailable[/dim]")
        
        OutputHelper.print_panel("\n".join(lines), title="Usage", border_style="data")
        
    except Exception as e:
        OutputHelper.print_panel(f"Error: {str(e)}", title="Usage Error", border_style="error")
        raise typer.Exit(1)


@app.command(rich_help_panel="Connection & Session")
def scan(
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Find and list all connected MicroPython boards.

Scans all serial ports to detect MicroPython devices.

[bold cyan]Usage:[/bold cyan]
  replx scan

[bold cyan]Output shows:[/bold cyan]
  [bold]Columns:[/bold]
    • [yellow]Port[/yellow]     - Serial port (COM3, /dev/ttyUSB0, /dev/serial/by-id/...)
    • [yellow]Version[/yellow]  - MicroPython version
    • [yellow]Core[/yellow]     - Chip type (RP2350, ESP32, etc.)
    • [yellow]Device[/yellow]   - Board name (ticle, pico, etc.)

  [bold]Status icons:[/bold]
    󰷌  Default connection (saved in .replx)

[bold cyan]Example output:[/bold cyan]
  PORT    VERSION  CORE    DEVICE  MANUFACTURER
  ─────────────────────────────────────────────
  COM19   1.29.0   RP2350  ticle   Raspberry Pi
  COM3    1.29.0   ESP32   ESP32   Espressif

[bold cyan]Tips:[/bold cyan]
  • Scan does not connect - it only detects available boards
  • Use the port from scan results with other commands

[bold cyan]Note:[/bold cyan]
  This command ignores -p/--port option.

[bold cyan]Related:[/bold cyan]
  replx COM3 setup        [dim]# Connect to a scanned board[/dim]"""
        OutputHelper.print_panel(help_text, title="scan", border_style="help")
        console.print()
        raise typer.Exit()

    serial_results = []

    history_default = None

    env_path = _find_env_file()
    if env_path:
        env_data = _read_env_ini(env_path)
        history_default = env_data.get('default')
    
    history_default_cmp = _serial_port_cmp_key(history_default) if history_default else None

    live_connections = {}
    os_port_cmp = set()
    try:
        running_agent_ports = _find_running_agent_ports(env_path)
        agent_port = (
            running_agent_ports[0]
            if running_agent_ports
            else _find_available_agent_port(env_path)
        )
        if not running_agent_ports:
            AgentClient.start_agent(port=agent_port)

        with AgentClient(port=agent_port) as client:
            scan_data = client.send_command('scan', timeout=60.0, max_retries=1)
        scanned = scan_data.get('scanned', [])
        permission_denied_ports = scan_data.get('permission_denied_ports', [])
        for connection in scan_data.get('connections', []):
            port = connection.get('port')
            if port:
                live_connections[port] = connection
                os_port_cmp.add(_serial_port_cmp_key(port))
    except Exception as exc:
        OutputHelper.print_panel(
            f"Could not safely scan serial ports.\n\n{exc}",
            title="Scan Cancelled",
            border_style="error",
        )
        raise typer.Exit(1)

    for port_device, board_info in scanned:
        version, core, device, manufacturer = board_info
        port_device = _serial_port_display(port_device)
        serial_results.append((
            port_device,
            version,
            core,
            device,
            manufacturer
        ))

    def port_sort_key(item):
        port = item[0]
        match = re.search(r'(\d+)$', port)
        if match:
            return (port[:match.start()], int(match.group(1)))
        return (port, 0)
    
    seen_ports_cmp = set()
    unique_results = []
    for result in serial_results:
        port = _serial_port_display(result[0])
        key = _serial_port_cmp_key(port)
        if key not in seen_ports_cmp:
            seen_ports_cmp.add(key)
            unique_results.append((port, result[1], result[2], result[3], result[4]))
    serial_results = unique_results
    
    serial_results.sort(key=port_sort_key)

    scanned_serial_ports_cmp = set(_serial_port_cmp_key(r[0]) for r in serial_results)

    for conn_key, conn_data in live_connections.items():
        port_cmp = _serial_port_cmp_key(conn_key)
        if (
            not conn_data.get('connected', True)
            or port_cmp in scanned_serial_ports_cmp
            or port_cmp not in os_port_cmp
        ):
            continue
        version = conn_data.get('version', '-') or '-'
        core = conn_data.get('core', '-') or '-'
        device = conn_data.get('device', '-') or '-'
        manufacturer = conn_data.get('manufacturer', '-') or '-'
        serial_results.append((_serial_port_display(conn_key), version, core, device, manufacturer))
        scanned_serial_ports_cmp.add(port_cmp)

    serial_results.sort(key=port_sort_key)
    
    def get_default_marker(conn_id):
        conn_cmp = _serial_port_cmp_key(conn_id)
        is_default = bool(history_default_cmp and conn_cmp == history_default_cmp)
        if is_default:
            return "[bright_yellow]󰷌[/bright_yellow]"
        return ""
    
    COLUMN_PADDING = 2
    
    max_port_width = max((len(r[0]) for r in serial_results), default=4)
    
    serial_table = Table(show_header=False, box=None, padding=(0, COLUMN_PADDING), collapse_padding=True, expand=False)
    serial_table.add_column("port", style="bright_cyan", no_wrap=True, justify="right", width=max_port_width + COLUMN_PADDING)
    serial_table.add_column("default", no_wrap=True)
    serial_table.add_column("version", no_wrap=True)
    serial_table.add_column("core", style="bright_green", no_wrap=True)
    serial_table.add_column("device", style="bright_yellow", no_wrap=True)
    serial_table.add_column("manufacturer", style="dim", no_wrap=True, overflow="ignore")
    
    has_serial = False
    for port, version, core, device, manufacturer in serial_results:
        has_serial = True
        serial_table.add_row(
            port,
            get_default_marker(port),
            version,
            core,
            device,
            manufacturer
        )
    
    string_io = StringIO()
    temp_console = OutputHelper.make_console(file=string_io, force_terminal=True, width=300)
    
    if has_serial:
        temp_console.print(serial_table)
        temp_console.print()
        temp_console.print("[dim]  󰷌 default[/dim]")
    else:
        temp_console.print("  [dim]No serial devices found[/dim]")
    
    output_text = string_io.getvalue().rstrip()
    
    text_content = Text.from_ansi(output_text)
    text_content.no_wrap = True
    
    OutputHelper.print_panel(
        text_content,
        title="MicroPython Devices",
        border_style="data",
        title_align="left"
    )

    if permission_denied_ports:
        ports_list = ", ".join(_serial_port_display(p) for p in permission_denied_ports)
        if sys.platform.startswith("linux"):
            hint = (
                f"[yellow]Permission denied on: {ports_list}[/yellow]\n"
                "[dim]Add your user to the dialout group, then log out/in (or reboot):[/dim]\n"
                "  sudo usermod -aG dialout $USER"
            )
        elif sys.platform == "darwin":
            hint = (
                f"[yellow]Permission denied on: {ports_list}[/yellow]\n"
                "[dim]Another process may be holding the port, or it needs access permission.[/dim]"
            )
        else:
            hint = f"[yellow]Permission denied on: {ports_list}[/yellow]"
        OutputHelper.print_panel(hint, title="Permission Issue", border_style="error")


from ..helpers.output import VALID_PANEL_CATEGORIES, _CATEGORY_COLOR_KEYS

_VALID_BOX_STYLES = ('rounded', 'horizontals', 'square', 'heavy', 'double', 'minimal')


@app.command(rich_help_panel="Configuration")
def theme(
    args: list[str] = typer.Argument(None, help="theme subcommand"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True),
):
    """Show or configure the UI theme, panel colors, and panel box style."""
    if show_help:
        _theme_print_help()
        return

    if not args:
        _theme_show()
        return

    sub = args[0].lower()

    if sub == "color":
        if len(args) == 3:
            _theme_set_color(args[1], args[2])
        elif len(args) == 2:
            _theme_show_color(args[1])
        else:
            OutputHelper.print_panel(
                "Usage:\n"
                "  [bright_blue]replx theme color[/bright_blue] [yellow]CATEGORY HEX[/yellow]   [dim]# override panel color[/dim]\n"
                "  [bright_blue]replx theme color[/bright_blue] [yellow]CATEGORY[/yellow]        [dim]# show current value[/dim]\n\n"
                f"Valid categories: {', '.join(VALID_PANEL_CATEGORIES)}",
                title="Theme Error",
                border_style="error",
            )
            raise typer.Exit(1)

    elif sub == "box":
        if len(args) == 2:
            _theme_set_box(args[1])
        elif len(args) == 1:
            _theme_show_box()
        else:
            OutputHelper.print_panel(
                "Usage:\n"
                "  [bright_blue]replx theme box[/bright_blue] [yellow]STYLE[/yellow]   [dim]# set panel box style[/dim]\n"
                "  [bright_blue]replx theme box[/bright_blue]           [dim]# show current style[/dim]\n\n"
                f"Valid styles: {', '.join(_VALID_BOX_STYLES)}",
                title="Theme Error",
                border_style="error",
            )
            raise typer.Exit(1)

    elif sub == "reset":
        if len(args) == 2:
            _theme_reset_color(args[1])
        else:
            _theme_reset_all()

    else:
        OutputHelper.print_panel(
            f"Unknown subcommand: [red]{sub}[/red]\n\n"
            "  [bright_blue]replx theme[/bright_blue]                        [dim]# show theme + colors[/dim]\n"
            "  [bright_blue]replx theme color[/bright_blue] [yellow]CATEGORY HEX[/yellow]      [dim]# override panel color[/dim]\n"
            "  [bright_blue]replx theme color[/bright_blue] [yellow]CATEGORY[/yellow]           [dim]# show one category[/dim]\n"
            "  [bright_blue]replx theme box[/bright_blue] [yellow]STYLE[/yellow]               [dim]# set panel box style[/dim]\n"
            "  [bright_blue]replx theme reset[/bright_blue] [yellow][CATEGORY][/yellow]         [dim]# remove override(s)[/dim]",
            title="Theme Error",
            border_style="error",
        )
        raise typer.Exit(1)


def _theme_print_help():
    help_text = """\
Configure the TUI theme, panel border colors, and panel box style.

[bold cyan]Usage:[/bold cyan]
  replx theme
  replx theme color [yellow]CATEGORY[/yellow] [[yellow]HEX[/yellow]]
  replx theme box [[yellow]STYLE[/yellow]]
  replx theme reset [[yellow]CATEGORY[/yellow]]

[bold cyan]Subcommands:[/bold cyan]
  [bright_blue]replx theme[/bright_blue]                         [dim]# Show current theme and all panel colors[/dim]
  [bright_blue]replx theme color[/bright_blue] [yellow]CATEGORY HEX[/yellow]      [dim]# Override a panel category color[/dim]
  [bright_blue]replx theme color[/bright_blue] [yellow]CATEGORY[/yellow]          [dim]# Show current color for a category[/dim]
  [bright_blue]replx theme box[/bright_blue] [yellow]STYLE[/yellow]               [dim]# Set the global panel box style[/dim]
  [bright_blue]replx theme box[/bright_blue]                     [dim]# Show current box style[/dim]
  [bright_blue]replx theme reset[/bright_blue] [yellow]CATEGORY[/yellow]          [dim]# Remove color override for one category[/dim]
  [bright_blue]replx theme reset[/bright_blue]                   [dim]# Remove all overrides (restore theme defaults)[/dim]

[bold cyan]Panel Categories:[/bold cyan]
  [bright_blue]help[/bright_blue]          --help panels and subcommand hints  [dim](default: blue)[/dim]
  [bright_blue]success[/bright_blue]       operation completed successfully    [dim](default: green)[/dim]
  [bright_blue]data[/bright_blue]          status / read-only query results    [dim](default: cyan)[/dim]
  [bright_blue]mode[/bright_blue]          interactive mode banners            [dim](default: magenta)[/dim]
  [bright_blue]warning[/bright_blue]       warnings / partial failures         [dim](default: yellow)[/dim]
  [bright_blue]neutral[/bright_blue]       no-op / already in that state       [dim](default: dim)[/dim]
  [bright_blue]error[/bright_blue]         errors / invalid input              [dim](default: red)[/dim]

[bold cyan]Panel Box Styles:[/bold cyan]
  [bright_blue]rounded[/bright_blue]       Rounded corners (default)
  [bright_blue]horizontals[/bright_blue]   Top and bottom lines only
  [bright_blue]square[/bright_blue]        Square corners
  [bright_blue]heavy[/bright_blue]         Heavy border
  [bright_blue]double[/bright_blue]        Double-line border
  [bright_blue]minimal[/bright_blue]       Minimal border

[bold cyan]Color Format:[/bold cyan]
  Hex color in [yellow]#RRGGBB[/yellow] format.  Examples:
    replx theme color help #61afef
    replx theme color error #ff4444
    replx theme box double
    replx theme reset

[bold cyan]Storage:[/bold cyan]
  Settings are saved in [dim]~/.replx/.config[/dim] and apply to all sessions.
  Theme base colors come from the active theme (vscode-auto, one-dark-pro, etc).
  Category overrides take priority over theme base colors."""
    OutputHelper.print_panel(help_text, title="theme", border_style="help")


def _theme_show():
    from rich.table import Table
    from rich.panel import Panel
    from rich.console import Group
    from rich.text import Text

    panel_colors = AgentPortManager.read_panel_colors()
    panel_box = AgentPortManager.read_panel_box()
    theme_name = OutputHelper.get_theme_display_name()
    stored = OutputHelper.get_theme()

    data_color  = OutputHelper._resolve_category_color('data')
    guide_color = OutputHelper._resolve_category_color('help')

    header_str = f"Theme: [{data_color}]{theme_name}[/{data_color}]"
    if stored == 'vscode-auto':
        header_str += "  [dim](vscode-auto)[/dim]"
    header_str += f"\nBox style: [{data_color}]{panel_box}[/{data_color}]"

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Category",    width=12)
    table.add_column("Base key",    width=12)
    table.add_column("Theme color", width=14)
    table.add_column("Override",    width=14)
    table.add_column("Active",      width=16)

    for cat in VALID_PANEL_CATEGORIES:
        color_key = _CATEGORY_COLOR_KEYS[cat]
        theme_hex = OutputHelper._theme_styles.get(color_key, "")
        override  = panel_colors.get(cat)
        active    = override if override else theme_hex
        swatch    = f"[{active}]██[/{active}]" if active else "  "
        override_display = f"[{guide_color}]{override}[/{guide_color}]" if override else "[dim]-[/dim]"
        table.add_row(cat, color_key, theme_hex, override_display, f"{active}  {swatch}")

    footer_str = (
        f"[dim]replx theme color[/dim] [{guide_color}]CATEGORY HEX[/{guide_color}]"
        f"   [dim]# e.g. replx theme color error #ff4444[/dim]\n"
        f"[dim]replx theme box[/dim] [{guide_color}]STYLE[/{guide_color}]"
        f"             [dim]# e.g. replx theme box double[/dim]\n"
        f"[dim]replx theme reset[/dim]"
        f"                   [dim]# remove all overrides[/dim]"
    )

    content = Group(
        Text.from_markup(header_str + "\n"),
        table,
        Text.from_markup("\n" + footer_str),
    )

    OutputHelper._console.print(Panel(
        content,
        title="Theme",
        border_style=data_color,
        box=get_panel_box(),
        expand=True,
        width=OutputHelper._get_panel_width(),
        title_align="left",
    ))


def _theme_show_color(name: str):
    name = name.lower()
    if name not in VALID_PANEL_CATEGORIES:
        OutputHelper.print_panel(
            f"Unknown category: [red]{name}[/red]\n\n"
            f"Valid categories: {', '.join(VALID_PANEL_CATEGORIES)}",
            title="Theme Error",
            border_style="error",
        )
        raise typer.Exit(1)
    color_key = _CATEGORY_COLOR_KEYS[name]
    theme_hex = OutputHelper._theme_styles.get(color_key, "")
    panel_colors = AgentPortManager.read_panel_colors()
    override = panel_colors.get(name)
    active = override if override else theme_hex
    swatch = f"[{active}]████[/{active}]" if active else ""
    msg = (f"[bold]{name}[/bold]  base-key: [dim]{color_key}[/dim]\n"
           f"  Theme:  [bright_cyan]{theme_hex}[/bright_cyan]\n"
           f"  Active: [bright_cyan]{active}[/bright_cyan]  {swatch}")
    if override:
        msg += f"\n  [yellow]Override active[/yellow]"
    OutputHelper.print_panel(msg, title="Theme Color", border_style="data")


def _theme_set_color(name: str, value: str):
    import re as _re
    name = name.lower()
    if name not in VALID_PANEL_CATEGORIES:
        OutputHelper.print_panel(
            f"Unknown category: [red]{name}[/red]\n\n"
            f"Valid categories: {', '.join(VALID_PANEL_CATEGORIES)}",
            title="Theme Error",
            border_style="error",
        )
        raise typer.Exit(1)

    v = value.strip()
    if not v.startswith('#'):
        v = '#' + v
    if not _re.fullmatch(r'#[0-9a-fA-F]{6}', v):
        OutputHelper.print_panel(
            f"Invalid hex color: [red]{value}[/red]\n\n"
            "Expected format: [yellow]#RRGGBB[/yellow]  (e.g. [bright_cyan]#61afef[/bright_cyan])",
            title="Theme Error",
            border_style="error",
        )
        raise typer.Exit(1)

    panel_colors = AgentPortManager.read_panel_colors()
    old = panel_colors.get(name)
    panel_colors[name] = v
    AgentPortManager.write_panel_colors(panel_colors)

    swatch = f"[{v}]████[/{v}]"
    msg = f"[bold]{name}[/bold]  [green]{v}[/green]  {swatch}"
    if old:
        msg += f"\n[dim]was: {old}[/dim]"
    OutputHelper.print_panel(msg, title="Color Updated", border_style="success")


def _theme_show_box():
    current = AgentPortManager.read_panel_box()
    OutputHelper.print_panel(
        f"Current box style: [bright_cyan]{current}[/bright_cyan]\n\n"
        f"Available: {', '.join(_VALID_BOX_STYLES)}\n\n"
        "[dim]replx theme box rounded[/dim]\n"
        "[dim]replx theme box square[/dim]\n"
        "[dim]replx theme box heavy[/dim]\n"
        "[dim]replx theme box double[/dim]\n"
        "[dim]replx theme box minimal[/dim]",
        title="Panel Box Style",
        border_style="data",
    )


def _theme_set_box(style: str):
    from ..helpers import invalidate_panel_box_cache
    style = style.strip().lower()
    if style not in _VALID_BOX_STYLES:
        OutputHelper.print_panel(
            f"Unknown box style: [red]{style}[/red]\n\n"
            f"Valid styles: {', '.join(_VALID_BOX_STYLES)}",
            title="Theme Error",
            border_style="error",
        )
        raise typer.Exit(1)
    AgentPortManager.write_panel_box(style)
    invalidate_panel_box_cache()
    OutputHelper.print_panel(
        f"Panel box style set to [bright_cyan]{style}[/bright_cyan].\n"
        "[dim]Takes effect immediately for all new panels.[/dim]",
        title="Box Style Updated",
        border_style="success",
    )


def _theme_reset_color(name: str):
    name = name.lower()
    if name not in VALID_PANEL_CATEGORIES:
        OutputHelper.print_panel(
            f"Unknown category: [red]{name}[/red]\n\n"
            f"Valid categories: {', '.join(VALID_PANEL_CATEGORIES)}",
            title="Theme Error",
            border_style="error",
        )
        raise typer.Exit(1)
    panel_colors = AgentPortManager.read_panel_colors()
    if name not in panel_colors:
        OutputHelper.print_panel(
            f"[dim]{name}[/dim] has no override — already using theme default.",
            title="Theme Reset",
            border_style="neutral",
        )
        return
    del panel_colors[name]
    AgentPortManager.write_panel_colors(panel_colors)
    color_key = _CATEGORY_COLOR_KEYS[name]
    default_hex = OutputHelper._theme_styles.get(color_key, '')
    OutputHelper.print_panel(
        f"[bold]{name}[/bold] reset to theme default: "
        f"[bright_cyan]{default_hex}[/bright_cyan]",
        title="Color Reset",
        border_style="success",
    )


def _theme_reset_all():
    AgentPortManager.write_panel_colors({})
    OutputHelper.print_panel(
        "All panel color overrides removed. Theme defaults restored.",
        title="Theme Reset",
        border_style="success",
    )
