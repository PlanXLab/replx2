import os
import sys
import time
import posixpath
import glob
import fnmatch
import threading
from typing import Iterator, Optional

import typer
from rich.panel import Panel
from rich.live import Live

from replx.utils.exceptions import ProtocolError
from replx.utils.constants import PUTDIR_EXCLUDED_DIRS, PUTDIR_EXCLUDED_EXTENSIONS
from ..helpers import OutputHelper, get_panel_box, CONSOLE_WIDTH
from ..connection import _ensure_connected, _create_agent_client, _get_device_port
from ..app import app


def _iter_uploadable_files(local_dir: str) -> Iterator[str]:
    for parent, child_dirs, child_files in os.walk(local_dir, followlinks=False):
        child_dirs[:] = [
            name for name in child_dirs if name.lower() not in PUTDIR_EXCLUDED_DIRS
        ]
        for filename in child_files:
            if os.path.splitext(filename)[1].lower() not in PUTDIR_EXCLUDED_EXTENSIONS:
                yield os.path.join(parent, filename)


@app.command(rich_help_panel="File Operations")
def get(
    args: Optional[list[str]] = typer.Argument(None, help="Remote file(s) and local destination"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Download files or directories from the device to your computer.

[bold cyan]Usage:[/bold cyan]
  replx get [yellow]REMOTE[/yellow] [yellow]LOCAL[/yellow]
  replx get [yellow]REMOTE...[/yellow] [yellow]LOCAL[/yellow]   [dim]# Multiple files[/dim]

[bold cyan]Arguments:[/bold cyan]
  [yellow]REMOTE[/yellow]    File(s) or directory on device [red][required][/red]
  [yellow]LOCAL[/yellow]     Destination on your computer [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  [dim]# Single file[/dim]
  replx get main.py ./               [dim]# Download to current dir[/dim]
  replx get /lib/audio.py ./backup   [dim]# Download to backup folder[/dim]

  [dim]# Directory (recursive)[/dim]
  replx get /lib ./mylib             [dim]# Download entire /lib[/dim]

  [dim]# Multiple files[/dim]
  replx get /a.py /b.py ./           [dim]# Download multiple files[/dim]

  [dim]# Wildcards[/dim]
  replx get /*.py ./backup           [dim]# All .py files from root[/dim]
  replx get /lib/*.mpy ./            [dim]# All .mpy from /lib[/dim]
  replx get test*.py ./              [dim]# Files starting with test[/dim]

[bold cyan]Note:[/bold cyan]
  • Last argument is always the local destination
  • Directories are downloaded recursively
  • Wildcards (*,?) are expanded on the device

[bold cyan]Related:[/bold cyan]
  replx put local /remote   [dim]# Upload files instead[/dim]"""
        OutputHelper.print_panel(help_text, title="get", border_style="help")
        console.print()
        raise typer.Exit()
    
    status = _ensure_connected()
    device_root_fs = status.get('device_root_fs', '/')
    
    if not args or len(args) < 2:
        OutputHelper.print_panel(
            "Missing required arguments.\n\n"
            "[bold cyan]Usage:[/bold cyan] replx get [yellow]REMOTE... LOCAL[/yellow]\n\n"
            "At least 2 arguments required: remote file(s) and local destination.",
            title="Download Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    cmd_idx = next((i for i, arg in enumerate(sys.argv) if arg == 'get'), None)
    if cmd_idx is not None and cmd_idx + 1 < len(sys.argv):
        raw_args = []
        for arg in sys.argv[cmd_idx + 1:]:
            if arg.startswith('-'):
                continue
            raw_args.append(arg)
        if len(raw_args) >= 2:
            args = raw_args
    
    local = args[-1]
    remotes = args[:-1]
    
    def normalize_remote(path: str) -> str:
        return OutputHelper.normalize_remote_path(path)
    
    client = _create_agent_client()
    
    files_to_download = []
    
    for remote_pattern in remotes:
        remote = normalize_remote(remote_pattern)
        
        if '*' in remote_pattern or '?' in remote_pattern:
            dir_path = posixpath.dirname(remote) or '/'
            basename_pattern = posixpath.basename(remote)
            
            try:
                result = client.send_command('ls', path=dir_path, detailed=True)
                if result is None:
                    raise RuntimeError("No response from device")
                items = [(item['name'], item['size'], item['is_dir']) for item in result.get('items', [])]
                
                for name, size, is_dir in items:
                    if fnmatch.fnmatch(name, basename_pattern):
                        full_path = posixpath.join(dir_path, name)
                        files_to_download.append((full_path, name, is_dir))
            except RuntimeError as e:
                if OutputHelper.handle_error(e, f"Download: {remote_pattern}"):
                    raise typer.Exit(1)
                OutputHelper.print_panel(
                    f"Download failed: [red]{e}[/red]",
                    title="Download Failed",
                    border_style="error"
                )
                continue
            except Exception:
                OutputHelper.print_panel(
                    f"[red]{remote_pattern}[/red] - pattern did not match any files.",
                    title="Download Failed",
                    border_style="error"
                )
                continue
        else:
            try:
                result = client.send_command('is_dir', path=remote)
                if result is None:
                    raise RuntimeError("No response from device")
                is_dir = result.get('is_dir', False)
                basename = posixpath.basename(remote.rstrip('/'))
                files_to_download.append((remote, basename, is_dir))
            except RuntimeError as e:
                display_remote = remote.replace(device_root_fs, "", 1)
                if OutputHelper.handle_error(e, f"Download: {display_remote}"):
                    raise typer.Exit(1)
                OutputHelper.print_panel(
                    f"Download failed: [red]{e}[/red]",
                    title="Download Failed",
                    border_style="error"
                )
                continue
            except Exception:
                display_remote = remote.replace(device_root_fs, "", 1)
                OutputHelper.print_panel(
                    f"[red]{display_remote}[/red] does not exist.",
                    title="Download Failed",
                    border_style="error"
                )
                continue
    
    if not files_to_download:
        OutputHelper.print_panel(
            "No files to download.",
            title="Download",
            border_style="warning"
        )
        raise typer.Exit(1)
    
    total_files = len(files_to_download)
    success_count = 0
    
    if total_files == 1:
        remote, basename, is_dir = files_to_download[0]
        display_remote = remote.replace(device_root_fs, "", 1)
        
        if os.path.exists(local) and os.path.isdir(local):
            local_path = os.path.join(local, basename)
        else:
            local_path = local
        
        try:
            if is_dir:
                progress_state = {"current": 0, "total": 0, "file": "", "status": "starting"}
                
                def progress_callback(progress_data):
                    progress_state.update(progress_data)
                
                with Live(OutputHelper.create_progress_panel(0, 1, title=f"Downloading {basename}", message="Scanning directory..."), console=OutputHelper._console, refresh_per_second=10) as live:
                    result_holder = {"result": None, "error": None, "done": False}
                    
                    def stream_callback(data):
                        progress_state.update(data)
                    
                    def download_task():
                        try:
                            result = client.send_command_streaming(
                                'getdir_to_local',
                                remote_path=remote,
                                local_path=local_path,
                                progress_callback=stream_callback,
                                timeout=300
                            )
                            result_holder["result"] = result
                        except Exception as e:
                            result_holder["error"] = str(e)
                        finally:
                            result_holder["done"] = True
                    
                    download_thread = threading.Thread(target=download_task, daemon=True)
                    download_thread.start()
                    
                    while not result_holder["done"]:
                        current = progress_state.get("current", 0)
                        total = progress_state.get("total", 1) or 1
                        file = progress_state.get("file", "")
                        status = progress_state.get("status", "")
                        
                        if status == "starting":
                            message = "Scanning directory..."
                        elif status == "downloading" and file:
                            message = f"Downloading {file}..."
                        else:
                            message = ""
                        
                        live.update(OutputHelper.create_progress_panel(current, total, title=f"Downloading {basename}", message=message))
                        time.sleep(0.05)
                    
                    live.update(OutputHelper.create_progress_panel(
                        progress_state.get("current", 0), 
                        progress_state.get("total", 0) or 1, 
                        title=f"Downloading {basename}"
                    ))
                    
                    if result_holder["error"]:
                        raise Exception(result_holder["error"])
            else:
                file_count = 1
                with Live(OutputHelper.create_progress_panel(0, file_count, title=f"Downloading {basename}", message="Downloading file..."), console=OutputHelper._console, refresh_per_second=10) as live:
                    result = client.send_command('get_to_local', remote_path=remote, local_path=local_path, timeout=60)
                    live.update(OutputHelper.create_progress_panel(1, 1, title=f"Downloading {basename}"))
            
            OutputHelper.print_panel(
                f"Downloaded [bright_blue]{display_remote}[/bright_blue]\nto [green]{local_path}[/green]",
                title="Download Complete",
                border_style="success"
            )
        except Exception as e:
            OutputHelper.print_panel(
                f"Download failed: [red]{str(e)}[/red]",
                title="Download Failed",
                border_style="error"
            )
            raise typer.Exit(1)
    else:
        if not os.path.exists(local):
            os.makedirs(local)
        elif not os.path.isdir(local):
            OutputHelper.print_panel(
                f"Destination [red]{local}[/red] must be a directory when downloading multiple files.",
                title="Download Failed",
                border_style="error"
            )
            raise typer.Exit(1)
        
        with Live(OutputHelper.create_progress_panel(0, total_files, title=f"Downloading {total_files} item(s)", message="Starting..."), console=OutputHelper._console, refresh_per_second=10) as live:
            for idx, (remote, basename, is_dir) in enumerate(files_to_download):
                display_remote = remote.replace(device_root_fs, "", 1)
                live.update(OutputHelper.create_progress_panel(idx, total_files, title=f"Downloading {total_files} item(s)", message=f"Downloading {display_remote}..."))
                
                local_path = os.path.join(local, basename)
                
                try:
                    if is_dir:
                        result = client.send_command_streaming(
                            'getdir_to_local', 
                            remote_path=remote, 
                            local_path=local_path, 
                            timeout=300
                        )
                    else:
                        result = client.send_command('get_to_local', remote_path=remote, local_path=local_path, timeout=60)
                    success_count += 1
                except Exception as e:
                    OutputHelper._console.print(f"[red]Failed to download {display_remote}: {str(e)}[/red]")
            
            live.update(OutputHelper.create_progress_panel(total_files, total_files, title=f"Downloading {total_files} item(s)"))
        
        OutputHelper.print_panel(
            f"Downloaded [green]{success_count}[/green] out of {total_files} file(s)\nto [green]{local}[/green]",
            title="Download Complete",
            border_style="success" if success_count == total_files else "warning"
        )


@app.command(name="cat", rich_help_panel="File Operations")
def cat(
    remote: str = typer.Argument("", help="Remote file path"),
    number: bool = typer.Option(False, "-n", "--number", help="Show line numbers"),
    lines: Optional[str] = typer.Option(None, "-L", "--lines", help="Range: lines (text) or bytes (binary)"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Display the contents of a file on the connected device.

Text files show as-is; binary files show in hex format.

[bold cyan]Usage:[/bold cyan]
  replx cat [yellow]FILE[/yellow]
  replx cat -n [yellow]FILE[/yellow]        [dim]# With line numbers[/dim]
  replx cat -L N:M [yellow]FILE[/yellow]   [dim]# Show lines N to M[/dim]

[bold cyan]Options:[/bold cyan]
  [yellow]-n, --number[/yellow]          Show line numbers (text only)
  [yellow]-L, --lines N:M[/yellow]       Line range (text) or byte range (binary)

[bold cyan]Arguments:[/bold cyan]
  [yellow]FILE[/yellow]      Remote file path [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  [dim]# Text files[/dim]
  replx cat main.py                   [dim]# Show entire file[/dim]
  replx cat -n /lib/audio.py          [dim]# With line numbers[/dim]
  replx cat -L 1:20 main.py           [dim]# Lines 1-20[/dim]
  replx cat -L 50: main.py            [dim]# From line 50 to end[/dim]
  replx cat -L :10 boot.py            [dim]# First 10 lines[/dim]

  [dim]# Binary files (.mpy, etc.)[/dim]
  replx cat audio.mpy                 [dim]# Show hex dump[/dim]
  replx cat -L 0:256 file.mpy         [dim]# First 256 bytes[/dim]
  replx cat -L 100:+64 file.mpy       [dim]# 64 bytes from offset 100[/dim]

[bold cyan]Related:[/bold cyan]
  replx get file ./       [dim]# Download to local machine[/dim]"""
        OutputHelper.print_panel(help_text, title="cat", border_style="help")
        console.print()
        raise typer.Exit()
    
    if not remote:
        OutputHelper.print_panel(
            "Missing required argument.\n\n"
            "[bold cyan]Usage:[/bold cyan] replx cat [yellow]FILE[/yellow]\n\n"
            "Use [bright_blue]replx cat --help[/bright_blue] for details.",
            title="Cat Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    _ensure_connected()

    remote = OutputHelper.normalize_remote_path(remote)
    
    display_remote = remote.replace('/', '', 1) if remote.startswith('/') else remote
    
    client = _create_agent_client()
    
    try:
        result = client.send_command('cat', path=remote)
        if result is None:
            raise RuntimeError("No response from device")
        content = result.get('content', '')
        is_binary = result.get('is_binary', False)
    except Exception as e:
        error_msg = str(e)
        if OutputHelper.handle_error(e, f"Read: {display_remote}"):
            raise typer.Exit(1)
        elif 'is a directory' in error_msg.lower():
            OutputHelper.print_panel(
                f"[red]{display_remote}[/red] is a directory, not a file.",
                title="Read Failed",
                border_style="error"
            )
        else:
            OutputHelper.print_panel(
                f"[red]{display_remote}[/red] does not exist.",
                title="Read Failed",
                border_style="error"
            )
        raise typer.Exit(1)
    
    if is_binary:
        raw_bytes = bytes.fromhex(content)
        total_bytes = len(raw_bytes)
        start_byte = 0
        end_byte = total_bytes
        
        if lines:
            try:
                if ':' not in lines:
                    raise ValueError("Invalid format")
                parts = lines.split(':')
                if len(parts) != 2:
                    raise ValueError("Invalid format")
                
                if parts[0]:
                    start_byte = int(parts[0])
                    if start_byte < 0:
                        start_byte = 0
                
                if parts[1]:
                    if parts[1].startswith('+'):
                        count = int(parts[1][1:])
                        end_byte = start_byte + count
                    else:
                        end_byte = int(parts[1])
                
                start_byte = max(0, min(start_byte, total_bytes))
                end_byte = max(start_byte, min(end_byte, total_bytes))
            except (ValueError, IndexError):
                OutputHelper.print_panel(
                    f"Invalid byte range format: [red]{lines}[/red]\nFor binary files, use N:M (byte range)",
                    title="Invalid Option",
                    border_style="error"
                )
                raise typer.Exit(1)
        
        data = raw_bytes[start_byte:end_byte]
        
        from rich.text import Text
        hex_output = Text()
        
        first_line_start = (start_byte // 16) * 16
        last_line_end = ((end_byte + 15) // 16) * 16
        
        for line_offset in range(first_line_start, last_line_end, 16):
            hex_output.append(f"{line_offset:08x}", style="cyan")
            hex_output.append("  ")
            
            hex_chars = []
            ascii_chars = []
            
            for byte_offset in range(line_offset, line_offset + 16):
                if start_byte <= byte_offset < end_byte:
                    data_index = byte_offset - start_byte
                    b = data[data_index]
                    hex_chars.append((f'{b:02x}', "bright_green"))
                    if 32 <= b < 127:
                        ascii_chars.append((chr(b), None))
                    else:
                        ascii_chars.append((".", "dim"))
                else:
                    hex_chars.append(("--", "dim"))
                    ascii_chars.append((" ", None))
            
            for i, (h, style) in enumerate(hex_chars):
                if i > 0:
                    hex_output.append(" ")
                hex_output.append(h, style=style)
            
            hex_output.append("   ")
            
            for c, style in ascii_chars:
                hex_output.append(c, style=style)
            
            hex_output.append("\n")
        
        range_info = f" (bytes {start_byte}-{end_byte})" if lines else f" ({total_bytes} bytes)"
        title = f"Binary File (Hex): {display_remote}{range_info}"
        
        OutputHelper.print_panel(
            hex_output,
            title=title,
            border_style="data"
        )
        return 
    else:
        text_content = content
        content_lines = text_content.split('\n')
        total_lines = len(content_lines)
        
        start_line = 1
        end_line = total_lines
        if lines:
            try:
                if ':' in lines:
                    parts = lines.split(':')
                    if parts[0]:
                        start_line = max(1, int(parts[0]))
                    if parts[1]:
                        if parts[1].startswith('+'):
                            end_line = start_line + int(parts[1][1:]) - 1
                        else:
                            end_line = int(parts[1])
                    end_line = min(end_line, total_lines)
            except (ValueError, IndexError):
                pass
        
        display_lines = content_lines[start_line-1:end_line]
        
        if number:
            width = len(str(start_line + len(display_lines) - 1))
            formatted = []
            for idx, line in enumerate(display_lines):
                line_num = start_line + idx
                formatted.append(f"{line_num:>{width}}: {line}")
            display_content = '\n'.join(formatted)
        else:
            display_content = '\n'.join(display_lines)
        
        range_info = f" (lines {start_line}-{end_line})" if lines else f" ({total_lines} lines)"
        title = f"File Content: {display_remote}{range_info}"
    
    syntax_extensions = {
        '.py': 'python',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.md': 'markdown',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'ini',
    }
    
    _, ext = os.path.splitext(remote.lower())
    language = syntax_extensions.get(ext)
    
    if language and not is_binary:
        from rich.syntax import Syntax
        
        syntax = Syntax(
            display_content if not number else '\n'.join(display_lines),
            language,
            theme=OutputHelper.get_syntax_theme(),
            line_numbers=number,
            start_line=start_line if number else 1,
            word_wrap=False
        )

        OutputHelper.print_panel(
            syntax,
            title=title,
            border_style="data"
        )
    else:
        OutputHelper.print_panel(
            display_content,
            title=title,
            border_style="data"
        )


@app.command(rich_help_panel="File Operations")
def mkdir(
    remotes: Optional[list[str]] = typer.Argument(None, help="Directories to create"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Create directories on the connected device.

[bold cyan]Usage:[/bold cyan]
  replx mkdir [yellow]DIR[/yellow]
  replx mkdir [yellow]DIR...[/yellow]        [dim]# Multiple directories[/dim]

[bold cyan]Arguments:[/bold cyan]
  [yellow]DIR[/yellow]       Directory path(s) to create [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  replx mkdir /lib                    [dim]# Create /lib[/dim]
  replx mkdir /tests                  [dim]# Create /tests[/dim]
  replx mkdir /lib/audio /lib/net     [dim]# Create multiple[/dim]
  replx mkdir /a/b/c                  [dim]# Creates /a/b/c (nested)[/dim]

[bold cyan]Note:[/bold cyan]
  • Creates parent directories automatically if needed
  • No error if directory already exists

[bold cyan]Related:[/bold cyan]
  replx rm -r /dir          [dim]# Remove directory[/dim]"""
        OutputHelper.print_panel(help_text, title="mkdir", border_style="help")
        console.print()
        raise typer.Exit()
    
    _ensure_connected()
    
    if not remotes:
        OutputHelper.print_panel(
            "Missing required arguments.\n\n"
            "[bold cyan]Usage:[/bold cyan] replx mkdir [yellow]DIR...[/yellow]\n\n"
            "Use [bright_blue]replx mkdir --help[/bright_blue] for details.",
            title="Create Directory Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    success_count = 0
    failed_items = []
    
    with _create_agent_client() as client:
        for remote in remotes:
            if not remote.startswith('/'):
                remote = '/' + remote
            
            try:
                client.send_command('mkdir', path=remote)
                success_count += 1
                if len(remotes) == 1:
                    OutputHelper.print_panel(
                        f"Directory [bright_blue]{remote}[/bright_blue] exists or was created.",
                        title="Create Directory",
                        border_style="success"
                    )
            except Exception as e:
                error_msg = str(e)
                failed_items.append(f"{remote}: {error_msg}")
                if len(remotes) == 1:
                    OutputHelper.print_panel(
                        f"Failed to create [bright_blue]{remote}[/bright_blue]: {error_msg}",
                        title="Create Directory",
                        border_style="error"
                    )
    
    if len(remotes) > 1:
        if failed_items:
            OutputHelper.print_panel(
                f"Ensured [green]{success_count}[/green] director{'y' if success_count == 1 else 'ies'} exist.\n"
                f"Failed:\n{chr(10).join(failed_items)}",
                title="Create Directories",
                border_style="warning" if success_count > 0 else "error"
            )
        else:
            OutputHelper.print_panel(
                f"Ensured [green]{success_count}[/green] director{'y' if success_count == 1 else 'ies'} exist.",
                title="Create Directories",
                border_style="success"
            )


@app.command(rich_help_panel="File Operations")
def rm(
    args: Optional[list[str]] = typer.Argument(None, help="Files or directories to remove"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Remove directories recursively"),
    force: bool = typer.Option(False, "-f", "--force", help="Force removal without confirmation"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Delete files or directories from the connected device.

[bold cyan]Usage:[/bold cyan]
  replx rm [yellow]FILE[/yellow]
  replx rm -r [yellow]DIR[/yellow]          [dim]# Remove directory[/dim]
  replx rm -f [yellow]FILE[/yellow]         [dim]# Skip confirmation[/dim]

[bold cyan]Options:[/bold cyan]
  [yellow]-r, --recursive[/yellow]       Remove directories and contents
  [yellow]-f, --force[/yellow]           Don't ask for confirmation

[bold cyan]Arguments:[/bold cyan]
  [yellow]FILE/DIR[/yellow]    File(s) or directory to remove [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  [dim]# Single file[/dim]
  replx rm /main.py                   [dim]# Delete file (asks confirm)[/dim]
  replx rm -f /main.py                [dim]# Delete without asking[/dim]

  [dim]# Multiple files[/dim]
  replx rm /a.py /b.py /c.py          [dim]# Delete multiple files[/dim]

  [dim]# Wildcards[/dim]
  replx rm /*.pyc                     [dim]# Delete all .pyc files[/dim]
  replx rm /lib/*.mpy                 [dim]# Delete .mpy in /lib[/dim]
  replx rm -f test*.py                [dim]# Delete test*.py silently[/dim]

  [dim]# Directories[/dim]
  replx rm -r /backup                 [dim]# Remove directory[/dim]
  replx rm -rf /temp                  [dim]# Remove without confirmation[/dim]

[bold yellow]Warning:[/bold yellow]
  Deleted files cannot be recovered!

[bold cyan]Related:[/bold cyan]
  replx get file ./         [dim]# Backup before deleting[/dim]"""
        OutputHelper.print_panel(help_text, title="rm", border_style="help")
        console.print()
        raise typer.Exit()
    
    status = _ensure_connected()
    device_root_fs = status.get('device_root_fs', '/')
    
    cmd_idx = next((i for i, arg in enumerate(sys.argv) if arg == 'rm'), None)
    if cmd_idx is not None and cmd_idx + 1 < len(sys.argv):
        raw_args = []
        for arg in sys.argv[cmd_idx + 1:]:
            if arg.startswith('-'):
                if 'f' in arg:
                    force = True
                if 'r' in arg:
                    recursive = True
                continue
            raw_args.append(arg)
        if raw_args:
            args = raw_args
    
    if not args:
        OutputHelper.print_panel(
            "Missing required arguments.\n\n"
            "[bold cyan]Usage:[/bold cyan] replx rm [yellow]FILE...[/yellow]\n\n"
            "Use [bright_blue]replx rm --help[/bright_blue] for details.",
            title="Remove Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    client = _create_agent_client()
    
    def resolve_patterns(patterns: list[str]) -> list[str]:
        resolved = []
        for pattern in patterns:
            remote = OutputHelper.normalize_remote_path(pattern)
            if '*' in pattern or '?' in pattern:
                dir_path = posixpath.dirname(remote) or '/'
                basename_pattern = posixpath.basename(remote)
                try:
                    result = client.send_command('ls', path=dir_path, detailed=True)
                    if result is None:
                        raise RuntimeError("No response from device")
                    items = result.get('items', [])
                    for item in items:
                        if fnmatch.fnmatch(item['name'], basename_pattern):
                            resolved.append(posixpath.join(dir_path, item['name']))
                except RuntimeError as e:
                    if OutputHelper.handle_error(e, "rm"):
                        raise typer.Exit(1)
                    resolved.append(pattern)
                except Exception:
                    resolved.append(pattern)
            else:
                resolved.append(remote)
        return resolved
    
    def check_exists(path: str) -> bool:
        try:
            result = client.send_command('is_dir', path=path)
            return result.get('exists', True)
        except Exception:
            return True
    
    if not force:
        has_wildcard = any('*' in p or '?' in p for p in args)
        
        if has_wildcard:
            resolved_files = resolve_patterns(args)
            if not resolved_files:
                OutputHelper.print_panel(
                    "No files matched the given pattern.",
                    title="Remove",
                    border_style="neutral"
                )
                raise typer.Exit(0)
            
            MAX_SHOW = 5
            if len(resolved_files) <= MAX_SHOW:
                files_display = '\n  '.join(resolved_files)
                confirm_msg = f"Remove {len(resolved_files)} item(s)?\n  {files_display}\n[y/N]"
            else:
                shown = '\n  '.join(resolved_files[:MAX_SHOW])
                remaining = len(resolved_files) - MAX_SHOW
                confirm_msg = f"Remove {len(resolved_files)} item(s)?\n  {shown}\n  ... and {remaining} more\n[y/N]"
        else:
            existing_files = []
            not_found_files = []
            for pattern in args:
                remote = OutputHelper.normalize_remote_path(pattern)
                if check_exists(remote):
                    existing_files.append(pattern)
                else:
                    not_found_files.append(pattern)
            
            if not_found_files:
                if len(not_found_files) == 1:
                    OutputHelper.print_panel(
                        f"rm: [red]{not_found_files[0]}[/red] does not exist.",
                        title="Remove Failed",
                        border_style="error"
                    )
                else:
                    files_str = ', '.join(not_found_files)
                    OutputHelper.print_panel(
                        f"rm: Files not found: [red]{files_str}[/red]",
                        title="Remove Failed",
                        border_style="error"
                    )
                raise typer.Exit(1)
            
            files_str = ', '.join(args)
            confirm_msg = f"Remove {files_str}? [y/N]"
        
        try:
            confirm = typer.prompt(confirm_msg, default="n", show_default=False)
        except (typer.Abort, EOFError):
            OutputHelper.print_panel(
                "Confirmation was not answered (no interactive input). Use [bright_blue]-f[/bright_blue] to remove without prompting.",
                title="Remove Cancelled",
                border_style="neutral"
            )
            raise typer.Exit(1)
        if confirm.lower() != 'y':
            typer.echo("Cancelled.")
            raise typer.Exit(0)
    
    success_count = 0
    failed_items = []
    dir_without_r = []
    
    for pattern in args:
        remote = OutputHelper.normalize_remote_path(pattern)
         
        if '*' in pattern or '?' in pattern:
            dir_path = posixpath.dirname(remote) or '/'
            basename_pattern = posixpath.basename(remote)
            
            try:
                result = client.send_command('ls', path=dir_path, detailed=True)
                if result is None:
                    raise RuntimeError("No response from device")
                items = [(item['name'], item['size'], item['is_dir']) for item in result.get('items', [])]
                matched = False
                
                for name, size, is_dir in items:
                    if fnmatch.fnmatch(name, basename_pattern):
                        matched = True
                        full_path = posixpath.join(dir_path, name)
                        try:
                            if is_dir:
                                if not recursive:
                                    dir_without_r.append(name)
                                    continue
                                client.send_command('rmdir', path=full_path)
                            else:
                                client.send_command('rm', path=full_path)
                            success_count += 1
                        except RuntimeError as e:
                            if OutputHelper.handle_error(e, "rm"):
                                raise typer.Exit(1)
                            failed_items.append(name)
                        except Exception:
                            failed_items.append(name)
                
                if not matched:
                    failed_items.append(pattern)
            except RuntimeError as e:
                if OutputHelper.handle_error(e, "rm"):
                    raise typer.Exit(1)
                failed_items.append(pattern)
            except Exception:
                failed_items.append(pattern)
        else:
            try:
                is_dir_result = client.send_command('is_dir', path=remote)
                if is_dir_result is None:
                    raise RuntimeError("No response from device")
                is_dir = is_dir_result.get('is_dir', False)
                
                if is_dir:
                    if not recursive:
                        display_remote = remote.replace(device_root_fs, "", 1)
                        dir_without_r.append(display_remote)
                        continue
                    client.send_command('rmdir', path=remote)
                    item_type = "Directory"
                else:
                    client.send_command('rm', path=remote)
                    item_type = "File"
                success_count += 1
                
                display_path = remote.replace(device_root_fs, "", 1)
                if len(args) == 1:
                    OutputHelper.print_panel(
                        f"{item_type} [bright_blue]{display_path}[/bright_blue] removed successfully.",
                        title="Remove",
                        border_style="success"
                    )
            except RuntimeError as e:
                if OutputHelper.handle_error(e, "rm"):
                    raise typer.Exit(1)
                failed_items.append(pattern)
            except Exception:
                failed_items.append(pattern)
    
    if dir_without_r:
        if len(dir_without_r) == 1:
            OutputHelper.print_panel(
                f"rm: [red]{dir_without_r[0]}[/red] is a directory.\n\n"
                "Use [cyan]-r[/cyan] option to remove directories recursively:\n"
                f"  replx rm -r {dir_without_r[0]}",
                title="Remove Failed",
                border_style="error"
            )
        else:
            dirs_str = "\n".join(f"  - {d}" for d in dir_without_r)
            OutputHelper.print_panel(
                f"rm: cannot remove directories (use [cyan]-r[/cyan] option):\n{dirs_str}\n\n"
                "Example: replx rm -r <directory>",
                title="Remove Failed",
                border_style="error"
            )
        if not success_count and not failed_items:
            raise typer.Exit(1)
    
    # Summary for multiple items
    if len(args) > 1 or success_count > 1:
        if failed_items:
            OutputHelper.print_panel(
                f"Removed [green]{success_count}[/green] item(s).\nFailed: {', '.join(failed_items)}",
                title="Remove Complete",
                border_style="warning"
            )
        else:
            OutputHelper.print_panel(
                f"Removed [green]{success_count}[/green] item(s) successfully.",
                title="Remove Complete",
                border_style="success"
            )
    elif failed_items and not dir_without_r:
        remote_display = args[0].replace(device_root_fs, "", 1) if args[0].startswith(device_root_fs) else args[0]
        OutputHelper.print_panel(
            f"rm: [red]{remote_display}[/red] does not exist.",
            title="Remove Failed",
            border_style="error"
        )
        raise typer.Exit(1)
    elif failed_items:
        remote_display = args[0].replace(device_root_fs, "", 1) if args[0].startswith(device_root_fs) else args[0]
        OutputHelper.print_panel(
            f"[red]{remote_display}[/red] does not exist.",
            title="Remove",
            border_style="error"
        )


@app.command(rich_help_panel="File Operations")
def cp(
    args: Optional[list[str]] = typer.Argument(None, help="Source file(s) and destination"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Copy directories recursively"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Copy files or directories on the connected device.

[bold cyan]Usage:[/bold cyan]
  replx cp [yellow]SRC[/yellow] [yellow]DEST[/yellow]
  replx cp -r [yellow]DIR[/yellow] [yellow]DEST[/yellow]      [dim]# Copy directory[/dim]
  replx cp [yellow]SRC...[/yellow] [yellow]DEST[/yellow]      [dim]# Multiple files[/dim]

[bold cyan]Options:[/bold cyan]
  [yellow]-r, --recursive[/yellow]       Copy directories and contents

[bold cyan]Arguments:[/bold cyan]
  [yellow]SRC[/yellow]       Source file(s) or directory [red][required][/red]
  [yellow]DEST[/yellow]      Destination path [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  [dim]# Single file[/dim]
  replx cp /main.py /backup.py        [dim]# Copy with new name[/dim]
  replx cp /lib/a.py /backup          [dim]# Copy to directory[/dim]

  [dim]# Multiple files[/dim]
  replx cp x.py y.py z.py /backup     [dim]# Copy multiple[/dim]

  [dim]# Wildcards[/dim]
  replx cp *.py /backup               [dim]# Copy all .py files[/dim]
  replx cp /lib/*.mpy /backup         [dim]# Copy all .mpy files[/dim]

  [dim]# Directories[/dim]
  replx cp -r /lib /lib_backup        [dim]# Copy entire directory[/dim]
  replx cp -r a.py dir1 /backup       [dim]# Mix files and directories[/dim]

[bold cyan]Note:[/bold cyan]
  • Last argument is always the destination
  • Use -r for directories (required)
  • Destination directory is created if needed

[bold cyan]Related:[/bold cyan]
  replx mv src dest       [dim]# Move instead of copy[/dim]"""
        OutputHelper.print_panel(help_text, title="cp", border_style="help")
        console.print()
        raise typer.Exit()
    
    _ensure_connected()
    
    if not args or len(args) < 2:
        OutputHelper.print_panel(
            "Missing required arguments.\n\n"
            "[bold cyan]Usage:[/bold cyan] replx cp [yellow]SOURCE... DEST[/yellow]\n\n"
            "At least 2 arguments required: source file(s) and destination.",
            title="Copy Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    cmd_idx = next((i for i, arg in enumerate(sys.argv) if arg == 'cp'), None)
    if cmd_idx is not None and cmd_idx + 1 < len(sys.argv):
        raw_args = []
        for arg in sys.argv[cmd_idx + 1:]:
            if arg in ('-r', '--recursive', '-h', '--help'):
                continue
            raw_args.append(arg)
        if len(raw_args) >= 2:
            args = raw_args
    
    dest = args[-1]
    sources = args[:-1]
    
    client = _create_agent_client()
    
    if len(sources) == 1 and '*' not in sources[0] and '?' not in sources[0]:
        source = sources[0]
        try:
            resp = client.send_command('cp', source=source, dest=dest, recursive=recursive)
            
            success_count = resp.get('files_count', 1) if resp.get('copied') else 0
            total_files = resp.get('files_count', 1) if 'files_count' in resp else 1
            is_empty_dir = resp.get('is_empty_dir', False)
            display_source = resp.get('source', source)
            display_dest = resp.get('dest', dest)
            
            if resp.get('copied'):
                if is_empty_dir:
                    OutputHelper.print_panel(
                        f"Copied empty directory [bright_blue]{display_source}[/bright_blue]\nto [green]{display_dest}[/green]",
                        title="Copy Complete",
                        border_style="success"
                    )
                elif total_files == 1:
                    OutputHelper.print_panel(
                        f"Copied [bright_blue]{display_source}[/bright_blue]\nto [green]{display_dest}[/green]",
                        title="Copy Complete",
                        border_style="success"
                    )
                else:
                    OutputHelper.print_panel(
                        f"Copied [green]{success_count}[/green] file(s)\nfrom [bright_blue]{display_source}[/bright_blue]\nto [green]{display_dest}[/green]",
                        title="Copy Complete",
                        border_style="success"
                    )
            else:
                OutputHelper.print_panel(
                    "Source directory is empty or no files to copy.",
                    title="Copy",
                    border_style="warning"
                )
        except RuntimeError as e:
            error = str(e)
            
            if 'not found' in error.lower() or 'does not exist' in error.lower():
                OutputHelper.print_panel(
                    f"[red]{source}[/red] does not exist.",
                    title="Copy Failed",
                    border_style="error"
                )
            elif 'is a directory' in error.lower() or 'EISDIR' in error:
                OutputHelper.print_panel(
                    f"cp: [red]{source}[/red] is a directory (not copied).\n\n"
                    "Use [cyan]-r[/cyan] option to copy directories recursively:\n"
                    f"  replx cp -r {source} <destination>",
                    title="Copy Failed",
                    border_style="error"
                )
            else:
                OutputHelper.print_panel(
                    f"Copy failed: [red]{error}[/red]",
                    title="Copy Failed",
                    border_style="error"
                )
            raise typer.Exit(1)
        return
    
    files_to_copy = []
    
    for source_pattern in sources:
        if '*' in source_pattern or '?' in source_pattern:
            dir_path = posixpath.dirname(source_pattern) or '/'
            pattern = posixpath.basename(source_pattern)
            
            try:
                result = client.send_command('ls', path=dir_path, detailed=True)
                items = result.get('items', []) if isinstance(result, dict) else []
                
                matched = False
                for item in items:
                    if isinstance(item, dict):
                        name = item.get('name', '')
                        is_dir = item.get('is_dir', False)
                    else:
                        name = str(item)
                        is_dir = False
                    if fnmatch.fnmatch(name, pattern):
                        full_path = posixpath.join(dir_path, name)
                        files_to_copy.append((full_path, name, is_dir))
                        matched = True
                if not matched:
                    OutputHelper.print_panel(
                        f"No files matching: [red]{source_pattern}[/red]",
                        title="Copy Failed",
                        border_style="error"
                    )
                    raise typer.Exit(1)
            except typer.Exit:
                raise
            except Exception as e:
                OutputHelper.print_panel(
                    f"Error processing pattern '{source_pattern}': {e}",
                    title="Copy Failed",
                    border_style="error"
                )
                raise typer.Exit(1)
        else:
            try:
                result = client.send_command('is_dir', path=source_pattern)
                is_dir = result if isinstance(result, bool) else result.get('is_dir', False)
            except Exception:
                OutputHelper.print_panel(
                    f"cp: [red]{source_pattern}[/red] does not exist.",
                    title="Copy Failed",
                    border_style="error"
                )
                raise typer.Exit(1)
            
            basename = posixpath.basename(source_pattern)
            
            if is_dir and not recursive:
                OutputHelper.print_panel(
                    f"cp: [red]{source_pattern}[/red] is a directory.\n"
                    f"Use [yellow]-r[/yellow] option to copy directories.",
                    title="Copy Failed",
                    border_style="error"
                )
                raise typer.Exit(1)
            files_to_copy.append((source_pattern, basename, is_dir))
    
    if not files_to_copy:
        OutputHelper.print_panel(
            "No files to copy.",
            title="Copy",
            border_style="warning"
        )
        raise typer.Exit(1)
    
    try:
        result = client.send_command('is_dir', path=dest)
        dest_is_dir = result if isinstance(result, bool) else result.get('is_dir', False)
    except Exception:
        dest_is_dir = False
    
    if len(files_to_copy) > 1 and not dest_is_dir:
        OutputHelper.print_panel(
            f"When copying multiple files, destination must be a directory.\n"
            f"Destination [red]{dest}[/red] is not a directory.",
            title="Copy Failed",
            border_style="error"
        )
        raise typer.Exit(1)
    
    success_count = 0
    for source_path, basename, is_dir in files_to_copy:
        if dest_is_dir:
            target = posixpath.join(dest, basename)
        else:
            target = dest
        
        try:
            client.send_command('cp', source=source_path, dest=target, recursive=recursive)
            success_count += 1
        except Exception as e:
            OutputHelper.print_panel(
                f"Failed to copy [red]{source_path}[/red]: {e}",
                title="Copy Failed",
                border_style="error"
            )
            if success_count > 0:
                OutputHelper.print_panel(
                    f"Copied {success_count} of {len(files_to_copy)} file(s) before error.",
                    title="Partial Copy",
                    border_style="warning"
                )
            raise typer.Exit(1)
    
    if success_count == 1:
        source_path = files_to_copy[0][0]
        OutputHelper.print_panel(
            f"Copied [bright_blue]{source_path}[/bright_blue]\nto [green]{dest}[/green]",
            title="Copy Complete",
            border_style="success"
        )
    else:
        OutputHelper.print_panel(
            f"Copied [green]{success_count}[/green] file(s) to [green]{dest}[/green]",
            title="Copy Complete",
            border_style="success"
        )


@app.command(rich_help_panel="File Operations")
def mv(
    args: Optional[list[str]] = typer.Argument(None, help="Source file(s) and destination"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Move directories recursively"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Move or rename files and directories on the connected device.

[bold cyan]Usage:[/bold cyan]
  replx mv [yellow]SRC[/yellow] [yellow]DEST[/yellow]           [dim]# Rename or move file[/dim]
  replx mv -r [yellow]DIR[/yellow] [yellow]DEST[/yellow]        [dim]# Move directory[/dim]
  replx mv [yellow]SRC...[/yellow] [yellow]DEST[/yellow]        [dim]# Multiple files[/dim]

[bold cyan]Options:[/bold cyan]
  [yellow]-r, --recursive[/yellow]       Move directories and contents

[bold cyan]Arguments:[/bold cyan]
  [yellow]SRC[/yellow]       Source file(s) or directory [red][required][/red]
  [yellow]DEST[/yellow]      Destination path [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  [dim]# Rename[/dim]
  replx mv /old.py /new.py            [dim]# Rename file[/dim]
  replx mv /tests /test               [dim]# Rename directory[/dim]

  [dim]# Move to directory[/dim]
  replx mv /main.py /backup           [dim]# Move file into /backup[/dim]
  replx mv x.py y.py z.py /backup     [dim]# Move multiple files[/dim]

  [dim]# Wildcards[/dim]
  replx mv *.py /backup               [dim]# Move all .py files[/dim]
  replx mv /lib/*.mpy /compiled       [dim]# Move all .mpy files[/dim]

  [dim]# Directories[/dim]
  replx mv -r /lib/audio /lib/sound   [dim]# Move directory[/dim]
  replx mv -r a.py dir1 /backup       [dim]# Mix files and dirs[/dim]

[bold cyan]Note:[/bold cyan]
  • Last argument is the destination
  • Use -r for directories (required)
  • Unlike copy, the source is removed after move

[bold cyan]Related:[/bold cyan]
  replx cp src dest       [dim]# Copy instead of move[/dim]"""
        OutputHelper.print_panel(help_text, title="mv", border_style="help")
        console.print()
        raise typer.Exit()
    
    _ensure_connected()
    
    if not args or len(args) < 2:
        OutputHelper.print_panel(
            "Missing required arguments.\n\n"
            "[bold cyan]Usage:[/bold cyan] replx mv [yellow]SOURCE... DEST[/yellow]\n\n"
            "At least 2 arguments required: source file(s) and destination.",
            title="Move Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    cmd_idx = next((i for i, arg in enumerate(sys.argv) if arg == 'mv'), None)
    if cmd_idx is not None and cmd_idx + 1 < len(sys.argv):
        raw_args = []
        for arg in sys.argv[cmd_idx + 1:]:
            if arg in ('-r', '--recursive', '-h', '--help'):
                continue
            raw_args.append(arg)
        if len(raw_args) >= 2:
            args = raw_args
    
    dest = args[-1]
    sources = args[:-1]
    
    client = _create_agent_client()
    
    if len(sources) == 1 and '*' not in sources[0] and '?' not in sources[0]:
        source = sources[0]
        try:
            result = client.send_command('mv', source=source, dest=dest)
            display_source = result.get('source', source)
            display_dest = result.get('dest', dest)
            
            OutputHelper.print_panel(
                f"Moved [bright_blue]{display_source}[/bright_blue]\nto [green]{display_dest}[/green]",
                title="Move Complete",
                border_style="success"
            )
        except Exception as e:
            error = str(e)
            
            if 'ENOENT' in error or 'not found' in error.lower() or 'does not exist' in error.lower():
                OutputHelper.print_panel(
                    f"mv: [red]{source}[/red] does not exist.",
                    title="Move Failed",
                    border_style="error"
                )
            elif 'is a directory' in error.lower():
                OutputHelper.print_panel(
                    f"mv: [red]{source}[/red] is a directory.\n"
                    f"Use [yellow]-r[/yellow] option to move directories.",
                    title="Move Failed",
                    border_style="error"
                )
            else:
                OutputHelper.print_panel(
                    f"Move failed: {error}",
                    title="Move Failed",
                    border_style="error"
                )
            raise typer.Exit(1)
        return
    
    files_to_move = []
    
    for source_pattern in sources:
        if '*' in source_pattern or '?' in source_pattern:
            dir_path = posixpath.dirname(source_pattern) or '/'
            pattern = posixpath.basename(source_pattern)
            
            try:
                result = client.send_command('ls', path=dir_path, detailed=True)
                items = result.get('items', []) if isinstance(result, dict) else []
                
                matched = False
                for item in items:
                    if isinstance(item, dict):
                        name = item.get('name', '')
                        is_dir = item.get('is_dir', False)
                    else:
                        name = str(item)
                        is_dir = False
                    if fnmatch.fnmatch(name, pattern):
                        full_path = posixpath.join(dir_path, name)
                        files_to_move.append((full_path, name, is_dir))
                        matched = True
                if not matched:
                    OutputHelper.print_panel(
                        f"No files matching: [red]{source_pattern}[/red]",
                        title="Move Failed",
                        border_style="error"
                    )
                    raise typer.Exit(1)
            except typer.Exit:
                raise
            except Exception as e:
                OutputHelper.print_panel(
                    f"Error processing pattern '{source_pattern}': {e}",
                    title="Move Failed",
                    border_style="error"
                )
                raise typer.Exit(1)
        else:
            try:
                result = client.send_command('is_dir', path=source_pattern)
                is_dir = result if isinstance(result, bool) else result.get('is_dir', False)
            except Exception:
                OutputHelper.print_panel(
                    f"mv: [red]{source_pattern}[/red] does not exist.",
                    title="Move Failed",
                    border_style="error"
                )
                raise typer.Exit(1)
            
            basename = posixpath.basename(source_pattern)
            
            if is_dir and not recursive:
                OutputHelper.print_panel(
                    f"mv: [red]{source_pattern}[/red] is a directory.\n"
                    f"Use [yellow]-r[/yellow] option to move directories.",
                    title="Move Failed",
                    border_style="error"
                )
                raise typer.Exit(1)
            files_to_move.append((source_pattern, basename, is_dir))
    
    if not files_to_move:
        OutputHelper.print_panel(
            "No files to move.",
            title="Move",
            border_style="warning"
        )
        raise typer.Exit(1)
    
    try:
        result = client.send_command('is_dir', path=dest)
        dest_is_dir = result if isinstance(result, bool) else result.get('is_dir', False)
    except Exception:
        dest_is_dir = False
    
    if len(files_to_move) > 1 and not dest_is_dir:
        OutputHelper.print_panel(
            f"When moving multiple files, destination must be a directory.\n"
            f"Destination [red]{dest}[/red] is not a directory.",
            title="Move Failed",
            border_style="error"
        )
        raise typer.Exit(1)
    
    success_count = 0
    failed_items = []
    
    for source, basename, is_dir in files_to_move:
        if dest_is_dir:
            final_dest = posixpath.join(dest, basename)
        else:
            final_dest = dest
        
        try:
            client.send_command('mv', source=source, dest=final_dest)
            success_count += 1
        except Exception as e:
            failed_items.append((source, str(e)))
    
    if len(files_to_move) == 1 and success_count == 1:
        source, basename, is_dir = files_to_move[0]
        display_dest = posixpath.join(dest, basename) if dest_is_dir else dest
        item_type = "Directory" if is_dir else "File"
        OutputHelper.print_panel(
            f"Moved [bright_blue]{source}[/bright_blue]\nto [green]{display_dest}[/green]",
            title=f"Move Complete ({item_type})",
            border_style="success"
        )
    elif success_count > 0:
        if failed_items:
            fail_list = "\n".join([f"  • {src}" for src, _ in failed_items])
            OutputHelper.print_panel(
                f"Moved [green]{success_count}[/green] out of {len(files_to_move)} file(s)\n"
                f"to [green]{dest}[/green]\n\n"
                f"Failed:\n{fail_list}",
                title="Move Partially Complete",
                border_style="warning"
            )
        else:
            OutputHelper.print_panel(
                f"Moved [green]{success_count}[/green] file(s)\nto [green]{dest}[/green]",
                title="Move Complete",
                border_style="success"
            )
    else:
        fail_list = "\n".join([f"  • {src}: {err}" for src, err in failed_items])
        OutputHelper.print_panel(
            f"Failed to move files:\n{fail_list}",
            title="Move Failed",
            border_style="error"
        )
        raise typer.Exit(1)


@app.command(rich_help_panel="File Operations")
def touch(
    remotes: Optional[list[str]] = typer.Argument(None, help="Files to create"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Create empty files on the connected device.

[bold cyan]Usage:[/bold cyan]
  replx touch [yellow]FILE[/yellow]
  replx touch [yellow]FILE...[/yellow]       [dim]# Multiple files[/dim]

[bold cyan]Arguments:[/bold cyan]
  [yellow]FILE[/yellow]      File path(s) to create [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  replx touch /config.py              [dim]# Create single file[/dim]
  replx touch /a.py /b.py /c.py       [dim]# Create multiple files[/dim]
  replx touch /lib/placeholder.txt    [dim]# Create in subdirectory[/dim]

[bold cyan]Note:[/bold cyan]
  • Creates missing files as empty and preserves existing file contents
  • Does not set modification timestamps
  • Parent directory must exist

[bold cyan]Use cases:[/bold cyan]
  • Create placeholder files
  • Create empty __init__.py for packages
  • Create config files to edit later

[bold cyan]Related:[/bold cyan]
  replx put file /        [dim]# Upload file with content[/dim]"""
        OutputHelper.print_panel(help_text, title="touch", border_style="help")
        console.print()
        raise typer.Exit()
    
    _ensure_connected()
    
    if not remotes:
        OutputHelper.print_panel(
            "Missing required arguments.\n\n"
            "[bold cyan]Usage:[/bold cyan] replx touch [yellow]FILE...[/yellow]\n\n"
            "Use [bright_blue]replx touch --help[/bright_blue] for details.",
            title="Touch Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    client = _create_agent_client()
    success_count = 0
    failed_items = []
    
    for remote in remotes:
        try:
            result = client.send_command('touch', path=remote)
            success_count += 1
            
            if len(remotes) == 1:
                display_path = result.get('created', remote)
                OutputHelper.print_panel(
                    f"File [bright_blue]{display_path}[/bright_blue] is ready (created if missing; contents preserved).",
                    title="Touch File",
                    border_style="success"
                )
        except Exception as e:
            failed_items.append(remote)
            if len(remotes) == 1:
                OutputHelper.print_panel(
                    f"Touch failed: {e}",
                    title="Touch Failed",
                    border_style="error"
                )
    
    if len(remotes) > 1:
        if failed_items:
            OutputHelper.print_panel(
                f"Ensured [green]{success_count}[/green] file(s) exist.\nFailed: {', '.join(failed_items)}",
                title="Touch Files",
                border_style="warning"
            )
        else:
            OutputHelper.print_panel(
                f"Ensured [green]{success_count}[/green] file(s) exist.",
                title="Touch Files",
                border_style="success"
            )


@app.command(rich_help_panel="File Operations")
def ls(
    path: str = typer.Argument("/", help="Directory path to list"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="List subdirectories recursively"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
List files and directories on the connected device.

[bold cyan]Usage:[/bold cyan]
  replx ls [[yellow]PATH[/yellow]]          [dim]# Default: / (root)[/dim]
  replx ls -r [[yellow]PATH[/yellow]]       [dim]# Recursive listing[/dim]

[bold cyan]Options:[/bold cyan]
  [yellow]-r, --recursive[/yellow]       Show subdirectories as tree

[bold cyan]Arguments:[/bold cyan]
  [yellow]PATH[/yellow]      Directory to list [dim][default: /][/dim]

[bold cyan]Examples:[/bold cyan]
  replx ls                    [dim]# List root directory[/dim]
  replx ls /lib               [dim]# List /lib directory[/dim]
  replx ls -r                 [dim]# Full tree from root[/dim]
  replx ls -r /lib            [dim]# Tree of /lib[/dim]

[bold cyan]Output shows:[/bold cyan]
  • [yellow]󴋋[/yellow]  Folders (yellow icon)
  • [cyan]󰄠[/cyan]  Python files (.py)
  • [orange]󰆧[/orange]  Compiled files (.mpy)
  • File sizes in bytes

[bold cyan]Related:[/bold cyan]
  replx cat file.py     [dim]# View file contents[/dim]
  replx get file ./     [dim]# Download file[/dim]"""
        OutputHelper.print_panel(help_text, title="ls", border_style="help")
        console.print()
        raise typer.Exit()
    
    if not path.startswith('/'):
        path = '/' + path

    client = _create_agent_client(include_device_port=False)
    try:
        _ensure_connected(client=client)
        result = client.send_command(
            'ls',
            port=_get_device_port(),
            path=path,
            detailed=True,
            recursive=recursive,
        )
        
        items = [(item['name'], item['size'], item['is_dir']) for item in result.get('items', [])]
        
        if not items:
            OutputHelper.print_panel(
                "Directory is empty.",
                title=f"Directory Listing: {path}",
                border_style="neutral"
            )
            return
        
        def get_icon(name: str, is_dir: bool) -> str:
            if is_dir:
                return "[#E6B450]󰉋[/#E6B450]" 
            ext_icons = {
                ".py":   "[#5CB8C2]󰌠[/#5CB8C2]",  
                ".mpy":  "[#D98C53]󰆧[/#D98C53]",  
                ".log":  "[#7A7A7A]󰌱[/#7A7A7A]",  
                ".ini":  "[#7A7A7A]󰘦[/#7A7A7A]",  
            }
            _, ext = os.path.splitext(str(name).lower())
            return ext_icons.get(ext, "[#8C8C8C]󰈙[/#8C8C8C]")  

        if recursive:
            from collections import defaultdict
            
            tree = defaultdict(list)
            
            for name, size, is_dir in items:
                parent = '/'.join(name.rsplit('/', 1)[:-1]) or '/'
                basename = name.rsplit('/', 1)[-1]
                tree[parent].append((basename, size, is_dir, name))
            
            for parent in tree:
                tree[parent].sort(key=lambda x: (not x[2], x[0].lower()))
            
            max_size = max((size for _, size, is_dir in items if not is_dir), default=0)
            size_width = len(str(max_size)) if max_size > 0 else 0
            
            lines = []
            
            def render_tree(dir_path: str, prefix: str = ""):
                children = tree.get(dir_path, [])
                for i, (basename, size, is_dir, full_path) in enumerate(children):
                    is_last = (i == len(children) - 1)
                    
                    branch = "└── " if is_last else "├── "
                    child_prefix = prefix + ("    " if is_last else "│   ")
                    
                    icon = get_icon(basename, is_dir)
                    
                    if is_dir:
                        name_str = f"[#73B8F1]{basename}[/#73B8F1]"
                        size_str = "".rjust(size_width)
                    else:
                        name_str = basename
                        size_str = str(size).rjust(size_width)
                    
                    lines.append(f"{size_str}  {prefix}{branch}{icon}  {name_str}")
                    
                    if is_dir and full_path in tree:
                        render_tree(full_path, child_prefix)
            
            root_icon = get_icon(path, True)
            root_name = f"[#73B8F1]{path}[/#73B8F1]"
            lines.append(f"{''.rjust(size_width)}  {root_icon}  {root_name}")
            
            if path not in tree and items:
                OutputHelper.print_panel(
                    f"No accessible items found in [yellow]{path}[/yellow]\n\n"
                    f"Received {len(items)} item(s) from device, but none are children of the requested path.\n"
                    "This may indicate:\n"
                    "  • Permission issues accessing subdirectories\n"
                    "  • File system errors during recursive traversal\n"
                    "  • Path mismatch between client and device\n\n"
                    "[dim]Try using 'replx ls' (non-recursive) to see direct children.[/dim]",
                    title=f"Directory Tree: {path}",
                    border_style="warning"
                )
                return
            
            render_tree(path, "")
            
            OutputHelper.print_panel(
                "\n".join(lines),
                title=f"Directory Tree: {path}",
                border_style="data"
            )
        else:
            display_items = []
            for name, size, is_dir in items:
                icon = get_icon(name, is_dir)
                display_items.append((is_dir, name, size, icon))

            if display_items:
                size_width = max(len(str(item[2])) for item in display_items)
                
                lines = []
                for is_dir, f_name, size, icon in display_items:
                    name_str = f"[#73B8F1]{f_name}[/#73B8F1]" if is_dir else f_name
                    size_str = "" if is_dir else str(size)
                    lines.append(f"{size_str.rjust(size_width)}  {icon}  {name_str}")
                
                title = f"Directory Listing: {path}"
                if len(display_items) == 1 and display_items[0][0] is False:
                    title = f"File: {path}"
                
                OutputHelper.print_panel(
                    "\n".join(lines),
                    title=title,
                    border_style="data"
                )

    except ProtocolError:
        OutputHelper.print_panel(
            f"[red]{path[1:]}[/red] does not exist.",
            title=f"Directory Listing: {path}",
            border_style="error"
        )
    except RuntimeError as e:
        if not OutputHelper.handle_error(e, f"Directory Listing: {path}"):
            OutputHelper.print_panel(
                f"[red]{str(e)}[/red]",
                title="Listing Error",
                border_style="error"
            )
    finally:
        client.disconnect()


@app.command(rich_help_panel="File Operations")
def put(
    args: Optional[list[str]] = typer.Argument(None, help="Local file(s) and remote destination"),
    show_help: bool = typer.Option(False, "--help", "-h", is_eager=True, hidden=True)
):
    if show_help:
        console = OutputHelper.make_console(width=CONSOLE_WIDTH)
        help_text = """\
Upload files or directories from your computer to the device.

[bold cyan]Usage:[/bold cyan]
  replx put [yellow]LOCAL[/yellow] [yellow]REMOTE[/yellow]
  replx put [yellow]LOCAL...[/yellow] [yellow]REMOTE[/yellow]   [dim]# Multiple files[/dim]

[bold cyan]Arguments:[/bold cyan]
  [yellow]LOCAL[/yellow]     File(s) or directory on your computer [red][required][/red]
  [yellow]REMOTE[/yellow]    Destination on device [red][required][/red]

[bold cyan]Examples:[/bold cyan]
  [dim]# Single file[/dim]
  replx put main.py /                 [dim]# Upload to root[/dim]
  replx put ./lib/audio.py /lib       [dim]# Upload to /lib[/dim]

  [dim]# Directory (recursive)[/dim]
  replx put ./mylib /lib              [dim]# Upload directory[/dim]

  [dim]# Multiple files[/dim]
  replx put a.py b.py /lib            [dim]# Upload multiple files[/dim]

  [dim]# Wildcards[/dim]
  replx put *.py /lib                 [dim]# Upload all .py files[/dim]
  replx put test*.py /                [dim]# Files starting with test[/dim]

[bold cyan]Note:[/bold cyan]
  • Last argument is always the remote destination
  • Directories are uploaded recursively
  • Directory uploads skip common caches/build artifacts (.git, .venv, __pycache__, *.pyc, native binaries)
  • Wildcards (*,?) are expanded locally
  • Remote directories are created if needed

[bold cyan]Tip:[/bold cyan]
    To compile a local file to .mpy first, use [yellow]replx mpy[/yellow] and then upload it.

[bold cyan]Related:[/bold cyan]
  replx get remote local    [dim]# Download files instead[/dim]
    replx mpy local.py        [dim]# Compile local Python to .mpy[/dim]"""
        OutputHelper.print_panel(help_text, title="put", border_style="help")
        console.print()
        raise typer.Exit()
    
    status = _ensure_connected()
    device_root_fs = status.get('device_root_fs', '/')
    
    if not args or len(args) < 2:
        OutputHelper.print_panel(
            "Missing required arguments.\n\n"
            "[bold cyan]Usage:[/bold cyan] replx put [yellow]LOCAL... REMOTE[/yellow]\n\n"
            "At least 2 arguments required: local file(s) and remote destination.",
            title="Upload Error",
            border_style="error"
        )
        raise typer.Exit(1)
    
    cmd_idx = next((i for i, arg in enumerate(sys.argv) if arg == 'put'), None)
    if cmd_idx is not None and cmd_idx + 1 < len(sys.argv):
        raw_args = []
        for arg in sys.argv[cmd_idx + 1:]:
            if arg.startswith('-'):
                continue
            raw_args.append(arg)
        if len(raw_args) >= 2:
            args = raw_args
    
    remote = args[-1]
    locals = args[:-1]

    remote = OutputHelper.normalize_remote_path(remote)
    
    files_to_upload = []
    had_input_errors = False
    
    for local_pattern in locals:
        if '*' in local_pattern or '?' in local_pattern:
            matched_files = glob.glob(local_pattern)
            if not matched_files:
                had_input_errors = True
                OutputHelper.print_panel(
                    f"[red]{local_pattern}[/red] - pattern did not match any files.",
                    title="Upload Failed",
                    border_style="error"
                )
                continue
            for matched in matched_files:
                if os.path.exists(matched):
                    files_to_upload.append(matched)
        else:
            if not os.path.exists(local_pattern):
                had_input_errors = True
                OutputHelper.print_panel(
                    f"[red]{local_pattern}[/red] does not exist.",
                    title="Upload Failed",
                    border_style="error"
                )
                continue
            files_to_upload.append(local_pattern)
    
    if not files_to_upload:
        if had_input_errors:
            raise typer.Exit(1)
        OutputHelper.print_panel(
            "No files to upload.",
            title="Upload",
            border_style="warning"
        )
        raise typer.Exit(1)
    
    client = _create_agent_client()

    def _exit_upload_error(error: RuntimeError) -> None:
        if OutputHelper.handle_error(error, "Upload"):
            raise typer.Exit(1)
        OutputHelper.print_panel(
            f"Upload failed: [red]{error}[/red]",
            title="Upload Failed",
            border_style="error"
        )
        raise typer.Exit(1)

    def ensure_remote_dir_tree(dir_path: str) -> None:
        normalized = OutputHelper.normalize_remote_path(dir_path).rstrip('/')
        if not normalized:
            return

        parts = [p for p in normalized.split('/') if p]
        current = ''
        for part in parts:
            current += '/' + part
            try:
                client.send_command('mkdir', path=current)
            except Exception as e:
                error_msg = str(e)
                if 'EEXIST' in error_msg or 'exists' in error_msg.lower():
                    continue
                raise
    
    try:
        result = client.send_command('is_dir', path=remote)
        is_remote_dir = ((result.get('is_dir', False) if result else False) or remote.endswith('/'))
    except Exception:
        is_remote_dir = remote.endswith('/')
    
    total_files = len(files_to_upload)
    success_count = 0
    
    if total_files == 1:
        local = files_to_upload[0]
        is_dir = os.path.isdir(local)
        base_name = os.path.basename(local)
        
        if is_remote_dir:
            remote_path = posixpath.join(remote, base_name)
        else:
            remote_path = remote

        target_dir = remote if is_remote_dir else posixpath.dirname(remote_path)
        if target_dir and target_dir != '/':
            try:
                ensure_remote_dir_tree(target_dir)
            except RuntimeError as e:
                _exit_upload_error(e)
        
        display_remote = remote_path.replace(device_root_fs, "", 1)
        item_type = "Directory" if is_dir else "File"
        
        file_count = sum(1 for _ in _iter_uploadable_files(local)) if is_dir else 1
        
        progress_state = {"current": 0, "total": file_count, "file": base_name}
        
        def progress_callback(data):
            progress_state["current"] = data.get("current", 0)
            progress_state["total"] = data.get("total", file_count)
            progress_state["file"] = data.get("file", base_name)
        
        try:
            with Live(OutputHelper.create_progress_panel(0, file_count, title=f"Uploading {base_name}", message=f"Uploading {item_type.lower()}..."), console=OutputHelper._console, refresh_per_second=10) as live:
                upload_error = [None]
                upload_result = [None]
                
                def do_upload():
                    try:
                        if is_dir:
                            upload_result[0] = client.send_command_streaming(
                                'putdir_from_local_streaming',
                                local_path=local,
                                remote_path=remote_path,
                                timeout=300,
                                progress_callback=progress_callback
                            )
                        else:
                            upload_result[0] = client.send_command_streaming(
                                'put_from_local_streaming',
                                local_path=local,
                                remote_path=remote_path,
                                timeout=60,
                                progress_callback=progress_callback
                            )
                    except Exception as e:
                        upload_error[0] = e
                
                upload_thread = threading.Thread(target=do_upload, daemon=True)
                upload_thread.start()
                
                while upload_thread.is_alive():
                    if is_dir:
                        live.update(OutputHelper.create_progress_panel(
                            progress_state["current"],
                            progress_state["total"],
                            title=f"Uploading {base_name}",
                            message=f"Uploading {progress_state['file']}..."
                        ))
                    else:
                        live.update(OutputHelper.create_progress_panel(
                            progress_state["current"],
                            progress_state["total"],
                            title=f"Uploading {base_name}",
                            message="Uploading file..."
                        ))
                    time.sleep(0.1)
                
                upload_thread.join()
                
                if upload_error[0]:
                    raise upload_error[0]
                
                live.update(OutputHelper.create_progress_panel(
                    progress_state["total"],
                    progress_state["total"],
                    title=f"Uploading {base_name}"
                ))
            
            OutputHelper.print_panel(
                f"Uploaded [green]{local}[/green]\nto [bright_blue]{display_remote}[/bright_blue]",
                title="Upload Complete",
                border_style="success"
            )
        except Exception as e:
            if isinstance(e, RuntimeError):
                _exit_upload_error(e)
            OutputHelper.print_panel(
                f"Upload failed: [red]{str(e)}[/red]",
                title="Upload Failed",
                border_style="error"
            )
            raise typer.Exit(1)
    else:
        if not is_remote_dir:
            OutputHelper.print_panel(
                f"Destination [red]{remote}[/red] must be a directory when uploading multiple files.",
                title="Upload Failed",
                border_style="error"
            )
            raise typer.Exit(1)

        if remote and remote != '/':
            try:
                ensure_remote_dir_tree(remote)
            except RuntimeError as e:
                _exit_upload_error(e)
        
        def count_bytes(path):
            if os.path.isfile(path):
                return os.path.getsize(path)
            elif os.path.isdir(path):
                total = 0
                for local_file in _iter_uploadable_files(path):
                    try:
                        total += os.path.getsize(local_file)
                    except OSError:
                        continue
                return total
            return 0
        
        total_bytes = sum(count_bytes(local) for local in files_to_upload)
        uploaded_bytes = [0]  # Track total uploaded bytes
        
        current_file_progress = {"file": "", "current": 0, "total": 0, "bytes": 0}
        
        def progress_callback(data):
            current_file_progress["file"] = data.get("file", "")
            current_file_progress["current"] = data.get("current", 0)
            current_file_progress["total"] = data.get("total", 0)
            current_file_progress["bytes"] = data.get("bytes", 0)
        
        with Live(OutputHelper.create_progress_panel(0, max(total_bytes, 1), title=f"Uploading {total_files} item(s)", message="Starting..."), console=OutputHelper._console, refresh_per_second=10) as live:
            for idx, local in enumerate(files_to_upload):
                base_name = os.path.basename(local)
                is_dir = os.path.isdir(local)
                remote_path = posixpath.join(remote, base_name)
                
                item_bytes = count_bytes(local)
                item_start_bytes = uploaded_bytes[0]
                
                # Reset current file progress
                current_file_progress["file"] = base_name
                current_file_progress["current"] = 0
                current_file_progress["total"] = 0
                current_file_progress["bytes"] = 0
                
                live.update(OutputHelper.create_progress_panel(
                    uploaded_bytes[0], total_bytes,
                    title=f"Uploading {total_files} item(s)",
                    message=f"Starting {base_name}..."
                ))
                
                max_retries = 2
                upload_success = False
                
                for retry in range(max_retries):
                    try:
                        with _create_agent_client() as file_client:
                            if is_dir:
                                upload_result = [None]
                                upload_error = [None]
                                upload_done = [False]
                                
                                def upload_dir():
                                    try:
                                        upload_result[0] = file_client.send_command_streaming(
                                            'putdir_from_local_streaming',
                                            local_path=local,
                                            remote_path=remote_path,
                                            timeout=300,
                                            progress_callback=progress_callback
                                        )
                                    except Exception as e:
                                        upload_error[0] = e
                                    finally:
                                        upload_done[0] = True
                                
                                thread = threading.Thread(target=upload_dir, daemon=True)
                                thread.start()
                                
                                while not upload_done[0]:
                                    curr = current_file_progress.get("current", 0)
                                    tot = current_file_progress.get("total", 1)
                                    file_name = current_file_progress.get("file", "")
                                    
                                    if tot > 0:
                                        progress_ratio = curr / tot
                                        estimated_bytes = item_start_bytes + int(item_bytes * progress_ratio)
                                        message = f"{base_name}/: {file_name} ({curr}/{tot} files)"
                                    else:
                                        estimated_bytes = item_start_bytes
                                        message = f"Scanning {base_name}/..."
                                    
                                    live.update(OutputHelper.create_progress_panel(
                                        estimated_bytes, total_bytes,
                                        title=f"Uploading {total_files} item(s)",
                                        message=message
                                    ))
                                    time.sleep(0.1)
                                
                                thread.join()
                                
                                if upload_error[0]:
                                    raise upload_error[0]
                                
                                uploaded_bytes[0] = item_start_bytes + item_bytes
                            else:
                                result = file_client.send_command_streaming(
                                    'put_from_local_streaming',
                                    local_path=local,
                                    remote_path=remote_path,
                                    timeout=60,
                                    progress_callback=progress_callback
                                )
                                uploaded_bytes[0] = item_start_bytes + item_bytes
                        
                        success_count += 1
                        upload_success = True
                        live.update(OutputHelper.create_progress_panel(
                            uploaded_bytes[0], total_bytes,
                            title=f"Uploading {total_files} item(s)",
                            message=f"✓ {base_name}"
                        ))
                        break 
                        
                    except RuntimeError as e:
                        if retry == max_retries - 1:
                            if OutputHelper.handle_error(e, f"Upload: {remote_path}"):
                                raise typer.Exit(1)
                            OutputHelper._console.print(f"[red]Failed to upload {base_name}: {str(e)}[/red]")
                        else:
                            time.sleep(0.2)
                    except Exception as e:
                        if retry == max_retries - 1:
                            OutputHelper._console.print(f"[red]Failed to upload {base_name}: {str(e)}[/red]")
                        else:
                            time.sleep(0.2)
                
                if not upload_success:
                    live.update(OutputHelper.create_progress_panel(
                        uploaded_bytes[0], total_bytes,
                        title=f"Uploading {total_files} item(s)",
                        message=f"✗ {base_name}"
                    ))
            
            live.update(OutputHelper.create_progress_panel(total_bytes, total_bytes, title=f"Uploading {total_files} item(s)"))
        
        display_remote = remote.replace(device_root_fs, "", 1)
        OutputHelper.print_panel(
            f"Uploaded [green]{success_count}[/green] out of {total_files} item(s) ([green]{OutputHelper.format_bytes(uploaded_bytes[0])}[/green])\nto [bright_blue]{display_remote}[/bright_blue]",
            title="Upload Complete",
            border_style="success" if success_count == total_files else "warning"
        )
