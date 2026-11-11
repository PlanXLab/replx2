import os
import glob
import base64
import hashlib
from typing import Optional

import typer
from rich.live import Live

from ..helpers import (
    OutputHelper, StoreManager, InstallHelper, CompilerHelper,
    get_panel_box, CONSOLE_WIDTH
)
from replx.utils import device_name_to_path
from ..config import STATE
from ..connection import (
    _ensure_connected, _create_agent_client
)
from ..app import app

_PKG_COMMAND_TIMEOUT = 60.0
_PKG_DOWNLOAD_TIMEOUT = 900.0
_PKG_INSTALL_TIMEOUT = 1800.0


def _sync_typehints(client) -> int:
    """Mirror agent-side package typehints into the client-side store so the
    IDE (replx setup) can use them even when the agent runs on another PC."""
    try:
        listing = client.send_command('pkg_typehints_list', timeout=_PKG_COMMAND_TIMEOUT)
    except Exception:
        return 0

    files = (listing or {}).get("files") or []
    if not files:
        return 0

    core = (listing.get("core") or STATE.core or "").strip()
    device = (listing.get("device") or STATE.device or "").strip()
    if not core:
        return 0

    synced = 0
    for entry in files:
        scope = entry.get("scope")
        relpath = entry.get("relpath", "")
        sha = entry.get("sha256", "")
        if scope not in ("core", "device") or not relpath or ".." in relpath:
            continue

        if scope == "core":
            base = os.path.join(StoreManager.pkg_root(), "core", core, "typehints")
        else:
            base = os.path.join(StoreManager.pkg_root(), "device", device_name_to_path(device), "typehints")
        out_path = os.path.join(base, relpath.replace("/", os.sep))

        if os.path.isfile(out_path) and sha:
            digest = hashlib.sha256()
            try:
                with open(out_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        digest.update(chunk)
                if digest.hexdigest() == sha:
                    continue
            except OSError:
                pass

        try:
            content = bytearray()
            offset = 0
            while True:
                resp = client.send_command(
                    'pkg_typehints_get', timeout=_PKG_COMMAND_TIMEOUT,
                    scope=scope, relpath=relpath, offset=offset,
                )
                chunk = base64.b64decode(resp.get("content", "") or "")
                content.extend(chunk)
                if resp.get("eof", True) or not chunk:
                    break
                offset += len(chunk)

            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(content)
            synced += 1
        except Exception:
            continue

    return synced


@app.command(name="pkg", rich_help_panel="Package Management")
def pkg(
    args: list[str] = typer.Argument(None, help="Package command and arguments"),
    owner: str = typer.Option("PlanXLab", help="GitHub repo owner (for search/download)"),
    repo: str = typer.Option("replx_libs", help="GitHub repo name (for search/download)"),
    ref: str = typer.Option("main", help="Git reference (for search/download)"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Package management for MicroPython devices.

[bold cyan]Usage:[/bold cyan] replx pkg [yellow]SUBCOMMAND[/yellow] [args]

[bold cyan]Subcommands:[/bold cyan]
  [yellow]search[/yellow] [dim][QUERY][/dim]          Search available libraries. [dim]QUERY[/dim] filters results by module name
  [yellow]download[/yellow]                Download to local store
  [yellow]update[/yellow] [green]TARGET[/green] [dim][OPTION][/dim]  Install to device (.py → .mpy)
  [yellow]clean[/yellow]                   Remove current core/device from local store

[bold cyan]Update Targets:[/bold cyan]
    [green]core.all[/green]                 Install all core libs for connected board
    [green]device.all[/green]               Install all device libs for connected board
    [green]core.<file>[/green]              Install one core file (e.g., core.termio.py)
    [green]device.<file>[/green]            Install one device file (e.g., device.termio.py)

[bold cyan]Examples:[/bold cyan]
  replx pkg search                                   [dim]List all libraries[/dim]
  replx pkg search audio                             [dim]Search by name[/dim]
  replx pkg download                                 [dim]Download for connected board[/dim]
  replx pkg update core.all                          [dim]Install all core libs[/dim]
  replx pkg update device.all                        [dim]Install all device libs[/dim]
  replx pkg update core.termio.py                    [dim]→ /lib/termio.mpy[/dim]
  replx pkg update device.termio.py                  [dim]→ /lib/<device>/termio.mpy[/dim]
  replx pkg clean                                    [dim]Remove current core/device[/dim]

[bold cyan]Workflow:[/bold cyan] search → download → update core.all

[bold cyan]Note:[/bold cyan]
  • Device connection required (--port or default)
  • Core/device auto-detected from connected board
    • Options --owner/--repo/--ref are for search/download/update only"""
        OutputHelper.print_panel(help_text, title="pkg", border_style="help")
        console.print()
        raise typer.Exit()
    
    if not args:
        OutputHelper.print_panel(
            "Subcommands: [bright_blue]search[/bright_blue]  [bright_blue]download[/bright_blue]  [bright_blue]update[/bright_blue]  [bright_blue]clean[/bright_blue]\n\n"
            "  [bright_green]replx pkg search[/bright_green]      [dim]# List available libraries[/dim]\n"
            "  [bright_green]replx pkg download[/bright_green]    [dim]# Download to local store[/dim]\n"
            "  [bright_green]replx pkg update[/bright_green]      [dim]# Install to device[/dim]\n"
            "  [bright_green]replx pkg clean[/bright_green]       [dim]# Remove current core/device[/dim]\n\n"
            "Use [bright_blue]replx pkg --help[/bright_blue] for details.",
            title="Package Management",
            border_style="help"
        )
        raise typer.Exit(1)
    
    cmd = args[0].lower()
    cmd_args = args[1:] if len(args) > 1 else []
    
    if cmd == "search":
        _pkg_search(cmd_args, owner, repo, ref)
    elif cmd == "download":
        _pkg_download(cmd_args, owner, repo, ref)
    elif cmd == "update":
        _pkg_update(cmd_args, owner, repo, ref)
    elif cmd == "clean":
        _pkg_clean(cmd_args)
    else:
        OutputHelper.print_panel(
            f"Unknown command: [red]{cmd}[/red]\n\n"
            "Available commands: [bright_blue]search[/bright_blue], [bright_blue]download[/bright_blue], [bright_blue]update[/bright_blue], [bright_blue]clean[/bright_blue]",
            title="Package Error",
            border_style="error"
        )
        raise typer.Exit(1)


def _pkg_search(args: list[str], owner: str, repo: str, ref: str):
    _ensure_connected()

    lib_name = args[0] if args else None

    client = _create_agent_client()
    try:
        result = client.send_command(
            'pkg_search', timeout=_PKG_COMMAND_TIMEOUT,
            owner=owner, repo=repo, ref=ref, query=lib_name,
        )
    except Exception as e:
        raise typer.BadParameter(f"Failed to load remote registry: {e}")

    rows = [tuple(r) for r in (result or {}).get("rows", [])]

    STAT_ICON_NEW = ""
    STAT_ICON_UPD = ""

    if not rows:
        OutputHelper.print_panel(
            "No results found.",
            title=f"Search Results [{owner}/{repo}@{ref}]",
            border_style="warning"
        )
        return

    def row_key(r):
        scope_order = 0 if r[0] == "core" else 1
        return (scope_order, r[1].lower(), r[4].lower())

    rows.sort(key=row_key)

    w1 = max(5, max(len(r[0]) for r in rows))
    w2 = max(6, max(len(r[1]) for r in rows))

    def _stat_display(stat: str) -> str:
        if stat == "NEW":
            return STAT_ICON_NEW
        if stat == "UPD":
            return STAT_ICON_UPD
        return ""

    w3 = max(4, max(len(_stat_display(r[2])) for r in rows))  # STAT
    w4 = max(3, max(len(r[3]) for r in rows))  # VER

    lines = []
    lines.append(f"{'SCOPE'.ljust(w1)}   {'TARGET'.ljust(w2)}   {'STAT'.ljust(w3)}   {'VER'.ljust(w4)}  FILE")
    lines.append("─" * (80 - 4))

    def _color_target(scope: str, padded: str) -> str:
        if scope == "core":
            return f"[bright_green]{padded}[/bright_green]"
        if scope == "device":
            return f"[bright_yellow]{padded}[/bright_yellow]"
        return padded

    def _color_stat(padded: str, stat: str) -> str:
        if stat == "NEW":
            return f"[bright_yellow]{padded}[/bright_yellow]"
        if stat == "UPD":
            return f"[cyan]{padded}[/cyan]"
        return padded

    def _color_file(padded: str, stat: str) -> str:
        if stat in ("NEW", "UPD"):
            return padded
        return f"[dim]{padded}[/dim]"

    for scope, target, stat, ver_str, shown_path, _pkg_name in rows:
        scope_cell = scope.ljust(w1)
        target_cell = _color_target(scope, target.ljust(w2))

        stat_shown = _stat_display(stat)
        stat_cell_raw = stat_shown.ljust(w3)
        stat_cell = _color_stat(stat_cell_raw, stat)

        ver_cell = ver_str.ljust(w4)

        file_plain = shown_path[4:]
        file_cell = _color_file(file_plain, stat)

        lines.append(f"{scope_cell}   {target_cell}   {stat_cell}   {ver_cell}  {file_cell}")

    lines.append("")
    lines.append(f"[dim]{STAT_ICON_NEW} new   {STAT_ICON_UPD} update[/dim]")

    
    OutputHelper.print_panel(
        "\n".join(lines),
        title=f"Search Results [{owner}/{repo}@{ref}]",
        border_style="mode",
    )


def _pkg_download(args: list[str], owner: str, repo: str, ref: str,
                  scope_filter: Optional[str] = None,
                  file_filter: Optional[str] = None):
    _ensure_connected()

    client = _create_agent_client()
    status = client.send_command('status')
    if not status or not status.get('connected'):
        OutputHelper.print_panel(
            "Device not connected.",
            title="Download Error",
            border_style="error"
        )
        raise typer.Exit(1)

    dev = status.get('device', '').strip()
    core = status.get('core', '').strip()

    if not core:
        OutputHelper.print_panel(
            "Failed to get device info from connected board.",
            title="Download Error",
            border_style="error"
        )
        raise typer.Exit(1)

    result = None
    with Live(OutputHelper.create_progress_panel(0, 1, title="Downloading", message="Checking remote registry..."),
              console=OutputHelper._console, refresh_per_second=10) as live:
        def on_progress(data):
            if not isinstance(data, dict) or data.get("phase") != "download":
                return
            done = data.get("current", 0)
            dl_total = data.get("total", 0) or 1
            target = data.get("target", "")
            live.update(OutputHelper.create_progress_panel(
                done, dl_total,
                title=f"Downloading {target}",
                message=f"Downloading... {data.get('file', '')} ({done}/{dl_total})"
            ))

        try:
            result = client.send_command_streaming(
                'pkg_download',
                timeout=_PKG_DOWNLOAD_TIMEOUT,
                progress_callback=on_progress,
                owner=owner, repo=repo, ref=ref,
                scope_filter=scope_filter,
                file_filter=file_filter,
            )
        except RuntimeError as e:
            live.stop()
            raise typer.BadParameter(str(e))

    result = result or {}

    if not result.get("core_in_registry", True):
        OutputHelper.print_panel(
            f"Core [yellow]{core}[/yellow] not found in remote registry.",
            title="Notice",
            border_style="warning"
        )
        raise typer.Exit(0)

    errors = result.get("errors") or []
    if errors:
        OutputHelper._console.print("\n[red]Download errors:[/red]")
        for err in errors[:5]:
            OutputHelper._console.print(f"  [yellow]•[/yellow] {err}")
        if len(errors) > 5:
            OutputHelper._console.print(f"  [dim]... and {len(errors) - 5} more errors[/dim]")
        raise typer.BadParameter(f"Failed to download {len(errors)} file(s)")

    total = result.get("total", 0)
    new_count = result.get("new", 0)
    upd_count = result.get("upd", 0)
    download_target = result.get("target", "")

    if not file_filter:
        _sync_typehints(client)

    if total == 0:
        if dev == core:
            message = f"Core [bright_green]{core}[/bright_green] is already up to date."
        else:
            message = f"Core [bright_green]{core}[/bright_green] and device [bright_green]{dev}[/bright_green] are already up to date."
    else:
        message = f"[bright_green]{download_target}[/bright_green]: [green]{total}[/green] file(s) downloaded. ( {new_count},  {upd_count})"
    
    OutputHelper.print_panel(
        message,
        title="Download Complete",
        border_style="success"
    )


INSTALL_HELP = """\
SPEC can be:
  (empty)             Install all core and device libs/files.
  core/               Install core libs into /lib/...
  device/             Install device libs into /lib/<device>/...
  ./foo.py            -> /lib/foo.mpy
  ./main.py|boot.py   -> /main.mpy or /boot.mpy
  ./app/              -> /app (folder)
  https://.../x.py    -> /lib/x.mpy
"""


def _install_spec_internal(spec: str, live=None, update_callback=None):
    if not (spec.startswith("core.") or spec.startswith("device.")):
        raise typer.BadParameter(f"Invalid spec format: {spec}")

    client = _create_agent_client()

    own_live = None

    def render(panel):
        if update_callback:
            update_callback(panel)
        elif live is not None:
            live.update(panel)
        elif own_live is not None:
            own_live.update(panel)

    def on_progress(data):
        if not isinstance(data, dict):
            return
        phase = data.get("phase")
        if phase == "compile":
            cur = data.get("current", 0)
            tot = data.get("total", 0) or 1
            render(OutputHelper.create_progress_panel(
                cur, tot,
                title="Compiling",
                message=f"Compiling {data.get('file', '')} ({min(cur + 1, tot)}/{tot})",
                counter_text=f"({cur}/{tot})",
            ))
        elif phase == "install":
            sent = data.get("current", 0)
            bytes_total = data.get("total", 0) or 1
            files_total = data.get("files_total", 0)
            fname = data.get("file", "")
            if fname:
                idx = data.get("file_index", 0)
                msg = f"[{idx + 1}/{files_total}] {fname} ({OutputHelper.format_bytes(data.get('file_bytes', 0))})"
            else:
                msg = "Complete"
            render(OutputHelper.create_progress_panel(
                sent, bytes_total,
                title=f"Installing {spec} to {STATE.device}",
                message=msg,
                counter_text=f"({OutputHelper.format_bytes(sent)}/{OutputHelper.format_bytes(bytes_total)})",
            ))

    try:
        if live is None and update_callback is None:
            own_live = Live(
                OutputHelper.create_progress_panel(
                    0, 1, title=f"Installing {spec} to {STATE.device}",
                    message="Preparing..."),
                console=OutputHelper._console, refresh_per_second=10)
            own_live.start()
        try:
            result = client.send_command_streaming(
                'pkg_install',
                timeout=_PKG_INSTALL_TIMEOUT,
                progress_callback=on_progress,
                spec=spec,
            )
        except RuntimeError as e:
            raise typer.BadParameter(str(e))
    finally:
        if own_live is not None:
            own_live.stop()

    if not result or not result.get("success"):
        raise RuntimeError(f"Library install failed: {result}")

    return {"files": result.get("files", 0), "bytes": result.get("bytes", 0)}


def _pkg_update(args: list[str], owner: str = "PlanXLab", repo: str = "replx_libs", ref: str = "main"):
    _ensure_connected()

    spec = args[0].strip() if args else None

    if len(args) > 1:
        OutputHelper.print_panel(
            "Only one TARGET is supported for [bright_blue]pkg update[/bright_blue].\n\n"
            "Valid targets:\n"
            "  [bright_blue]core.all[/bright_blue]\n"
            "  [bright_blue]device.all[/bright_blue]\n"
            "  [bright_blue]core.<file>[/bright_blue]\n"
            "  [bright_blue]device.<file>[/bright_blue]",
            title="Update Error",
            border_style="error"
        )
        raise typer.Exit(1)

    if spec in ("core/", "device/", "core", "device"):
        OutputHelper.print_panel(
            f"Unsupported target: [red]{spec}[/red]\n\n"
            "Use the new target format:\n"
            "  [bright_blue]core.all[/bright_blue]\n"
            "  [bright_blue]device.all[/bright_blue]\n"
            "  [bright_blue]core.<file>[/bright_blue]\n"
            "  [bright_blue]device.<file>[/bright_blue]",
            title="Update Error",
            border_style="error"
        )
        raise typer.Exit(1)

    if not spec:
        OutputHelper.print_panel(
            "Specify a target:\n\n"
            "  [bright_blue]core.all[/bright_blue]        Install all core libraries\n"
            "  [bright_blue]device.all[/bright_blue]      Install all device libraries\n"
            "  [bright_blue]core.<file>[/bright_blue]     Install one core file\n"
            "  [bright_blue]device.<file>[/bright_blue]   Install one device file\n\n"
            "Examples:\n"
            "  [bright_blue]replx pkg update core.all[/bright_blue]\n"
            "  [bright_blue]replx pkg update core.termio.py[/bright_blue]",
            title="Update Error",
            border_style="error"
        )
        raise typer.Exit(1)

    try:
        scope, rest = InstallHelper.resolve_spec(spec)
    except typer.BadParameter:
        OutputHelper.print_panel(
            f"Invalid target: [red]{spec}[/red]\n\n"
            "Valid targets:\n"
            "  [bright_blue]core.all[/bright_blue]\n"
            "  [bright_blue]device.all[/bright_blue]\n"
            "  [bright_blue]core.<file>[/bright_blue]\n"
            "  [bright_blue]device.<file>[/bright_blue]",
            title="Update Error",
            border_style="error"
        )
        raise typer.Exit(1)

    _pkg_download(
        [], owner, repo, ref,
        scope_filter=scope,
        file_filter=rest if rest else None,
    )

    try:
        _install_spec_internal(spec)
    except typer.BadParameter as e:
        if rest and "No local files to install" in str(e):
            OutputHelper.print_panel(
                f"Target file not found in local store: [red]{spec}[/red]\n\n"
                "Run [bright_blue]replx pkg search[/bright_blue] to inspect available modules.",
                title="Update Error",
                border_style="error"
            )
            raise typer.Exit(1)
        raise
    return


def _pkg_clean(args: list[str]):
    import shutil

    _ensure_connected()

    def _remove_client_typehints_cache():
        for path in (
            os.path.join(StoreManager.pkg_root(), "core", STATE.core),
            os.path.join(StoreManager.pkg_root(), "device", device_name_to_path(STATE.device)),
        ):
            if os.path.isdir(path):
                try:
                    shutil.rmtree(path)
                except OSError:
                    pass

    client = _create_agent_client()
    try:
        result = client.send_command('pkg_clean', timeout=_PKG_COMMAND_TIMEOUT)
    except Exception as e:
        OutputHelper.print_panel(
            f"Failed to clean local store: [red]{e}[/red]",
            title="Clean Error",
            border_style="error"
        )
        raise typer.Exit(1)

    result = result or {}

    if not result.get("found"):
        _remove_client_typehints_cache()
        OutputHelper.print_panel(
            f"No libraries for [yellow]{STATE.core}/{STATE.device}[/yellow] found in local store.",
            title="Clean",
            border_style="warning"
        )
        return

    removed_items = []
    for item in result.get("removed", []):
        if "entries" in item:
            removed_items.append(f"{item['item']} ({item['entries']} entries removed)")
        else:
            removed_items.append(f"{item['item']} ({OutputHelper.format_bytes(item.get('size', 0))})")

    total_size = result.get("total_size", 0)

    _remove_client_typehints_cache()

    if removed_items:
        items_text = "\n".join(f"  [green]✓[/green] {item}" for item in removed_items)
        OutputHelper.print_panel(
            f"Removed from local store:\n{items_text}\n\n"
            f"Total freed: [bright_yellow]{OutputHelper.format_bytes(total_size)}[/bright_yellow]",
            title="Clean Complete",
            border_style="success"
        )


@app.command(name="mpy", rich_help_panel="Package Management")
def mpy(
    files: list[str] = typer.Argument(None, help="Python files or directories to compile"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path (for single file)"),
    device: Optional[str] = typer.Option(None, "--device", "-d", help="Board destination path for .mpy (e.g., lib)"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Compile Python files to MicroPython bytecode (.mpy).

[bold cyan]Usage:[/bold cyan] replx mpy [yellow]FILE(s)[/yellow] [OPTIONS]

[bold cyan]Options:[/bold cyan]
  [yellow]-o, --output PATH[/yellow]     Output path (single file only)
  [yellow]-d, --device PATH[/yellow]     Install compiled .mpy to board at this path (e.g., lib)

[bold cyan]Examples:[/bold cyan]
  replx mpy main.py                  [dim]# Compile single file[/dim]
  replx mpy main.py -o out.mpy       [dim]# Specify output path[/dim]
  replx mpy main.py -d lib           [dim]# Compile and install to /lib/ on device[/dim]
  replx mpy *.py -d lib              [dim]# Compile all and install to /lib/ on device[/dim]
  replx mpy *.py                     [dim]# Compile all .py files[/dim]
  replx mpy src/                     [dim]# Compile folder[/dim]

[bold cyan]Output:[/bold cyan]
  • Single file: same directory as source (or -o path)
  • Multiple files: same directory as each source
  • Folder: parallel structure in folder

[bold cyan]Note:[/bold cyan]
  • Requires board connection (architecture auto-detected)
  • Compiled .mpy files are smaller and use less RAM"""
        OutputHelper.print_panel(help_text, title="mpy", border_style="help")
        console.print()
        raise typer.Exit()
    
    if not files:
        OutputHelper.print_panel(
            "Specify Python files to compile:\n\n"
            "  [bright_green]replx mpy main.py[/bright_green]          [dim]# Single file[/dim]\n"
            "  [bright_green]replx mpy *.py[/bright_green]             [dim]# Multiple files[/dim]\n"
            "  [bright_green]replx mpy src/[/bright_green]             [dim]# Folder[/dim]\n\n"
            "Use [bright_blue]replx mpy --help[/bright_blue] for details.",
            title="MPY Compiler",
            border_style="help"
        )
        raise typer.Exit(1)
    
    _ensure_connected()
    target_arch = STATE.core
    
    if not target_arch:
        OutputHelper.print_panel(
            "Could not determine board architecture.\n\n"
            "Please reconnect the board and try again.",
            title="Architecture Unknown",
            border_style="error"
        )
        raise typer.Exit(1)
    
    py_files = []
    for pattern in files:
        if '*' in pattern or '?' in pattern:
            matches = glob.glob(pattern)
            for m in matches:
                if m.endswith('.py') and os.path.isfile(m):
                    py_files.append(os.path.abspath(m))
        elif os.path.isdir(pattern):
            for root, _, fnames in os.walk(pattern):
                for fn in fnames:
                    if fn.endswith('.py'):
                        py_files.append(os.path.abspath(os.path.join(root, fn)))
        elif os.path.isfile(pattern):
            if pattern.endswith('.py'):
                py_files.append(os.path.abspath(pattern))
            else:
                OutputHelper.print_panel(
                    f"Not a Python file: [red]{pattern}[/red]",
                    title="Invalid File",
                    border_style="error"
                )
                raise typer.Exit(1)
        else:
            OutputHelper.print_panel(
                f"File not found: [red]{pattern}[/red]",
                title="File Not Found",
                border_style="error"
            )
            raise typer.Exit(1)
    
    if not py_files:
        OutputHelper.print_panel(
            "No Python files found to compile.",
            title="No Files",
            border_style="warning"
        )
        raise typer.Exit(1)
    
    if output and len(py_files) > 1:
        OutputHelper.print_panel(
            "The [yellow]-o/--output[/yellow] option can only be used with a single file.",
            title="Invalid Option",
            border_style="error"
        )
        raise typer.Exit(1)
    
    version = STATE.version if STATE.version else "1.29.0"
    arch_args = CompilerHelper._march_for_core(target_arch, version)
    
    compiled = []
    failed = []
    total_src_size = 0
    total_mpy_size = 0
    
    try:
        import mpy_cross
    except ImportError:
        OutputHelper.print_panel(
            "mpy-cross is not installed.\n\n"
            "Install it with: [bright_green]pip install mpy-cross[/bright_green]",
            title="Missing Dependency",
            border_style="error"
        )
        raise typer.Exit(1)
    
    for py_file in py_files:
        src_size = os.path.getsize(py_file)
        total_src_size += src_size
        
        if output:
            out_mpy = output if output.endswith('.mpy') else output + '.mpy'
        else:
            out_mpy = os.path.splitext(py_file)[0] + '.mpy'
        
        try:
            compiled_out = CompilerHelper.compile_file(py_file, out_mpy, target_arch, version)
            mpy_size = os.path.getsize(compiled_out)
            total_mpy_size += mpy_size
            compiled.append((py_file, compiled_out, src_size, mpy_size))
        except Exception as e:
            failed.append((py_file, str(e)))
    
    if compiled:
        if len(compiled) == 1:
            py_file, out_mpy, src_size, mpy_size = compiled[0]
            ratio = (1 - mpy_size / src_size) * 100 if src_size > 0 else 0
            OutputHelper.print_panel(
                f"[green]✓[/green] {os.path.basename(py_file)} → {os.path.basename(out_mpy)}\n\n"
                f"  Source: [cyan]{OutputHelper.format_bytes(src_size)}[/cyan]\n"
                f"  Output: [cyan]{OutputHelper.format_bytes(mpy_size)}[/cyan] [dim]({ratio:.0f}% smaller)[/dim]\n"
                f"  Arch:   [yellow]{target_arch}[/yellow]",
                title="Compiled",
                border_style="success"
            )
        else:
            lines = []
            for py_file, out_mpy, src_size, mpy_size in compiled:
                lines.append(f"[green]✓[/green] {os.path.basename(py_file)} → {os.path.basename(out_mpy)} ({OutputHelper.format_bytes(mpy_size)})")
            
            ratio = (1 - total_mpy_size / total_src_size) * 100 if total_src_size > 0 else 0
            lines.append("")
            lines.append(f"Total: [cyan]{OutputHelper.format_bytes(total_src_size)}[/cyan] → [cyan]{OutputHelper.format_bytes(total_mpy_size)}[/cyan] [dim]({ratio:.0f}% smaller)[/dim]")
            lines.append(f"Arch:  [yellow]{target_arch}[/yellow]")
            
            OutputHelper.print_panel(
                "\n".join(lines),
                title=f"Compiled {len(compiled)} files",
                border_style="success"
            )
    
    if device and compiled:
        device_path = device.lstrip("/").rstrip("/")
        client = _create_agent_client()
        try:
            client.send_command('mkdir', path="/" + device_path)
        except Exception:
            pass

        upload_failed = []
        upload_ok = []

        for py_file, out_mpy, src_size, mpy_size in compiled:
            basename = os.path.basename(out_mpy)
            remote_path = f"/{device_path}/{basename}"

            progress_state = {"current": 0}
            progress_lock = threading.Lock()

            def progress_callback(data, _state=progress_state, _lock=progress_lock):
                with _lock:
                    if isinstance(data, dict):
                        _state["current"] = data.get("current", 0)

            upload_result = [None]

            def do_upload(lp=out_mpy, rp=remote_path):
                try:
                    upload_result[0] = client.send_command_streaming(
                        'put_from_local_streaming',
                        progress_callback=progress_callback,
                        local_path=lp,
                        remote_path=rp
                    )
                except Exception as e:
                    upload_result[0] = {"error": str(e)}

            upload_thread = threading.Thread(target=do_upload, daemon=True)

            with Live(OutputHelper.create_progress_panel(0, mpy_size, title=f"Installing to {STATE.device}", message=f"{basename} ({OutputHelper.format_bytes(mpy_size)})", counter_text=f"0/{OutputHelper.format_bytes(mpy_size)}"), console=OutputHelper._console, refresh_per_second=10) as live:
                upload_thread.start()
                while upload_thread.is_alive():
                    with progress_lock:
                        current_bytes = progress_state["current"]
                    live.update(OutputHelper.create_progress_panel(current_bytes, mpy_size, title=f"Installing to {STATE.device}", message=f"{basename} ({OutputHelper.format_bytes(mpy_size)})", counter_text=f"{OutputHelper.format_bytes(current_bytes)}/{OutputHelper.format_bytes(mpy_size)}"))
                    time.sleep(0.05)
                upload_thread.join()
                live.update(OutputHelper.create_progress_panel(mpy_size, mpy_size, title=f"Installing to {STATE.device}", message=f"{basename} ({OutputHelper.format_bytes(mpy_size)})", counter_text=f"{OutputHelper.format_bytes(mpy_size)}/{OutputHelper.format_bytes(mpy_size)}"))

            resp = upload_result[0]
            if resp and not resp.get('success'):
                upload_failed.append((basename, resp.get('error', 'Unknown error')))
            else:
                upload_ok.append((basename, remote_path, mpy_size))

        if upload_ok:
            if len(upload_ok) == 1:
                name, rpath, size = upload_ok[0]
                OutputHelper.print_panel(
                    f"[green]✓[/green] {name} → [cyan]{rpath}[/cyan]\n\n"
                    f"  Size: [cyan]{OutputHelper.format_bytes(size)}[/cyan]",
                    title=f"Installed to {STATE.device}",
                    border_style="success"
                )
            else:
                lines = [f"[green]✓[/green] {name} → [cyan]{rpath}[/cyan] ({OutputHelper.format_bytes(size)})" for name, rpath, size in upload_ok]
                total_uploaded = sum(s for _, _, s in upload_ok)
                lines.append("")
                lines.append(f"Total: [cyan]{OutputHelper.format_bytes(total_uploaded)}[/cyan]  Dest: [cyan]/{device_path}/[/cyan]")
                OutputHelper.print_panel(
                    "\n".join(lines),
                    title=f"Installed {len(upload_ok)} files to {STATE.device}",
                    border_style="success"
                )

        if upload_failed:
            lines = [f"[red]✗[/red] {name}: {err}" for name, err in upload_failed]
            OutputHelper.print_panel(
                "\n".join(lines),
                title="Upload Failed",
                border_style="error"
            )
            raise typer.Exit(1)

    if failed:
        lines = [f"[red]✗[/red] {os.path.basename(f)}: {err}" for f, err in failed]
        OutputHelper.print_panel(
            "\n".join(lines),
            title=f"Failed ({len(failed)} files)",
            border_style="error"
        )
        raise typer.Exit(1)
